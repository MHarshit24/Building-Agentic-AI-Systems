# stateful_trip_agent.py
import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
# -------------------------------
# Environment Setup
# -------------------------------
BASE_DIR = Path(__file__).resolve().parents[4]

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

# -------------------------------
# Initialize FastAPI App
# -------------------------------
app = FastAPI(title="Stateful Travel & Trip Planner Agent")



# Task1 : Enable CORS for secure frontend-backend communication on localhost.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite frontend
        "http://localhost:3000"   # Alternative React port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# LLM Setup
# -------------------------------
llm = ChatOpenAI(
    model=model_name, 
    api_key=api_key, 
    base_url=base_url, 
    streaming=True)

# -------------------------------
# Prompt Template with Memory
# -------------------------------
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful travel assistant. Remember the user's trip details, activities, and preferences during this session."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])

# -------------------------------
# Session Memory Store
# -------------------------------
store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# -------------------------------
# Core LCEL Chain
# -------------------------------
core_chain = prompt | llm | StrOutputParser()

# -------------------------------
# Wrap with Session-Based Memory
# -------------------------------
stateful_chain = RunnableWithMessageHistory(
    runnable=core_chain,
    get_session_history=get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

# -------------------------------
# FastAPI Endpoint
# -------------------------------

class ChatInput(BaseModel):
    input: str
    session_id: str

@app.get("/new-session")
def new_session():
    """Generate a new chat session ID."""
    return {"session_id": str(uuid.uuid4())}

@app.post("/chat")
async def chat(payload: ChatInput):
    """
    Stateful chat endpoint that remembers context per session.
    Streams the model's response token by token.
    """
    config = {"configurable": {"session_id": payload.session_id}}

    async def event_generator():
        try:
            # Use .astream() for non-blocking streaming in an async context
            async for chunk in stateful_chain.astream({"input": payload.input}, config=config):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            # Log the full error for debugging
            print(f"Error during stream: {e}")
            yield f"data: Error: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# -------------------------------
# Run App
# -------------------------------
if __name__ == "__main__":
    
    uvicorn.run("stateful_trip_agent:app", host="0.0.0.0", port=8000)
