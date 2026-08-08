"""Parola hash'leme (bcrypt) ve JWT access/refresh token uretimi/dogrulamasi."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _encode(payload: dict, ttl: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    data = {
        **payload,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, tenant_id: int, role: str) -> str:
    return _encode(
        {"sub": str(user_id), "tenant_id": tenant_id, "role": role},
        timedelta(minutes=settings.access_token_ttl_min),
        "access",
    )


def create_refresh_token(user_id: int, tenant_id: int) -> str:
    return _encode(
        {"sub": str(user_id), "tenant_id": tenant_id},
        timedelta(days=settings.refresh_token_ttl_days),
        "refresh",
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Token'i dogrula; gecersiz/expire ise jwt.PyJWTError firlatir."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Beklenen token turu {expected_type}, gelen {payload.get('type')}")
    return payload
