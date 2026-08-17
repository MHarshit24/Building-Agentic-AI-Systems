# Autonomous Event Planning Team

A LangGraph-based multi-agent system that turns an event brief into a full
event plan: a manager agent decomposes the work, five specialist agents
(logistics, budget, marketing, schedule, risk) plan in parallel, and a
reflection agent critiques and iterates on the result until it clears a
quality bar or hits the iteration limit. A FastAPI backend (`app/`) exposes
this as a REST API with live-progress polling, and a Next.js frontend
(`front-end/`) provides a full UI on top of it.

## Repo layout

```
app/            FastAPI backend, LangGraph orchestrator, agents, tools
front-end/      Next.js (App Router, TypeScript, Tailwind) UI
tests/          pytest suite for the backend (offline, mocked LLM)
scripts/        local run + IIS/Vercel deployment scripts
docs/           sample requests and project write-up
```

## Features

### Multi-agent orchestration (`app/orchestrator/`, `app/agents/`)

A LangGraph state machine drives the whole plan:

```
START -> intake -> decompose -> ┬ logistics ┬ -> synthesize -> reflect -> finalize -> END
                                 ├ budget    ┤                     │
                                 ├ marketing ┤                     └─(quality gate: not yet passed
                                 ├ schedule  ┤                         & under max_iterations)─┐
                                 └ risk      ┘                                                 │
                                       ^______________________________________________________┘
```

- **Manager agent** (`agents/manager_agent.py`) decomposes a brief into
  per-specialist work on the first pass, then synthesizes the five
  specialist outputs plus an LLM-written summary into one `EventBlueprint`.
- **Five specialist agents** (`agents/{logistics,budget,marketing,schedule,risk}_agent.py`)
  run independently and in parallel. Each grounds its numeric/structural
  output in a deterministic tool (see below) and asks the LLM only for the
  bounded, qualitative part of its schema — with a deterministic fallback if
  the LLM call fails or returns unparseable JSON, so the graph never crashes:
  - **Logistics** — picks a venue from a capacity-matched catalog, then asks
    the LLM for catering/vendors/equipment.
  - **Budget** — computes a cost baseline from a per-head pricing model, then
    asks the LLM for a bounded (0–50%) contingency buffer to apply on top.
  - **Marketing** — computes an outreach start date from the event date,
    then asks the LLM for channels and a content calendar.
  - **Schedule** — builds a standard milestone timeline and flags calendar
    conflicts (blackout dates, past dates, colliding milestones), then asks
    the LLM for up to 3 event-specific milestones to add.
  - **Risk** — fully LLM-driven risk register (no deterministic source of
    truth for risk exists), with a sensible default risk list as fallback.
- **Reflection agent** (`agents/reflection_agent.py`) scores the draft
  blueprint on four weighted dimensions (feasibility 0.35, budget fit 0.25,
  risk coverage 0.20, coherence 0.20). A plan passes at a weighted score
  ≥ `quality_gate_threshold` (default 0.80, overridable per request);
  otherwise the failing dimensions are re-queued for another
  decompose → specialists → synthesize → reflect loop, bounded by
  `MAX_ITERATIONS`.

### Tools (`app/tools/`)

Deterministic, dependency-free Python functions the specialists call for
grounded numbers instead of hallucinating them: a venue catalog lookup, a
per-head + fixed-cost pricing model, and calendar milestone/conflict logic.

### LLM layer (`app/llm/`)

A single `complete(prompt, tier, provider=None)` entry point (via LiteLLM)
that every agent calls through `BaseAgent._think()`.

- `tier="reasoning"` (manager, specialists, reflection) tries **Azure OpenAI
  → Anthropic → Gemini** in order, skipping any provider without credentials
  configured. Callers (and the frontend, via `POST /plans`'s `provider`
  field) can pin a single provider instead of the fallback chain —
  `app/llm/model_router.py::resolve_chain` handles both.
