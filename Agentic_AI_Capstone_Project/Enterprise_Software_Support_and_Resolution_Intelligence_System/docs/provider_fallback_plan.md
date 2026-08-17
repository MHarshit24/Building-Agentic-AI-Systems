# Azure → Groq/Gemini provider fallback — concrete plan

Planning document only — matches the discipline already used for
`production_readiness_gaps_plan.md`/`deletion_gaps_plan.md`. No
implementation yet.

## Goal, restated precisely

At startup: prefer Azure OpenAI (gpt-5-mini + text-embedding-3-small) if
and only if both its chat deployment and its embedding deployment are
genuinely reachable. If either is not, fall back to Groq
(`openai/gpt-oss-20b` for chat) + Gemini (`gemini-embedding-001` for
embeddings), but only if Groq, Gemini, *and* the already-implemented
judge model (`llama-3.3-70b-versatile`, unchanged) are all confirmed
reachable too. If neither tier fully checks out, refuse to start rather
than silently serving from `MockLLMClient` or a half-working provider.
Designed so the reachability-check functions themselves can be reused
later when API keys become per-end-user instead of env-sourced.

## Complete model-name inventory, and exactly where each setting lives

Convention, confirmed against real existing code, not assumed: API
**keys** are account-level shared secrets → root `.env`. Model/deployment
**names** are project-specific choices → project `.env`. Checked directly
against both real files — `GROQ_JUDGE_MODEL=llama-3.3-70b-versatile`
already lives in *project* `.env`, confirming this is the real, live
convention to mirror, not a guess. (Azure's own deployment names
currently live in *root* `.env` instead — an existing inconsistency,
already there before this plan, not being changed here since Azure's
setup isn't being touched.)

| Setting | Value | Location | Status |
|---|---|---|---|
| `azure_openai_api_key` | (secret) | root `.env` | existing, unchanged |
| `azure_openai_llm_deployment` | `gpt-5-mini` | root `.env` | existing, unchanged |
| `azure_openai_embedding_deployment` | `text-embedding-3-small` | root `.env` | existing, unchanged |
| `groq_api_key` | (secret) | root `.env` | existing, unchanged |
| `groq_judge_model` | `llama-3.3-70b-versatile` | project `.env` | existing, unchanged |
| `gemini_api_key` | (secret) | root `.env` | **new** |
| `groq_chat_model` | `openai/gpt-oss-20b` | project `.env` | **new** |
| `gemini_vision_model` | `gemini-2.5-flash` | project `.env` | **new** |
| `gemini_embedding_model` | `gemini-embedding-001` | project `.env` | **new** |

**Image captioning, answered directly**: `gemini-2.5-flash`, via
`generate_vision()` — not `gemini-3.6-flash`. Reasoning below.

## litellm — verified, not assumed, as requested

Checked directly against the real installed package
(`C:\...\site-packages\litellm`, version `1.82.5`, already declared in
`requirements.txt` — `litellm>=1.82.0,<2.0.0`, added for
`evaluation/groq_judge_client.py`):

- `"azure"`, `"groq"`, `"gemini"` are all real entries in
  `litellm.provider_list` — confirmed by import, not documentation.
- Traced `litellm/main.py`'s real `embedding()` dispatch directly:
  `elif custom_llm_provider == "gemini":` (line 5181) routes to
  `google_batch_embeddings.batch_embeddings(...)`, the **same**
  underlying transformation code
  (`llms/vertex_ai/gemini_embeddings/batch_embed_content_transformation.py`,
  confirmed to reference `output_dimensionality`) that the separate,
  paid Vertex AI path uses — invoked with
  `vertex_project=None, vertex_credentials=None`, i.e. the plain
  AI-Studio-key auth path matching the free `GEMINI_API_KEY`. Genuinely
  confirmed by reading the real dispatch code, not inferred from the
  directory name (which would have been misleading alone, since it
  lives under a `vertex_ai/` path).
- Conclusion: litellm is the right choice for the actual runtime
  generate/embed calls, unifying Azure/Groq/Gemini behind one call
  shape, exactly as it already does for the judge.
- **Not used for provider selection.** litellm's `Router.fallbacks`
  fires per-request, only once a real call actually fails — every live
  request would attempt (and pay for) Azure first, forever, even after
  Azure is confirmed dead. Provider selection stays a separate, explicit,
  startup-time decision; litellm is only the calling layer once that
  decision is made.

## The reachability checks — free metadata endpoints, never a real generate/embed call

- **Azure**: `GET {azure_openai_endpoint}/openai/deployments?api-version=...`
  — lists real deployments on the resource; check the configured chat
  and embedding deployment names both appear.
- **Groq**: `GET https://api.groq.com/openai/v1/models` — confirms both
  `openai/gpt-oss-20b` and `llama-3.3-70b-versatile` are listed.
- **Gemini**: `GET https://generativelanguage.googleapis.com/v1beta/models`
  — confirms `gemini-embedding-001` (with `embedContent` in its
  `supportedGenerationMethods`) and `gemini-2.5-flash` are listed.

All three are list/metadata calls only — no tokens spent, no billed
inference, on Azure or anywhere else, ever, as part of this check.

**Named tradeoff**: a model being listed isn't a guarantee it works for
a real call (confirmed earlier this session: `gemini-2.5-flash-lite`
404'd despite being listed; `gemini-2.0-flash` had `limit: 0` free quota
despite being listed). This catches the dominant real failure modes
(expired/revoked key, renamed deployment, model removed from the tier)
for free; it isn't airtight. The residual gap is left to
`call_llm_structured`'s existing bounded-retry logic, same as any other
transient real-call failure already has to be handled.

## Caching/re-check strategy — decided: no caching, recheck every startup

Re-run the full check on every app start, always — no cache, no TTL, no
invalidation logic to design. The checks are free, so there's no real
cost to re-checking, and this means if Azure becomes valid again later,
the app picks it back up automatically on the next restart with zero
manual intervention.

## The vision-call gap — why Gemini, and specifically 2.5 Flash not 3.6

`BaseLLMClient.generate_vision()` (`app/llm/base.py`) is a required
abstract method, used for real diagram/image captioning (§8.2,
`extract_images.py`). `gpt-oss-20b` is text-only; Groq has no
vision-capable model on this free tier. Resolution: the fallback client
routes `generate_vision()` to Gemini instead — the Gemini key is already
needed for embeddings, so this adds no new credential.

`gemini-2.5-flash`, not `gemini-3.6-flash`, specifically: confirmed this
session that `gemini-2.5-flash` had zero reliability failures across
multiple real calls (just slower, ~4.5–17s), while `gemini-3.6-flash`
failed 8 of 10 real calls with `503 high-demand` in the same test run.
Image captioning happens at ingestion time, never on the live chat
request path, so 2.5's slowness costs nothing there — reliability is
what actually matters for this specific call.

Concrete routing for the fallback tier's composite client:

| Method | Routes to | Why |
|---|---|---|
| `generate()` | Groq `openai/gpt-oss-20b` | Fastest and most accurate fallback-tier chat model; only one confirmed to support native strict `json_schema` — verified this session against your actual `DocRetrievalOutput`/`EscalationOutput`/`RerankResponse` schemas, all three passed |
| `generate_vision()` | Gemini `gemini-2.5-flash` | Groq has no vision model on this tier; reliability over latency for an ingestion-only call |
| `embed()` / `embed_batch()` | Gemini `gemini-embedding-001`, `output_dimensionality: 1536` | Confirmed dimension-matched — no schema migration or corpus re-embed needed |

**One open item, flagged not verified**: `gemini-embedding-001`'s real
latency wasn't measured this session (only reachability and dimension
were checked), and unlike vision, `embed_text()` runs on the live chat
request path too (Layer B's scope check, `vector_search()`'s query
embedding) — so its latency does matter for the SLO. Left as a real
open question for implementation time, not assumed fine.

