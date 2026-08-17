import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableBranch

# Load environment
BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()
    
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set. Please configure it in your .env file.")

# Initialize LLM
llm = ChatOpenAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    api_key=api_key,
    base_url=os.getenv("GEMINI_OPENAI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai/")
)

# -------------------------------
# Step 1: Intent Classification
# -------------------------------

intent_prompt = ChatPromptTemplate.from_messages([
    ("system", "Classify this travel-related query as one of the following:\n"
               "- BOOKING: user wants to book/reserve a trip, hotel, or flight.\n"
               "- CANCELLATION: user wants to cancel or change an existing booking.\n"
               "- GENERAL: user is asking about travel info or suggestions.\n"
               "Respond with only one word: BOOKING, CANCELLATION, or GENERAL."),
    ("user", "{query}")
])

intent_chain = intent_prompt | llm | StrOutputParser()

# -------------------------------
# Step 2: Condition Functions
# -------------------------------
def is_booking(x):
    return "BOOKING" in x["intent"]

def is_cancellation(x):
    return "CANCELLATION" in x["intent"]

# -------------------------------
# Step 3: Branch Chains
# -------------------------------
booking_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a travel assistant helping users book trips."),
    ("user", "{query}")
])

booking_chain = booking_prompt | llm | StrOutputParser()

cancellation_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a travel assistant handling cancellations and refunds."),
    ("user", "{query}")
])

cancellation_chain = cancellation_prompt | llm | StrOutputParser()

general_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful travel assistant providing general travel advice."),
    ("user", "{query}")
])

general_chain = general_prompt | llm | StrOutputParser()

# -------------------------------
# Step 4: Router
# -------------------------------
router = RunnableBranch(
    (is_booking, booking_chain),
    (is_cancellation, cancellation_chain),
    general_chain
)

# -------------------------------
# Step 5: Orchestration
# -------------------------------
full_chain = (
    {
        "intent": intent_chain,
        "query": lambda x: x["query"]
    }
    | router
)

# -------------------------------
# Step 6: FastAPI Setup
# -------------------------------
app = FastAPI(title="Travel Router - LCEL")

class QueryInput(BaseModel):
    query: str

@app.post("/route_query")
def route_query(input: QueryInput):
    result = full_chain.invoke({"query": input.query})
    return {
        "query": input.query,
        "response": result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("travel_router:app", host="0.0.0.0", port=8000)