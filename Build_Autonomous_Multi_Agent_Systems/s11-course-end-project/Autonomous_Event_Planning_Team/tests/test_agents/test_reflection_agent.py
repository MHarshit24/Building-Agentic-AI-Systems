"""Responsible for tests covering the reflection agent behavior."""

from app.agents.reflection_agent import ReflectionAgent


def test_reflection_agent_creates_critique_note(mock_llm_complete, sample_event_brief):
    state = {
        "plan_id": "test-plan-1",
        "brief": sample_event_brief,
        "draft_blueprint": {"overview": {"event_type": "AI Workshop"}},
        "critique_history": [],
        "iteration_count": 1,
    }

    result = ReflectionAgent().critique(state)

    assert "critique_history" in result
    assert len(result["critique_history"]) == 1
    note = result["critique_history"][0]
    assert note.duration_ms is not None
    assert note.threshold_delta is not None
    assert note.score_delta is None  # no prior critique_history entry to diff against
    assert isinstance(result["active_revision_targets"], list)
