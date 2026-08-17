from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, APIError
import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .db_operations import insert_query

from .schemas import ConceptRequest, ExplanationResponse


"""
AI Tutor API Module

A FastAPI application that provides AI-powered concept explanations using the Gemini API.
This module handles HTTP requests for explaining concepts in Agentic AI, with support for
both standard and streaming responses. It includes rate limiting to prevent abuse and CORS
configuration for cross-origin requests.

Environment Variables:
    GEMINI_API_KEY: API key for authentication with the Gemini API (required).
    GEMINI_BASE_URL: Base URL for the Gemini API endpoint (e.g., OpenAI-compatible endpoint).
    GEMINI_MODEL: The model identifier to use for AI completions (e.g., 'gpt-4').

Key Features:
    - Concept explanation endpoint with full response
    - Streaming endpoint for real-time explanation chunks
    - Rate limiting (2 requests per minute per IP)
    - CORS middleware for cross-origin requests
    - Comprehensive error handling and logging
    - SSE (Server-Sent Events) for streaming responses
"""

# Configure logging for the application
# Logs are formatted with timestamp, severity level, logger name, and message
# INFO level logs important events like request processing and API responses
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parents[4]

env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

# Retrieve Gemini API configuration from environment variables
api_key = os.getenv("GEMINI_API_KEY")
base_url = os.getenv("GEMINI_OPENAI_ENDPOINT")
model = os.getenv("GEMINI_MODEL")

# Validate that the required API key is present; fail fast if missing
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file!")

# Initialize the OpenAI client configured for the Gemini API
# Uses OpenAI SDK with a custom base_url pointing to the Gemini endpoint
CLOUD_CLIENT = OpenAI(api_key=api_key, base_url=base_url)
# Store the model identifier for use in API calls
CLOUD_MODEL = model

# Initialize rate limiter using the client's IP address as the key
# This ensures rate limits are applied per IP address, preventing API abuse
limiter = Limiter(key_func=get_remote_address, enabled=not os.getenv("TESTING"))

# Create FastAPI application instance with metadata for documentation
app = FastAPI(
    title="AI Tutor API",
    description="AI Tutor with Cloud Models",
    version="2.0.0"
)

# Attach the rate limiter to the app state for use across endpoints
app.state.limiter = limiter
# Add custom exception handler for rate limit exceeded errors (HTTP 429)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware to allow cross-origin requests from any origin
# This enables the API to be called from web browsers with different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow credentials (cookies, auth headers)
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"]  # Allow any custom headers
)


