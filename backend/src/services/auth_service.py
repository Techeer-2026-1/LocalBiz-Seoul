"""인증 비즈니스 로직 — 회원가입(signup_email) + 로그인(login_email) + Google 로그인(login_google).

19 불변식 #15 인증 매트릭스 준수:
  - email 가입: auth_provider='email', password_hash NOT NULL, google_id NULL
  - google 가입: auth_provider='google', password_hash NULL, google_id NOT NULL

DB CHECK 제약 (users_email_or_google_chk)이 위반을 차단하지만,
코드에서도 명시적으로 분기하여 INSERT.

동시성 정책 (CodeRabbit #4 권장 반영):
  - check-then-insert 패턴 금지 (race window 발생 가능)
  - INSERT ... ON CONFLICT DO NOTHING RETURNING 으로 atomic 보장
  - asyncpg.UniqueViolationError를 명시적으로 잡아 500 대신 409 응답

비동기 정책 (CodeRabbit Major 학습 — 본 PR #42):
  - async def 함수에서 동기 I/O (HTTP, blocking syscall) 호출 금지
  - 외부 라이브러리의 동기 함수는 asyncio.to_thread()로 감싸서 별도 스레드 실행
  - event loop 블록 방지 → 동시 요청 처리 능력 보존

보안 정책 (CodeRabbit #3 학습 적용):
  - 로그인 401 응답은 항상 동일한 고정 메시지.
  - wrong_password / user_not_found / google_user 시도 모두 동일 (user enumeration 방지).
  - Google 토큰 검증 실패 시에도 고정 메시지 ("유효하지 않은 Google 토큰입니다").
  - 상세 사유는 logger.info로만 기록 — 단, **이메일은 마스킹 후 기록** (PII 보호).
  - **id_token 자체는 어떤 형태로도 logger 진입 절대 금지** (탈취 방지).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import asyncpg
from fastapi import HTTPException, status

from src.config import get_settings  # pyright: ignore[reportMissingImports]
from src.core.security import (  # pyright: ignore[reportMissingImports]
    create_access_token,
    hash_password,
    verify_google_id_token,
    verify_password,
)
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.user import (  # pyright: ignore[reportMissingImports]
    GoogleLoginRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)


# 로그인 401 응답에 사용하는 고정 메시지 (사용자에게 노출되는 유일한 사유 텍스트).
# wrong_password / user_not_found / google_user 시도를 모두 동일 메시지로 통일하여
# 정보 노출(user enumeration) 방지.
_LOGIN_ERROR_DETAIL = "이메일 또는 비밀번호가 올바르지 않습니다"

# Google 로그인 401 응답 메시지 (id_token 검증 실패).
# 위조/만료/audience 불일치 모든 케이스를 동일 메시지로 통일.
_GOOGLE_TOKEN_INVALID_DETAIL = "유효하지 않은 Google 토큰입니다"

# Google 로그인 409 응답 메시지 (email 충돌).
# 같은 email이 email/password 방식으로 이미 가입된 경우 자동 통합 거부.
# 보안 정책: Google 계정 탈취 시 password 가입자 계정까지 탈취되는 위험 차단.
_EMAIL_CONFLICT_DETAIL = "이미 다른 방식으로 가입된 이메일입니다"

# Google 로그인 410 응답 메시지 (탈퇴자 google_id 재사용).
# soft-deleted 사용자가 같은 google_id로 재가입 시도하는 경우.
# 본 PR은 차단 정책 (계정 복구는 후속 plan에서).
_DELETED_USER_DETAIL = "탈퇴 처리된 계정입니다. 관리자에게 문의해주세요"


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

    회원가입/로그인/Google 로그인 모두 동일 양식 사용.
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


# ---------------------------------------------------------------------------
# Google 소셜 로그인 — Issue #42
# ---------------------------------------------------------------------------
async def login_google(req: GoogleLoginRequest) -> tuple[TokenResponse, bool]:
    """Google ID token으로 로그인 또는 자동 회원가입.

    반환:
      (TokenResponse, is_new_user)
      - is_new_user=False → 기존 사용자 로그인 (라우터가 200 반환)
      - is_new_user=True  → 신규 사용자 자동 가입 (라우터가 201 반환)

    실패:
      401 — id_token 무효 (위조/만료/audience 불일치 등)
      409 — email 충돌 (같은 email이 email/password 방식으로 이미 가입됨)
      410 — 탈퇴자 google_id 재사용 (관리자 문의 안내)

    동시성:
      INSERT ... ON CONFLICT (google_id) DO NOTHING으로 atomic 보장.
      추가로 asyncpg.UniqueViolationError를 명시적으로 잡아 email UNIQUE 위반도 처리.

    비동기 (CodeRabbit Major 학습):
      verify_google_id_token이 동기 HTTP I/O를 수행하므로 asyncio.to_thread로 감싸
      event loop 블록 방지. 동시 요청 처리 능력 보존.

    19 불변식 #15:
      - 신규 INSERT 시 auth_provider='google' 고정, password_hash NULL, google_id NOT NULL.
      - DB CHECK 제약 users_email_or_google_chk가 자동 강제.

    PII 보호 (#19 불변식):
      - id_token 자체는 어떤 형태로도 logger 진입 금지 (탈취 방지).
      - email은 _mask_email() 통해 마스킹.
      - google_id는 Google이 발급하는 외부 ID라 그대로 노출 OK (사용자 식별 불가).
    """
    pool = get_pool()
    settings = get_settings()

    # 1) Google ID token 검증 — google-auth 라이브러리 위임.
    # 동기 함수라 asyncio.to_thread()로 감싸서 별도 스레드 실행 (event loop 블록 방지).
    # ValueError: 위조/만료/audience 불일치 등 모든 검증 실패.
    # 모든 ValueError를 401로 일괄 처리 (user enumeration 방지).
    try:
        payload = await asyncio.to_thread(
            verify_google_id_token,
            req.id_token,
            settings.google_client_id,
        )
    except ValueError:
        logger.info("google login failed: invalid id_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_GOOGLE_TOKEN_INVALID_DETAIL,
        ) from None

    # 2) payload에서 필수 필드 추출
    google_id = payload.get("sub")
    email = payload.get("email")
    if not google_id or not email:
        logger.info("google login failed: missing sub or email in payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_GOOGLE_TOKEN_INVALID_DETAIL,
        )

    # name은 없을 수 있음 (Google이 안 줄 수도 있음). nickname=None 허용.
    nickname: Optional[str] = payload.get("name") or None

    # 3) 기존 google 사용자 조회 — is_deleted=FALSE 강제
    existing = await pool.fetchrow(
        """
        SELECT user_id, email, nickname
        FROM users
        WHERE google_id = $1 AND is_deleted = FALSE
        """,
        google_id,
    )

    # 3-a) 기존 사용자 → 200 로그인
    if existing is not None:
        return (
            _build_token_response(
                user_id=existing["user_id"],
                email=existing["email"],
                nickname=existing["nickname"],
            ),
            False,
        )

    # 4) 신규 INSERT — atomic, race-safe.
    # 두 가지 UNIQUE 제약 (email, google_id) 모두 처리:
    #   - ON CONFLICT (google_id) DO NOTHING: 같은 google_id 충돌 → RETURNING None
    #   - email UNIQUE 위반: asyncpg.UniqueViolationError raise
    # try/except로 두 케이스 모두 명시적 처리하여 raw 500 방지.
    try:
        inserted = await pool.fetchrow(
            """
            INSERT INTO users (email, password_hash, auth_provider, google_id, nickname)
            VALUES ($1, NULL, 'google', $2, $3)
            ON CONFLICT (google_id) DO NOTHING
            RETURNING user_id, email, nickname
            """,
            email,
            google_id,
            nickname,
        )
    except asyncpg.UniqueViolationError as e:
        # email UNIQUE 위반 — 같은 email이 다른 auth_provider(=email) 사용자에게 이미 존재.
        # 보안 정책: 자동 통합 거부 (Google 계정 탈취 시 password 가입자 계정까지 탈취 위험).
        constraint = getattr(e, "constraint_name", None) or ""
        logger.info(
            "google login failed: unique violation on insert (email=%s, constraint=%s)",
            _mask_email(email),
            constraint,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_EMAIL_CONFLICT_DETAIL,
        ) from None

    # 4-a) 신규 INSERT 성공 → 201 신규 가입
    if inserted is not None:
        return (
            _build_token_response(
                user_id=inserted["user_id"],
                email=inserted["email"],
                nickname=inserted["nickname"],
            ),
            True,
        )

    # 4-b) RETURNING None = google_id ON CONFLICT 발동.
    # 두 가지 케이스 가능:
    #   - 동시 요청이 같은 google_id로 INSERT 성공 (race window) → 활성 사용자로 SELECT 가능
    #   - soft-deleted 사용자가 같은 google_id로 재가입 시도 → is_deleted=FALSE SELECT 결과 없음
    raced = await pool.fetchrow(
        """
        SELECT user_id, email, nickname, is_deleted
        FROM users
        WHERE google_id = $1
        """,
        google_id,
    )

    # 4-b-1) 정상 흐름에선 도달 불가 (방금 ON CONFLICT 발동했으니 row 존재해야 함). 방어적 코드.
    if raced is None:
        logger.warning(
            "google login race: ON CONFLICT but SELECT failed (google_id=%s)",
            google_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error during google login",
        )

    # 4-b-2) 탈퇴자 → 410 (관리자 문의 안내, 자동 복구 거부)
    # 본 PR은 차단 정책. 계정 복구는 후속 plan.
    if raced["is_deleted"]:
        logger.info(
            "google login blocked: deleted user attempted re-signup (google_id=%s)",
            google_id,
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_DELETED_USER_DETAIL,
        )

    # 4-b-3) 활성 사용자 (race window 정상 처리) → 200 로그인
    return (
        _build_token_response(
            user_id=raced["user_id"],
            email=raced["email"],
            nickname=raced["nickname"],
        ),
        False,
    )
