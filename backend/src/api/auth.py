"""인증 라우터 — /api/v1/auth/signup (Issue #4) + /login (Issue #2) + /google (Issue #42).

기획서 §4.2 + 기능 명세서 CSV의 Request/Response 예시 준수.
모두 stateless: JWT만 발급, 서버측 세션 없음.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from src.models.user import (  # pyright: ignore[reportMissingImports]
    GoogleLoginRequest,
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


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Google 소셜 로그인",
    responses={
        200: {"description": "기존 Google 사용자 로그인"},
        201: {"description": "신규 Google 사용자 자동 가입"},
        401: {"description": "유효하지 않은 Google 토큰"},
        409: {"description": "이미 다른 방식으로 가입된 이메일"},
    },
)
async def google_login(req: GoogleLoginRequest, response: Response) -> TokenResponse:
    """Google ID token으로 로그인 또는 자동 회원가입.

    신규 사용자는 자동 가입 후 201 Created, 기존 사용자는 200 OK 반환.
    FE는 응답 코드로 신규 가입 여부 구분 가능 (환영 메시지 등).
    """
    token_response, is_new_user = await auth_service.login_google(req)
    if is_new_user:
        response.status_code = status.HTTP_201_CREATED
    return token_response
