"""User-related Pydantic schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    full_name: str
    role: str = "athlete"  # 'athlete' or 'coach'


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str


class UserResponse(UserBase):
    """Schema for user response (without sensitive data)."""

    id: UUID

    class Config:
        from_attributes = True  # Pydantic v2: ORM mode


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Schema for Google OAuth authentication."""

    google_token: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(TokenResponse):
    """Schema for login/register response with user data."""

    user: UserResponse

