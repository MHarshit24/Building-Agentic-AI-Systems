"""Responsible for observability and tracing integration with Langfuse.

Best-effort and config-gated: if Langfuse credentials are absent or the
`langfuse` package can't produce a client, tracing silently no-ops so
observability never blocks or breaks a planning run.
"""

import contextvars
from contextlib import contextmanager
from functools import lru_cache

from app.config import get_settings

# A bare session_id with no trace_id ingests fine (the API returns 201) but
# never materializes into a queryable score — Langfuse's score model needs
# a trace (or observation) to attach to. This tracks the most recent
# generation's trace_id so record_score() can attach to something real.
# contextvars.ContextVar (not a module global) so concurrent asyncio tasks
# — e.g. two plans' background tasks running interleaved — don't clobber
# each other's value; asyncio.Task copies the context at creation, so each
# task's writes stay isolated.
_last_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_last_trace_id", default=None
)


@lru_cache
def _get_client():
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
    except ImportError:
        return None

    try:
        kwargs = {
            "public_key": settings.langfuse_public_key,
            "secret_key": settings.langfuse_secret_key,
        }
        if settings.langfuse_host:
            kwargs["host"] = settings.langfuse_host
        return Langfuse(**kwargs)
    except Exception:
        return None


@contextmanager
def trace_llm(name: str, tier: str, prompt: str, session_id: str | None = None):
    """Wrap one LLM call. Yields a `finish(output, model=None, duration_ms=None)`
    callback the caller invokes with the completion result; no-ops
    end-to-end when Langfuse isn't configured or errors.

    session_id (the plan_id) groups every LLM call for one plan under the
    same Langfuse session, so a plan's specialist + reflection calls are
    browsable together instead of appearing as unrelated traces."""
    client = _get_client()
    if client is None:
        yield lambda output, model=None, duration_ms=None: None
        return

    _last_trace_id.set(None)
    generation = None
    try:
        # session_id must be attached via propagate_attributes() *before* the
        # observation is created — langfuse v4 (OTel-based) has no
        # equivalent of the old v3 generation.update_trace(session_id=...)
        # to retrofit it after the fact.
        trace_id = None
        if session_id:
            from langfuse import create_trace_id, propagate_attributes

            trace_id = create_trace_id()
            with propagate_attributes(session_id=session_id):
                generation = client.start_observation(
                    name=name,
                    as_type="generation",
                    input=prompt,
                    metadata={"tier": tier},
                    trace_id=trace_id,
                )
        else:
            generation = client.start_observation(
                name=name,
                as_type="generation",
                input=prompt,
                metadata={"tier": tier},
            )
    except Exception as e:
        print("LANGFUSE ERROR:", repr(e))
        generation = None

    def finish(output, model=None, duration_ms=None):
        if generation is None:
            return
        try:
            metadata = {"tier": tier}
            if duration_ms is not None:
                metadata["duration_ms"] = duration_ms
            generation.update(output=output, model=model, metadata=metadata)
            generation.end()
            _last_trace_id.set(generation.trace_id)
        except Exception:
            pass

    try:
        yield finish
    finally:
        if generation is not None:
            try:
                client.flush()
            except Exception:
                pass


def record_score(
    plan_id: str,
    name: str,
    value: float,
    comment: str | None = None,
) -> None:
    """Attach a numeric score (e.g. the weighted critique score, the
    quality-gate threshold, or the delta between them) to the most recent
    LLM call's trace (expected to be this same reflection iteration's own
    critique generation, called right after its trace_llm() block exits) —
    a score needs a trace_id or observation_id to ever become queryable;
    session_id alone is accepted by ingestion but never materializes into a
    visible score. The API rejects a score body carrying both trace_id and
    session_id ("provide exactly one of traceId, sessionId or
    datasetRunId"), so trace_id is used whenever available — the trace
    itself already carries this plan's session_id (see trace_llm's
    propagate_attributes call), so the score still shows up grouped with
    the rest of the plan's traces. Falls back to session_id only if no
    trace_id was captured (e.g. Langfuse was down for that LLM call).
    Called with the exact same values the API serves on CritiqueNote, so a
    plan's score/threshold/delta shown in the app and in Langfuse are
    always the same numbers — never a second, independently-recomputed
    copy. No-ops if Langfuse isn't configured, same as trace_llm."""
    client = _get_client()
    if client is None:
        return
    trace_id = _last_trace_id.get()
    try:
        client.create_score(
            session_id=None if trace_id else plan_id,
            trace_id=trace_id,
            name=name,
            value=value,
            data_type="NUMERIC",
            comment=comment,
        )
        # create_score only enqueues the event (self._resources.add_score_task);
        # without an explicit flush it sits until the next auto-flush interval
        # and is lost entirely if the process exits first, same reasoning as
        # the flush() at the end of trace_llm.
        client.flush()
    except Exception:
        pass
