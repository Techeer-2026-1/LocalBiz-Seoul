"""인증 보안 유틸 — bcrypt 해시, JWT 발급/검증, Google id_token 검증.

19 불변식 #15 인증 매트릭스 준수:
  - email 가입: password_hash NOT NULL
  - google 가입: google_id NOT NULL, password_hash NULL

Phase 1 — access token 단일. refresh token은 후속 plan에서.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import jwt
from passlib.context import CryptContext

from src.config import get_settings  # pyright: ignore[reportMissingImports]

# ---------------------------------------------------------------------------
# 비밀번호 해싱 (bcrypt cost 12)
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain: str) -> str:
    """평문 비밀번호 → bcrypt 해시. cost 12."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """평문 ↔ 해시 비교. False면 인증 실패."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT (HS256, access token only)
# ---------------------------------------------------------------------------
def create_access_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """user_id를 sub로 담은 JWT 발급.

    payload: {sub: str(user_id), iat, exp}
    유효기간: expires_delta 없으면 settings.jwt_expire_minutes 사용.
    """
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET 환경변수가 설정되지 않았습니다.")

    now = datetime.now(UTC)
    delta = expires_delta if expires_delta is not None else timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """JWT 디코드 + 서명/만료 검증. 실패 시 JWTError raise.

    호출측에서 JWTError를 잡아 401로 변환.
    """
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET 환경변수가 설정되지 않았습니다.")
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    return payload


# ---------------------------------------------------------------------------
# Google id_token 검증
# ---------------------------------------------------------------------------
def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]:
    """Google id_token 검증 + payload 반환.

    내부적으로 https://oauth2.googleapis.com/tokeninfo 호출 + 서명/iss/aud 검증.
    실패 시 ValueError raise (잘못된 토큰, 만료, audience 불일치 등).

    반환 dict 주요 키:
      - sub: Google 계정 고유 ID (= users.google_id)
      - email: 이메일
      - email_verified: bool
      - name: 표시 이름 (닉네임 후보, 없을 수 있음)
    """
    payload: dict[str, Any] = google_id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        client_id,
    )
    return payload
