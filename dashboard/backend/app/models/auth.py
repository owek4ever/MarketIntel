from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str
