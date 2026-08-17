import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

# -------------------------------
# Environment setup
# -------------------------------

BASE_DIR = Path(__file__).resolve().parents[3]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
base_url = os.getenv("GEMINI_OPENAI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai/")

if not api_key:
    raise ValueError("GEMINI_API_KEY is not set. Please configure it in your .env file.")

# Initialize LLM
llm = ChatOpenAI(
    model=model_name,
    api_key=api_key,
    base_url=base_url
)

# -------------------------------
# Step 1: Sentiment Classification Prompt
# -------------------------------

sentiment_prompt = ChatPromptTemplate.from_messages([
    ("system", "Classify the sentiment of the following feedback as POSITIVE, NEGATIVE, or NEUTRAL. Respond with only one word."),
    ("user", "{feedback}")
])

sentiment_chain = sentiment_prompt | llm | StrOutputParser()

# -------------------------------
# Step 2: Urgency Classification Function
# -------------------------------

def map_urgency(sentiment: str):
    sentiment = sentiment.strip().upper()

    if "NEGATIVE" in sentiment:
        urgency = "HIGH"
    elif "NEUTRAL" in sentiment:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    return {
        "sentiment": sentiment,
        "urgency": urgency
    }   

urgency_chain = RunnableLambda(map_urgency)

# -------------------------------
# Step 3: Response Strategy Prompt
# -------------------------------

strategy_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a professional customer support agent for a travel company. "
               "Based on the sentiment and urgency, generate a suitable response strategy."),
    ("user", "Sentiment: {sentiment}\nUrgency: {urgency}")
])

strategy_chain = strategy_prompt | llm | StrOutputParser()

# -------------------------------
# Step 4: Full LCEL Chain
# -------------------------------

full_chain = (
    sentiment_chain
    | urgency_chain
    | {
        "sentiment": lambda x: x["sentiment"],
        "urgency": lambda x: x["urgency"],
        "strategy": strategy_chain
    }
)

# -------------------------------
# Step 5: FastAPI Setup
# -------------------------------

app = FastAPI(title="Travel Feedback Analyzer - LCEL")

class FeedbackInput(BaseModel):
    feedback: str

@app.post("/analyze_feedback")
def analyze_feedback(input: FeedbackInput):
    result = full_chain.invoke({"feedback": input.feedback})
    return {
        "feedback": input.feedback,
        "sentiment": result["sentiment"],
        "urgency": result["urgency"],
        "strategy": result["strategy"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("feedback_chain:app", host="0.0.0.0", port=8000)
