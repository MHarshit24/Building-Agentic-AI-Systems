# Autonomous Event Planning — Frontend

A Next.js (App Router, TypeScript, Tailwind CSS) UI for the event planning
API in `../app`. Submit an event brief, watch live progress while the
specialist agents and reflection loop run, then review and refine the
resulting plan.

No component library or icon package — everything is hand-built and styled
with Tailwind so the whole app stays self-contained.

## How live progress works

`POST /plans` on the backend returns immediately (the graph run is kicked off
as a background task) rather than blocking for the full run, which can take
well over a minute against real LLM providers. This app then polls
`GET /plans/{id}` every ~1.5 seconds (`hooks/usePlanPolling.ts`) and renders
whichever specialists have produced output so far, the current iteration
count, and the growing review history — until the plan reaches a terminal
status (`completed`, `needs_review`, or `failed`).

## Local development

1. Make sure the backend is running (see the project root `README.md`):
   ```
   python scripts/run_local.py
   ```
   By default it serves on `http://localhost:8000`.
2. Install dependencies and configure the API URL:
   ```
   npm install
   cp .env.example .env.local
   ```
3. Run the dev server:
   ```
   npm run dev
   ```
   Open `http://localhost:3000`.

## Deploying to Vercel

**Important: only this frontend goes on Vercel.** The FastAPI backend
(long-running graph execution, a SQLite file, background tasks) is not a fit
for Vercel's serverless functions — it needs to be hosted somewhere that
keeps a persistent process running (a VM, Render, Railway, Azure App Service,
etc.), reachable over HTTPS.

1. Deploy/host the backend first and note its public URL.
2. On that backend, set `CORS_ALLOWED_ORIGINS` (see project root
   `.env.example`) to the frontend's Vercel URL once you have it (or leave it
   as the default `*` while testing, then lock it down).
3. Deploy this folder to Vercel — either:
   - **Dashboard:** import the repo, set the project root to `front-end/`,
     and Vercel will auto-detect Next.js (no build config needed).
   - **CLI:**
     ```
     npm install -g vercel
     vercel
     ```
     (run from inside `front-end/`).
4. In the Vercel project's Environment Variables, set:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://your-backend-host.example.com
   ```
   (no trailing slash), then redeploy.

## Project structure

- `app/` — routes (`page.tsx`), root layout, global styles.
- `components/` — `BriefForm`, `ProgressPanel`, `BlueprintView`, `RefineForm`,
  and shared inline-SVG `icons.tsx`.
- `hooks/usePlanPolling.ts` — the polling loop behind live progress.
- `lib/types.ts` — TypeScript mirrors of the backend's Pydantic schemas.
- `lib/api.ts` — fetch wrapper for `POST /plans`, `GET /plans/{id}`,
  `POST /plans/{id}/refine`, unwrapping the backend's `{success, data, error,
  request_id}` response envelope.