## Concrete file changes

1. **`app/config.py`** — add the four new settings from the inventory
   table above. `llm_provider` gains a third real value, `"groq"`,
   alongside today's `"azure"`/`"mock"`.

2. **New `app/llm/provider_resolution.py`** — the reachability-check
   functions, each parameterized by explicit key/endpoint arguments (not
   reading `get_settings()` internally) so they're reusable later for
   per-end-user keys without rewriting the check logic — only the
   orchestration changes when that future need becomes real:
   ```python
   async def azure_deployments_reachable(api_key: str, endpoint: str, api_version: str,
                                          chat_deployment: str, embedding_deployment: str) -> bool: ...
   async def groq_model_reachable(api_key: str, model_id: str) -> bool: ...
   async def gemini_model_reachable(api_key: str, model_id: str, required_method: str) -> bool: ...

   async def resolve_llm_provider(settings: Settings) -> str:
       """Returns "azure" or "groq". Raises RuntimeError if neither tier
       is fully reachable — never returns "mock" as a fallback."""
   ```

3. **`app/main.py`'s `lifespan()`** — call `resolve_llm_provider(settings)`
   once, mutate `settings.llm_provider` on the cached `Settings` instance
   (same trick `_apply_calibrated_thresholds()` already uses), log the
   outcome via `log_event` before `build_graph()` runs.

