from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

security = HTTPBearer(auto_error=False)

# JWKS client with 1-hour cache — avoids per-request calls to Supabase
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL is not configured")
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


@dataclass
class UserContext:
    id: str  # Supabase auth.users UUID
    email: str
    email_verified: bool
    display_name: Optional[str] = None


def _decode_supabase_jwt(token: str) -> dict:
    """Decode and verify a Supabase JWT using JWKS (RS256)."""
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience="authenticated",
        issuer=f"{settings.supabase_url}/auth/v1",
    )


async def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """FastAPI dependency: require a valid Supabase user JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        payload = _decode_supabase_jwt(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except (jwt.PyJWTError, Exception) as exc:
        logger.debug("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user_meta = payload.get("user_metadata", {})
    return UserContext(
        id=payload["sub"],
        email=payload.get("email", user_meta.get("email", "")),
        email_verified=payload.get("email_confirmed_at") is not None,
        display_name=user_meta.get("display_name") or user_meta.get("full_name") or user_meta.get("name"),
    )


async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[UserContext]:
    """FastAPI dependency: return UserContext if valid token present, else None."""
    if credentials is None:
        return None

    try:
        payload = _decode_supabase_jwt(credentials.credentials)
    except Exception:
        return None

    user_meta = payload.get("user_metadata", {})
    return UserContext(
        id=payload["sub"],
        email=payload.get("email", user_meta.get("email", "")),
        email_verified=payload.get("email_confirmed_at") is not None,
        display_name=user_meta.get("display_name") or user_meta.get("full_name") or user_meta.get("name"),
    )


__all__ = ["UserContext", "require_user", "optional_user"]
