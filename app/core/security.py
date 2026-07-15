import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.repositories import UserRepository
from app.db.session import get_db


bearer_scheme = HTTPBearer(auto_error=False)
AUTH_COOKIE_NAME = "rfc_rag_agent_access_token"


def password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    subject: str,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    active_settings = settings or get_settings()
    secret = jwt_secret(active_settings)
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=active_settings.jwt_access_token_expire_minutes)
    )
    header = {"alg": active_settings.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    signing_input = ".".join(
        [
            base64url_json(header),
            base64url_json(payload),
        ]
    )
    signature = sign_hs256(signing_input, secret)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    active_settings = settings or get_settings()
    secret = jwt_secret(active_settings)
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("invalid token format") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = sign_hs256(signing_input, secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("invalid token signature")

    header = base64url_decode_json(header_b64)
    if header.get("alg") != active_settings.jwt_algorithm:
        raise ValueError("unsupported token algorithm")

    payload = base64url_decode_json(payload_b64)
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("missing token expiration")
    if datetime.now(timezone.utc).timestamp() >= exp:
        raise ValueError("token expired")
    return payload


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if not settings.auth_enabled:
        return None
    token = access_token_from_request(request, credentials)
    if token is None:
        raise auth_exception()
    try:
        payload = decode_access_token(token, settings=settings)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise auth_exception() from exc
    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise auth_exception()
    return user


def require_current_user(
    current_user: User | None = Depends(get_current_user),
) -> User:
    if current_user is None:
        raise auth_exception()
    return current_user


def require_admin(
    current_user: User = Depends(require_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return current_user


def require_admin_when_auth_enabled(
    current_user: User | None = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if not settings.auth_enabled:
        return None
    if current_user is None:
        raise auth_exception()
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return current_user


def require_authenticated_in_production(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if settings.app_env.strip().casefold() != "production":
        return None
    if not settings.auth_enabled:
        return None
    token = access_token_from_request(request, credentials)
    if token is None:
        raise auth_exception()
    try:
        payload = decode_access_token(token, settings=settings)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise auth_exception() from exc
    current_user = UserRepository(db).get_by_id(user_id)
    if current_user is None or not current_user.is_active:
        raise auth_exception()
    return current_user


def require_admin_in_production(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if settings.app_env.strip().casefold() != "production":
        return None
    if not settings.auth_enabled:
        return None
    token = access_token_from_request(request, credentials)
    if token is None:
        raise auth_exception()
    try:
        payload = decode_access_token(token, settings=settings)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise auth_exception() from exc
    current_user = UserRepository(db).get_by_id(user_id)
    if current_user is None:
        raise auth_exception()
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return current_user


def access_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None and credentials.scheme.casefold() == "bearer":
        return credentials.credentials
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    return cookie_token.strip() if cookie_token and cookie_token.strip() else None


def auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def jwt_secret(settings: Settings) -> str:
    secret = settings.jwt_secret_key.strip()
    if not secret:
        if settings.auth_enabled:
            raise RuntimeError("JWT_SECRET_KEY is required when auth is enabled")
        secret = "development-only-jwt-secret"
    return secret


def base64url_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64url_encode(raw)


def base64url_decode_json(value: str) -> dict[str, Any]:
    raw = base64url_decode(value)
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError("token part must be a JSON object")
    return decoded


def sign_hs256(signing_input: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64url_encode(digest)


def base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
