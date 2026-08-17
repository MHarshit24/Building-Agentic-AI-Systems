import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7  # not specified explicitly in §16 — 7 days chosen as a reasonable default; confirm or adjust

def create_access_token(data: dict[str, Any]) -> str:
    """Create a new JWT access token valid for 30 minutes."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    })
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a new JWT refresh token valid for REFRESH_TOKEN_EXPIRE_DAYS days."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    })
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT access token and return its payload."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token's jti is in the Redis blacklist. Fails gracefully if Redis is unreachable."""
    settings = get_settings()
    if not settings.redis_url:
        return False
        
    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        async with redis_client:
            is_blacklisted = await redis_client.exists(f"blacklist:{jti}")
            return bool(is_blacklisted)
    except Exception as e:
        logger.warning("Redis is unreachable, skipping JWT blacklist check: %s", e)
        return False

async def blacklist_token(jti: str, expires_at: datetime) -> None:
    """
    Add a token's jti to the Redis blacklist until its natural expiry (§16 —
    logout can't delete a stateless JWT, so this makes it unusable until it
    would have expired anyway, then Redis auto-expires the blacklist entry
    itself, needing no cleanup job).
    """
    settings = get_settings()
    if not settings.redis_url:
        logger.warning(
            "Redis not configured — cannot blacklist jti=%s; it remains valid until natural expiry.",
            jti,
        )
        return

    ttl_seconds = max(int((expires_at - datetime.now(timezone.utc)).total_seconds()), 1)
    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        async with redis_client:
            await redis_client.setex(f"blacklist:{jti}", ttl_seconds, "1")
    except Exception as e:
        logger.warning("Redis is unreachable, could not blacklist jti=%s: %s", jti, e)