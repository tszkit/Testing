"""JWT-based token issuance and verification for OAuth2 account linking."""
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from core.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_authorization_code() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: str, client_id: str) -> tuple[str, datetime]:
    """Return (access_token, expires_at)."""
    expires_at = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "client_id": client_id,
        "exp": expires_at,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_refresh_token(user_id: str, client_id: str) -> tuple[str, datetime]:
    """Return (refresh_token, expires_at)."""
    expires_at = _now() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "client_id": client_id,
        "exp": expires_at,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None if invalid/expired."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> str | None:
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return payload.get("sub")
    return None
