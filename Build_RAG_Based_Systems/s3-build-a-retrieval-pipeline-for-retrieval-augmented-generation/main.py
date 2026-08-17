"""
Application entry point for RAG Query Pipeline API.

Run the FastAPI server using:
    uv run python main.py
    or
    uv run uvicorn main.app:app --reload --host 0.0.0.0 --port 8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disabled to prevent watchfiles spam
        log_level="info"
    )

