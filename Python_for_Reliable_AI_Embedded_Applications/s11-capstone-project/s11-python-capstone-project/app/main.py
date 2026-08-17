from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from app.utils.database import get_postgres_connection#, init_db

from app.routes import mentor_routes

#init_db()

get_postgres_connection()

def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Code Mentor API",
    description="AI Pair Programmer Backend",
    version="1.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(mentor_routes.router)

@app.get("/")
def root():
    """
    Health check endpoint.

    Returns:
        dict: API status message
    """
    return {"message": "Code Mentor API is running"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Something went wrong, Please Verify the Code"
        }
    )