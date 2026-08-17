"""Tests for the Langfuse tracing integration."""

import contextlib
import sys
import types

from app.observability.langfuse_tracer import trace_llm


def test_trace_llm_uses_v4_trace_id_and_flush(monkeypatch):
    calls = {}

    class FakeGeneration:
        def __init__(self, trace_id):
            self.trace_id = trace_id

        def update(self, **kwargs):
            calls["update_kwargs"] = kwargs

        def end(self):
            calls["ended"] = True

    class FakeClient:
        def __init__(self):
            self.started = None

        def start_observation(self, **kwargs):
            self.started = kwargs
            return FakeGeneration(kwargs.get("trace_id", "trace-id"))

        def flush(self):
            calls["flushed"] = True

    fake_client = FakeClient()
    fake_langfuse = types.ModuleType("langfuse")
    fake_langfuse.create_trace_id = lambda: "trace-id-123"
    fake_langfuse.propagate_attributes = lambda **kwargs: contextlib.nullcontext()

    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse)
    monkeypatch.setattr("app.observability.langfuse_tracer._get_client", lambda: fake_client)

    with trace_llm("demo", "reasoning", "prompt", session_id="plan-1") as finish:
        finish("done", model="demo-model", duration_ms=12.5)

    assert fake_client.started["trace_id"] == "trace-id-123"
    assert calls["flushed"] is True
    assert calls["update_kwargs"]["output"] == "done"
