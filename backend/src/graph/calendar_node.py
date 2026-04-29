"""CALENDAR intent 노드 — Google Calendar 일정 추가 (P1).

사용자의 자연어 요청에서 Gemini가 파싱한 일정 정보를
Google Calendar REST API로 해당 유저 캘린더에 생성한다.

흐름:
  processed_query에서 event_title, start_time, end_time, location 꺼냄
  → user_id로 user_oauth_tokens 테이블에서 refresh_token 조회
  → refresh_token으로 access_token 발급 (TTLCache 58분 캐시)
  → Google Calendar API 호출 → 이벤트 생성
  → text_stream 블록 + calendar 블록 반환

API 명세서 CALENDAR 블록 순서: intent → text_stream → calendar → done
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from cachetools import TTLCache

from src.config import get_settings  # pyright: ignore[reportMissingImports]
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.graph.state import AgentState  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

# access_token 캐시 — user_id 기준, 58분 (구글 기본 만료 1시간보다 2분 짧게)
_token_cache: TTLCache = TTLCache(maxsize=1000, ttl=3480)

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_KST = timezone(timedelta(hours=9))


class _CalendarError(Exception):
    """사용자에게 안내가 필요한 캘린더 오류."""


async def calendar_node(state: AgentState) -> dict[str, Any]:
    """CALENDAR intent 노드.

    processed_query에서 일정 정보를 꺼내 Google Calendar에 이벤트를 생성하고
    text_stream + calendar 블록으로 반환한다.

    Args:
        state: AgentState. user_id와 processed_query 필드 필수.

    Returns:
        {"response_blocks": [text_stream 블록, calendar 블록]} 또는 error 블록.
    """
    pq: Optional[dict[str, Any]] = state.get("processed_query")
    user_id: Optional[int] = state.get("user_id")

    if not user_id:
        return {"response_blocks": [_error_block("로그인이 필요합니다.")]}

    if not pq or not pq.get("start_time"):
        return {"response_blocks": [_error_block("일정 시작 시간을 알려주세요. 예) '5월 2일 오후 2시'")]}

    if not pq.get("event_title"):
        return {"response_blocks": [_error_block("일정 제목을 알려주세요.")]}

    event_title: str = pq["event_title"]
    start_time: str = pq["start_time"]
    end_time: Optional[str] = pq.get("end_time") or _add_one_hour(start_time)
    location: Optional[str] = pq.get("location")

    try:
        access_token = await _get_access_token(user_id)
        calendar_link = await _create_event(
            access_token=access_token,
            event_title=event_title,
            start_time=start_time,
            end_time=end_time,
            location=location,
        )
        status = "created"
    except _CalendarError as e:
        return {"response_blocks": [_error_block(str(e))]}
    except Exception:
        logger.exception("calendar_node: 이벤트 생성 실패")
        calendar_link = None
        status = "failed"

    return {
        "response_blocks": [
            _text_stream_block(event_title, start_time, status),
            _calendar_block(
                event_title=event_title,
                start_time=start_time,
                end_time=end_time,
                location=location,
                calendar_link=calendar_link,
                status=status,
            ),
        ]
    }


async def _get_access_token(user_id: int) -> str:
    """user_oauth_tokens 테이블에서 refresh_token 조회 후 access_token 발급.

    access_token은 TTLCache(user_id 기준)로 캐시해 중복 발급을 방지.

    Raises:
        _CalendarError: refresh_token 없거나 발급 실패 시.
    """
    if user_id in _token_cache:
        return str(_token_cache[user_id])

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT refresh_token FROM user_oauth_tokens
            WHERE user_id = $1
              AND provider = 'google'
              AND scope LIKE '%calendar%'
              AND is_deleted = false
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    if not row:
        raise _CalendarError("Google Calendar 연동이 필요합니다. Google 계정으로 로그인해 주세요.")

    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "refresh_token": row["refresh_token"],
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code != 200:
        logger.warning("calendar_node: access_token 발급 실패 status=%d", resp.status_code)
        raise _CalendarError("Google Calendar 연동에 실패했습니다. 다시 시도해 주세요.")

    access_token: str = resp.json()["access_token"]
    _token_cache[user_id] = access_token
    return access_token


async def _create_event(
    access_token: str,
    event_title: str,
    start_time: str,
    end_time: Optional[str],
    location: Optional[str],
) -> str:
    """Google Calendar API로 이벤트를 생성하고 htmlLink를 반환.

    Raises:
        httpx.HTTPStatusError: API 호출 실패 시 (caller에서 status="failed" 처리).
    """
    event_body: dict[str, Any] = {
        "summary": event_title,
        "start": {"dateTime": start_time, "timeZone": "Asia/Seoul"},
        "end": {"dateTime": end_time, "timeZone": "Asia/Seoul"},
    }
    if location:
        event_body["location"] = location

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GOOGLE_CALENDAR_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json=event_body,
        )

    resp.raise_for_status()
    return str(resp.json()["htmlLink"])


def _add_one_hour(iso_time: str) -> Optional[str]:
    """ISO 8601 문자열에 1시간을 더해 반환. 파싱 실패 시 None."""
    try:
        dt = datetime.fromisoformat(iso_time)
        return (dt + timedelta(hours=1)).isoformat()
    except ValueError:
        logger.warning("calendar_node: end_time 계산 실패 — iso_time=%s", iso_time)
        return None


def _text_stream_block(event_title: str, start_time: str, status: str) -> dict[str, Any]:
    if status == "created":
        prompt = f"'{event_title}' 일정을 Google Calendar에 추가했어요. ({start_time})"
    else:
        prompt = "죄송합니다. Google Calendar 일정 추가에 실패했습니다. 잠시 후 다시 시도해 주세요."

    return {
        "type": "text_stream",
        "system": "Google Calendar 일정 추가 결과를 친절하게 안내하세요. 불필요한 내용은 추가하지 마세요.",
        "prompt": prompt,
    }


def _calendar_block(
    event_title: str,
    start_time: str,
    end_time: Optional[str],
    location: Optional[str],
    calendar_link: Optional[str],
    status: str,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "calendar",
        "event_title": event_title,
        "start_time": start_time,
        "status": status,
    }
    if end_time:
        block["end_time"] = end_time
    if location:
        block["location"] = location
    if calendar_link:
        block["calendar_link"] = calendar_link
    return block


def _error_block(message: str) -> dict[str, Any]:
    return {"type": "error", "message": message}