4. **New `app/llm/groq_gemini_client.py`** — a `BaseLLMClient`
   implementation (like `AzureLLMClient`/`MockLLMClient`) built on
   `litellm.acompletion`/`litellm.aembedding`, routing per the table
   above.

5. **`app/llm/azure_client.py`'s `get_llm_client()`** — add the third
   branch: `if settings.llm_provider == "groq": return
   GroqGeminiClient()`.

6. **No changes needed** to `app/ingestion/embedding_client.py` — it
   already calls `get_llm_client().embed(...)`, so it picks up whichever
   provider was resolved automatically.

7. **No migration** — embedding dimension already confirmed compatible.

## Test design — fully mocked, no real calls anywhere, in testing or development

Per explicit instruction: no real call, of any kind, as part of building
or testing this feature — not even an eval-marked one. Every test below
uses mocked HTTP responses only:

- `provider_resolution.py`'s reachability functions — tested against
  mocked HTTP responses for every real scenario already observed this
  session (200 + model present, 200 + model absent/different name,
  401/403 invalid key, 404, `limit: 0` quota, timeout) — never a real
  network call.
- `resolve_llm_provider()` — tested with all four combinations (Azure
  up/down × fallback tier up/down) via mocked reachability functions,
  asserting the correct provider string or the correct `RuntimeError`.
- `GroqGeminiClient` — tested the same way `MockLLMClient`/
  `AzureLLMClient` already are elsewhere: `litellm.acompletion`/
  `litellm.aembedding` mocked via `monkeypatch`, never a real Groq/Gemini
  call.
- **No new eval-marked real-call test is added for this feature.** If
  and when real end-to-end confirmation is wanted, that's a manual step
  you run yourself, not something built into the implementation or test
  suite.

## Order of implementation

1. `app/config.py` — new settings.
2. `app/llm/provider_resolution.py` — reachability checks + orchestration,
   fully mocked tests alongside.
3. `app/llm/groq_gemini_client.py` — the composite client, fully mocked
   tests alongside.
4. `app/llm/azure_client.py` — `get_llm_client()`'s third branch.
5. `app/main.py` — wire `resolve_llm_provider()` into `lifespan()`.
6. Full non-eval suite run to confirm zero regression to the existing
   Azure/mock paths.

No real-call verification step included — stops at the mocked test
suite passing. Awaiting confirmation before implementing.
