"""Auth router — login, refresh, logout, me, register, forgot-password, reset-password."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie

from app.core.config import settings
from app.core.email import generate_otp, send_otp_email, send_welcome_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.pool import acquire
from app.dependencies import get_current_user
from app.models.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ─── LOGIN ────────────────────────────────────────────────────────────────────

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


# ─── REFRESH ──────────────────────────────────────────────────────────────────

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


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

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


# ─── ME ───────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)


# ─── REGISTER ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    """Create a new analyst account. Email must be unique."""
    async with acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM dashboard.users WHERE email = $1",
            payload.email,
        )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    hashed = hash_password(payload.password)

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dashboard.users (email, hashed_pwd, role, is_active)
            VALUES ($1, $2, 'analyst', TRUE)
            """,
            payload.email,
            hashed,
        )

    # Fire-and-forget welcome email (non-fatal if it fails)
    try:
        await send_welcome_email(payload.email)
    except Exception as exc:
        logger.warning("Welcome email failed for %s: %s", payload.email, exc)

    return {"detail": "Account created successfully. You can now log in."}


# ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(payload: ForgotPasswordRequest):
    """
    Send a 6-digit OTP to the given email.
    Always returns 200 to avoid email-enumeration attacks.
    """
    async with acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM dashboard.users WHERE email = $1 AND is_active = TRUE",
            payload.email,
        )

    if user is None:
        # Return 200 anyway — never reveal whether the email exists
        return {"detail": "If that email is registered, a reset code has been sent."}

    code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.otp_expire_minutes
    )

    async with acquire() as conn:
        # Invalidate any existing unused codes for this email
        await conn.execute(
            """
            UPDATE dashboard.otp_codes
            SET used = TRUE
            WHERE email = $1 AND purpose = 'password_reset' AND used = FALSE
            """,
            payload.email,
        )
        # Insert new code
        await conn.execute(
            """
            INSERT INTO dashboard.otp_codes (email, code, purpose, expires_at)
            VALUES ($1, $2, 'password_reset', $3)
            """,
            payload.email,
            code,
            expires_at,
        )

    await send_otp_email(to=payload.email, code=code)

    return {"detail": "If that email is registered, a reset code has been sent."}


# ─── RESET PASSWORD ───────────────────────────────────────────────────────────

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(payload: ResetPasswordRequest):
    """Verify OTP code and update the user's password."""
    async with acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT id, expires_at, used
            FROM dashboard.otp_codes
            WHERE email = $1
              AND code = $2
              AND purpose = 'password_reset'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            payload.email,
            payload.code,
        )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code",
        )

    if record["used"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code has already been used",
        )

    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code has expired — please request a new one",
        )

    new_hash = hash_password(payload.new_password)

    async with acquire() as conn:
        updated = await conn.fetchval(
            """
            UPDATE dashboard.users
            SET hashed_pwd = $1
            WHERE email = $2 AND is_active = TRUE
            RETURNING id
            """,
            new_hash,
            payload.email,
        )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found or inactive",
        )

    # Mark OTP as used and revoke all active sessions for security
    async with acquire() as conn:
        await conn.execute(
            "UPDATE dashboard.otp_codes SET used = TRUE WHERE id = $1",
            record["id"],
        )
        await conn.execute(
            """
            UPDATE dashboard.refresh_tokens
            SET revoked = TRUE
            WHERE user_id = $1 AND revoked = FALSE
            """,
            updated,
        )

    return {"detail": "Password reset successfully. Please log in with your new password."}
