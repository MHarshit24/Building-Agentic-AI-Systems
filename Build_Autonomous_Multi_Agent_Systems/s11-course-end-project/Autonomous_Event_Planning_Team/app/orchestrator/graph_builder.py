"""Responsible for constructing the orchestration graph structure."""

from app.config import get_settings

try:
    from app.errors.exceptions import PlanNotFoundError
except ImportError:  # pragma: no cover - compatibility with the current exception module
    class PlanNotFoundError(Exception):
        pass

from app.orchestrator.edges import quality_gate_edge
from app.orchestrator.nodes import (
    budget_node,
    decompose_node,
    finalize_node,
    intake_node,
    logistics_node,
    marketing_node,
    reflect_node,
    risk_node,
    schedule_node,
    synthesize_node,
)
from app.schemas.domain import EventBrief, EventPlanState
from langgraph.graph import END, START, StateGraph

# LangGraph's default recursion_limit (25 superstep transitions) is too
# tight for this graph: intake -> decompose -> 5 parallel specialists ->
# synthesize -> reflect is one iteration, and the quality gate can loop
# that up to max_iterations (default 3) times before finalize. Left at the
# default, a run that actually needs all 3 iterations risks a hard
# GraphRecursionError instead of cleanly finishing at "needs_review" — set
# a generous explicit cap instead (Sprint 3/4 pitfall: "GraphRecursionError
# -> raise/limit recursion_limit").
_RECURSION_LIMIT = 100


def build_graph(checkpointer=None):
    graph = StateGraph(EventPlanState)
    graph.add_node("intake", intake_node)
    graph.add_node("decompose", decompose_node)
    graph.add_node("logistics", logistics_node)
    graph.add_node("budget", budget_node)
    graph.add_node("marketing", marketing_node)
    graph.add_node("schedule", schedule_node)
    graph.add_node("risk", risk_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "decompose")
    graph.add_edge("decompose", "logistics")
    graph.add_edge("decompose", "budget")
    graph.add_edge("decompose", "marketing")
    graph.add_edge("decompose", "schedule")
    graph.add_edge("decompose", "risk")
    graph.add_edge("logistics", "synthesize")
    graph.add_edge("budget", "synthesize")
    graph.add_edge("marketing", "synthesize")
    graph.add_edge("schedule", "synthesize")
    graph.add_edge("risk", "synthesize")
    graph.add_edge("synthesize", "reflect")
    graph.add_conditional_edges("reflect", quality_gate_edge, {"decompose": "decompose", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


class PlanningOrchestrator:
    def __init__(self, checkpointer=None):
        self._graph = build_graph(checkpointer=checkpointer)
        self._checkpointer = checkpointer

    async def run_new_plan(
        self,
        plan_id: str,
        brief: EventBrief,
        provider: str | None = None,
        quality_gate_threshold: float | None = None,
    ) -> dict:
        initial_state = {
            "plan_id": plan_id,
            "brief": brief,
            "provider": provider,
            "quality_gate_threshold": quality_gate_threshold,
            "constraints": brief.constraints,
            "specialist_outputs": {},
            "draft_blueprint": None,
            "critique_history": [],
            "iteration_count": 0,
            "max_iterations": get_settings().max_iterations,
            "active_revision_targets": [],
            "status": "in_progress",
        }
        return await self._graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": plan_id}, "recursion_limit": _RECURSION_LIMIT},
        )

    async def refine_plan(self, plan_id: str, instruction: str, target_agents: list[str] | None = None) -> dict:
        # Starting the invoke over from the intake entry point with the modified state as fresh input is a deliberate simplification rather than using LangGraph's update_state/resume-from-node APIs, and this should be tested carefully since it re-runs intake and decompose from scratch rather than truly resuming mid-graph.
        current_state = await self.get_plan_state(plan_id)
        if current_state is None:
            raise PlanNotFoundError(f"Plan {plan_id} was not found")

        modified_state = dict(current_state)
        modified_state.setdefault("constraints", [])
        modified_state["constraints"].append(instruction)
        if target_agents is not None and target_agents:
            modified_state["active_revision_targets"] = target_agents
        else:
            modified_state["active_revision_targets"] = ["logistics", "budget", "marketing", "schedule", "risk"]
        modified_state["status"] = "in_progress"
        modified_state["iteration_count"] = 0

        return await self._graph.ainvoke(
            modified_state,
            config={"configurable": {"thread_id": plan_id}, "recursion_limit": _RECURSION_LIMIT},
        )

    async def get_plan_state(self, plan_id: str) -> dict | None:
        try:
            state = await self._graph.aget_state(config={"configurable": {"thread_id": plan_id}})
            if state is not None and getattr(state, "values", None):
                return state.values
        except Exception:
            return None
        return None
