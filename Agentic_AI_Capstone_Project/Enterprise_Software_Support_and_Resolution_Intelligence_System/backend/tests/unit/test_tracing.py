"""
tests/unit/test_tracing.py

L1 tests (§19) for app/observability/tracing.py's defensive wrapper
design — no real Langfuse network calls (see test_tracing_eval.py for
the real, non-CI end-to-end smoke test). The whole point of this module
is that a Langfuse failure never breaks the real work it's tracing and
never fails silently (no bare `except: pass`) — every test here forces
a specific Langfuse call to fail and asserts both halves of that
contract: the real node's return value is untouched, AND a specific,
diagnosable log_event() call was made naming exactly which call failed.
"""

from __future__ import annotations

import logging

import pytest

from app.observability import tracing


class _FakeSpan:
    def __init__(self, *, fail_update: bool = False):
        self.fail_update = fail_update
        self.updates: list[dict] = []

    def update(self, **kwargs):
        if self.fail_update:
            raise RuntimeError("boom-update")
        self.updates.append(kwargs)


class _FakeCM:
    def __init__(self, span, *, fail_exit: bool = False):
        self._span = span
        self.fail_exit = fail_exit
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self._span

    def __exit__(self, *args):
        self.exited = True
        if self.fail_exit:
            raise RuntimeError("boom-exit")


class _FakeClient:
    """Configurable fake — each keyword controls one specific failure
    point, mirroring the individual try/except blocks in tracing.py."""

    def __init__(
        self,
        *,
        fail_start: bool = False,
        fail_update: bool = False,
        fail_exit: bool = False,
        fail_score: bool = False,
        fail_flush: bool = False,
    ):
        self.fail_start = fail_start
        self.fail_update = fail_update
        self.fail_exit = fail_exit
        self.fail_score = fail_score
        self.fail_flush = fail_flush
        self.last_span: _FakeSpan | None = None
        self.start_calls: list[dict] = []

    def start_as_current_observation(self, **kwargs):
        self.start_calls.append(kwargs)
        if self.fail_start:
            raise RuntimeError("boom-start")
        span = _FakeSpan(fail_update=self.fail_update)
        self.last_span = span
        return _FakeCM(span, fail_exit=self.fail_exit)

    def create_score(self, **kwargs):
        if self.fail_score:
            raise RuntimeError("boom-score")

    def flush(self):
        if self.fail_flush:
            raise RuntimeError("boom-flush")


