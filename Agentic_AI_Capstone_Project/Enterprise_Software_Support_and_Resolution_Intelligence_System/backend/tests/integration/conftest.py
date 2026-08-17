"""
tests/integration/conftest.py

L3 VCR cassette infrastructure (§19, §25 Stage 9) — genuinely built from
zero here, not extended: confirmed before writing this that vcrpy/
pytest-recording were declared in requirements.txt ("VCR cassettes for L3
integration tests") but never actually invoked anywhere in this suite —
tests/cassettes/ held only a .gitkeep, and the sole "VCR" mention in test
code was a comment in test_graph_e2e.py explaining why that file *doesn't*
need it. The existing @pytest.mark.eval tests (test_hybrid_search.py,
test_escalation_mcp.py) are NOT this layer, despite living in the same
directory — they make a real, live, uncosted-by-cassette call every time
they run (L4's shape: real LLM, nightly/manual, not every PR), where L3's
whole point is recording once and replaying free/fast on every PR
afterward.

record_mode="none" is the deliberate DEFAULT here, not "once" — running a
@pytest.mark.vcr test with no cassette recorded yet must fail loudly with
vcrpy's own "cassette not found" error, never silently fall through to a
real, costed network call. Recording a new cassette is a genuine,
separate, deliberate action: run once locally with
`--record-mode=once` (or `=rewrite` to re-record after a real prompt/
schema change), inspect the resulting cassette file for anything
sensitive before committing it, then it replays via the "none" default
for everyone else from then on.

filter_headers scrubs real credentials (Authorization bearer tokens,
api-key headers) from ever being written into a cassette file — cassette
files are committed to version control (tests/cassettes/), so a secret
baked into one would leak the same way a hardcoded key in source would.
match_on intentionally excludes exact body matching: this project's real
request bodies (Azure structured-output json_schema payloads, especially)
are large and can vary in incidental ways (e.g. schema key ordering)
between two calls that are semantically identical — matching on
method+URI is enough to catch a genuine call-shape regression (wrong
endpoint, wrong model deployment) without cassette playback breaking on
harmless serialization differences.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    return {
        "record_mode": "none",
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("api-key", "REDACTED"),
            ("Authorization", "REDACTED"),
            ("Api-Key", "REDACTED"),
        ],
        "decode_compressed_response": True,
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """One cassette file per test module, under tests/cassettes/ — the
    directory §18/§25 already name, previously holding only .gitkeep."""
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1] / "cassettes")