@app.post(
    "/explain",
    response_model=ExplanationResponse,
    tags=["Explanations"],
    summary="Get Factual Explanation",
    responses={
        200: {"description": "Successful explanation"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("2/minute")  # Rate limit: 2 requests per minute per IP address
def get_explanation(request: Request, concept_request: ConceptRequest):
    """
    Get a complete explanation for a given concept.
    
    This endpoint accepts a concept name and returns a fully-formed explanation
    from the Gemini AI model. The response is returned as a complete object,
    not streamed.
    
    Args:
        request (Request): FastAPI request object (required for rate limiting).
        concept_request (ConceptRequest): Request body containing the concept to explain.
    
    Returns:
        ExplanationResponse: Contains the concept, full explanation, and model used.
    
    Raises:
        HTTPException: 500 error if API call fails or internal error occurs.
    """
    try:
        # Log the incoming request for debugging and monitoring
        logger.info(f"Processing explanation request for concept: {concept_request.concept}")
        
        # Construct the message to send to the AI model
        # The prompt is tailored to provide beginner-friendly explanations in Agentic AI
        messages = [{
            "role": "user",
            "content": f"Explain {concept_request.concept} in Agentic AI clearly and concisely for a beginner."
        }]
        
        # Call the Gemini API (via OpenAI SDK) to generate the explanation
        # stream=False means we wait for the complete response before returning
        response = CLOUD_CLIENT.chat.completions.create(model=CLOUD_MODEL, messages=messages)
        
        # Extract the text content from the API response
        explanation = response.choices[0].message.content
        logger.info(f"Successfully generated explanation for concept: {concept_request.concept}")
        
        insert_query(
            concept_request.concept,
            explanation,
            CLOUD_MODEL
        )
        
        # Return a structured response containing the explanation
        return ExplanationResponse(
            concept=concept_request.concept,
            explanation=explanation,
            model=CLOUD_MODEL
        )
    except APIError as e:
        # Handle errors from the Gemini API (e.g., authentication, rate limits from API)
        logger.error(f"API Error while processing explanation request: {e}")
        raise HTTPException(status_code=500, detail={"error": "API Error", "message": str(e)})
    except Exception as e:
        # Handle any other unexpected errors during processing
        logger.error(f"Internal Error while processing explanation request: {e}")
        raise HTTPException(status_code=500, detail={"error": "Internal Error", "message": str(e)})

@app.post(
    "/explain/stream",
    tags=["Explanations"],
    summary="Get Streaming Explanation",
    responses={
        200: {"description": "Streaming explanation"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("2/minute")  # Rate limit: 2 requests per minute per IP address
def get_explanation_stream(request: Request, concept_request: ConceptRequest):
    """
    Get a streaming explanation for a given concept.
    
    This endpoint accepts a concept name and streams the explanation in real-time
    using Server-Sent Events (SSE). Useful for progressive rendering in clients.
    The stream includes metadata, content chunks, and a completion signal.
    
    Args:
        request (Request): FastAPI request object (required for rate limiting).
        concept_request (ConceptRequest): Request body containing the concept to explain.
    
    Returns:
        StreamingResponse: SSE stream with metadata, content chunks, and completion signal.
    """
    
    def format_sse(data: dict) -> str:
        """
        Format a dictionary into Server-Sent Events (SSE) format.
        
        SSE format requires lines to start with 'data: ' and end with double newlines.
        This allows browsers and clients to receive a stream of JSON events.
        
        Args:
            data (dict): Dictionary to be JSON-encoded and formatted as SSE.
        
        Returns:
            str: Formatted SSE message.
        """
        return f"data: {json.dumps(data)}\n\n"
    
    async def generate_stream():
        """
        Asynchronous generator that streams explanation chunks via SSE.
        
        This function calls the AI API with stream=True to receive tokens incrementally,
        then yields them in SSE format. It also yields metadata at the start and
        a completion signal at the end.
        
        Yields:
            str: Formatted SSE messages containing metadata, content, or errors.
        """
        try:
            # Log the start of streaming for monitoring
            logger.info(f"Streaming explanation for: {concept_request.concept}")
            
            # Call the Gemini API with stream=True to receive tokens incrementally
            # stream=True enables the API to return a generator of response chunks
            stream = CLOUD_CLIENT.chat.completions.create(
                model=CLOUD_MODEL,
                messages=[{
                    "role": "user",
                    "content": f"Explain {concept_request.concept} in Agentic AI clearly and concisely for a beginner."
                }],
                stream=True
            )
            
            # Send metadata first so clients know what concept is being explained
            # Metadata includes the concept name and the model being used
            yield format_sse({
                "type": "metadata",
                "concept": concept_request.concept,
                "model": CLOUD_MODEL
            })
            
            # Iterate through the stream and yield each content chunk as it arrives
            # Each chunk contains a partial response token
            for chunk in stream:
                # Extract the content from the delta (incremental change)
                content = chunk.choices[0].delta.content
                if content:  # Only yield if content exists (skip empty deltas)
                    yield format_sse({"type": "content", "content": content})
            
            # Send a completion signal to indicate the stream is finished
            yield format_sse({"type": "done"})
            logger.info(f"Completed streaming for: {concept_request.concept}")
            
        except Exception as e:
            # Handle any errors during streaming by sending an error message to the client
            # Differentiate between API errors and internal errors for debugging
            error_type = "API Error" if isinstance(e, APIError) else "Internal Error"
            logger.error(f"{error_type} in streaming: {e}")
            yield format_sse({
                "type": "error",
                "error": error_type,
                "message": str(e)
            })
    
    # Return a StreamingResponse with SSE configuration
    # SSE (Server-Sent Events) is an HTTP standard for pushing data to clients over a single connection
    return StreamingResponse(
        generate_stream(),  # The async generator that yields SSE messages
        media_type="text/event-stream",  # Required MIME type for Server-Sent Events
        headers={
            "Cache-Control": "no-cache",  # Prevent caching of streaming responses
            "Connection": "keep-alive",  # Keep the connection open for continuous streaming
            "X-Accel-Buffering": "no"  # Prevent proxy buffering (for nginx/reverse proxies)
        }
    )


@app.get("/", tags=["System"], summary="API Information")
def root():
    """
    Get API information and available endpoints.
    
    This is a simple health check endpoint that returns metadata about the API,
    including the name, version, description, and links to documentation.
    
    Returns:
        dict: API metadata and endpoint information.
    """
    return {
        "name": "AI Tutor API",
        "version": "2.0.0",
        "description": "Personalized Learning with Cloud AI Models",
        "documentation": {
            "interactive": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "explain": "/explain",
            "explain/stream": "/explain/stream"
        }
    }