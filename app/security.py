from __future__ import annotations

import base64
import hashlib
import secrets
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app import models
from app.config import settings
from app import database

_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 390000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_raw, salt_raw, digest_raw = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
        salt = _unb64(salt_raw)
        expected = _unb64(digest_raw)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return secrets.compare_digest(actual, expected)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_api_token(
    session: Session,
    user: models.User,
    label: str = "default",
    *,
    expires_in_days: int | None = None,
) -> str:
    token = f"{settings.api_token_prefix}{secrets.token_urlsafe(32)}"
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    row = models.ApiToken(
        user_id=user.id,
        label=label or "default",
        token_prefix=token[:12],
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    session.add(row)
    session.commit()
    return token


def authenticate_token(session: Session, token: str) -> Optional[models.User]:
    if not token:
        return None
    token_hash = _hash_token(token)
    row = session.exec(
        select(models.ApiToken).where(models.ApiToken.token_hash == token_hash)
    ).first()
    if not row:
        return None
    now = datetime.utcnow()
    if row.revoked_at is not None:
        return None
    if row.expires_at is not None and row.expires_at <= now:
        return None
    user = session.get(models.User, row.user_id)
    if not user or not user.is_active:
        return None
    row.last_used_at = now
    session.add(row)
    session.commit()
    return user


def authenticate_password(session: Session, email: str, password: str) -> Optional[models.User]:
    user = session.exec(
        select(models.User).where(models.User.email == email.strip().lower())
    ).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def ensure_default_user(session: Session) -> models.User:
    user = session.exec(
        select(models.User).where(models.User.is_default == True)  # noqa: E712
    ).first()
    if user:
        return user
    user = session.exec(
        select(models.User).where(models.User.email == settings.default_user_email)
    ).first()
    if user:
        user.is_default = True
        if not user.display_name:
            user.display_name = settings.default_user_name
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    user = models.User(
        email=settings.default_user_email,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        display_name=settings.default_user_name,
        is_default=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_default_user_exists() -> models.User:
    with Session(database.engine) as session:
        return ensure_default_user(session)


def get_current_user_id(required: bool = True) -> int | None:
    user_id = _current_user_id.get()
    if required and not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def set_current_user(user_id: int):
    return _current_user_id.set(user_id)


def reset_current_user(token) -> None:
    _current_user_id.reset(token)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name)


def is_api_request_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def is_public_api_path(path: str) -> bool:
    if path in {"/api/health", "/api/app-shell", "/api/auth/login", "/api/auth/register"}:
        return True
    return False


def read_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if cookie_token:
        return cookie_token
    return None


def resolve_request_user(request: Request) -> Optional[models.User]:
    token = read_bearer_token(request)
    with Session(database.engine) as session:
        if token:
            user = authenticate_token(session, token)
            if user:
                return user
        if settings.local_auto_user:
            return ensure_default_user(session)
    return None


def get_request_user(request: Request) -> models.User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_current_user(
    request: Request,
    session: Session = Depends(database.session_dependency),
) -> models.User:
    request_user = getattr(request.state, "user", None)
    if request_user:
        user = session.get(models.User, request_user.id)
        if user and user.is_active:
            return user
    raise HTTPException(status_code=401, detail="Authentication required")