class _EventRecorder:
    """Stand-in for log_event — records (level, event, context) triples
    instead of actually logging, so tests can assert on the exact event
    name without parsing JSON output."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, logger: logging.Logger, level: str, event: str, **context):
        self.calls.append((level, event, context))

    def events(self) -> list[str]:
        return [event for _, event, _ in self.calls]


@pytest.fixture()
def recorder(monkeypatch):
    rec = _EventRecorder()
    monkeypatch.setattr(tracing, "log_event", rec)
    return rec


def _install_client(monkeypatch, client) -> None:
    monkeypatch.setattr(tracing, "get_client", lambda: client)


# ---------------------------------------------------------------------------
# safe_create_trace_id
# ---------------------------------------------------------------------------


def test_safe_create_trace_id_returns_real_value_on_success(monkeypatch):
    monkeypatch.setattr(tracing.Langfuse, "create_trace_id", staticmethod(lambda seed=None: "lf_real_id"))
    assert tracing.safe_create_trace_id() == "lf_real_id"


def test_safe_create_trace_id_falls_back_to_uuid_scheme_on_failure(monkeypatch, recorder):
    def _raise(seed=None):
        raise RuntimeError("boom-create-trace-id")

    monkeypatch.setattr(tracing.Langfuse, "create_trace_id", staticmethod(_raise))

    result = tracing.safe_create_trace_id()

    assert result.startswith("trace_")
    assert "langfuse_create_trace_id_failed" in recorder.events()


# ---------------------------------------------------------------------------
# traced() — the node-wrapping decorator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_traced_returns_node_result_unchanged_on_success(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "usage"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({"trace_id": "trace_abc", "conversation_id": "c1"})

    assert result == {"category": "usage"}
    assert client.last_span.updates  # a real update was recorded
    assert recorder.events() == []  # nothing failed, nothing logged


@pytest.mark.asyncio
async def test_traced_propagates_real_node_exceptions_even_when_tracing_works(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    async def node(state):
        raise ValueError("genuine node bug")

    wrapped = tracing.traced(node, "classify")

    with pytest.raises(ValueError, match="genuine node bug"):
        await wrapped({"trace_id": "trace_abc"})


@pytest.mark.asyncio
async def test_traced_returns_node_result_when_span_start_fails(monkeypatch, recorder):
    client = _FakeClient(fail_start=True)
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "billing"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({"trace_id": "trace_abc"})

    assert result == {"category": "billing"}
    assert "langfuse_span_start_failed" in recorder.events()


@pytest.mark.asyncio
async def test_traced_returns_node_result_when_span_update_fails(monkeypatch, recorder):
    client = _FakeClient(fail_update=True)
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "security"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({"trace_id": "trace_abc"})

    assert result == {"category": "security"}
    assert "langfuse_span_update_failed" in recorder.events()


@pytest.mark.asyncio
async def test_traced_returns_node_result_when_span_exit_fails(monkeypatch, recorder):
    client = _FakeClient(fail_exit=True)
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "integration"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({"trace_id": "trace_abc"})

    assert result == {"category": "integration"}
    assert "langfuse_span_exit_failed" in recorder.events()


@pytest.mark.asyncio
async def test_traced_skips_span_entirely_when_state_has_no_trace_id(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "usage"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({})  # no trace_id key at all

    assert result == {"category": "usage"}
    assert client.start_calls == []  # never even attempted
    assert recorder.events() == []


@pytest.mark.asyncio
async def test_traced_returns_node_result_when_get_client_itself_fails(monkeypatch, recorder):
    def _raise_get_client():
        raise RuntimeError("boom-get-client")

    monkeypatch.setattr(tracing, "get_client", _raise_get_client)

    async def node(state):
        return {"category": "usage"}

    wrapped = tracing.traced(node, "classify")
    result = await wrapped({"trace_id": "trace_abc"})

    assert result == {"category": "usage"}
    assert "langfuse_get_client_failed" in recorder.events()


@pytest.mark.asyncio
async def test_traced_terminal_span_reattaches_trace_metadata_with_escalation_flag(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    async def node(state):
        return {"final_answer": "here you go"}

    wrapped = tracing.traced(node, "respond")
    state = {
        "trace_id": "trace_abc",
        "conversation_id": "conv-1",
        "customer_id": 42,
        "handled_by_user_id": 7,
        "escalation_flag": False,
    }
    await wrapped(state)

    [update] = client.last_span.updates
    metadata = update["metadata"]
    assert metadata["escalation_flag"] is False
    assert metadata["session_id"] == "conv-1"
    assert metadata["handled_by_user_id"] == 7
    assert metadata["customer_id_hashed"] is not None  # hashed, never the raw id
    assert metadata["customer_id_hashed"] != "42"


@pytest.mark.asyncio
async def test_traced_sets_real_input_and_output_not_just_metadata(monkeypatch, recorder):
    """Regression test for a real, confirmed-live gap: every span this
    module created only ever set metadata=, never Langfuse's own
    dedicated input=/output= parameters — confirmed directly in the real
    Langfuse UI showing "Input: null" / "Output: undefined" on every
    trace. input= must carry the real query; output= must be the node's
    own real return dict, unmodified."""
    client = _FakeClient()
    _install_client(monkeypatch, client)

    async def node(state):
        return {"category": "usage", "severity_initial": "Low"}

    wrapped = tracing.traced(node, "classify")
    await wrapped({"trace_id": "trace_abc", "query": "How do I reset my password?"})

    [start_call] = client.start_calls
    assert start_call["input"] == {"query": "How do I reset my password?"}

    [update] = client.last_span.updates
    assert update["output"] == {"category": "usage", "severity_initial": "Low"}


# ---------------------------------------------------------------------------
# traced_root_span / traced_child_span / end_child_span
# ---------------------------------------------------------------------------


def test_traced_root_span_returns_none_none_when_start_fails(monkeypatch, recorder):
    client = _FakeClient(fail_start=True)
    _install_client(monkeypatch, client)

    cm, span = tracing.traced_root_span("ingestion_job", "trace_xyz")

    assert cm is None and span is None
    assert "langfuse_root_span_start_failed" in recorder.events()


def test_traced_child_span_returns_none_none_when_start_fails(monkeypatch, recorder):
    client = _FakeClient(fail_start=True)
    _install_client(monkeypatch, client)

    cm, span = tracing.traced_child_span("hybrid_search")

    assert cm is None and span is None
    assert "langfuse_child_span_start_failed" in recorder.events()


def test_traced_root_span_passes_real_input_through_to_langfuse(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    tracing.traced_root_span(
        "ingestion_job", "trace_xyz", input={"document_id": "doc-1", "doc_title": "Runbook"}
    )

    [start_call] = client.start_calls
    assert start_call["input"] == {"document_id": "doc-1", "doc_title": "Runbook"}


def test_traced_child_span_passes_real_input_through_to_langfuse(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    tracing.traced_child_span("hybrid_search", input={"query": "reset my password", "filters": None})

    [start_call] = client.start_calls
    assert start_call["input"] == {"query": "reset my password", "filters": None}


def test_end_child_span_passes_real_output_through_to_langfuse(monkeypatch, recorder):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    cm, span = tracing.traced_child_span("hybrid_search", input={"query": "q"})
    tracing.end_child_span(cm, span, output={"result_count": 3, "asset_ids": [1, 2, 3]})

    [update] = client.last_span.updates
    assert update["output"] == {"result_count": 3, "asset_ids": [1, 2, 3]}


def test_end_child_span_is_a_safe_no_op_when_both_are_none(recorder):
    tracing.end_child_span(None, None, output_metadata={"result_count": 3})
    assert recorder.events() == []


def test_end_child_span_logs_update_and_exit_failures_independently(monkeypatch, recorder):
    client = _FakeClient(fail_update=True, fail_exit=True)
    _install_client(monkeypatch, client)

    cm, span = tracing.traced_child_span("extract_text")
    tracing.end_child_span(cm, span, output_metadata={"chunk_count": 5})

    assert "langfuse_child_span_update_failed" in recorder.events()
    assert "langfuse_child_span_exit_failed" in recorder.events()


# ---------------------------------------------------------------------------
# safe_create_score / safe_flush
# ---------------------------------------------------------------------------


def test_safe_create_score_logs_on_failure_and_never_raises(monkeypatch, recorder):
    client = _FakeClient(fail_score=True)
    _install_client(monkeypatch, client)

    tracing.safe_create_score(trace_id="trace_abc", name="task_success", value=1.0)

    assert "langfuse_create_score_failed" in recorder.events()


def test_safe_flush_logs_on_failure_and_never_raises(monkeypatch, recorder):
    client = _FakeClient(fail_flush=True)
    _install_client(monkeypatch, client)

    tracing.safe_flush()  # must not raise

    assert "langfuse_flush_failed" in recorder.events()


def test_safe_flush_is_a_no_op_when_client_is_unavailable(monkeypatch, recorder):
    monkeypatch.setattr(tracing, "get_client", lambda: (_ for _ in ()).throw(RuntimeError("no client")))

    tracing.safe_flush()  # must not raise despite two layers of failure

    assert "langfuse_get_client_failed" in recorder.events()
