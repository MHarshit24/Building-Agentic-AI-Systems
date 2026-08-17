from typing import Any, Callable
from fastapi import Depends, HTTPException, status

from app.middleware.jwt_auth import get_current_user

def require_role(allowed_roles: list[str]) -> Callable:
    """Dependency factory that enforces RBAC checking against the user payload."""
    def role_checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return role_checker

# Gating for /chat, /metrics, /conversations
require_support_or_admin = require_role(["support_agent", "admin"])

# Gating for /ingest*
require_admin = require_role(["admin"])
