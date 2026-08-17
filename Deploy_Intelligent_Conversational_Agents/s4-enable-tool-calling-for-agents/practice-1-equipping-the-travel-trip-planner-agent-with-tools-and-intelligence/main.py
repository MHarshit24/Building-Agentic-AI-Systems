import json
from fastapi import FastAPI, HTTPException
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from travel_tools import get_destination_info, get_user_location
import os
import uvicorn
# -------------------------------
# Environment Setup
# -------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()
GEMINI_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://api.openai.com/v1")
GEMINI_MODEL_NAME = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

app = FastAPI(title="Travel & Trip Planner Bot", version="4.0")

@app.on_event("startup")
async def validate_config():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set — set OPENROUTER_API_KEY in your .env file")

# -------------------------------
# Initialize LLM (Gemini)
# -------------------------------
model = ChatOpenAI(
    base_url=GEMINI_BASE_URL,
    model=GEMINI_MODEL_NAME,
    api_key=GEMINI_API_KEY,
    temperature=0.3,
    default_headers={
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Travel-Agent-App"
    }
)


# -------------------------------
# Step 2: Setup with Tools
# -------------------------------

tools = [get_destination_info, get_user_location]

# -------------------------------
# Step 3: Create Agent
# -------------------------------

prompt = """
You are a helpful travel and trip planning assistant.

Behavior rules:

1. If the user asks about places near them or in their area:
   - FIRST call get_user_location
   - THEN call get_destination_info using the detected city
   - DO NOT ask follow-up questions

2. If the user asks about a specific destination (e.g., "Tell me about Paris"):
   - Call get_destination_info with the destination name
   - Return the travel details directly

3. If the user asks about their current location (e.g., "Where am I?"):
   - Call get_user_location
   - Return the location details directly

Always choose the correct tool automatically based on the query.
Do not ask unnecessary follow-up questions.
"""

# Create an Agent using create_agent with the prompt and tools
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=prompt
)

# -------------------------------
# ROUTES
# -------------------------------
# Task -1 Test internal tool
# Create an endpoint (`/tools/internal`) and call the get_destination_info tool.
#Implement a FastAPI route that calls the internal LangChain tool get_destination_info, parses its output,
# and handles exceptions with HTTP errors.

@app.post("/tools/internal")
async def test_internal_tool(destination: str):
    try:
        result = get_destination_info.invoke(destination)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Task -2 External Tool Test
# Create an endpoint (`/tools/external`) and call the get_user_location tool.
#Implement a FastAPI route that calls the get_user_location LangChain tool, parses the JSON response, 
#and handles any exceptions with HTTP errors

@app.post("/tools/external")
async def test_external_tool():
    try:
        result = get_user_location.invoke("")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Task-3 Intelligent Agent Endpoint
# Create an endpoint (`/ask`) which will accept input from user and invoke the agent.

@app.post("/ask")
async def ask_agent(query: str):
    try:
        response = agent.invoke({
            "messages": [
                {"role": "user", "content": query}
            ]
        })

        if isinstance(response, dict) and "messages" in response:
            messages = response["messages"]

            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    output = msg.content
                    break
            else:
                output = "No response generated."

        elif hasattr(response, "content"):
            output = response.content

        else:
            output = str(response)

        return {
            "response": output
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Run Server
# -------------------------------
if __name__ == "__main__":
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)