"""
app/guardrails/pii.py

Presidio-based PII redaction (§16/§24.3), built in Stage 6 — this is the
stage where structured account data first flows toward a user-facing
response (§25's own Stage 6 line).

Investigated against the real schema (app/db/models.py) before building
this, not assumed: customers/support_tickets/incident_logs have no
email/phone/personal-name column anywhere — the §24.3 red-team scenario
("What's the email/phone number on file for customer X?") is already
partly defended by schema absence, since there's nothing to leak from
structured fields. The one real, live PII surface is
IncidentLog.root_cause — free text a human engineer typed, which could
plausibly contain an incidentally-typed email/phone even though no
column is *designed* to hold PII — potentially flowing into
account_validation_node's own LLM-generated `narrative`, which becomes
part of the user-facing answer.

This module therefore scans response-bound TEXT (the narrative prose),
not the raw sql_results dicts — matching §24.3's own wording precisely:
"Presidio redaction applied to any account data before it reaches the
response." doc_retrieval_node's final_answer (ingested admin-authored
technical documentation, not customer data) is explicitly out of scope
for this guardrail.
"""

from __future__ import annotations

import asyncio
import logging

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from app.logging.structured_logger import log_event

logger = logging.getLogger(__name__)

# Module-level singletons — AnalyzerEngine() loads an NLP model at
# construction time (real, measurable startup cost); building it once per
# process rather than once per redact_pii() call is the whole difference
# between "a few hundred ms per account-validation request" and "however
# long model loading takes, every single time."
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# The two entities §24.3's own red-team example names explicitly
# ("email/phone number on file"). Not the full default entity list —
# scoped deliberately to what this schema's one free-text risk
# (IncidentLog.root_cause) could plausibly contain, not a generic
# maximal PII sweep unrelated to the actual data this system handles.
PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER"]


def _redact_pii_sync(text: str) -> str:
    results = _analyzer.analyze(text=text, language="en", entities=PII_ENTITIES)
    if not results:
        return text

    log_event(logger, "WARNING", "pii_redacted", entity_types=sorted({r.entity_type for r in results}))

    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text


async def redact_pii(text: str) -> str:
    """Scans `text` for the entities in PII_ENTITIES and replaces any hits
    with a placeholder (<EMAIL_ADDRESS>, <PHONE_NUMBER>). A hit firing is
    logged at WARNING — a genuine, rare, worth-flagging event, mirroring
    Stage 5's Layer-B scope-guardrail logging convention — since it means
    a human typed something PII-shaped into a free-text field this system
    is about to narrate back to another user.

    async, dispatching the actual Presidio work via asyncio.to_thread —
    found necessary, not just a style choice: presidio_analyzer's
    AnalyzerEngine.analyze()/AnonymizerEngine.anonymize() are synchronous,
    CPU-bound calls (real spaCy NLP work). Calling them directly inside an
    async node blocks the single-threaded asyncio event loop for their
    entire duration, which — since account_validation_node runs
    concurrently with doc_retrieval_node during Stage 6's Send-based
    Hybrid/Critical fan-out — would silently serialize that concurrency
    from the inside, defeating the whole point of the fan-out, without
    ever raising an error. Caught via test_graph_parallel_fanout.py's own
    concurrency-timing test, not assumed safe."""
    if not text:
        return text
    return await asyncio.to_thread(_redact_pii_sync, text)
