"""인증 비즈니스 로직 — 회원가입(signup_email) 단일.

후속 PR에서 login_email / login_google 함수가 같은 모듈에 추가될 예정.

19 불변식 #15 인증 매트릭스 준수:
  - email 가입: auth_provider='email', password_hash NOT NULL, google_id NULL
  - google 가입(다음 PR): auth_provider='google', password_hash NULL, google_id NOT NULL

DB CHECK 제약 (users_email_or_google_chk)이 위반을 차단하지만,
코드에서도 명시적으로 분기하여 INSERT.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from src.core.security import (  # pyright: ignore[reportMissingImports]
    create_access_token,
    hash_password,
)
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    SignupRequest,
    TokenResponse,
)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------
def _build_token_response(user_id: int, email: str, nickname: Optional[str]) -> TokenResponse:
    """user_id로 JWT 발급 + TokenResponse 조립.

    후속 PR(로그인/Google 로그인)에서도 재사용.
    """
    access_token = create_access_token(user_id)
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",  # noqa: S106 — OAuth2 token type, not a password
        user_id=user_id,
        email=email,
        nickname=nickname,
    )


# ---------------------------------------------------------------------------
# 회원가입 (이메일+비밀번호)
# ---------------------------------------------------------------------------
async def signup_email(req: SignupRequest) -> TokenResponse:
    """이메일+비밀번호 회원가입.

    실패:
      409 — 이메일 중복
    """
    pool = get_pool()

    # 1) 중복 체크 (is_deleted 포함 — 같은 email 재가입 정책은 후속 plan)
    existing = await pool.fetchrow(
        "SELECT user_id FROM users WHERE email = $1",
        req.email,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )

    # 2) bcrypt 해싱 (cost 12)
    pw_hash = hash_password(req.password)

    # 3) INSERT — auth_provider='email' 고정, google_id NULL
    row = await pool.fetchrow(
        """
        INSERT INTO users (email, password_hash, auth_provider, nickname)
        VALUES ($1, $2, 'email', $3)
        RETURNING user_id, email, nickname
        """,
        req.email,
        pw_hash,
        req.nickname,
    )
    if row is None:
        # 정상 흐름에선 도달 불가 — INSERT 실패 시 asyncpg가 예외 raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create user",
        )

    return _build_token_response(
        user_id=row["user_id"],
        email=row["email"],
        nickname=row["nickname"],
    )
