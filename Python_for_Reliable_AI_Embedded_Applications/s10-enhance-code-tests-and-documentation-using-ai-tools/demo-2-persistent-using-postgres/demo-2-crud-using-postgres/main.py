"""
Simple FastAPI App with Rate Limiting

This example shows how to add rate limiting to protect your API.
Rate limiting controls how many requests a user can make in a time period.

Key Concepts:
1. Rate limiting prevents API abuse
2. Different endpoints can have different limits
3. Limits are tracked per IP address
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from openai import OpenAI, RateLimitError
import os
from dotenv import load_dotenv
from db.db_operations import insert_query

# Import rate limiting tools
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables from .env file
load_dotenv()

# Get API credentials
api_key = os.getenv("GEMINI_API_KEY")
base_url = os.getenv("GEMINI_BASE_URL")
model = os.getenv("GEMINI_MODEL")

# Create OpenAI client
client = OpenAI(api_key=api_key, base_url=base_url)

# ============================================
# STEP 1: Setup Rate Limiter
# ============================================
# This tracks how many requests each IP address makes
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(title="Simple Rate-Limited API")

# Add rate limiter to the app
app.state.limiter = limiter

# ============================================
# STEP 2: Define Data Models
# ============================================

class QuestionRequest(BaseModel):
    """What the user sends to us"""
    prompt: str

class AnswerResponse(BaseModel):
    """What we send back to the user"""
    answer: str

# ============================================
# STEP 3: Create API Endpoints
# ============================================
@app.post("/ask", response_model=AnswerResponse)
@limiter.limit("2/minute")  # Allow only 1 requests per minute
def ask_ai(request: Request, question: QuestionRequest):
    """
    Ask a question to the AI
    
    Rate Limit: 10 requests per minute per user
    This protects against abuse and controls API costs
    """

    try:
        # Call the AI model
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question.prompt}]
        )
        
        # Get the AI's answer
        answer = response.choices[0].message.content
        # Persist the user query and LLM response (best-effort; don't break request on DB failure)
        try:
            insert_query(question.prompt, answer)
        except Exception:
            # Intentionally swallow DB errors to avoid impacting the API response
            pass
        
        # Return the answer
        return AnswerResponse(answer=answer)
    
    except RateLimitError as e:
        # Handle rate limit errors from the API provider
        raise HTTPException(
            status_code=429, 
            detail={
                "error": "API rate limit exceeded",
                "message": "The AI provider's rate limit has been reached. Please wait a moment and try again.",
                "type": "api_rate_limit_error"
            }
        )


@app.post("/ask/stream")
@limiter.limit("2/minute")  # Same rate limit as non-streaming endpoint
def ask_ai_stream(request: Request, question: QuestionRequest):
    """
    Ask a question to the AI with streaming response
    
    Rate Limit: 2 requests per minute per user
    Returns a stream of text chunks as the AI generates the response
    """
    
    def generate_stream():
        """Generator function that yields text chunks from the LLM"""
        try:
            # Call the AI model with streaming enabled
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": question.prompt}],
                stream=True
            )
            
            # Yield each chunk as it arrives
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except RateLimitError as e:
            # Handle rate limit errors from the API provider
            error_message = "API rate limit exceeded. Please wait and try again."
            yield f"ERROR: {error_message}"
    
    # Return streaming response
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain"
    )


# How Rate Limiting Works:
# ============================================
# 
# 1. First 10 requests -> Success (200 OK)
# 2. Request 11+ -> Rate limited (429 Error)
# 3. After 60 seconds -> Limit resets, can make 10 more requests
#
# Rate limits are tracked per IP address
# Each user's limits are independent
# ============================================


