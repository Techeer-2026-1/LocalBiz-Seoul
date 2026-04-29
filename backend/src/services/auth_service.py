"""인증 비즈니스 로직 — 회원가입(signup_email) + 로그인(login_email).

후속 PR에서 login_google 함수가 같은 모듈에 추가될 예정.

19 불변식 #15 인증 매트릭스 준수:
  - email 가입: auth_provider='email', password_hash NOT NULL, google_id NULL
  - google 가입(다음 PR): auth_provider='google', password_hash NULL, google_id NOT NULL

DB CHECK 제약 (users_email_or_google_chk)이 위반을 차단하지만,
코드에서도 명시적으로 분기하여 INSERT.

동시성 정책 (CodeRabbit #4 권장 반영):
  - check-then-insert 패턴 금지 (race window 발생 가능)
  - INSERT ... ON CONFLICT DO NOTHING RETURNING 으로 atomic 보장
  - 결과가 None이면 동시에 다른 요청이 같은 email로 가입 성공 → 409

보안 정책 (CodeRabbit #3 학습 적용):
  - 로그인 401 응답은 항상 동일한 고정 메시지.
  - wrong_password / user_not_found / google_user 시도 모두 동일 (user enumeration 방지).
  - 상세 사유는 logger.info로만 기록 — 단, **이메일은 마스킹 후 기록** (PII 보호).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, status

from src.core.security import (  # pyright: ignore[reportMissingImports]
    create_access_token,
    hash_password,
    verify_password,
)
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    LoginRequest,
    SignupRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)


# 로그인 401 응답에 사용하는 고정 메시지 (사용자에게 노출되는 유일한 사유 텍스트).
# wrong_password / user_not_found / google_user 시도를 모두 동일 메시지로 통일하여
# 정보 노출(user enumeration) 방지.
_LOGIN_ERROR_DETAIL = "이메일 또는 비밀번호가 올바르지 않습니다"


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------
def _mask_email(email: str) -> str:
    """이메일을 로깅용으로 마스킹.

    예시:
      'pytest-signup@example.com' → 'p***p@example.com'
      'a@b.com'                   → 'a*@b.com'
      'ab@b.com'                  → 'a*@b.com'

    PII 보호 정책 (CodeRabbit #3 학습 적용):
      - 인증 실패 로그에 이메일 원문 노출 금지 (GDPR/개인정보보호 컴플라이언스)
      - 디버깅에 유용한 단서 (도메인 + local 첫/마지막 글자)는 보존
      - 마스킹 실패 시 완전 가림 (안전한 default)
    """
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            return f"{local[0]}*@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    except (ValueError, IndexError):
        return "***@***"


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


# ---------------------------------------------------------------------------
# 로그인 (이메일+비밀번호) — Issue #2
# ---------------------------------------------------------------------------
async def login_email(req: LoginRequest) -> TokenResponse:
    """이메일+비밀번호 로그인.

    실패:
      401 — 이메일/비밀번호 오류 (고정 메시지, user enumeration 방지)

    동시성:
      SELECT만이라 race window 없음. 같은 email 동시 로그인 시도 100건이 와도 모두 같은 결과.

    19 불변식 #15:
      - auth_provider='email' 사용자: password_hash NOT NULL → verify_password 호출
      - auth_provider='google' 사용자: password_hash IS NULL → 즉시 401 (verify 호출 안 함)

    PII 보호 (CodeRabbit #3 학습):
      - 모든 logger.info 호출이 _mask_email 통해 이메일 마스킹.
    """
    pool = get_pool()

    # 1) 사용자 조회 — is_deleted=FALSE 강제 (탈퇴자는 로그인 불가)
    row = await pool.fetchrow(
        """
        SELECT user_id, email, password_hash, nickname
        FROM users
        WHERE email = $1 AND is_deleted = FALSE
        """,
        req.email,
    )

    # 2) 사용자 미존재 → 401 (고정 메시지)
    if row is None:
        logger.info("login failed: user not found (email=%s)", _mask_email(req.email))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_LOGIN_ERROR_DETAIL,
        )

    # 3) password_hash IS NULL → google 가입자가 password 로그인 시도 → 401
    if row["password_hash"] is None:
        logger.info(
            "login failed: google user attempted password login (email=%s)",
            _mask_email(req.email),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_LOGIN_ERROR_DETAIL,
        )

    # 4) bcrypt 검증 — 틀린 비밀번호 → 401 (동일 메시지)
    if not verify_password(req.password, row["password_hash"]):
        logger.info("login failed: wrong password (email=%s)", _mask_email(req.email))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_LOGIN_ERROR_DETAIL,
        )

    # 5) 성공 → JWT 발급
    return _build_token_response(
        user_id=row["user_id"],
        email=row["email"],
        nickname=row["nickname"],
    )
