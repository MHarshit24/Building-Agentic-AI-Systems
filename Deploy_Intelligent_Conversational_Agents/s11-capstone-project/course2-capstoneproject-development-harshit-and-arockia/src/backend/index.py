"""
Vercel entry point — Job Placement Agent Backend
-------------------------------------------------
Uses Mangum to wrap the FastAPI ASGI app as an AWS-Lambda/Vercel handler.
All env vars must be configured in the Vercel project dashboard.
"""
import sys
import os

# Make backend modules importable: fastapi_app, agent/, auth/, models/, observability/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi_app import app  # noqa: E402  FastAPI ASGI application
from mangum import Mangum    # noqa: E402  ASGI → Lambda/Vercel adapter

# Vercel's Python runtime invokes `handler` as the serverless entry point
handler = Mangum(app, lifespan="off")
