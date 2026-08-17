"""
FinDoc Analyzer — Application entry point.
Run: python main.py
"""

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from main.app import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "main.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )