"""
Sprint 3 Solution — Travel & Trip Planner Agent
LangChain + FastAPI + ChatOpenAI (via langchain_openai)

Implements:
  • Task 1: Fetch Prompt from Langfuse
  • Task 2: Few-Shot Prompting with ChatPromptTemplate.from_messages()
  • Task 3: Structured Output with PydanticOutputParser
"""

import os
from typing import List
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError


# LangChain imports

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langfuse import Langfuse

# -------------------------------------------------------------------
# Load environment
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_OPENAI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
if not GEMINI_API_KEY:
    raise RuntimeError("Please set GEMINI_API_KEY in your .env file.")
if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
    raise RuntimeError("Please set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in your .env file.")

# -------------------------------------------------------------------
# Initialize FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title="Travel Planner Advanced - Sprint 3")
#-------------------------------------------------------------------
# Initialize the Langfuse client using environment variables for public key, secret key, and host URL
#-------------------------------------------------------------------

langfuse = Langfuse(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    host=LANGFUSE_HOST
)

# -------------------------------------------------------------------
# Helper: initialize LLM client
# -------------------------------------------------------------------

llm= ChatOpenAI(
        model=GEMINI_MODEL_NAME,
        api_key=GEMINI_API_KEY,
        base_url=GEMINI_BASE_URL,
        temperature=0.3,
        max_retries=2,
    )

# -------------------------------------------------------------------
# Task 1 — Fetch Prompt from Langfuse
# -------------------------------------------------------------------
#Define a Pydantic model to capture itinerary request details: destination, number of days, and budget

class ItineraryRequest(BaseModel):
    destination: str
    days: int
    budget: int

#Implement an async FastAPI route that retrieves a production prompt from Langfuse, replaces placeholders with user 
# data, invokes the LLM, and returns the response, handling errors if the prompt is missing

@app.post("/task1")
async def task1(data: ItineraryRequest):
    try:
        prompt = langfuse.get_prompt(
            "niit_agentic_ai_travel_itinerary_generator_v1",
            label="production"
        )

        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        compiled_prompt = prompt.compile(
            destination=data.destination,
            days=data.days,
            budget=data.budget
        )

        llm_task1 = ChatOpenAI(
            model=GEMINI_MODEL_NAME,
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
            temperature=0.7,
            max_retries=2,
        )

        response = llm_task1.invoke(compiled_prompt)

        return {"itinerary": response.content}

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

# -------------------------------------------------------------------
# Task 2 — Few-Shot Prompting with ChatPromptTemplate.from_messages()
# -------------------------------------------------------------------

#Define a Pydantic model UserQuery to capture the user’s input query for processing

class UserQuery(BaseModel):
    query: str

# Create a POST endpoint /task2 that uses few-shot prompting with ChatPromptTemplate to generate a day-by-day travel itinerary 
# from a user query

@app.post("/task2")
async def task2(user: UserQuery):
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a smart travel planner."),
            ("human", "Plan a 3-day trip to Goa with budget 10000"),
            ("ai", "Day 1: Beaches...\nDay 2: Forts...\nDay 3: Shopping..."),
            ("human", "Plan a 5-day romantic trip to Paris with budget 2000 euros"),
            ("ai", "Day 1: Eiffel Tower...\nDay 2: Louvre...\nDay 3: Seine Cruise..."),
            ("human", "{query}")
        ])

        chain = prompt | llm
        response = chain.invoke({"query": user.query})

        return {"result": response.content}

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

# -------------------------------------------------------------------
# Task 3 — Structured Output Parsing (PydanticOutputParser)
# -------------------------------------------------------------------
# Define Pydantic schema for validated output

class TripPlan(BaseModel):
    destination: str = Field( 
        min_length=1,
        description="Travel destination")
    days: int = Field( 
        ge=1,
        le=30,
        description="Number of days for the trip")
    estimated_cost: str = Field( 
        min_length=1,
        description="Estimated total cost for the trip")
    highlights: List[str] = Field( 
        min_items=1,
        max_items=10,
        description="Top highlights of the destination")

class TripPlanRequest(BaseModel):
    destination: str 
    days: int 
    budget: int 

#Implement an async FastAPI route that formats a prompt with ChatPromptTemplate, invokes the LLM, 
# parses the response with PydanticOutputParser, and handles validation or general errors gracefully.

@app.post("/task3")
async def task3(data: TripPlanRequest):
    try:
        parser = PydanticOutputParser(pydantic_object=TripPlan)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a travel planner. Return ONLY valid JSON. Do not include explanations or markdown."),
            ("human", "Plan a trip to {destination} for {days} days with budget {budget}.\n{format_instructions}")
        ])

        formatted_prompt = prompt.format_messages(
            destination=data.destination,
            days=data.days,
            budget=data.budget,
            format_instructions=parser.get_format_instructions()
        )

        response = llm.invoke(formatted_prompt)

        parsed = parser.parse(response.content)

        return parsed.model_dump()

    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")    

# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
