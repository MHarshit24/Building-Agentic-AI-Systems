# Deployment Plan — Enterprise Software Support & Resolution Intelligence System

## Context

This is a first-ever deployment for the project. The project (FastAPI backend + React/Vite frontend + LangGraph multi-agent orchestration + Postgres/pgvector + optional Redis) is currently only run locally; `README.md §34` and `§35` honestly document that no real instance has ever been stood up, and `tests/load/locustfile.py` has never been run against a live deployment.

Platform choice: **Render** for frontend (Static Site), backend (Web Service), and Redis (Key Value) — the only free-tier platform in 2026 that supports a persistent process (needed for SSE streaming and the MCP notification server's stdio subprocess spawn) — plus **Neon** for Postgres+pgvector specifically, since Render's own free Postgres self-deletes after 30 days and Neon's doesn't expire. Sequencing: deploy the current, already-tested codebase (301 passing tests, real CI) now, and treat the README's known gaps and the not-yet-built "per-user API keys" feature as later, separate work.

Two further decisions were confirmed:
- **GitHub mirror scope: whole `Agentic_AI_Capstone_Project` monorepo** (not just the project subfolder). This push happens at the user's own convenience — it does not block anything else in this plan.
- **Backend runtime: Render's native Python runtime**, not Docker, for this first deploy (Docker can be layered in later once the basic deploy is working).

A real blocker was discovered during research: the project's git `origin` is a self-hosted institutional GitLab instance (`myrepos.stackroute.niit.com`), and Render only connects to github.com/gitlab.com/bitbucket.org — so a GitHub mirror is a hard prerequisite, not optional polish.

No application code changes are in scope here except one *conditional* one-line-per-property edit to `config.py`'s connection-string properties, only if Neon's TLS requirement turns out to need an explicit query param (verified in Phase 1, step 5, before touching Render at all).

## Phase 0 — Local repo hygiene

1. Resolve the currently uncommitted changes (`git status` shows modified: `README.md`, `backend/app/cache/redis_cache.py`, `backend/app/ingestion/embedding_client.py`, `backend/app/llm/azure_client.py`, `backend/app/llm/base.py`, `backend/app/llm/groq_gemini_client.py`, `backend/app/llm/mock_client.py`, plus an untracked `backend/tests/unit/test_embedding_client.py`) — commit them to the institutional `origin` first. Render/GitHub only ever see what's committed and pushed.
2. Confirm tests are green on the commit about to be mirrored (`pytest -m "not eval"` in `backend/`).

## Phase 1 — Neon (Postgres + pgvector)

1. Create a free Neon project (neon.tech). Pick a region close to where the Render services will run (Render's free-tier regions: Oregon, Ohio, Virginia, Frankfurt, Singapore).
2. In the SQL editor, run `CREATE EXTENSION IF NOT EXISTS vector;` — confirms pgvector is available before Alembic creates any vector columns.
3. Copy Neon's **direct** (non-pooler) connection string. Don't use the pooled/PgBouncer endpoint — `langgraph-checkpoint-postgres` manages its own psycopg pool, and mixing that with Neon's own pooler is a known source of prepared-statement errors.
4. Split the single connection string into the five values `app/config.py`'s `Settings` expects: `DB_HOST`, `DB_PORT` (5432), `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Keep these aside for Phase 3 — don't commit them anywhere.
5. **Local smoke test before touching Render** — this is the cheapest place to discover any Neon TLS issue, not a failed Render deploy. From `backend/`, with the Neon values exported as env vars:
   - Run `alembic upgrade head` pointed at Neon (exercises psycopg3, used by `config.py`'s `database_url` property).
   - Start the app locally pointed at Neon (`uvicorn app.main:app --loop app.win_loop:loop_factory` on Windows) — this exercises both asyncpg (`async_database_url`, the runtime engine) and the LangGraph Postgres checkpointer (`checkpointer_conn_string`), since `main.py`'s lifespan builds the checkpointer at startup.
   - If either fails with a TLS/SSL negotiation error: append `?sslmode=require` to the psycopg-based strings (`database_url`, `checkpointer_conn_string`) and `?ssl=require` to the asyncpg-based one (`async_database_url`) — asyncpg doesn't recognize `sslmode`. This is a one-line-per-property edit in `backend/app/config.py` around lines 228–257, done only if the smoke test actually shows it's needed.

## Phase 2 — GitHub mirror (whole monorepo)

1. Create a new, empty GitHub repo under the user's personal account (no auto-init README/license/gitignore, to avoid a merge step).
2. In the existing local repo at `Agentic_AI_Capstone_Project`:
   ```bash
   git remote add github https://github.com/<username>/<repo-name>.git
   git push github main
   ```
   This adds a second remote alongside `origin` (the institutional GitLab) — `origin` is never touched, stays the official submission history.
3. Verify on GitHub that the push landed, including `.env` is **not** present (already confirmed gitignored — `.gitignore` line 111 excludes it, and `git ls-files` confirms nothing named `.env` is tracked anywhere in the repo).
4. Not required now, optional later: `.github/workflows/*.yml` currently live under `Enterprise_Software_Support_and_Resolution_Intelligence_System/.github/workflows/`, which is not the GitHub repo's root — so GitHub Actions won't auto-discover `backend-ci.yml` on this mirror. This doesn't block Render (Render's own deploy doesn't depend on GitHub Actions), so it can be fixed later with a one-time `git mv` if/when CI-on-the-mirror matters.

## Phase 3 — Render backend Web Service

1. Render dashboard → New → Web Service → connect the GitHub repo from Phase 2 → branch `main`.
2. Configuration (native Python runtime):
   - **Root Directory**: `Enterprise_Software_Support_and_Resolution_Intelligence_System/backend`
   - **Runtime**: Python 3 — Render defaults to Python 3.14.3 as of Feb 2026, matching this project; no version pin needed unless Render's default drifts away from 3.14 later.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` — no `--loop` flag. `win_loop.py` and the `sys.platform == "win32"` branch in `main.py` are Windows-only dev workarounds, dead code on Render's Linux containers.
   - **Pre-Deploy Command**: `alembic upgrade head` — runs after build, before the new instance receives traffic (matches the Blueprint's "new schema live before new code" rule). Do not put this in the Start Command — that would re-run it on every process restart, not just every deploy.
   - **Health Check Path**: `/health`.
3. Environment variables (Render dashboard → Environment) — full inventory from `Settings` in `config.py`:
   - **Required, no default** (instantiation fails without these): `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (Phase 1's Neon values), `JWT_SECRET_KEY` (generate a fresh production value, don't reuse the local dev one), `MCP_NOTIFICATION_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `APPLICATION_EMAIL`, `SUPPORT_EMAIL`.
   - **Have defaults, set explicitly anyway**: `DB_PORT=5432`, `AZURE_OPENAI_LLM_DEPLOYMENT=gpt-5-mini`, `LLM_PROVIDER=azure`, `PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=30`, `ACTIVE_PROMPT_VERSION=v1`.
   - **`CORS_ALLOWED_ORIGINS`** — set to a placeholder for now (e.g. the backend's own URL); updated for real in Phase 6 once Phase 4 produces the frontend's URL.
   - **Leave at defaults, no action needed**: `CONFIDENCE_HIGH_THRESHOLD`/`CONFIDENCE_MEDIUM_THRESHOLD` — `evaluation/results/calibrated_thresholds.json` is present in the repo and overrides these at runtime automatically, as designed.
   - **Optional, leave blank for first deploy**: `GROQ_API_KEY`, `GROQ_JUDGE_MODEL`, `GEMINI_API_KEY`, `GROQ_CHAT_MODEL`, `GEMINI_VISION_MODEL`, `GEMINI_EMBEDDING_MODEL` (only needed if the Groq/Gemini fallback tier or eval judge should work in prod). `REDIS_URL` — leave unset until Phase 5.
4. Deploy. Watch build/pre-deploy/deploy logs for: Alembic succeeding against Neon (confirms Phase 1's TLS question in the real prod path), `pip install` succeeding for Presidio/PyMuPDF's native deps on Render's Linux image, the checkpointer building at startup, and no `ModuleNotFoundError` for `mcp_servers.notification_mcp.server` — that specific error would mean Root Directory wasn't set correctly, since `app/mcp_client/notification_client.py` spawns `python -m mcp_servers.notification_mcp.server` as a subprocess and that module path only resolves with `backend/` as the process's working directory.
5. Note the assigned URL (`https://<service>.onrender.com`) — needed for Phase 4.

## Phase 4 — Render frontend Static Site

1. Render dashboard → New → Static Site → same GitHub repo → branch `main`.
2. **Root Directory**: `Enterprise_Software_Support_and_Resolution_Intelligence_System/frontend`
3. **Build Command**: `npm install && npm run build` (matches `package.json`'s `"build": "tsc -b && vite build"`)
4. **Publish Directory**: `dist` (Vite's default; not overridden in `vite.config.ts`)
5. **Build-time environment variables** — Vite bakes `VITE_*` values into the static bundle at build time, so these must be set before the build runs, not just at runtime:
   - `VITE_API_BASE_URL` = the backend URL from Phase 3, step 5
   - `VITE_USE_MOCKS` = `false`
6. Deploy. Note the assigned URL (`https://<site>.onrender.com`).

## Phase 5 — Render Key Value (Redis) — optional, can be done last

1. Render dashboard → New → Key Value → free tier.
2. Copy the internal connection string.
3. Back in the Phase 3 backend service's Environment settings, set `REDIS_URL` to it, then redeploy.
4. Since `redis_url: str | None = None` and every consumer (cache, rate limiting, JWT blacklist) degrades gracefully without it, this step is genuinely optional and doesn't block anything else.

## Phase 6 — Wiring follow-up

1. Update the Phase 3 backend's `CORS_ALLOWED_ORIGINS` from its placeholder to the real Phase 4 frontend URL (comma-separate with `http://localhost:5173` too, if local dev against the deployed backend is ever wanted). Redeploy — `CORSMiddleware` reads this at app construction time, not per-request.
2. If the backend's URL ever changes after Phase 4, the frontend needs a rebuild (not just a backend-side env var edit), since `VITE_API_BASE_URL` is compiled into the JS bundle.
3. Turn on **Render's own native auto-deploy-on-push** (Web Service and Static Site settings → Auto-Deploy → On) — the simplest path, no CI secrets needed. Leave `backend-ci.yml`'s Job 4 (Render/Railway deploy-hook trigger) unused for now to avoid two mechanisms racing on the same push; it's a reasonable thing to switch to later once the CI Docker-build job is actually wired to something real.
4. **One-time manual data seed** (not part of the ongoing Pre-Deploy Command): run `python scripts/seed_synthetic_data.py` once, via Render's Shell tab on the backend service (working directory is already `backend/` there) or locally against the Neon connection string. It's idempotent, safe if run twice, but is a one-off action, not something to bake into every future deploy.

## Verification (run in order)

1. `GET https://<backend>.onrender.com/health` → HTTP 200, `"postgres": "ok"`, `"azure_openai": "ok"`, `"redis": "ok"` or `"not_configured"`. Confirms Neon and Azure reachability from Render's actual network.
2. Open the frontend URL, confirm no console errors pointing at `localhost` (stale build indicator).
3. Real login through the deployed frontend against the deployed backend — exercises JWT + Neon-backed user table.
4. Real chat message end-to-end — confirms a real (non-mock) Azure OpenAI response, the full LangGraph run, the Postgres checkpointer against Neon, and a trace showing up in the Langfuse dashboard.
5. Confirm the chat response actually streams token-by-token in the browser network tab (not buffered as one blocked response) — worth checking explicitly since some platform proxies buffer streaming responses.
6. Trigger a real escalation path, confirm the email lands in Mailtrap — the concrete test that the MCP subprocess spawn works on Render's Linux container with the correct working directory, and that `SMTP_*` is wired correctly end to end.
7. Run `backend/tests/load/locustfile.py` from a local machine pointed at the live Render backend URL — the first real measurement against a deployed instance, closing the `TBD` latency gap noted in `docs/slo_evaluation_report.md`.

## Critical files referenced

- `backend/app/config.py` — full `Settings` field inventory; the three connection-string properties (`database_url`, `async_database_url`, `checkpointer_conn_string`, lines ~228–257) that may need the conditional SSL query-param fix
- `.github/workflows/backend-ci.yml` — existing Job 4's Render deploy-hook logic (not used in this plan, left for later)
- `frontend/.env.example` — the two build-time Vite vars
- `backend/app/mcp_client/notification_client.py` — the subprocess module-path constraint driving the Root Directory requirement, and the target of verification step 6
- `backend/scripts/seed_synthetic_data.py` — the one-time manual seed step
- `backend/tests/load/locustfile.py` — final verification step
