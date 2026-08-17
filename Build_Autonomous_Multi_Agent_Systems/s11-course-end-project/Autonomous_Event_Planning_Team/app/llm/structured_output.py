"""Responsible for schema-constrained LLM output (Sprint 2 "structured
output" / Sprint 6 "output_pydantic" concept, adapted for the litellm
completion() call in app/llm/client.py rather than a LangChain/CrewAI model
object).

Every specialist prompt previously asked the model to "respond with nothing
but a single valid JSON object" and hoped for the best — with no schema
enforcement, a model that wraps its answer in prose or a markdown fence
produces a JSON.loads() failure and the caller silently falls back to a
generic canned response. Passing a JSON schema via response_format cuts
that failure mode off at the provider level instead of relying on prompt
wording alone.

response_format is passed straight through to litellm.completion(), which
normalizes it per-provider (OpenAI/Azure OpenAI json_schema strict mode,
Gemini response_schema/response_mime_type, etc.). If a provider/model in
the chain doesn't support it, the call raises and app.llm.client.complete()
already falls through to the next provider — and if every provider fails,
each agent's own try/except already degrades to its fallback response — so
this is safe to attempt unconditionally.
"""

import json


def build_response_format(name: str, schema: dict) -> dict:
    """Wrap a plain JSON Schema dict into the response_format shape
    litellm/OpenAI-compatible providers expect."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
            "strict": True,
        },
    }


def parse_structured_json(response: str, required_keys: set[str] | None = None) -> dict | None:
    """Best-effort parse of a model response into a dict, tolerating a
    markdown code fence even though response_format should make one
    unnecessary. Returns None (never raises) if the result isn't a dict
    containing every key in required_keys."""
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        candidate = json.loads(cleaned)
    except Exception:
        return None

    if not isinstance(candidate, dict):
        return None
    if required_keys is not None and not required_keys.issubset(candidate.keys()):
        return None
    return candidate
