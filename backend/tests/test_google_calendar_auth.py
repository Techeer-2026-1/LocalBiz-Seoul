"""google_calendar_auth 단위 테스트.

httpx는 respx로, asyncpg pool은 unittest.mock으로 대체.
FastAPI 핸들러를 async 함수로 직접 호출해 로직만 검증.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from fastapi import HTTPException
from httpx import Response

from src.api.google_calendar_auth import (
    _CALENDAR_SCOPE,
    _make_state,
    _verify_state,
    google_calendar_auth_url,
    google_calendar_callback,
)

_SECRET = "test-jwt-secret"
_USER_ID = 42


# ---------------------------------------------------------------------------
# _make_state / _verify_state
# ---------------------------------------------------------------------------


def test_make_state_format() -> None:
    """state 형식이 {user_id}:{ts}:{sig} 3파트인지 확인."""
    state = _make_state(_USER_ID, _SECRET)
    parts = state.split(":")
    assert len(parts) == 3
    assert parts[0] == str(_USER_ID)
    assert parts[1].isdigit()
    assert len(parts[2]) == 64  # SHA-256 hex digest


def test_verify_state_roundtrip() -> None:
    """정상 서명 → user_id 반환."""
    state = _make_state(_USER_ID, _SECRET)
    assert _verify_state(state, _SECRET) == _USER_ID


def test_verify_state_wrong_secret_returns_400() -> None:
    """잘못된 시크릿으로 서명 검증 실패 → 400."""
    state = _make_state(_USER_ID, _SECRET)
    with pytest.raises(HTTPException) as exc:
        _verify_state(state, "wrong-secret")
    assert exc.value.status_code == 400


def test_verify_state_tampered_user_id_returns_400() -> None:
    """user_id를 위조하면 서명 검증 실패 → 400."""
    state = _make_state(_USER_ID, _SECRET)
    parts = state.split(":")
    forged = f"999:{parts[1]}:{parts[2]}"
    with pytest.raises(HTTPException) as exc:
        _verify_state(forged, _SECRET)
    assert exc.value.status_code == 400


def test_verify_state_expired_returns_400() -> None:
    """만료된 state (11분 전) → 400."""
    old_ts = int(time.time()) - 660  # 11분 전
    payload = f"{_USER_ID}:{old_ts}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    expired_state = f"{payload}:{sig}"
    with pytest.raises(HTTPException) as exc:
        _verify_state(expired_state, _SECRET)
    assert exc.value.status_code == 400


def test_verify_state_invalid_format_returns_400() -> None:
    """파트 수가 3개가 아니면 → 400."""
    with pytest.raises(HTTPException) as exc:
        _verify_state("invalid", _SECRET)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/auth/google/calendar — 동의 URL 반환
# ---------------------------------------------------------------------------


def _settings_mock(jwt_secret: str = _SECRET) -> Any:
    m = MagicMock()
    m.jwt_secret = jwt_secret
    m.google_calendar_client_id = "test-client-id"
    m.google_calendar_redirect_uri = "http://localhost:8000/api/v1/auth/google/calendar/callback"
    return m


@pytest.mark.asyncio
async def test_auth_url_returns_google_consent_url() -> None:
    """정상 요청 → accounts.google.com + scope + state 포함 URL 반환."""
    with patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()):
        result = await google_calendar_auth_url(user_id=_USER_ID)

    assert "auth_url" in result
    assert "accounts.google.com" in result["auth_url"]
    assert "calendar" in result["auth_url"]
    assert "state=" in result["auth_url"]
    assert "prompt=consent" in result["auth_url"]


@pytest.mark.asyncio
async def test_auth_url_no_jwt_secret_raises_503() -> None:
    """jwt_secret 미설정(빈 문자열) → 503."""
    with patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock(jwt_secret="")):
        with pytest.raises(HTTPException) as exc:
            await google_calendar_auth_url(user_id=_USER_ID)
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/v1/auth/google/calendar/callback — code 교환 → upsert
# ---------------------------------------------------------------------------


def _pool_mock() -> Any:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


def _make_valid_state() -> str:
    return _make_state(_USER_ID, _SECRET)


@pytest.mark.asyncio
async def test_callback_success_upserts_token() -> None:
    """정상 code + valid state → user_oauth_tokens upsert 후 200 반환."""
    pool = _pool_mock()
    state = _make_valid_state()

    with (
        patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()),
        patch("src.api.google_calendar_auth.get_pool", return_value=pool),
        respx.mock,
    ):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(200, json={"refresh_token": "rt-xyz", "access_token": "at-xyz"})
        )

        result = await google_calendar_callback(code="auth-code", state=state, error=None)

    assert result == {"message": "Google Calendar 연동이 완료되었습니다."}

    conn = pool.acquire().__aenter__.return_value
    conn.execute.assert_awaited_once()
    call_args = conn.execute.await_args
    assert _USER_ID in call_args.args
    assert _CALENDAR_SCOPE in call_args.args
    assert "rt-xyz" in call_args.args


@pytest.mark.asyncio
async def test_callback_token_exchange_failure_raises_400() -> None:
    """code 교환 실패 (구글 400) → 400."""
    state = _make_valid_state()

    with (
        patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()),
        patch("src.api.google_calendar_auth.get_pool", return_value=_pool_mock()),
        respx.mock,
    ):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )

        with pytest.raises(HTTPException) as exc:
            await google_calendar_callback(code="bad-code", state=state, error=None)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_no_refresh_token_raises_400() -> None:
    """구글이 refresh_token 없이 응답 → 400 (prompt=consent 미적용 케이스)."""
    state = _make_valid_state()

    with (
        patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()),
        patch("src.api.google_calendar_auth.get_pool", return_value=_pool_mock()),
        respx.mock,
    ):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(200, json={"access_token": "at-only"})
        )

        with pytest.raises(HTTPException) as exc:
            await google_calendar_callback(code="auth-code", state=state, error=None)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_missing_code_raises_400() -> None:
    """code 파라미터 없음 → 400."""
    state = _make_valid_state()
    with patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()):
        with pytest.raises(HTTPException) as exc:
            await google_calendar_callback(code=None, state=state, error=None)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_error_param_raises_400() -> None:
    """구글이 error 파라미터 전달 (사용자 거부) → 400."""
    with patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()):
        with pytest.raises(HTTPException) as exc:
            await google_calendar_callback(code=None, state=None, error="access_denied")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_invalid_state_raises_400() -> None:
    """위조된 state → 400."""
    with patch("src.api.google_calendar_auth.get_settings", return_value=_settings_mock()):
        with pytest.raises(HTTPException) as exc:
            await google_calendar_callback(code="auth-code", state=f"1:{int(time.time())}:fakesig", error=None)
    assert exc.value.status_code == 400
