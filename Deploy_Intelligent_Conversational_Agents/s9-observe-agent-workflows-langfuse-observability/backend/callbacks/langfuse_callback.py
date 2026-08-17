"""
Langfuse Callback Handler Module

This module provides a centralized Langfuse callback handler for tracing
LangChain chain executions in the Langfuse dashboard.
"""
import os
from typing import Optional
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse
from pathlib import Path
from dotenv import load_dotenv

# -------------------------------
# Environment Setup
# -------------------------------
BASE_DIR = Path(__file__).resolve().parents[4]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

## Task 2: Add Observability with Langfuse Callback Handler (Chat API)

langfuse = Langfuse()


def get_langfuse_manager(
    session_id: str,
    user_id: Optional[str] = None,
    trace_name: str = "chat-trace"
):
    """
    Create a Langfuse callback handler with metadata.
    """

    handler = CallbackHandler()

    config = {
        "callbacks": [handler],
        "metadata": {
            "session_id": session_id,
            "user_id": user_id,
            "trace_name": trace_name,
        }
    }

    return config, handler