- `tier="helper"` (cheap sub-steps) targets a local Ollama model only, and
  never falls back to a paid provider.
- `app/llm/structured_output.py` wraps specialist prompts' JSON schemas into
  a `response_format` passed straight through to `litellm.completion()`
  (OpenAI/Azure `json_schema` strict mode, Gemini `response_schema`, etc.),
  so a model that would otherwise wrap its answer in prose fails at the
  provider level instead of producing an unparseable response — with
  `parse_structured_json()` as a tolerant fallback parser either way.

Every call is wrapped in Langfuse tracing (see Observability). If no
provider is configured or every attempt fails, `complete()` raises
`LLMProviderError` — which every current caller already catches to fall
back to a deterministic default.

### REST API (`app/api/`, `app/main.py`)

A FastAPI app exposing:

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness check, which providers are configured (`available_providers`), and the default quality gate threshold |
| `POST /plans` | Create a plan from an `EventBrief`-shaped body (optionally pinning a `provider` and/or a per-request `quality_gate_threshold`); runs the graph as a background task and returns immediately with `status: "in_progress"` |
| `GET /plans` | List all plans (most recent first) with a lightweight summary — backs the frontend's history view |
| `GET /plans/{plan_id}` | Fetch a plan's current/finalized state (poll target while a plan is in progress) |
| `POST /plans/{plan_id}/refine` | Re-run the graph with an added free-text instruction (and optionally a specific set of `target_agents`) |

`POST /plans` and the refine endpoint both return immediately because a full
run can take well over a minute against real LLM providers; `GET /plans/{id}`
is meant to be polled until the plan reaches a terminal status (`completed`,
`needs_review`, or `failed`).

Every response — success or error — is wrapped in the same envelope:
`{"success": bool, "data": ..., "error": {"code", "message"} | null, "request_id": str}`,
so callers can branch on `success` once instead of special-casing each
endpoint's error shape. Domain errors map to `NOT_FOUND` (404),
`VALIDATION_ERROR` (422), or `UPSTREAM_ERROR` (502).

### Persistence (`app/store/`, `app/orchestrator/checkpointer.py`)

Both layers are backed by the same SQLite file (`DATABASE_URL`, default
`./event_plans.db`) and survive a process restart:

- `checkpointer.py` uses LangGraph's `AsyncSqliteSaver` to checkpoint the
  full in-flight `EventPlanState` after every node, so a plan can be
  re-invoked/refined without replaying from scratch.
- `plan_store.py` holds each plan's lifecycle record (status, brief summary,
  finalized blueprint, critique history, or failure message) in its own
  table in that same file, so `GET /plans` and `GET /plans/{id}` stay
  queryable without replaying the graph's checkpoint history.

### Security & observability (`app/security/`, `app/observability/`) — best-effort

Inbound briefs are PII-scrubbed via Presidio before hitting the graph
(`PII_ENGINE` / `PRESIDIO_ENABLED`), and an optional Guardrails-based output
check is available (`GUARDRAILS_API_KEY`). Every LLM call can be traced to
Langfuse (`LANGFUSE_*`). All three are config-gated and fail open — a
missing key or unavailable library never blocks a planning request.

### Testing (`tests/`)

A `pytest` suite covering the specialist agents (happy path + fallback for
each), the tools, the orchestrator's edges/graph wiring, the manager and
reflection agents, and the API endpoints (health plus the full plan
create/list/get/refine flow against a fake orchestrator) — all offline,
thanks to a `mock_llm_complete` fixture that swaps out `app.llm.client` so
no test needs live network or LLM access.

## Frontend (`front-end/`)

A Next.js (App Router, TypeScript, Tailwind CSS) UI with no component/icon
library — everything is hand-built so the app stays self-contained. See
[front-end/README.md](front-end/README.md) for the full breakdown; in short:

