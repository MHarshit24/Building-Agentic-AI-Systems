import os
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from router import assess_complexity


def _load_env():
    # Load from root .env at Building_Agentic_AI_Systems/ (parents[4] from this file's location)
    BASE_DIR = Path(__file__).resolve().parents[4]
    base_env_path = BASE_DIR / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()


_load_env()

# ---------- Configuration & Clients ----------
# LiteLLM already handles the model routing via config
LITELLM_GATEWAY_URL = "http://localhost:4000/v1"

# TODO: Initialize the OpenAI client pointing to the LiteLLM Gateway
# api_key is set to a placeholder string because LiteLLM does not require a real key for local routing
client = OpenAI(
    base_url=LITELLM_GATEWAY_URL,
    api_key=os.getenv("OPENAI_API_KEY", "not-needed"),
)

app = FastAPI(title="Support Gateway Router")

# ---------- Schema ----------
# TODO: Define the Pydantic model for the incoming request (TicketRequest)
# It should ONLY take a 'description' field.
class TicketRequest(BaseModel):
    description: str

# ---------- Core Logic ----------

@app.post("/resolve")
async def resolve_ticket(ticket: TicketRequest):
    """
    TASK 2: Implement the Gateway Router Logic.
    
    Steps:
    1. Call the 'assess_complexity' function from router.py.
    2. Determine which model tier to use:
       - complexity == "complex" -> "complex-agent"
       - complexity == "simple"  -> "simple-agent"
    3. Call the LiteLLM Gateway via the OpenAI client.
    4. Return the resolution and the routing metadata.
    """
    
    # TODO: Step 1 & 2 - Heuristic Assessment & Model Selection
    complexity = assess_complexity(ticket.description)
    model_tier = "complex-agent" if complexity == "complex" else "simple-agent"

    try:
        # TODO: Step 3 - Call GateWay (LiteLLM)
        # Use a system message: "You are a professional customer support assistant. Provide helpful and concise resolutions."
        response = client.chat.completions.create(
            model=model_tier,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional customer support assistant. Provide helpful and concise resolutions.",
                },
                {
                    "role": "user",
                    "content": ticket.description,
                },
            ],
        )

        resolution = response.choices[0].message.content

        # TODO: Step 4 - Return the response
        return {
            "complexity_assessment": complexity,
            "routed_model_tier": model_tier,
            "resolution": resolution,
        }
            
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gateway Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)