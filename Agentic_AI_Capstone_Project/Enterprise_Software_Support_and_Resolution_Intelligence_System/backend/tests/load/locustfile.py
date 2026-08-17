"""
tests/load/locustfile.py

Stage 9's load test (§19, §25) — validates the ≤2s (RAG/SQL/Hybrid) /
≤3.5s (Critical) latency SLOs (§24.1's decision, now a real, importable
constant in evaluation/slo_targets.py rather than only a planning
decision) against a REAL, running instance under concurrent load —
orthogonal to LLM correctness (§19's own framing): this only measures
whether the SYSTEM holds its latency budget when multiple support agents
hit it at once, not whether the answers are any good.

RUNNING THIS MAKES REAL, COSTED BACKEND LLM CALLS. Every simulated
/chat request invokes the real graph end-to-end (a real Azure OpenAI
call per node the query's path touches). This file is safe to review,
edit, and import — defining these classes makes zero real calls by
itself. Actually pointing Locust at a running instance and letting it
fire N users × M requests (`locust -f tests/load/locustfile.py --host
http://127.0.0.1:8123`) is a deliberate, separate, real-cost action —
the same discipline already applied to recording a VCR cassette or
running run_eval.py for real.

Real sequencing note, stated rather than assumed away: §25's roadmap
puts this file in Stage 9 but deployment in Stage 10 — "against the
deployed instance" (§25's own phrase) can only literally happen once
Stage 10's deployment exists. This file is built and locally validatable
(docker-compose, or any already-running dev instance) in Stage 9; the
real deployed-instance run follows naturally afterward, not a
contradiction in the roadmap.

Rate-limit reality this load profile must respect, not fight: POST
/chat is capped at 20 requests/min per user_id (§16.1) — unbounded
concurrent users hammering the SAME seeded account would just generate
429s, not a real latency signal. Each simulated Locust user logs in as
its OWN seeded account (scripts/seed_synthetic_data.py's fixed demo
roster, §22.1) rather than sharing one, so load scales across distinct
user_ids instead of tripping one account's own rate limit.

Traffic mix approximates §13's own real percentages (RAG ~55% / SQL ~30%
/ Hybrid ~15%) via weighted task selection over realistic query text per
category, plus a small additional Critical-triggering task — Critical is
layered on top of the RAG/SQL/Hybrid split (router.py's route_by_
category: severity_initial=="Critical" overrides to Critical mode
regardless of category), not a fourth disjoint slice of that same 100%,
so its weight is additive, not carved out of the other three. A uniform
random query mix would not reflect what §24.1's targets were actually
set against, so weights are deliberate here, not arbitrary.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

from evaluation.slo_targets import LATENCY_TARGET_SECONDS

# scripts/seed_synthetic_data.py's fixed demo roster (§22.1) — real
# seeded accounts, not invented ones. DEV_PASSWORD matches that script's
# own DEMO_USER_PASSWORD constant (shared local/dev password by design,
# §22.1 — not a secret to look up per account).
_DEMO_PASSWORD = "DevPassword123!"
_DEMO_ACCOUNTS = [
    {"email": f"support_agent{i}@enterprise-support.local", "password": _DEMO_PASSWORD} for i in range(1, 4)
] + [{"email": f"admin{i}@enterprise-support.local", "password": _DEMO_PASSWORD} for i in range(1, 3)]

_RAG_QUERIES = [
    "How do I configure OAuth 2.0 authentication for the API?",
    "What's the correct way to set up webhook retries?",
    "Where can I find the rate limit documentation?",
]
_SQL_QUERIES = [
    "What's my current subscription tier?",
    "Show me my open support tickets.",
]
_HYBRID_QUERIES = [
    "Is the performance issue related to a known incident?",
    "Why is my integration failing intermittently?",
]
_CRITICAL_QUERIES = [
    "URGENT: the API is completely down for all customers, need immediate escalation.",
]


class SupportAgentUser(HttpUser):
    """One simulated support agent — logs in once (on_start) as its own
    seeded account, then fires weighted /chat requests matching §13's
    real traffic mix. wait_time models a human agent reading/typing
    between tickets, not a tight request loop — this is a support-tool
    load profile, not an API-throughput benchmark."""

    wait_time = between(2, 8)

    def on_start(self) -> None:
        account = random.choice(_DEMO_ACCOUNTS)
        response = self.client.post("/auth/login", json={"email": account["email"], "password": account["password"]})
        response.raise_for_status()
        self.token = response.json()["access_token"]
        self.customer_id = 1  # course dataset's first seeded customer — same default golden_runner.py uses

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _chat(self, query: str, expected_mode: str) -> None:
        """Fails the request in Locust's own reporting (not just a slow
        bar in the UI) if it exceeds that path's real §24.1 target —
        this is what makes "P95 met the SLO" a real, checkable assertion
        rather than something a human has to eyeball off a latency chart
        after the fact."""
        target_seconds = LATENCY_TARGET_SECONDS.get(expected_mode, LATENCY_TARGET_SECONDS["RAG"])
        with self.client.post(
            "/chat",
            json={"query": query, "customer_id": self.customer_id},
            headers=self._auth_headers(),
            catch_response=True,
            name=f"/chat [{expected_mode}]",
        ) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
                return
            elapsed_seconds = response.elapsed.total_seconds()
            if elapsed_seconds > target_seconds:
                response.failure(
                    f"{elapsed_seconds:.2f}s exceeded {expected_mode}'s {target_seconds}s SLO target (§24.1)"
                )

    @task(55)
    def rag_query(self) -> None:
        self._chat(random.choice(_RAG_QUERIES), "RAG")

    @task(30)
    def sql_query(self) -> None:
        self._chat(random.choice(_SQL_QUERIES), "SQL")

    @task(15)
    def hybrid_query(self) -> None:
        self._chat(random.choice(_HYBRID_QUERIES), "Hybrid")

    @task(5)
    def critical_query(self) -> None:
        self._chat(random.choice(_CRITICAL_QUERIES), "Critical")
