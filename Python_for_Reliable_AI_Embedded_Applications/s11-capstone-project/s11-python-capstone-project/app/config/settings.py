import os
from dotenv import load_dotenv
from pathlib import Path

# More reliable path resolution
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"

# BASE_DIR = Path(__file__).resolve().parents[5]
# env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # Default model
GEMINI_ENDPOINT = os.getenv("GEMINI_ENDPOINT")

OLLAMA_MODEL_PATH = "http://localhost:11434/api/generate"