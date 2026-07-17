from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app import models, schemas, security
from app import database
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ensure_auth_feature_enabled() -> None:
    if settings.desktop_mode:
        raise HTTPException(status_code=404, detail="桌面模式不提供网页登录或扩展令牌")


@router.post("/register", response_model=schemas.AuthResponse)
def register(
    body: schemas.RegisterRequest,
    response: Response,
    session: Session = Depends(database.session_dependency),
):
    _ensure_auth_feature_enabled()
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="请输入有效邮箱")
    if len(body.password or "") < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    exists = session.exec(select(models.User).where(models.User.email == email)).first()
    if exists:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    user = models.User(
        email=email,
        password_hash=security.hash_password(body.password),
        display_name=(body.display_name or email.split("@", 1)[0]).strip(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = security.issue_api_token(session, user, label="web-session", expires_in_days=30)
    security.set_session_cookie(response, token)
    return schemas.AuthResponse(user=user, token=token)


@router.post("/login", response_model=schemas.AuthResponse)
def login(
    body: schemas.LoginRequest,
    response: Response,
    session: Session = Depends(database.session_dependency),
):
    _ensure_auth_feature_enabled()
    user = security.authenticate_password(session, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = security.issue_api_token(session, user, label="web-session", expires_in_days=30)
    security.set_session_cookie(response, token)
    return schemas.AuthResponse(user=user, token=token)


@router.post("/logout")
def logout(response: Response):
    if settings.desktop_mode:
        return {"ok": True}
    security.clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=schemas.UserRead)
def me(user: models.User = Depends(security.get_current_user)):
    return user


@router.post("/tokens")
def create_token(
    body: schemas.TokenCreateRequest,
    session: Session = Depends(database.session_dependency),
    user: models.User = Depends(security.get_current_user),
):
    _ensure_auth_feature_enabled()
    token = security.issue_api_token(session, user, label=body.label or "extension")
    return {"token": token}
