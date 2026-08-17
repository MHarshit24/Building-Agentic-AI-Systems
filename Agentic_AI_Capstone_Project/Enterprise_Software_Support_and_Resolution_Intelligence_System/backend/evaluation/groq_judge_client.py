"""
evaluation/groq_judge_client.py

The independent LLM judge (§24.2) — a held-out model never used in
production, so self-grading bias (the same model judging its own output)
never taints an eval score the way it would if reflect_node's own model
(GPT-5-mini) also graded the golden-eval run.

Model: llama-3.3-70b-versatile on Groq — a Production-tier model on
Groq's genuine perpetual free tier (not a Preview model). Confirmed by
real research: this model is WEAKER than GPT-5-mini on standard
benchmarks, not comparable and not stronger — stated plainly, not
softened. The justification for this pick is independence (Meta's Llama
lineage, unrelated to OpenAI's GPT-5-mini training lineage — avoids the
self-grading bias problem an independent judge exists to catch in the
first place), never superiority. An earlier pick, qwen/qwen3.6-27b, was
tried first and replaced after real, empirical problems surfaced during
this stage's build (see below) — this is the second, current choice, not
the original one.

Standard instruct model, no internal reasoning/thinking phase — confirmed
against Groq's own reasoning-models documentation, which lists exactly
five reasoning models (openai/gpt-oss-20b/120b/safeguard-20b,
qwen/qwen3.6-27b, minimaxai/minimax-m2.7); this model is not among them.
This matters architecturally, not just as a fact: because this model has
no internal chain-of-thought to fall back on, every judge call in this
module's callers (ragas_metrics.py, calibrate_thresholds.py) is
deliberately decomposed into small, atomic, single-decision calls (one
claim extracted and verified at a time, one retrieved item judged at a
time, one ground-truth fact confirmed at a time) rather than one call
asking for a compound, multi-fact judgment in a single pass — decomposing
the task explicitly is how reasoning quality gets recovered from a model
that has no internal multi-step reasoning of its own.

Built on litellm rather than a hand-built openai.AsyncOpenAI(base_url=...)
wrapper: real model-catalog volatility was observed twice during this
project's own history (DeepSeek-R1-distill vanished from Groq's live
catalog during initial judge-model planning; qwen/qwen3.6-27b was itself
later replaced by this model after real cost/reliability problems).
Routing through litellm.acompletion(model="groq/...") means a future
provider or model swap is a config/model-string change, not a client
rewrite.

response_format={"type": "json_object"} — confirmed necessary regardless
of which Groq model is used, not qwen3.6-27b-specific: Groq's own
structured-outputs documentation lists only the GPT-OSS family
(openai/gpt-oss-20b/120b/safeguard-20b) as supporting native json_schema
mode; every other model, including this one, falls back to JSON Object
Mode (syntactically-valid-JSON-only, no schema enforcement — callers must
still say "json" in the prompt and validate the parsed result themselves,
both already true of every call site via app/prompts/_shared.py's
JSON_ONLY_CLAUSE + call_llm_structured's own Pydantic validation).

Historical note on why qwen/qwen3.6-27b was replaced (kept for context,
does not describe this model's current behavior): qwen3.6-27b defaulted
to emitting a verbose hidden <think>...</think> reasoning preamble before
its real answer, with no separate reasoning-token accounting (thinking
tokens billed as ordinary completion_tokens) — this caused real,
confirmed failures (empty generations when the hidden reasoning alone
consumed the entire completion budget) and made per-call cost highly
input-dependent and hard to bound. A real extraction call against a
realistic pipeline prompt needed 2,088 completion tokens against a 2,000
cap; even after raising the cap, the resulting request sizes collided
with Groq's TPM rate limiter (which reserves against requested max_tokens,
not realized usage — confirmed by a real 429). This model has none of
that: no hidden reasoning phase, no separate token-accounting surprise,
and — per the module docstring above — the decomposition work already
done to compensate for a non-reasoning judge stays exactly as useful here
as it would be for any other non-reasoning model.

Deliberately NOT a BaseLLMClient subclass (app/llm/base.py) — that ABC
requires generate/generate_vision/embed/embed_batch, and a judge that
only ever does text-in/text-out scoring would be forced to stub 3 unused
abstract methods for no benefit. This module's generate() is duck-typed
to match exactly what call_llm_structured's new client= parameter
expects (app/llm/structured_output.py) — nothing more.

Real Groq free-tier limits for this exact model, fetched directly from
Groq's own documentation (not estimated): 30 RPM / 12K TPM / 1K RPD /
100K TPD — note the TPD cap is actually LOWER than qwen3.6-27b's (200K),
even though per-call token cost is much lower without thinking-mode
overhead; the two effects partly cancel for full-run feasibility (see
ragas_metrics.py's own updated estimate). A real full 50-query eval pass
is still not practically feasible on this free tier — hence --sample
being the permanent, intended operating mode (not a temporary
workaround) and the --sample/preflight-ceiling/pacing machinery below
being load-bearing, not optional polish.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import litellm

from app.config import get_settings

# Confirmed directly from Groq's own docs for llama-3.3-70b-versatile
# (free tier). Note TPD is lower than qwen3.6-27b's 200K despite this
# model's much cheaper per-call cost (no thinking-mode overhead) — see
# module docstring.
GROQ_RPM_LIMIT = 30
GROQ_TPM_LIMIT = 12_000
GROQ_RPD_LIMIT = 1_000
GROQ_TPD_LIMIT = 100_000

# Blended real per-call average across this model's call shapes (extraction-
# shaped calls ~850 tokens, verification-shaped calls ~600-650 tokens — see
# ragas_metrics.py's EXTRACTION_MAX_TOKENS/VERIFICATION_MAX_TOKENS and their
# own real-data justification), no longer inflated by thinking-mode
# uncertainty the way qwen3.6-27b's estimate was.
ESTIMATED_TOKENS_PER_CALL = 600

# Per-query judge call count, worst case, after decomposing every judge
# call into atomic single-decision checks (§ this stage's call-site
# review): faithfulness (1 extract + ≤5 verify ≈ 6) + correctness
# (1 extract + ≤5 verify ≈ 6) + answer relevance (1) + context precision
# (~4) + context recall (0, label-matching only) = 17.
ESTIMATED_CALLS_PER_QUERY = 17

DEFAULT_SAFETY_MARGIN = 0.8  # only ever budget up to 80% of the daily token cap by default


class CallBudgetExceededError(Exception):
    """Raised by preflight_check() when a requested run would risk
    exceeding Groq's real daily token cap — refuses to start rather than
    failing partway through a real, costed run."""


def estimate_call_count(num_queries: int) -> int:
    return num_queries * ESTIMATED_CALLS_PER_QUERY


def max_safe_call_count(safety_margin: float = DEFAULT_SAFETY_MARGIN) -> int:
    return int((GROQ_TPD_LIMIT * safety_margin) // ESTIMATED_TOKENS_PER_CALL)


def preflight_check(num_queries: int, *, safety_margin: float = DEFAULT_SAFETY_MARGIN, force: bool = False) -> int:
    """Computes the expected call count for a run against `num_queries`
    golden queries and refuses to proceed (raising CallBudgetExceededError)
    if it would come within an unsafe margin of Groq's real daily token
    cap. Returns the estimated call count on success. `force=True` (an
    explicit, deliberate override — never a default) skips the check."""
    estimated = estimate_call_count(num_queries)
    if force:
        return estimated
    ceiling = max_safe_call_count(safety_margin)
    if estimated > ceiling:
        raise CallBudgetExceededError(
            f"Running {num_queries} golden queries is estimated at ~{estimated} judge calls, "
            f"exceeding the safety ceiling of {ceiling} calls (~{safety_margin:.0%} of Groq's "
            f"{GROQ_TPD_LIMIT:,}-token/day free-tier cap for llama-3.3-70b-versatile, at a conservative "
            f"~{ESTIMATED_TOKENS_PER_CALL} tokens/call). Use --sample with a smaller N, or pass "
            f"force=True / --force to override this ceiling explicitly."
        )
    return estimated


class RatePacer:
    """Paces judge calls to stay under Groq's confirmed free-tier RPM/TPM
    limits — computed from ESTIMATED_TOKENS_PER_CALL, so pacing stays
    conservative until real per-call token usage (post thinking-mode
    suppression, if any) is confirmed. Prevents a run that fits under the
    daily cap from still 429-ing mid-run by bursting requests too fast."""

    def __init__(
        self,
        *,
        rpm: int = GROQ_RPM_LIMIT,
        tpm: int = GROQ_TPM_LIMIT,
        tokens_per_call: int = ESTIMATED_TOKENS_PER_CALL,
    ) -> None:
        calls_per_minute_by_rpm = rpm
        calls_per_minute_by_tpm = tpm / tokens_per_call
        safe_calls_per_minute = max(min(calls_per_minute_by_rpm, calls_per_minute_by_tpm), 1)
        self._min_interval = 60.0 / safe_calls_per_minute
        self._last_call_at: float | None = None

    async def wait(self) -> None:
        now = time.monotonic()
        if self._last_call_at is not None:
            elapsed = now - self._last_call_at
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
        self._last_call_at = time.monotonic()


async def generate(prompt: str, **kwargs: Any) -> Any:
    """Duck-typed to match call_llm_structured's client= parameter
    exactly (app/llm/structured_output.py) — the only method it ever
    calls on a client is generate(prompt, **kwargs).

    response_format override — a real, confirmed finding, not a
    precaution: call_llm_structured always builds an Azure/OpenAI-strict-
    mode json_schema response_format (_make_strict_compatible() —
    additionalProperties: false + every key forced into "required" on
    every nested object). litellm has no native json_schema support for
    this Groq model, so it emulates structured output via a synthetic
    tool/function call — and a real verification call confirmed Groq's
    own tool-call validator rejects that Azure-shaped schema even when
    the model's actual generated answer was already correct (error
    "tool_use_failed", with the correct JSON sitting right there in the
    error's own failed_generation field). Fix, verified against that
    same real call: ignore the json_schema response_format
    call_llm_structured built and substitute Groq's simpler
    {"type": "json_object"} mode instead — no schema/tool-calling
    involved, just "return JSON", which every prompt built with
    app/prompts/_shared.py's JSON_ONLY_CLAUSE already satisfies (that
    mode's one real requirement — the prompt must say "json" — every
    caller already does via that shared clause)."""
    settings = get_settings()
    if not settings.groq_api_key or not settings.groq_judge_model:
        raise RuntimeError(
            "GROQ_API_KEY (root .env) / GROQ_JUDGE_MODEL (project .env) are not both configured — "
            "cannot run the independent judge."
        )
    kwargs["response_format"] = {"type": "json_object"}
    # No reasoning_format handling here — llama-3.3-70b-versatile has no
    # internal reasoning/thinking phase at all (confirmed absent from
    # Groq's reasoning-models list, see module docstring), so the
    # parameter that was load-bearing for qwen3.6-27b (suppressing a
    # hidden <think> preamble that could otherwise consume the whole
    # completion budget) would be meaningless here, not just unnecessary.
    # max_tokens still gets a conservative backstop default; callers pass
    # an explicit, call-shape-specific value in practice (see
    # ragas_metrics.py's EXTRACTION_MAX_TOKENS/VERIFICATION_MAX_TOKENS),
    # so this setdefault mostly guards any caller that doesn't.
    kwargs.setdefault("max_tokens", 1000)
    return await litellm.acompletion(
        model=f"groq/{settings.groq_judge_model}",
        messages=[{"role": "user", "content": prompt}],
        api_key=settings.groq_api_key,
        **kwargs,
    )
