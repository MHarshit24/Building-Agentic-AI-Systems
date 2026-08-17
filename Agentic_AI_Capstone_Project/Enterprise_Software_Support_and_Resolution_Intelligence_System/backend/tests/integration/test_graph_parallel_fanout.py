"""
tests/integration/test_graph_parallel_fanout.py

Stage 6's genuine concurrent fan-out (doc_retrieval_node ∥
account_validation_node, via LangGraph's Send API, Hybrid/Critical mode)
and the new SQL-alone single-node branch (Gap 1's resolution), over real
HTTP, under LLM_PROVIDER=mock.

Unlike test_graph_e2e.py's simple ordered-queue fake client (correct for
Stage 5's strictly sequential graph), Hybrid/Critical mode runs
doc_retrieval_node and account_validation_node CONCURRENTLY — both call
the same shared fake LLM client from separate asyncio tasks, so the order
their generate() calls actually land in is not deterministic. A
_RoutedFakeClient below dispatches by inspecting each prompt's own
content for a schema-unique field-name marker (the same technique used to
fix app/llm/mock_client.py's real keyword-collision bug earlier in this
project), which works correctly regardless of call order.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

import app.llm.structured_output as structured_output_module
import app.orchestration.nodes.doc_retrieval as doc_retrieval_module
from app.retrieval.vector_search import SearchResult

CANNED = {
    "doc_retrieval": (
        '{"draft_answer": "This looks related to a known incident.", '
        '"cited_source_ids": ["chunk_1"], "evidence_sufficient": true, "rewritten_query": null}'
    ),
    "account_validation": '{"narrative": "Your account is active.", "evidence_sufficient": true}',
    "incident_severity": '{"severity_final": "High", "severity_reasoning": "Matches an active incident."}',
    "reflect": '{"confidence_score": 0.9, "groundedness_flag": true, "confidence_tier": "High"}',
}


def _classify_response(category: str, severity_initial: str = "High") -> str:
    return f'{{"category": "{category}", "severity_initial": "{severity_initial}", "explicit_human_request": false}}'


class _RoutedFakeClient:
    """Dispatches canned responses by schema-unique field-name marker in
    the prompt text, not call order — required for correctness once two
    nodes can call generate() concurrently. Optional `delays` sleeps
    before returning, for the concurrency-timing assertion below."""

    MARKERS = [
        ("cited_source_ids", "doc_retrieval"),
        ("narrative", "account_validation"),
        ("severity_reasoning", "incident_severity"),
        ("groundedness_flag", "reflect"),
        ("severity_initial", "classify"),
    ]

    def __init__(
        self,
        classify_response: str,
        delays: dict[str, float] | None = None,
        canned_overrides: dict[str, str] | None = None,
    ) -> None:
        self._classify_response = classify_response
        self._delays = delays or {}
        # Per-test override, checked before the module-level CANNED default
        # — needed whenever a test's assertions depend on a value only
        # known at test time (e.g. account_validation's cited_record_ids
        # must reference the real, dynamically-created customer_id from
        # make_customer(), not a fixed literal CANNED can hold).
        self._canned_overrides = canned_overrides or {}
        self.call_counts: dict[str, int] = {name: 0 for _, name in self.MARKERS}
        # (start, end) monotonic timestamps per call, for the
        # overlap-based concurrency proof — recorded by this one object
        # regardless of which asyncio task called generate(), so
        # comparing them is immune to cross-request environment noise
        # (unlike comparing wall-clock durations of two separate HTTP
        # requests, which proved too flaky in this environment — see
        # test_hybrid_mode_branches_run_concurrently_not_sequentially's
        # own docstring for that history).
        self.intervals: dict[str, tuple[float, float]] = {}

    def _identify(self, prompt: str) -> str:
        lowered = prompt.lower()
        for marker, name in self.MARKERS:
            if marker in lowered:
                return name
        raise AssertionError(f"could not identify which node this prompt belongs to: {prompt[:200]!r}")

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        name = self._identify(prompt)
        self.call_counts[name] += 1
        start = time.monotonic()
        if name in self._delays:
            await asyncio.sleep(self._delays[name])
        self.intervals[name] = (start, time.monotonic())
        if name == "classify":
            return self._classify_response
        return self._canned_overrides.get(name, CANNED[name])

    async def generate_vision(self, image_bytes: bytes, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError("not exercised by this test")


@pytest.fixture
def patch_llm_client(monkeypatch):
    def _patch(
        classify_response: str,
        delays: dict[str, float] | None = None,
        canned_overrides: dict[str, str] | None = None,
    ) -> _RoutedFakeClient:
        fake = _RoutedFakeClient(classify_response, delays, canned_overrides)
        monkeypatch.setattr(structured_output_module, "get_llm_client", lambda: fake)
        return fake

    return _patch


@pytest.fixture
def patch_hybrid_search_with_one_result(monkeypatch):
    async def _fake_hybrid_search(query: str, filters: dict | None = None):
        return [
            SearchResult(
                asset_type="chunk",
                asset_row_id=1,
                text="Known incidents are tracked in the incident log.",
                source_document="Incident Response Guide",
                section_header="Overview",
                page_number=1,
                product_version=None,
                category="incident",
                score=0.5,
            )
        ]

    monkeypatch.setattr(doc_retrieval_module, "hybrid_search", _fake_hybrid_search)


@pytest.fixture
def patch_embed_text_fast(monkeypatch):
    """Real bug fix: doc_retrieval_node's §31 Layer B scope check calls the
    real embed_text() (a genuine Azure embedding network call) BEFORE its
    own timed LLM call even starts — this test file's own docstring on
    test_hybrid_mode_branches_run_concurrently_not_sequentially already
    named this as the root cause of that test's real, uncontrolled-latency
    flakiness, but never actually mocked it out. Confirmed directly: 3/3
    repeated real runs failed consistently (not intermittently) without
    this fixture. Mocking just this one call removes the uncontrolled
    variance from the interval-overlap timing measurement while leaving
    every other real behavior (the actual LLM calls being timed) untouched
    — get_cached_centroid()/is_in_scope() downstream of this still run for
    real and can still raise/short-circuit exactly as before."""

    async def _fake_embed_text(text: str) -> list[float]:
        return [0.0] * 8

    monkeypatch.setattr(doc_retrieval_module, "embed_text", _fake_embed_text)


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_hybrid_mode_runs_both_branches_and_incident_severity_exactly_once(
    client, support_agent_user, make_customer, patch_llm_client, patch_hybrid_search_with_one_result, cleanup_conversations
):
    """category="incident" -> Hybrid mode -> Send([doc_retrieval, account_validation])
    -> SEVCHECK is true (category=incident) -> incident_severity_node."""
    user, password = support_agent_user
    token = await _login(client, user, password)
    customer = await make_customer(company_name="Acme Corp")

    # cited_record_ids must reference the real, dynamically-created
    # customer_id — frontend integration pass: account_validation_node's
    # sql sources are now filtered by cited_record_ids (same mechanism
    # doc_retrieval already used), so a static CANNED response with no
    # citations would make sql_sources empty below.
    account_validation_response = (
        '{"narrative": "Your account is active.", '
        f'"cited_record_ids": ["customers_{customer.customer_id}"], '
        '"evidence_sufficient": true}'
    )
    fake = patch_llm_client(
        _classify_response("incident", "High"),
        canned_overrides={"account_validation": account_validation_response},
    )

    resp = await client.post(
        "/chat",
        json={"query": "Is my performance issue related to a known incident?", "customer_id": customer.customer_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    assert body["retrieval_mode"] == "Hybrid"
    assert body["escalated"] is False

    # Both branches genuinely ran — proving state population alone (this
    # assertion) is necessary but not sufficient; the call-count assertion
    # below is what actually proves fan-in convergence, not just that both
    # branches eventually ran (see this file's module docstring).
    sql_sources = [s for s in body["sources"] if s["type"] == "sql"]
    chunk_sources = [s for s in body["sources"] if s["type"] == "chunk"]
    assert sql_sources, "expected at least one sql-type source — account_validation_node's branch never ran"
    assert chunk_sources, "expected at least one chunk-type source — doc_retrieval_node's branch never ran"

    assert fake.call_counts["doc_retrieval"] == 1
    assert fake.call_counts["account_validation"] == 1
    # The direct, non-negotiable proof of fan-in convergence (Stage 6 plan,
    # added after review): if LangGraph ran incident_severity_node once
    # per incoming edge instead of once per converged step, this would be
    # 2, not 1 — silent double cost/latency on every Hybrid/Critical query.
    assert fake.call_counts["incident_severity"] == 1, (
        f"expected incident_severity_node's LLM to be called exactly once after the Hybrid fan-out "
        f"converges, got {fake.call_counts['incident_severity']} — fan-in is not deduplicating as assumed"
    )

    # Regression check for a real bug found via manual QA: account_validation
    # _node's own narrative used to be silently discarded in Hybrid mode —
    # only doc_retrieval_node's RAG-only text ever reached the user, even
    # when the actually-relevant answer was the SQL/account one. Both
    # narratives must now appear in the final merged answer (reflect_node's
    # _merge_final_answer()).
    assert "This looks related to a known incident." in body["answer"], "doc_retrieval's narrative missing from the final answer"
    assert "Your account is active." in body["answer"], "account_validation's narrative missing from the final answer"


@pytest.mark.asyncio
async def test_hybrid_mode_branches_run_concurrently_not_sequentially(
    client,
    support_agent_user,
    make_customer,
    patch_llm_client,
    patch_hybrid_search_with_one_result,
    patch_embed_text_fast,
    cleanup_conversations,
):
    """Proves concurrency via TIMESTAMP OVERLAP within a single request,
    not by comparing wall-clock durations across two separate requests.

    No longer eval-marked — real bug fix, not just a re-diagnosis: this
    test's own mocks used to never intercept app/orchestration/nodes/
    doc_retrieval.py's §31 Layer B scope check, which calls the real
    embed_text() (a genuine Azure embedding call) on every /chat request
    that reaches doc_retrieval_node. app/cache/redis_cache.py's own
    module docstring already documented this exact test as historically
    broken by this exact interaction, but the fixture to actually mock it
    out was never built — confirmed directly: 3/3 repeated real runs
    failed consistently (not intermittently) without it, since the real
    network latency reliably ate into the interval-overlap margin.
    patch_embed_text_fast (this file) closes that gap. Every other call in
    this test was already the fake LLM client (_RoutedFakeClient), never
    real Azure — with the one genuinely real, uncontrolled call now mocked
    too, this test is fully deterministic and belongs in the normal
    PR-blocking suite, not gated behind eval.

    History worth keeping, since it shaped this design: two earlier
    versions of this test compared a delayed request's total elapsed time
    against a baseline (no-delay) request's — first with a 0.5s delay and
    an absolute threshold, then with a 0.5s delay and a delta-vs-baseline
    threshold. Both flaked in this environment, because real per-request
    noise (DB connection setup, Presidio's own cost, general ASGI/DB
    variance) swings by several hundred ms to over a second between two
    otherwise-identical requests — enough to swamp or even invert a 0.5s
    signal. Even doubling the delay to 2s still wasn't reliably enough
    margin. Comparing two separate HTTP requests' total durations was the
    actual flaw, not the delay size — cross-request noise has no natural
    upper bound to budget against.

    This version records each call's own (start, end) monotonic
    timestamps, from a single fake client object, within a SINGLE
    request. Two calls being genuinely concurrent is then a structural
    fact — their intervals overlap — independent of how fast or slow the
    surrounding environment happens to be on this particular run.

    Found empirically (2 of 3 repeated runs passed at delay=0.3, one
    failed with a real, non-overlapping ~70ms gap): overlap isn't only
    threatened by cross-request noise (the earlier wall-clock version's
    flaw) — it's also threatened by pre-LLM-call setup-time SKEW between
    the two branches within the SAME request. account_validation_node
    does three real DB queries (get_customer/get_tickets/get_incidents)
    before it ever reaches its LLM call (where interval recording
    starts); doc_retrieval_node's own pre-LLM work is mocked to be near-
    instant (patch_hybrid_search_with_one_result). If that DB-query time
    exceeds `delay`, the two LLM-call windows can fail to overlap even
    though both nodes genuinely started concurrently — the fake client's
    sleep is too short to bridge a real setup-time head start. Raised to
    1.5s: comfortably larger than plausible DB round-trip variance under
    load, while still fast enough not to matter for a test that isn't
    PR-blocking-critical-path.
    """
    user, password = support_agent_user
    token = await _login(client, user, password)
    customer = await make_customer()
    delay = 1.5

    fake = patch_llm_client(
        _classify_response("incident", "High"),
        delays={"doc_retrieval": delay, "account_validation": delay},
    )

    resp = await client.post(
        "/chat",
        json={"query": "Is this a known incident?", "customer_id": customer.customer_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    cleanup_conversations.append(resp.json()["conversation_id"])

    doc_start, doc_end = fake.intervals["doc_retrieval"]
    acct_start, acct_end = fake.intervals["account_validation"]

    overlaps = doc_start < acct_end and acct_start < doc_end
    assert overlaps, (
        f"doc_retrieval interval ({doc_start:.3f}, {doc_end:.3f}) and account_validation interval "
        f"({acct_start:.3f}, {acct_end:.3f}) never overlapped — doc_retrieval_node and "
        "account_validation_node ran sequentially, not concurrently"
    )


@pytest.mark.asyncio
async def test_sql_mode_never_invokes_doc_retrieval_or_incident_severity(
    client, support_agent_user, make_customer, patch_llm_client, cleanup_conversations
):
    """category="billing" -> route_by_category returns "SQL" -> single edge
    to account_validation_node alone (Gap 1's resolution) — doc_retrieval_node
    must never run, and SEVCHECK must never fire (billing is never
    incident/security, and Critical always overrides to "Critical" mode,
    never "SQL" — see router.py's own route_by_category mapping)."""
    user, password = support_agent_user
    token = await _login(client, user, password)
    customer = await make_customer(company_name="Beta LLC")

    account_validation_response = (
        '{"narrative": "Your account is active.", '
        f'"cited_record_ids": ["customers_{customer.customer_id}"], '
        '"evidence_sufficient": true}'
    )
    fake = patch_llm_client(
        _classify_response("billing", "Low"),
        canned_overrides={"account_validation": account_validation_response},
    )

    resp = await client.post(
        "/chat",
        json={"query": "Why was I charged twice this month?", "customer_id": customer.customer_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    assert body["retrieval_mode"] == "SQL"
    assert body["escalated"] is False
    assert body["answer"]
    assert any(s["type"] == "sql" for s in body["sources"])
    assert not any(s["type"] == "chunk" for s in body["sources"])

    assert fake.call_counts["doc_retrieval"] == 0, "doc_retrieval_node's LLM was called in SQL-alone mode"
    assert fake.call_counts["incident_severity"] == 0, "incident_severity_node ran for a non-incident SQL query"
    assert fake.call_counts["account_validation"] == 1


@pytest.mark.asyncio
async def test_sql_sources_are_filtered_to_only_what_the_narrative_actually_cited(
    client, support_agent_user, make_customer, make_ticket, patch_llm_client, cleanup_conversations
):
    """Regression test for a real citation-noise bug found via manual QA:
    account_validation_node used to put EVERY fetched row into sources
    unconditionally (§14 point 1's "grounded by construction" was read as
    "no filtering needed," which produced a dozen+ region-wide incident
    citations for a simple one-line account question). Seeds a customer
    with TWO tickets, but the canned narrative only cites ONE of them —
    proves the uncited ticket is genuinely excluded from sources, not just
    that at least one sql source exists (the weaker check every other
    test in this file uses)."""
    user, password = support_agent_user
    token = await _login(client, user, password)
    customer = await make_customer(company_name="Gamma Retail")
    ticket_cited = await make_ticket(customer.customer_id, issue_category="billing")
    ticket_uncited = await make_ticket(customer.customer_id, issue_category="performance")

    account_validation_response = (
        '{"narrative": "Your billing ticket is open.", '
        f'"cited_record_ids": ["support_tickets_{ticket_cited.ticket_id}"], '
        '"evidence_sufficient": true}'
    )
    patch_llm_client(
        _classify_response("billing", "Low"),
        canned_overrides={"account_validation": account_validation_response},
    )

    resp = await client.post(
        "/chat",
        json={"query": "What's the status of my billing ticket?", "customer_id": customer.customer_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    cleanup_conversations.append(body["conversation_id"])

    sql_sources = [s for s in body["sources"] if s["type"] == "sql"]
    cited_record_ids = {s["record_id"] for s in sql_sources if s["table"] == "support_tickets"}
    assert ticket_cited.ticket_id in cited_record_ids
    assert ticket_uncited.ticket_id not in cited_record_ids, (
        "an uncited ticket appeared in sources — account_validation_node's cited_record_ids "
        "filter is not actually excluding rows the narrative didn't rely on"
    )
    # The customer record itself was never mentioned in cited_record_ids either — must not appear.
    assert not any(s["table"] == "customers" for s in sql_sources)
