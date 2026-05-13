"""Google Calendar OAuth 2.0 연동 엔드포인트 (P1).

흐름:
  1. GET /api/v1/auth/google/calendar  (JWT 필수)
     → HMAC-SHA256 state 생성 → 구글 캘린더 동의 URL 반환
  2. GET /api/v1/auth/google/calendar/callback  (JWT 없음, 구글이 호출)
     → state 검증 → code ↔ refresh_token 교환 → user_oauth_tokens upsert
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from src.api.deps import get_current_user_id  # pyright: ignore[reportMissingImports]
from src.config import get_settings  # pyright: ignore[reportMissingImports]
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.graph.calendar_node import clear_token_cache  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/google", tags=["auth"])

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_STATE_TTL = 600  # 10분 (replay attack 방지)


def _make_state(user_id: int, secret: str) -> str:
    """HMAC-SHA256으로 서명한 state 파라미터 생성.

    형식: {user_id}:{unix_timestamp}:{hex_sig}
    """
    ts = int(time.time())
    payload = f"{user_id}:{ts}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_state(state: str, secret: str) -> int:
    """state 파라미터 서명 검증 + 10분 만료 확인.

    Returns:
        user_id (int)

    Raises:
        HTTPException 400: 서명 불일치 또는 만료.
    """
    try:
        parts = state.split(":")
        if len(parts) != 3:
            raise ValueError
        user_id_str, ts_str, received_sig = parts
        user_id = int(user_id_str)
        ts = int(ts_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 state 파라미터입니다.")

    if time.time() - ts > _STATE_TTL:
        raise HTTPException(status_code=400, detail="state가 만료되었습니다. 다시 시도해 주세요.")

    payload = f"{user_id_str}:{ts_str}"
    expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        raise HTTPException(status_code=400, detail="유효하지 않은 state 파라미터입니다.")

    return user_id


@router.get("/calendar")
async def google_calendar_auth_url(
    user_id: int = Depends(get_current_user_id),
) -> dict[str, str]:
    """Google Calendar 동의 URL 발급.

    JWT 인증 필수. 반환된 auth_url로 사용자를 리다이렉트하면
    구글 동의 후 /callback이 자동 호출된다.
    """
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="서버 설정 오류: JWT 시크릿 미설정.")
    if not settings.google_calendar_client_id:
        raise HTTPException(status_code=503, detail="서버 설정 오류: Google Calendar Client ID 미설정.")

    state = _make_state(user_id, settings.jwt_secret)
    params = {
        "client_id": settings.google_calendar_client_id,
        "redirect_uri": settings.google_calendar_redirect_uri,
        "response_type": "code",
        "scope": _CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": auth_url}


def _calendar_redirect(base_url: str, error: Optional[str] = None) -> RedirectResponse:
    """FE /calendar/connected 페이지로 302 리다이렉트. 에러 시 ?error= 쿼리 추가."""
    url = f"{base_url}/calendar/connected"
    if error:
        url = f"{url}?error={error}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/calendar/callback")
async def google_calendar_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> RedirectResponse:
    """Google OAuth 콜백 — code 수신 → refresh_token 저장 → FE redirect.

    구글이 직접 호출하는 엔드포인트. JWT 인증 없음.
    user_id는 state 파라미터 서명 검증으로 추출.
    성공/실패 모두 FE /calendar/connected 페이지로 redirect.
    """
    settings = get_settings()
    base_url = settings.frontend_base_url

    if error:
        return _calendar_redirect(base_url, error=error)
    if not code or not state:
        return _calendar_redirect(base_url, error="invalid_request")

    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="서버 설정 오류: JWT 시크릿 미설정.")

    try:
        user_id = _verify_state(state, settings.jwt_secret)
    except HTTPException:
        return _calendar_redirect(base_url, error="invalid_state")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "redirect_uri": settings.google_calendar_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if resp.status_code != 200:
        logger.warning(
            "google_calendar_callback: token 교환 실패 status=%d body=%s",
            resp.status_code,
            resp.text[:200],
        )
        return _calendar_redirect(base_url, error="token_exchange_failed")

    token_data = resp.json()
    refresh_token: Optional[str] = token_data.get("refresh_token")
    if not refresh_token:
        return _calendar_redirect(base_url, error="no_refresh_token")

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_oauth_tokens (user_id, provider, scope, refresh_token)
              VALUES ($1, 'google', $2, $3)
              ON CONFLICT (user_id, provider, scope)
              DO UPDATE SET refresh_token = EXCLUDED.refresh_token,
                            is_deleted    = false,
                            updated_at    = NOW()
            """,
            user_id,
            _CALENDAR_SCOPE,
            refresh_token,
        )

    clear_token_cache(user_id)
    logger.info("google_calendar_callback: user_id=%d calendar OAuth 완료", user_id)
    return _calendar_redirect(base_url)
