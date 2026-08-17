"""
Sprint 2: Building the Core of the Travel Suggestion Agent (FastAPI Edition)
--------------------------------------------------------------
Implements:
1. Baseline itinerary generator (synchronous)
2. Factual & Creative modes with user input
3. Asynchronous travel suggestion with user input

Uses:
- langchain_openai for LLM access
- FastAPI for interactive endpoints
"""

# Import essential libraries, load environment variables, and set up FastAPI with LangChain support

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import os
from langchain_openai import ChatOpenAI

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

# -----------------------------------------------------
# Load API credentials from the .env file and set up the FastAPI app with a project title

gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("GEMINI_OPENAI_ENDPOINT")
if not base_url:
    raise ValueError("GEMINI base url not found in environment variables")

gemini_model = os.getenv("GEMINI_MODEL_NAME") or os.getenv("GEMINI_MODEL")
if not gemini_model:    
    raise ValueError("GEMINI_MODEL not found in environment variables")


#Set up the Gemini LLM with API key, model name, and tuning parameters like retries and temperature

llm = ChatOpenAI(
    model=gemini_model,
    api_key=gemini_api_key,
    base_url=base_url,
    temperature=0.3,
    max_retries=2
)

# -----------------------------------------------------
# Task 1: Baseline Itinerary Generator
# -----------------------------------------------------
#Create Pydantic models to capture user inputs (destination, theme, days) and return the AI-generated response

class TripRequest(BaseModel):
    destination: str
    theme: str
    days: int

#Implement a FastAPI POST route that constructs a prompt from the request, calls the LLM, and wraps the output 
# in a Pydantic response model, handling errors gracefully
    
@app.post("/task1")
def task1(request: TripRequest):
    try:
        prompt = f"Suggest a {request.days}-day itinerary for a trip to {request.destination} focusing on {request.theme}."

        result = llm.invoke(prompt)

        return {
            "itinerary": result.content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------
# Task 2: Factual & Creative Modes
# -----------------------------------------------------


# Initialize a factual-focused Gemini model using LangChain with low temperature and token limit for precise responses.

factual_llm = ChatOpenAI(
    model=gemini_model,
    api_key=gemini_api_key,
    base_url=base_url,
    temperature=0.2,
    max_tokens=150
)

#Initialize a creative-focused Gemini model using LangChain with high temperature and larger token limit for more imaginative responses

creative_llm = ChatOpenAI(
    model=gemini_model,
    api_key=gemini_api_key,
    base_url=base_url,
    temperature=0.9,
    max_tokens=300
)

#Create Pydantic models for a prompt-based endpoint, returning factual and creative responses in JSON.

class PromptRequest(BaseModel):
    prompt: str

#Implement a FastAPI POST route that constructs prompts from the request, invokes factual_llm and creative_llm, and returns a structured JSON response, handling errors gracefully

@app.post("/task2")
def task2(request: PromptRequest):
    try:
        factual_result = factual_llm.invoke(request.prompt)
        creative_result = creative_llm.invoke(request.prompt)

        return {
            "factual": factual_result.content,
            "creative": creative_result.content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------
# Task 3: Asynchronous Suggestion
# -----------------------------------------------------

#Implement an async helper function that invokes the LLM with ainvoke and returns the response content, 
# ensuring exceptions are caught
    
async def generate_async_suggestion(prompt: str):
    try:
        result = await llm.ainvoke(prompt)
        return result.content
    except Exception as e:
        return str(e)
    
    
#Design data models to validate input for asynchronous LLM calls and structure the corresponding response

class AsyncSuggestionRequest(BaseModel):
    question: str

class AsyncSuggestionResponse(BaseModel):
    response: str


#Implement a FastAPI POST route that constructs a prompt, invokes the async LLM function with asyncio.run, 
# and wraps the output in a Pydantic response model with error handling.

@app.post("/task3", response_model=AsyncSuggestionResponse)
async def task3(request: AsyncSuggestionRequest):
    try:
        prompt = request.question
        result = await generate_async_suggestion(prompt)

        return AsyncSuggestionResponse(response=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------
# Local Script Execution
# -----------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)