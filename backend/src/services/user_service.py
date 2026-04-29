"""사용자 비즈니스 로직 — 닉네임 변경(update_nickname) (Issue #15).

후속 PR에서 change_password 함수가 같은 모듈에 추가될 예정.

19 불변식:
  - #2 timestamp: UPDATE 시 updated_at = NOW() 명시 갱신
  - #8 SQL 파라미터: $1, $2 양식 준수
  - #9 Optional: NULL 가능 컬럼 명시
  - #15 인증 매트릭스: nickname만 수정. auth_provider/password_hash/google_id 무관

PII 보호 정책 (로그인 PR #2 학습 적용):
  - logger 호출 시 user_id로만 로깅 (email 노출 0)
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    NicknameUpdate,
    UserResponse,
)

logger = logging.getLogger(__name__)


# 사용자 미존재(탈퇴자 포함) 응답 메시지.
_USER_NOT_FOUND_DETAIL = "사용자를 찾을 수 없습니다"


# ---------------------------------------------------------------------------
# 닉네임 변경 — Issue #15
# ---------------------------------------------------------------------------
async def update_nickname(user_id: int, req: NicknameUpdate) -> UserResponse:
    """현재 사용자의 닉네임 변경.

    실패:
      404 — 사용자 미존재 (탈퇴자가 옛 토큰으로 시도하는 등)

    동시성:
      UPDATE 단일 SQL이라 race window 없음. 같은 user_id 동시 변경 시 PostgreSQL row-lock으로
      직렬화. last-write-wins (운영상 허용).

    19 불변식 #15:
      - nickname만 수정. auth_provider/password_hash/google_id 무관 → CHECK 제약 위반 가능성 0.
      - email/google 사용자 모두 nickname 변경 가능.
    """
    pool = get_pool()

    # UPDATE — is_deleted=FALSE 강제 (탈퇴자는 변경 불가).
    # updated_at = NOW()로 19 불변식 #2 timestamp 강제.
    row = await pool.fetchrow(
        """
        UPDATE users
        SET nickname = $1, updated_at = NOW()
        WHERE user_id = $2 AND is_deleted = FALSE
        RETURNING user_id, email, nickname, auth_provider
        """,
        req.nickname,
        user_id,
    )

    # RETURNING None = 사용자 미존재 또는 탈퇴자 = 404
    if row is None:
        logger.info("nickname update failed: user not found (user_id=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_USER_NOT_FOUND_DETAIL,
        )

    return UserResponse(
        user_id=row["user_id"],
        email=row["email"],
        nickname=row["nickname"],
        auth_provider=row["auth_provider"],
    )