- **`app/page.tsx`** — submit a brief (`BriefForm`), watch live progress.
- **`app/history/`** — `GET /plans`-backed list view plus a per-plan detail
  page (`app/history/[planId]/page.tsx`) that resumes polling or shows the
  finalized blueprint and lets you submit a refinement.
- **Live progress** — `hooks/usePlanPolling.ts` polls `GET /plans/{id}`
  every ~1.5s; `components/AgentGraph.tsx` animates each specialist through
  `pending → working → waiting → done` states, `ProgressPanel` and
  `CritiqueHistoryList` render iteration/score history, and
  `components/agentTheme.tsx` is the single source of truth mapping each
  agent to a label/icon/color used consistently across all of them.
- **`components/StatusBadge.tsx`** — plan status pill (`completed`,
  `needs_review`, `failed`, `in_progress`) used in the history list and
  detail view.
- **`lib/types.ts`** / **`lib/api.ts`** — TypeScript mirrors of the backend's
  Pydantic schemas and a fetch wrapper that unwraps the `{success, data,
  error, request_id}` envelope.

## Setup

### Backend

1. Install dependencies (see `pyproject.toml`):
   ```
   pip install -e .
   ```
2. Copy `.env.example` to `.env` in the project root and fill in the values
   you need (see Configuration below — everything is optional except what's
   needed for the LLM provider(s) you plan to use).
3. Run the API locally:
   ```
   python scripts/run_local.py
   ```
   or, for a live smoke test, `POST /plans` with an `EventBrief`-shaped body
   (see `docs/sample-requests.md`) and check `GET /health`.
4. Run the test suite:
   ```
   pytest
   ```

### Frontend

1. Install dependencies and configure the API URL:
   ```
   cd front-end
   npm install
   cp .env.example .env.local
   ```
2. With the backend running (step 3 above), start the dev server:
   ```
   npm run dev
   ```
   Open `http://localhost:3000`.

## Deployment

Two deployment paths, each with a script under `scripts/`:

