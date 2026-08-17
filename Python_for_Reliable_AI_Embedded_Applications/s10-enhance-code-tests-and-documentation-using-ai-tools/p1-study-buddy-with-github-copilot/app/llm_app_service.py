from openai import OpenAI
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[4]

env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)
api_key = os.getenv("GEMINI_API_KEY")
base_url = os.getenv("GEMINI_OPENAI_ENDPOINT")
model = os.getenv("GEMINI_MODEL")

client = OpenAI(api_key=api_key, base_url=base_url)


def generate_explanation(concept: str) -> str:
    """
    Generate explanation for a concept using Gemini API.
    """

    messages = [
        {
            "role": "user",
            "content": f"Explain {concept} in Agentic AI clearly and concisely for a beginner."
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages
    )

    return response.choices[0].message.content