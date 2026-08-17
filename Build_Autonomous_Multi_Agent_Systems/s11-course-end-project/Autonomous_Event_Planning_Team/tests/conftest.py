from datetime import date
import sys
import types

import pytest

from app.schemas.domain import BudgetConstraint, EventBrief, TimelinePreference


@pytest.fixture
def mock_llm_complete(monkeypatch):
    module_name = "app.llm.client"
    module = types.ModuleType(module_name)
    module.complete = lambda prompt, **kwargs: "MOCKED_LLM_RESPONSE"
    module.get_last_duration_ms = lambda: 123.4
    sys.modules[module_name] = module
    monkeypatch.setitem(sys.modules, module_name, module)

    package = types.ModuleType("app.llm")
    package.client = module
    sys.modules["app.llm"] = package
    monkeypatch.setitem(sys.modules, "app.llm", package)

    import app

    monkeypatch.setattr(app, "llm", package, raising=False)
    monkeypatch.setattr(package, "client", module, raising=False)
    return module.complete


@pytest.fixture
def sample_event_brief():
    return EventBrief(
        event_type="AI Workshop",
        objective="Educate 200 students",
        audience_size=200,
        budget=BudgetConstraint(currency="INR", max_amount=500000.0),
        timeline=TimelinePreference(preferred_date=date(2030, 12, 1), duration_days=1),
        venue_preference="on-campus auditorium",
        constraints=["No loud music after 9 PM"],
    )
