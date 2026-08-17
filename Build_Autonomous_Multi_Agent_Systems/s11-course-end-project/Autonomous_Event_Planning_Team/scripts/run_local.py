"""Responsible for local development entry-point execution."""

import sys
from pathlib import Path

# Running this file directly (`python scripts/run_local.py`) puts scripts/,
# not the project root, on sys.path[0] — so "app" wouldn't resolve without
# this. uvicorn's reload=True also re-runs this module (unguarded top-level
# code only) in each respawned worker process, so the fix has to live here
# rather than at the call site.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
