"""인증 라우터 — /api/v1/auth/signup (Issue #4) + /login (Issue #2).

후속 PR에서 /google 라우트가 같은 모듈에 추가될 예정.

기획서 §4.2 + 기능 명세서 CSV의 Request/Response 예시 준수.
모두 stateless: JWT만 발급, 서버측 세션 없음.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from src.models.user import (  # pyright: ignore[reportMissingImports]
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from src.services import auth_service  # pyright: ignore[reportMissingImports]

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 (이메일+비밀번호)",
)
async def signup(req: SignupRequest) -> TokenResponse:
    """이메일/비밀번호로 새 계정 생성 후 access_token 즉시 발급."""
    return await auth_service.signup_email(req)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="로그인 (이메일+비밀번호)",
)
async def login(req: LoginRequest) -> TokenResponse:
    """이메일/비밀번호 검증 후 access_token 발급."""
    return await auth_service.login_email(req)
