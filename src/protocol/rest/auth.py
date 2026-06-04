from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=32)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(min_length=1)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    created_at: datetime
    rating: int
    games_played: int
    calibration_complete: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int


class AuthResponse(BaseModel):
    user: UserPublic
    token: TokenResponse


class MeResponse(BaseModel):
    user: UserPublic
