"""사용자 라우터 — /api/v1/users/me PATCH (Issue #15).

후속 PR에서 /me/password (비밀번호 변경) 라우트가 같은 모듈에 추가될 예정.

기획서 §4.2 + 기능 명세서 CSV의 Request/Response 예시 준수.
인증 필수: Authorization 헤더의 Bearer 토큰 (deps.py 처리).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.deps import get_current_user_id  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    NicknameUpdate,
    UserResponse,
)
from src.services import user_service  # pyright: ignore[reportMissingImports]

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="닉네임 변경",
)
async def update_me_nickname(
    req: NicknameUpdate,
    user_id: int = Depends(get_current_user_id),
) -> UserResponse:
    """현재 인증된 사용자의 닉네임을 변경한다."""
    return await user_service.update_nickname(user_id, req)
