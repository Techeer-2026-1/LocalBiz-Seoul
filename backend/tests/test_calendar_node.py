"""calendar_node 단위 테스트.

asyncpg pool은 unittest.mock으로, httpx는 respx로 mock.
실제 DB / Google Calendar API 호출 없이 로직만 검증.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from src.graph.calendar_node import _token_cache, calendar_node

_START = "2026-05-02T14:00:00+09:00"
_END = "2026-05-02T16:00:00+09:00"
_LINK = "https://calendar.google.com/calendar/event?eid=test123"


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """각 테스트 전 캐시 초기화."""
    _token_cache.clear()


def _make_pool_mock(has_token: bool = True) -> Any:
    """asyncpg pool mock 생성 헬퍼."""
    row = {"refresh_token": "test-refresh-token"} if has_token else None
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_user_id_returns_error() -> None:
    state: dict[str, Any] = {
        "processed_query": {"event_title": "경복궁 방문", "start_time": _START},
    }
    result = await calendar_node(state)  # type: ignore[arg-type]
    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "error"
    assert "로그인" in blocks[0]["message"]


@pytest.mark.asyncio
async def test_missing_start_time_returns_error() -> None:
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {"event_title": "경복궁 방문"},
    }
    result = await calendar_node(state)  # type: ignore[arg-type]
    blocks = result["response_blocks"]
    assert blocks[0]["type"] == "error"
    assert "시작 시간" in blocks[0]["message"]


@pytest.mark.asyncio
async def test_missing_event_title_returns_error() -> None:
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {"start_time": _START},
    }
    result = await calendar_node(state)  # type: ignore[arg-type]
    blocks = result["response_blocks"]
    assert blocks[0]["type"] == "error"
    assert "제목" in blocks[0]["message"]


# ---------------------------------------------------------------------------
# OAuth 토큰 없음
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_oauth_token_returns_error() -> None:
    pool = _make_pool_mock(has_token=False)
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {"event_title": "경복궁 방문", "start_time": _START},
    }
    with patch("src.graph.calendar_node.get_pool", return_value=pool):
        result = await calendar_node(state)  # type: ignore[arg-type]

    blocks = result["response_blocks"]
    assert blocks[0]["type"] == "error"
    assert "Google" in blocks[0]["message"]


# ---------------------------------------------------------------------------
# 성공 케이스
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_successful_creation_returns_calendar_block() -> None:
    pool = _make_pool_mock()
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {
            "event_title": "경복궁 방문",
            "start_time": _START,
            "end_time": _END,
            "location": "경복궁",
        },
    }
    with (
        patch("src.graph.calendar_node.get_pool", return_value=pool),
        patch("src.graph.calendar_node.get_settings") as mock_settings,
        respx.mock,
    ):
        mock_settings.return_value.google_calendar_client_id = "cid"
        mock_settings.return_value.google_calendar_client_secret = "csec"

        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(200, json={"access_token": "test-access-token"})
        )
        respx.post("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(
            return_value=Response(200, json={"htmlLink": _LINK})
        )

        result = await calendar_node(state)  # type: ignore[arg-type]

    blocks = result["response_blocks"]
    assert len(blocks) == 2

    text_block = blocks[0]
    assert text_block["type"] == "text_stream"

    cal_block = blocks[1]
    assert cal_block["type"] == "calendar"
    assert cal_block["event_title"] == "경복궁 방문"
    assert cal_block["status"] == "created"
    assert cal_block["calendar_link"] == _LINK
    assert cal_block["location"] == "경복궁"


# ---------------------------------------------------------------------------
# 실패 케이스 — API 오류 시 status="failed"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_calendar_api_failure_returns_failed_status() -> None:
    pool = _make_pool_mock()
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {
            "event_title": "경복궁 방문",
            "start_time": _START,
            "end_time": _END,
        },
    }
    with (
        patch("src.graph.calendar_node.get_pool", return_value=pool),
        patch("src.graph.calendar_node.get_settings") as mock_settings,
        respx.mock,
    ):
        mock_settings.return_value.google_calendar_client_id = "cid"
        mock_settings.return_value.google_calendar_client_secret = "csec"

        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(200, json={"access_token": "test-access-token"})
        )
        respx.post("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(
            return_value=Response(500, json={"error": "internal"})
        )

        result = await calendar_node(state)  # type: ignore[arg-type]

    blocks = result["response_blocks"]
    assert len(blocks) == 2
    cal_block = blocks[1]
    assert cal_block["status"] == "failed"
    assert cal_block.get("calendar_link") is None


# ---------------------------------------------------------------------------
# end_time 없을 때 자동으로 +1시간 적용 확인
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_end_time_defaults_to_one_hour_later() -> None:
    pool = _make_pool_mock()
    state: dict[str, Any] = {
        "user_id": 1,
        "processed_query": {
            "event_title": "경복궁 방문",
            "start_time": _START,
        },
    }
    with (
        patch("src.graph.calendar_node.get_pool", return_value=pool),
        patch("src.graph.calendar_node.get_settings") as mock_settings,
        respx.mock,
    ):
        mock_settings.return_value.google_calendar_client_id = "cid"
        mock_settings.return_value.google_calendar_client_secret = "csec"

        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=Response(200, json={"access_token": "test-access-token"})
        )

        captured: dict[str, Any] = {}

        def capture_request(request: Any) -> Response:
            import json

            captured["body"] = json.loads(request.content)
            return Response(200, json={"htmlLink": _LINK})

        respx.post("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(side_effect=capture_request)

        await calendar_node(state)  # type: ignore[arg-type]

    assert captured["body"]["end"]["dateTime"] == "2026-05-02T15:00:00+09:00"
