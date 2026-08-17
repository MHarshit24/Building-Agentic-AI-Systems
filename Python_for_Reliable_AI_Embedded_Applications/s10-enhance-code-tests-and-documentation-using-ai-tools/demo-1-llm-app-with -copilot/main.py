"""
Demo 1: LLM App with GitHub Copilot

This project demonstrates a **production-ready FastAPI application** with **LLM integration**, **rate limiting**, and **streaming responses**.
It showcases how to use **GitHub Copilot** to enhance code quality and development speed.
"""


from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI, RateLimitError
import os
from dotenv import load_dotenv


from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models import QueryRequest, AnswerResponse


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
base_url = os.getenv("GEMINI_BASE_URL")
model = os.getenv("GEMINI_MODEL_NAME")


client = OpenAI(api_key=api_key, base_url=base_url)


limiter = Limiter(key_func=get_remote_address)


app = FastAPI(title="Simple Rate-Limited API")


app.state.limiter = limiter


@app.post("/ask", response_model=AnswerResponse)
@limiter.limit("2/minute")  
def ask_ai(request: Request, question: QueryRequest):

    try:
       
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question.prompt}]
        )
        
       
        answer = response.choices[0].message.content
        
        
        return AnswerResponse(answer=answer)
    
    except RateLimitError as e:
       
        raise HTTPException(
            status_code=429, 
            detail={
                "error": "API rate limit exceeded",
                "message": "The AI provider's rate limit has been reached. Please wait a moment and try again.",
                "type": "api_rate_limit_error"
            }
        )


@app.post("/ask/stream")
@limiter.limit("2/minute")  
def ask_ai_stream(request: Request, question: QueryRequest):
    def generate_stream():
        """Generator function that yields text chunks from the LLM"""
        try:
            
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": question.prompt}],
                stream=True
            )
            
           
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except RateLimitError as e:
           
            error_message = "API rate limit exceeded. Please wait and try again."
            yield f"ERROR: {error_message}"
    
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain"
    )
