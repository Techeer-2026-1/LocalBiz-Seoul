"""사용자/인증 관련 Pydantic 스키마.

기획서 §4.2 + 기능 명세서 CSV의 Request/Response 예시 준수.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class SignupRequest(BaseModel):
    """POST /api/v1/auth/signup 요청 본문."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login 요청 본문."""

    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    """POST /api/v1/auth/google 요청 본문.

    FE의 Google Identity Services에서 받은 id_token을 그대로 전달.
    BE가 google-auth로 서명/iss/aud 검증.
    """

    id_token: str


class NicknameUpdate(BaseModel):
    """PATCH /api/v1/users/me 요청 본문."""

    nickname: str = Field(min_length=1, max_length=100)


class PasswordUpdate(BaseModel):
    """PATCH /api/v1/users/me/password 요청 본문.

    auth_provider='email' 사용자만 사용 가능. google 사용자는 400.
    """

    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    """signup/login/google 공통 응답 — JWT + 사용자 식별 정보."""

    access_token: str
    token_type: str = "Bearer"
    user_id: int
    email: str
    nickname: Optional[str] = None


class UserResponse(BaseModel):
    """사용자 프로필 응답 (PATCH /me 등)."""

    user_id: int
    email: str
    nickname: Optional[str] = None
    auth_provider: str
