"""Auth router — login, refresh, logout, me."""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.pool import acquire
from app.dependencies import get_current_user
from app.models.auth import LoginRequest, RefreshRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response):
    async with acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, email, hashed_pwd, role, is_active
            FROM dashboard.users
            WHERE email = $1
            """,
            payload.email,
        )

    if user is None or not verify_password(payload.password, user["hashed_pwd"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    user_id = str(user["id"])
    access_token = create_access_token({"sub": user_id, "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user_id})

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dashboard.refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            UUID(user_id),
            _hash_token(refresh_token),
            expires_at,
        )
        await conn.execute(
            "UPDATE dashboard.users SET last_login = NOW() WHERE id = $1",
            UUID(user_id),
        )

    # Set refresh token in HttpOnly cookie
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str | None = Cookie(None)):
    token = refresh_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    decoded = decode_token(token)

    if decoded is None or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    token_hash = _hash_token(token)

    async with acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT id, user_id, expires_at, revoked
            FROM dashboard.refresh_tokens
            WHERE token_hash = $1
            """,
            token_hash,
        )

    if record is None or record["revoked"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is revoked or not found",
        )

    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    user_id = str(record["user_id"])
    async with acquire() as conn:
        user = await conn.fetchrow(
            "SELECT role, is_active FROM dashboard.users WHERE id = $1",
            UUID(user_id),
        )

    if user is None or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token({"sub": user_id, "role": user["role"]})
    return TokenResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, refresh_token: str | None = Cookie(None)):
    if refresh_token:
        token_hash = _hash_token(refresh_token)
    async with acquire() as conn:
        await conn.execute(
            "UPDATE dashboard.refresh_tokens SET revoked = TRUE WHERE token_hash = $1",
            token_hash,
        )
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)
