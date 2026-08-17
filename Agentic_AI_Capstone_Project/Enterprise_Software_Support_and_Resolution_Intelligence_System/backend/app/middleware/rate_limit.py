from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.auth.jwt_handler import verify_access_token

settings = get_settings()

def get_user_id_or_ip(request: Request) -> str:
    """
    Returns the user_id from the JWT if present, otherwise the IP address.
    This ensures authenticated endpoints rate-limit per user, not per IP.
    """
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        payload = verify_access_token(token)
        if payload and "user_id" in payload:
            return f"user:{payload['user_id']}"
            
    return get_remote_address(request)

# Configure the limiter
if settings.redis_url:
    limiter = Limiter(key_func=get_user_id_or_ip, storage_uri=settings.redis_url, swallow_errors=True)
else:
    # In-memory fallback if Redis is not available
    limiter = Limiter(key_func=get_user_id_or_ip, swallow_errors=True)

# The limiter instance is used via @limiter.limit(...) in the routers.
# Per Blueprint §16.1:
# - /auth/login: "5/15minute" keyed by source IP (can just use get_remote_address)
# - /chat: "20/minute" keyed by user_id
# - /ingest: "5/minute" keyed by user_id
# - /conversations, /metrics, /health: "60/minute"
