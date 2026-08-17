"""
app/prompts/doc_retrieval_v1.py

Prompt builder for the Documentation Retrieval Agent (§3 roster #3,
§39.3's DocRetrievalOutput schema). §32.2 template order:
ROLE_INSTRUCTIONS -> OUTPUT_SCHEMA -> FEW_SHOT (incl. a grounded-refusal
example per §14) -> TOOL_DEFS -> dynamic retrieved-context -> history ->
query.

TOOL_DEFS here is descriptive, not a literal OpenAI function-calling
schema: hybrid_search() is called deterministically by doc_retrieval.py
itself (plain Python, same pattern as every ingestion extractor calling
its own sub-functions) before this prompt is ever built — the retrieved
evidence arrives already-fetched in dynamic_ctx. call_llm_structured()
has no multi-turn tool-calling loop built (checked: it only enforces
provider-level structured JSON output, §39.1), so there's no real
function-calling round-trip to describe; TOOL_DEFS documents that the
evidence below came from that tool, for the model's own context.
"""

from app.prompts._shared import INJECTION_DEFENSE_CLAUSE, JSON_ONLY_CLAUSE

ROLE_INSTRUCTIONS = (
    "You are the Documentation Retrieval Agent for an enterprise software support system. "
    "You are given a user's query and a set of retrieved evidence snippets (chunks, tables, "
    "diagram captions) already fetched by a hybrid search tool. Answer ONLY from this "
    "retrieved evidence — never from general knowledge. If the evidence doesn't actually "
    "support a good answer, say so explicitly (\"I don't have enough information to answer "
    "that\") rather than guessing or filling gaps from training knowledge.\n\n"
    "Cite every retrieved item your answer actually relies on by putting its [id] label in "
    "cited_source_ids. Do not cite an item you didn't use.\n\n"
    "draft_answer must read as clean prose for an end user — never write an [id] tag "
    "inside draft_answer itself. Citations belong ONLY in the separate cited_source_ids "
    "list, never inline in the answer text.\n\n"
    f"{INJECTION_DEFENSE_CLAUSE}"
)

OUTPUT_SCHEMA = (
    "Output schema:\n"
    '{"draft_answer": str, "cited_source_ids": list[str], "evidence_sufficient": bool, '
    '"rewritten_query": str | null}\n\n'
    "rewritten_query: only fill this in when evidence_sufficient is false — a rephrased "
    "version of the query that might retrieve better evidence (different wording, more "
    "specific terms, or a synonym the retrieved evidence suggests is more precise). Leave it "
    "null when evidence_sufficient is true.\n\n"
    f"{JSON_ONLY_CLAUSE}"
)

FEW_SHOT = (
    "Example 1 (normal case, evidence sufficient):\n"
    "Query: \"What does a 429 error mean?\"\n"
    "Evidence: [id=table_6] \"429 | Rate limit exceeded | Wait 60s, implement exponential "
    "backoff\"\n"
    'Output: {"draft_answer": "A 429 error means the rate limit was exceeded. Wait 60 '
    'seconds and implement exponential backoff before retrying.", "cited_source_ids": '
    '["table_6"], "evidence_sufficient": true, "rewritten_query": null}\n\n'
    "Example 2 (grounded refusal — evidence insufficient, §14):\n"
    "Query: \"What is the maximum number of API keys per account?\"\n"
    "Evidence: [id=chunk_12] \"API keys are scoped to specific permissions and can be "
    "rotated.\" (no mention of any per-account limit)\n"
    'Output: {"draft_answer": "I don\'t have enough information to answer that — the '
    "retrieved documentation doesn't state a maximum number of API keys per account.\", "
    '"cited_source_ids": [], "evidence_sufficient": false, "rewritten_query": "API key '
    'limit per account maximum quota"}'
)

TOOL_DEFS = (
    "Tool context: the evidence below was retrieved by a hybrid_search tool, automatically "
    "filtered to the query's classified category and any mentioned product version. You do "
    "not call this tool yourself — it has already run."
)


ACCOUNT_CONTEXT_NOTE = (
    "NOTE: this query also touches account-specific data (e.g. this customer's own tickets, "
    "incidents, or subscription details). A separate agent has already looked that up "
    "independently and its findings will be shown to the user alongside your answer — you do "
    "not have access to it and must not guess at it. Do NOT state that you lack access to the "
    "customer's account/subscription/ticket information as a caveat or disclaimer; that would "
    "contradict the account data the user is about to see right next to your answer. Simply "
    "answer whatever part of the query the retrieved documentation evidence below actually "
    "covers, and say nothing about account-specific facts one way or the other."
)


def build_prompt(static_ctx: dict, dynamic_ctx: dict) -> list[dict]:
    """
    static_ctx: unused (module-level constants below are always identical).
    dynamic_ctx: {"query": str, "history": list[dict], "evidence": str, "account_context": str | None}
      "evidence" is a pre-formatted string of retrieved items with [id] labels
      (built by doc_retrieval.py from hybrid_search's results).
      "account_context": real bug fix — see ACCOUNT_CONTEXT_NOTE's own docstring-adjacent
      comment in doc_retrieval.py for the concrete symptom this closes. Truthy whenever
      account_validation_node has already produced a real account_narrative elsewhere in this
      request (Hybrid/Critical mode, or a reflect-loopback retry after an original SQL-alone
      attempt) — this agent must never issue a blanket "I don't have access to your account"
      denial in that case, since that denial gets concatenated right next to the real account
      answer by reflect.py's _merge_final_answer(), producing a self-contradictory response.
    """
    query = dynamic_ctx["query"]
    history = dynamic_ctx.get("history") or []
    evidence = dynamic_ctx.get("evidence") or "(no evidence retrieved)"
    account_context = dynamic_ctx.get("account_context")

    static_section = "\n\n".join([ROLE_INSTRUCTIONS, OUTPUT_SCHEMA, FEW_SHOT, TOOL_DEFS])

    dynamic_parts = []
    if account_context:
        dynamic_parts.append(ACCOUNT_CONTEXT_NOTE)
    dynamic_parts.append(f"Retrieved evidence:\n{evidence}")
    if history:
        history_text = "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history)
        dynamic_parts.append(f"Conversation history:\n{history_text}")
    dynamic_parts.append(f"Query: {query}")

    return [
        {"role": "static", "content": static_section},
        {"role": "dynamic", "content": "\n\n".join(dynamic_parts)},
    ]
