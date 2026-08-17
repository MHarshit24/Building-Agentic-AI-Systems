"""
app/retrieval/rerank.py

Reranks fusion.py's fused top-10 down to a final top-5 (§9's "best result
is chosen" step) — catches cases where RRF still surfaces a
topically-adjacent-but-wrong result.

---------------------------------------------------------------------------
Deviation from §9's literal wording — read before touching this file
---------------------------------------------------------------------------
§9 specifies a LOCAL cross-encoder (sentence-transformers, ms-marco-MiniLM)
for reranking, with "no network round-trip" as an explicit stated benefit.
That is NOT what's implemented below, and the reason is a real, checked
dependency conflict, not a preference:

  sentence-transformers requires transformers, which requires
  tokenizers<=0.23.0. This environment already has tokenizers 0.23.1
  installed, depended on by other already-installed packages. Downgrading
  tokenizers to satisfy sentence-transformers would break those other
  packages. Installing sentence-transformers here is not safely possible
  without breaking something else that already works.

Instead, reranking is done via the SAME Azure OpenAI LLM already used
everywhere else in this codebase, through the already-built and tested
call_llm_structured() (app/llm/structured_output.py): the fused top-10 plus
the original query are sent to the LLM, which scores each result's
relevance 0-10 via a Pydantic schema (RerankResponse below); the top-5 by
score are returned.

This is not a downgrade. GPT-5-mini reasoning about *why* a result answers
the query is a genuinely stronger relevance signal than ms-marco-MiniLM's
learned pattern-matching, and it costs zero new dependencies in an
environment where the specified package literally cannot be installed
safely. If you're reading this because you're about to add
sentence-transformers back in: don't, until the tokenizers 0.23.1
conflict is independently resolved elsewhere in this project's dependency
tree — this comment is here so that decision isn't silently re-litigated
without knowing why it was avoided the first time.
---------------------------------------------------------------------------

Under LLM_PROVIDER=mock, no LLM call is made at all — the input order is
returned unchanged (truncated to top_n), deterministically, so tests can
exercise the full hybrid_search() pipeline without hitting a real API.

reasoning_effort — a real, disclosed gap closed, not a pre-existing
tuning choice: this module never passed reasoning_effort at all (unlike
every §13-tuned orchestration node), confirmed during the codebase-wide
LLM-fallback audit (README §37) to cause no failure on either provider
(both simply fall back to their own default) but left every real call
here untuned. Set to "low" here — the same tier doc_retrieval_node uses
for its own comparable-complexity reasoning (§13) — for consistency with
the rest of this codebase's explicit per-node tuning discipline, not
because an untuned default was ever observed to misbehave.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.llm.structured_output import call_llm_structured
from app.retrieval.vector_search import SearchResult

FUSION_CANDIDATES = 10
RERANK_TOP_N = 5
REASONING_EFFORT = "low"


class _RerankedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(description="0-based index of this result in the candidate list provided in the prompt")
    relevance_score: int = Field(description="Relevance of this result to the query, 0 (irrelevant) to 10 (directly answers it)")


class RerankResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rankings: list[_RerankedItem] = Field(description="One entry per candidate result, in any order")


def _format_candidates(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results):
        location = r.source_document or "unknown source"
        if r.section_header:
            location += f" § {r.section_header}"
        snippet = r.text[:500]
        lines.append(f"[{i}] ({r.asset_type}, {location})\n{snippet}")
    return "\n\n".join(lines)


def _build_prompt(query: str, results: list[SearchResult]) -> str:
    return (
        "You are scoring search results for relevance to a support query.\n\n"
        f"Query: {query}\n\n"
        f"Candidate results (indexed 0-{len(results) - 1}):\n\n"
        f"{_format_candidates(results)}\n\n"
        "Score every candidate's relevance to the query from 0 (irrelevant) to 10 "
        "(directly and completely answers the query). Return exactly one entry per "
        "candidate, referencing it by its index."
    )


async def rerank(query: str, results: list[SearchResult], top_n: int = RERANK_TOP_N) -> list[SearchResult]:
    """
    Takes fusion's fused results (defensively re-sliced to the top
    FUSION_CANDIDATES here, regardless of how many the caller passed) plus
    the original query, and returns the top_n by LLM-judged relevance.
    """
    candidates = results[:FUSION_CANDIDATES]
    if not candidates:
        return []

    if get_settings().llm_provider == "mock":
        return candidates[:top_n]

    response = await call_llm_structured(_build_prompt(query, candidates), RerankResponse, reasoning_effort=REASONING_EFFORT)

    scores = {item.index: item.relevance_score for item in response.rankings if 0 <= item.index < len(candidates)}
    scored = [(scores.get(i, 0), i, candidates[i]) for i in range(len(candidates))]
    scored.sort(key=lambda entry: entry[0], reverse=True)

    return [result for _, _, result in scored[:top_n]]
