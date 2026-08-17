"""Responsible for orchestration node definitions and behavior."""

import importlib
import sys
from typing import Any


SPECIALIST_KEYS_TO_MODULES = {
    "logistics": ("app.agents.logistics_agent", "LogisticsAgent"),
    "budget": ("app.agents.budget_agent", "BudgetAgent"),
    "marketing": ("app.agents.marketing_agent", "MarketingAgent"),
    "schedule": ("app.agents.schedule_agent", "ScheduleAgent"),
    "risk": ("app.agents.risk_agent", "RiskAgent"),
}


def intake_node(state) -> dict:
    # Validation already happened before the graph was invoked at the API layer,
    # so this node currently exists only as an explicit entry point for readability.
    return {}


def decompose_node(state) -> dict:
    from app.agents.manager_agent import ManagerAgent

    agent = ManagerAgent()
    return agent.decompose(state)


def make_specialist_node(key: str):
    def specialist_node(state) -> dict:
        if key not in state["active_revision_targets"]:
            return {}

        module_path, class_name = SPECIALIST_KEYS_TO_MODULES[key]
        try:
            module = importlib.import_module(module_path)
            agent_cls = getattr(module, class_name)
        except ImportError:
            print(f"Warning: {module_path} is not implemented yet", file=sys.stderr)
            return {}

        agent = agent_cls()
        specialist_output = agent.run(state)
        specialist_outputs = dict(state.get("specialist_outputs", {}))
        specialist_outputs.update(specialist_output)
        return {"specialist_outputs": specialist_outputs}

    return specialist_node


logistics_node = make_specialist_node("logistics")
budget_node = make_specialist_node("budget")
marketing_node = make_specialist_node("marketing")
schedule_node = make_specialist_node("schedule")
risk_node = make_specialist_node("risk")


def synthesize_node(state) -> dict:
    from app.agents.manager_agent import ManagerAgent

    agent = ManagerAgent()
    return agent.synthesize(state)


def reflect_node(state) -> dict:
    from app.agents.reflection_agent import ReflectionAgent

    agent = ReflectionAgent()
    return agent.critique(state)


def finalize_node(state) -> dict:
    if state.get("critique_history"):
        last_entry = state["critique_history"][-1]
        if hasattr(last_entry, "passed"):
            passed = last_entry.passed
        else:
            passed = last_entry.get("passed", False)
        if passed:
            return {"status": "completed"}
    return {"status": "needs_review"}
