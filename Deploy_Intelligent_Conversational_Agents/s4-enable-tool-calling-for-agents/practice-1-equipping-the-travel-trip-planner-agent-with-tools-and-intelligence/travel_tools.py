# travel_tools.py
"""
Implements:
- Internal Tool: get_destination_info
- External Tool: get_user_location (via apiip.net)
"""


import os
from langchain_openai import ChatOpenAI
from langchain.tools import tool
import json
import requests

from pathlib import Path
from dotenv import load_dotenv


# -------------------------------
# Environment Setup
# -------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()
API_KEY = os.getenv("APIIP_API_KEY")  # Ensure correct variable name in .env file
GEMINI_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://api.openai.com/v1")
GEMINI_MODEL_NAME = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

# -------------------------------
# LLM Initialization
# -------------------------------
def _get_llm():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    return ChatOpenAI(
        base_url=GEMINI_BASE_URL,
        model=GEMINI_MODEL_NAME,
        api_key=GEMINI_API_KEY,
        temperature=0.3,
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Travel-Agent-App"
        }
    )

llm = _get_llm() if GEMINI_API_KEY else None

# -------------------------------
# Task 1: Internal Tool (LLM-powered)
# -------------------------------
#Implement a tool function that validates the destination input, invokes the LLM with a travel 
# prompt, and returns structured JSON with destination info or error messages.

@tool
def get_destination_info(destination: str) -> dict:
    """
    Fetch travel information about a destination including best time to visit,
    top attractions, and notable features.
    """

    try:
        # 1. Input validation
        if not destination or not destination.strip():
            raise ValueError("Destination cannot be empty")

        # 2. Create prompt
        prompt = f"""
        You are a strict travel assistant.

        Generate travel information ONLY for: {destination}.

        IMPORTANT RULES:
        - ALL attractions MUST be located in {destination}
        - DO NOT mention any place outside {destination}
        - If unsure, return an empty list instead of guessing
        - DO NOT include cities like New York, London, etc. unless the destination is that city

        Return ONLY valid JSON with:
        - best_time_to_visit
        - top_attractions (real places in {destination}) (list)
        - notable_features

        Be factually correct and location-specific.
        """

        # 3. Call LLM
        if llm is None:
            raise ValueError("GEMINI_API_KEY is not set")
        response = llm.invoke(prompt)

        # 4. Extract text safely
        content = response.content if hasattr(response, "content") else str(response)

        # 5. Strip accidental markdown fences before parsing
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        # 6. Try parsing JSON — return dict directly (no double-encoding)
        try:
            parsed = json.loads(content)
            return {
                "best_time_to_visit": parsed.get("best_time_to_visit", ""),
                "top_attractions": parsed.get("top_attractions", []),
                "notable_features": parsed.get("notable_features", ""),
            }
        except json.JSONDecodeError:
            return {
                "destination": destination,
                "info": content
            }

    except Exception as e:
        return {
            "error": str(e)
        }

# -------------------------------
# Task 2: External Tool
# -------------------------------

#Implement a tool function that validates the API key, calls the external apiip.net service, 
# handles network errors, and returns user location data in JSON format

@tool
def get_user_location(input: str = "") -> dict:
    """
    Fetch user location based on IP using apiip.net
    """

    try:
        # 1. Check API key
        if not API_KEY:
            raise ValueError("APIIP_API_KEY is missing in environment variables")

        # 2. API endpoint
        url = f"https://apiip.net/api/check?accessKey={API_KEY}"

        # 3. Make request
        response = requests.get(url, timeout=5)

        # 4. Handle bad status
        if response.status_code != 200:
            raise Exception(f"API failed with status {response.status_code}")

        data = response.json()

        # 5. Extract useful fields — return dict directly (no double-encoding)
        location_data = {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("regionName"),
            "country": data.get("countryName")
        }

        return location_data

    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}

    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

    except Exception as e:
        return {"error": str(e)}