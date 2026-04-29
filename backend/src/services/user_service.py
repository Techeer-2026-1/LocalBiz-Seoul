"""사용자 비즈니스 로직 — 닉네임 변경(update_nickname) (Issue #15) + 비밀번호 변경(change_password) (Issue #16).

19 불변식:
  - #2 timestamp: UPDATE 시 updated_at = NOW() 명시 갱신
  - #8 SQL 파라미터: $1, $2 양식 준수
  - #9 Optional: NULL 가능 컬럼 명시
  - #15 인증 매트릭스: nickname은 무관, password_hash 변경은 email 사용자만 (google 사용자 400)

PII 보호 정책 (로그인 PR #2 + 닉네임 PR #15 학습 누적):
  - logger 호출 시 user_id로만 로깅 (email 노출 0)
  - 비밀번호 자체(old/new) 어떤 형태로도 logger 진입 절대 금지 (#19 불변식)
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from src.core.security import (  # pyright: ignore[reportMissingImports]
    hash_password,
    verify_password,
)
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    NicknameUpdate,
    PasswordUpdate,
    UserResponse,
)

logger = logging.getLogger(__name__)


# 사용자 미존재(탈퇴자 포함) 응답 메시지.
_USER_NOT_FOUND_DETAIL = "사용자를 찾을 수 없습니다"

# 비밀번호 변경 — google 사용자 차단 메시지 (auth_provider 정책 위반).
_GOOGLE_USER_PW_DETAIL = "Google 계정은 비밀번호 변경을 지원하지 않습니다"

# 비밀번호 변경 — old_password 불일치 메시지.
# 보안 정책 (CodeRabbit #3 학습): deps.py 401 메시지와 통일하여 user enumeration 방지.
_AUTH_ERROR_DETAIL = "유효하지 않은 인증"


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


# ---------------------------------------------------------------------------
# 비밀번호 변경 — Issue #16
# ---------------------------------------------------------------------------
async def change_password(user_id: int, req: PasswordUpdate) -> UserResponse:
    """현재 사용자의 비밀번호 변경 (email 사용자만).

    실패:
      404 — 사용자 미존재 (탈퇴자가 옛 토큰으로 시도)
      400 — google 사용자가 비밀번호 변경 시도 (auth_provider 정책 위반)
      401 — old_password 불일치 (토큰 탈취자 방지)

    동시성:
      SELECT-then-UPDATE 패턴. 같은 사용자만 동시 시도 가능 (악의적 타이밍 공격 무관).
      PostgreSQL row-lock으로 직렬화. last-write-wins.

    19 불변식 #15:
      - SELECT 결과 password_hash IS NULL → google 사용자 → 400
      - email 사용자: verify(old) → hash(new) → UPDATE password_hash만 (auth_provider/google_id 무관)
      - CHECK 제약 위반 가능성 0 (email 사용자의 password_hash NOT NULL 유지)

    PII 보호 (#19 불변식):
      - user_id로만 로깅. old_password / new_password 절대 logger 진입 금지.
    """
    pool = get_pool()

    # 1) 사용자 조회 — is_deleted=FALSE 강제
    row = await pool.fetchrow(
        """
        SELECT user_id, email, password_hash, auth_provider
        FROM users
        WHERE user_id = $1 AND is_deleted = FALSE
        """,
        user_id,
    )

    # 2) 사용자 미존재 또는 탈퇴자 → 404
    if row is None:
        logger.info("password change failed: user not found (user_id=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_USER_NOT_FOUND_DETAIL,
        )

    # 3) password_hash IS NULL → google 사용자 → 400
    # (auth_provider='google'이지만 명시적 NULL 체크가 더 안전)
    if row["password_hash"] is None:
        logger.info(
            "password change failed: google user attempted (user_id=%s)",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_GOOGLE_USER_PW_DETAIL,
        )

    # 4) old_password 검증 — 틀리면 401 (deps.py 메시지와 통일)
    if not verify_password(req.old_password, row["password_hash"]):
        logger.info(
            "password change failed: wrong old password (user_id=%s)",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
        )

    # 5) 새 비밀번호 해싱 (cost 12)
    new_hash = hash_password(req.new_password)

    # 6) UPDATE — password_hash만 갱신, updated_at = NOW()
    updated = await pool.fetchrow(
        """
        UPDATE users
        SET password_hash = $1, updated_at = NOW()
        WHERE user_id = $2 AND is_deleted = FALSE
        RETURNING user_id, email, nickname, auth_provider
        """,
        new_hash,
        user_id,
    )

    # 정상 흐름에선 도달 불가 (이미 위에서 사용자 존재 확인). 방어적 코드.
    if updated is None:
        logger.warning(
            "password change race: user disappeared between SELECT and UPDATE (user_id=%s)",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_USER_NOT_FOUND_DETAIL,
        )

    return UserResponse(
        user_id=updated["user_id"],
        email=updated["email"],
        nickname=updated["nickname"],
        auth_provider=updated["auth_provider"],
    )
