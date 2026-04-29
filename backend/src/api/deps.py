"""공통 의존성 — JWT 기반 인증.

FastAPI의 Depends() 시스템:
  - 라우터 함수의 파라미터에 Depends(함수)를 넣으면,
    요청이 올 때마다 그 함수가 먼저 실행되고, 반환값이 파라미터에 주입된다.
  - 예: user_id: int = Depends(get_current_user_id)
    → 요청 들어옴 → get_current_user_id() 실행 → 반환값(user_id)이 파라미터에 들어감

이전엔 placeholder (return 1 하드코딩)였으나, 본 PR(#4 회원가입)에서
JWT 발급/검증 인프라가 들어왔으므로 진짜 인증으로 교체.

보안 정책 (CodeRabbit #3 권장 반영):
  - 401 응답에는 항상 고정된 일반 메시지만 반환.
  - 토큰 검증 실패 상세(만료/위조/형식)를 클라이언트에 노출하지 않음.
  - 상세 사유는 서버 로깅으로만 보존 (공격자에게 단서 제공 방지).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from src.core.security import decode_access_token  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


# 401 응답에 사용하는 고정 메시지 (사용자에게 노출되는 유일한 사유 텍스트).
# 토큰 부재/형식오류/만료/위조를 모두 동일한 메시지로 통일하여 정보 노출 방지.
_AUTH_ERROR_DETAIL = "유효하지 않은 인증"
_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
) -> int:
    """현재 인증된 사용자 ID 반환.

    프로토콜:
      1. Authorization 헤더에서 "Bearer {token}" 추출
      2. JWT 토큰 디코딩 → payload에서 user_id (sub) 꺼냄
      3. 토큰 부재/형식오류/만료/위조 시 401 Unauthorized (고정 메시지)

    Authorization 헤더 양식:
      Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

    19 불변식 #15 인증 매트릭스: JWT payload의 sub 클레임이 user_id (BIGINT).
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
            headers=_AUTH_HEADERS,
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.info("Authorization header malformed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
            headers=_AUTH_HEADERS,
        )

    token = parts[1]

    try:
        payload = decode_access_token(token)
    except Exception as e:
        # 상세 사유는 서버 로깅으로만 (만료/위조/형식 구분 가능).
        # 클라이언트에는 일반 메시지만 노출.
        logger.info("JWT decode failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
            headers=_AUTH_HEADERS,
        ) from e

    sub = payload.get("sub")
    if sub is None:
        logger.info("JWT payload missing sub claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
            headers=_AUTH_HEADERS,
        )

    try:
        return int(sub)
    except (TypeError, ValueError) as e:
        logger.info("JWT sub claim not int: %r", sub)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_ERROR_DETAIL,
            headers=_AUTH_HEADERS,
        ) from e


# 일부 라우터가 의존성 자체를 import해서 쓸 수 있도록 alias 노출
CurrentUserId = Depends(get_current_user_id)
