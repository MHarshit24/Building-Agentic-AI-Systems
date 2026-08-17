# stateful_trip_agent.py
import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import BaseModel
import uuid

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
app = FastAPI(title="Stateful Travel & Trip Planner Agent")

# -------------------------------
# LLM Setup
# -------------------------------
llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)

# -------------------------------
# Prompt Template with Memory
# -------------------------------
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful travel assistant. You remember the user's travel plans during the conversation."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])

# -------------------------------
# Session Memory Store
# -------------------------------
store = {}

#Create a function get_session_history that returns a unique ChatMessageHistory for each session,
# initializing it if it doesn’t already exist, to enable session-specific short-term memory in the agent.
def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# -------------------------------
# Core LCEL Chain
# -------------------------------
core_chain = prompt | llm

# -------------------------------
# Wrap with Session-Based Memory
# -------------------------------
# Wrap the core_chain with RunnableWithMessageHistory to make it stateful, 
# enabling the agent to track and recall conversation history per session using the get_session_history function.
stateful_chain = RunnableWithMessageHistory(
    core_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

# -------------------------------
# FastAPI Endpoint
# -------------------------------

class ChatInput(BaseModel):
    input: str
    session_id: str

#Create a FastAPI endpoint /new-session that generates and returns a unique session ID for each new chat,
# enabling session-based memory tracking.
@app.get("/new-session")
def new_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}

# Create a FastAPI /chat endpoint that accepts user input and session ID, invokes the stateful_chain to maintain conversation context, 
# and returns the session ID, user input, and agent’s response.
@app.post("/chat")
def chat(chat_input: ChatInput):
    response = stateful_chain.invoke(
        {"input": chat_input.input},
        config={"configurable": {"session_id": chat_input.session_id}}
    )

    return {
        "session_id": chat_input.session_id,
        "input": chat_input.input,
        "response": response.content
    }

# -------------------------------
# Run App
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("stateful_trip_agent:app", host="0.0.0.0", port=8000)