- **`scripts/deploy-iis.ps1`** — deploys both apps to local IIS via
  HttpPlatformHandler (backend on `http://localhost:8080`, frontend on
  `http://localhost:3000`), each supervised as a persistent process so the
  `POST /plans` background-task pattern and the SQLite-backed store keep
  working exactly as in local dev. Run `npm run build` in `front-end/`
  first; run as Administrator; pass `-BackendOnly` to skip the frontend
  (e.g. if it's hosted on Vercel instead). See the script's header comment
  for details, and `web.config` / `front-end/web.config` for the underlying
  HttpPlatformHandler config.
- **`scripts/deploy-vercel.ps1`** — deploys the backend and frontend as two
  separate Vercel projects (`vercel.json` at the repo root scopes the
  backend function to `app/main.py`), then wires the frontend's
  `NEXT_PUBLIC_API_BASE_URL` to the backend's stable alias URL and tightens
  the backend's `CORS_ALLOWED_ORIGINS` to the frontend's origin. Requires
  `vercel login` first. Note the backend's serverless functions are
  request/response only (no long-lived process), so `PRESIDIO_ENABLED` is
  forced off to avoid a cold-start model download, and `MAX_ITERATIONS`
  and Vercel's `maxDuration` matter more for whether a full multi-iteration
  run completes before the platform kills the invocation (see the script's
  header comment for the known limitation on Vercel Hobby's 60s cap).

## Configuration

All settings are loaded once via `app/config.py::get_settings()` — no other
module reads `os.environ` or calls `load_dotenv()` directly. Everything
below lives in a single `.env` file at the project root; nothing is
required to boot the app (every optional integration degrades gracefully
when its variables are unset), but you need at least one LLM provider
configured for `tier="reasoning"` calls to produce anything other than
fallback output.

> **Note on the dual `.env` load in `app/config.py`:** that file also knows
> how to load a second, shared `.env` from several directories up (a
> convenience for a machine running multiple course projects off one set of
> provider keys). If that shared file doesn't exist on your machine, it's
> skipped automatically — a single project-root `.env` with everything in
> it, per this file, is all you need. This lookup is skipped entirely when
> `VERCEL` is set, since a serverless deploy has no such directory tree and
> gets its env vars injected directly.

### LLM providers (`app/llm/`)

| Variable | Required | Default | Used for |
|---|---|---|---|
| `AZURE_OPENAI_API_KEY` | For Azure (1st in `reasoning` chain) | — | Azure OpenAI auth |
| `AZURE_OPENAI_ENDPOINT` | With the above | — | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_LLM_DEPLOYMENT` | With the above | — | Deployment name (alias: `AZURE_OPENAI_DEPLOYMENT_NAME`) |
| `AZURE_OPENAI_API_VERSION` | With the above | — | Azure API version, e.g. `2024-02-15-preview` |
| `ANTHROPIC_API_KEY` | For Anthropic (2nd in `reasoning` chain) | — | Anthropic auth |
| `ANTHROPIC_MODEL_NAME` | No | `claude-sonnet-5` | Anthropic model id (alias: `ANTHROPIC_MODEL`) |
| `GEMINI_API_KEY` | For Gemini (3rd in `reasoning` chain) | — | Gemini auth |
| `GEMINI_MODEL_NAME` | No | `gemini-flash-lite-latest` | Gemini model id (alias: `GEMINI_MODEL`) |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Local Ollama server for the `helper` tier |
| `OLLAMA_MODEL_NAME` | No | `phi3:mini` | Local model name pulled in Ollama |

`tier="reasoning"` (manager, specialists, reflection) tries Azure, then
Anthropic, then Gemini, skipping any provider missing credentials — unless a
specific `provider` is passed (via `POST /plans`'s `provider` field or the
frontend's model picker), in which case only that provider is tried, with no
fallback. `tier="helper"` (cheap sub-steps) only ever targets Ollama. If no
provider is configured/available for a tier, `app/llm/client.py` raises
`LLMProviderError`; every current caller catches this and falls back to a
deterministic default rather than crashing the graph.

### Security / PII (`app/security/`) — best-effort, never blocks a request

| Variable | Default | Notes |
|---|---|---|
| `PII_ENGINE` | `presidio` | Which scrubbing engine `pii_validator.py` delegates to |
| `PRESIDIO_ENABLED` | `true` | Set `false` to skip PII scrubbing entirely (also avoids Presidio's spaCy model download — forced off on the Vercel deploy) |
| `GUARDRAILS_API_KEY` | — | Enables `guardrails_engine.py`'s output validation; left unset, it no-ops |

### Observability (`app/observability/`) — best-effort

| Variable | Default | Notes |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | — | Leave unset (with the secret key) to disable tracing entirely |
| `LANGFUSE_SECRET_KEY` | — | |
| `LANGFUSE_HOST` | Langfuse cloud default | Only needed for a self-hosted Langfuse instance |

### App behavior

| Variable | Default | Notes |
|---|---|---|
| `DEBUG_MODE` | `false` | Reserved for future use |
| `DATABASE_URL` | `sqlite:///./event_plans.db` | SQLite file backing both the LangGraph checkpointer and the plan store |
| `MAX_ITERATIONS` | `3` | Max manager/reflection refinement loops before a plan is force-finalized |
| `QUALITY_GATE_THRESHOLD` | `0.80` | Default weighted reflection score required to pass the quality gate (0.5–0.9); overridable per request via `POST /plans`'s `quality_gate_threshold` field |
| `CORS_ALLOWED_ORIGINS` | `*` | Comma-separated origins allowed to call this API cross-origin, e.g. a deployed frontend's URL |

### Frontend (`front-end/.env.local`)

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend, no trailing slash |

Never commit a real `.env` — it's already covered by `.gitignore`.
