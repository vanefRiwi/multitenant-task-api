from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.presentation.http.schemas.common import RequestModel


class RegisterRequest(RequestModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RequestModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime
