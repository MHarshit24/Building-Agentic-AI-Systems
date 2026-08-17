# trip_memory_prompt.py
import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, Query
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# -------------------------------
# Environment Setup
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
if not model_name:
    raise ValueError("GEMINI_MODEL is not set. Please configure it in your .env file.")
if not base_url:
    raise ValueError("GEMINI_OPENAI_ENDPOINT is not set. Please configure it in your .env file.")

# -------------------------------
# Initialize FastAPI App
# -------------------------------
app = FastAPI(title="Memory-Aware Prompt Demo")

# -------------------------------
# Initialize LLM
# -------------------------------
llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)

# -------------------------------
# Memory-Aware Prompt Template
# -------------------------------
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful travel assistant. You remember the user's travel plans during the conversation."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])

#-------------------------------
# Sample Chat History 
#------------------------------
# Create a sample chat_history list containing alternating human and AI messages to simulate a 
# conversation, which can be used to test prompts or memory integration.
chat_history = [
    HumanMessage(content="I want to plan a trip to Goa."),
    AIMessage(content="Great choice! When are you planning to travel?"),
    HumanMessage(content="Next month for 5 days."),
    AIMessage(content="Nice! Do you prefer beaches, nightlife, or sightseeing?")
]

# -------------------------------
# Endpoint
# -------------------------------
#Create a FastAPI /trip_chat endpoint that demonstrates memory-aware prompts by appending user input to a manual chat_history, formatting the prompt with MessagesPlaceholder, 
# invoking the LLM, and returning the user input and agent’s response.

@app.get("/trip_chat")
def trip_chat(user_input: str = Query(...)):
    # Append new user message to history
    chat_history.append(HumanMessage(content=user_input))

    # Format prompt with history
    formatted_prompt = prompt.invoke({
        "chat_history": chat_history,
        "input": user_input
    })

    # Call LLM
    response = llm.invoke(formatted_prompt)

    # Append AI response to history
    chat_history.append(AIMessage(content=response.content))

    return {
        "user_input": user_input,
        "response": response.content
    }

# -------------------------------
# Run App
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("trip_memory_prompt:app", host="0.0.0.0", port=8000)