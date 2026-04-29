"""인증 비즈니스 로직 — 회원가입(signup_email) 단일.

후속 PR에서 login_email / login_google 함수가 같은 모듈에 추가될 예정.

19 불변식 #15 인증 매트릭스 준수:
  - email 가입: auth_provider='email', password_hash NOT NULL, google_id NULL
  - google 가입(다음 PR): auth_provider='google', password_hash NULL, google_id NOT NULL

DB CHECK 제약 (users_email_or_google_chk)이 위반을 차단하지만,
코드에서도 명시적으로 분기하여 INSERT.

동시성 정책 (CodeRabbit #4 권장 반영):
  - check-then-insert 패턴 금지 (race window 발생 가능)
  - INSERT ... ON CONFLICT DO NOTHING RETURNING 으로 atomic 보장
  - 결과가 None이면 동시에 다른 요청이 같은 email로 가입 성공 → 409
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

    구현 노트:
      check-then-insert (SELECT then INSERT) 패턴은 race window가 있어
      두 동시 요청이 둘 다 SELECT를 통과한 뒤 한쪽이 UNIQUE 제약 위반으로
      DB 예외를 일으킬 수 있다. atomic INSERT ... ON CONFLICT DO NOTHING
      RETURNING 으로 한 번에 처리하여 race-safe.
    """
    pool = get_pool()

    # 1) bcrypt 해싱 (cost 12) — INSERT 전에 미리 계산
    pw_hash = hash_password(req.password)

    # 2) Atomic INSERT — auth_provider='email' 고정, google_id NULL.
    # ON CONFLICT (email) DO NOTHING: 같은 email이 이미 있으면 INSERT 안 함 + RETURNING None.
    # email_idx (partial index WHERE is_deleted=FALSE)와 별개로 users.email UNIQUE constraint가
    # row 0건이든 100건이든 동일하게 작동한다.
    row = await pool.fetchrow(
        """
        INSERT INTO users (email, password_hash, auth_provider, nickname)
        VALUES ($1, $2, 'email', $3)
        ON CONFLICT (email) DO NOTHING
        RETURNING user_id, email, nickname
        """,
        req.email,
        pw_hash,
        req.nickname,
    )

    # 3) 결과 None = ON CONFLICT 발동 = 이미 존재하는 email = 409
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )

    return _build_token_response(
        user_id=row["user_id"],
        email=row["email"],
        nickname=row["nickname"],
    )
