"""place_bookmarks API 단위 테스트.

asyncpg pool은 unittest.mock으로 대체. 실제 DB 호출 없이 로직만 검증.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.place_bookmarks import (
    create_place_bookmark,
    delete_place_bookmark,
    list_place_bookmarks,
)
from src.models.place_bookmarks import PlaceBookmarkCreateRequest

_USER_ID = 1
_NOW = datetime(2026, 5, 14, 0, 0, 0, tzinfo=UTC)


def _pool_mock() -> Any:
    pool = MagicMock()
    pool.fetch = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()
    return pool


def _make_row(**kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "bookmark_id": 1,
        "place_id": "place-uuid-001",
        "name": "경복궁",
        "category": "관광명소",
        "address": "서울 종로구",
        "district": "종로구",
        "lat": 37.5796,
        "lng": 126.9770,
        "rating": 4.5,
        "image_url": None,
        "summary": None,
        "source_thread_id": None,
        "source_message_id": None,
        "created_at": _NOW,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# GET 목록
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_items() -> None:
    """정상 조회 → items 반환."""
    pool = _pool_mock()
    pool.fetch = AsyncMock(return_value=[_make_row()])

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        result = await list_place_bookmarks(cursor=None, limit=20, user_id=_USER_ID)

    assert len(result.items) == 1
    assert result.items[0].name == "경복궁"
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_list_cursor_pagination() -> None:
    """limit+1개 반환 시 next_cursor 설정."""
    rows = [_make_row(bookmark_id=i) for i in range(21, 0, -1)]
    pool = _pool_mock()
    pool.fetch = AsyncMock(return_value=rows)

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        result = await list_place_bookmarks(cursor=None, limit=20, user_id=_USER_ID)

    assert len(result.items) == 20
    assert result.next_cursor is not None


@pytest.mark.asyncio
async def test_list_invalid_cursor_raises_400() -> None:
    """cursor가 정수 아니면 400."""
    pool = _pool_mock()
    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        with pytest.raises(HTTPException) as exc:
            await list_place_bookmarks(cursor="abc", limit=20, user_id=_USER_ID)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# POST 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_bookmark() -> None:
    """정상 생성 → bookmark_id 반환."""
    pool = _pool_mock()
    pool.fetchrow = AsyncMock(return_value=_make_row())

    body = PlaceBookmarkCreateRequest(place_id="place-uuid-001", name="경복궁")

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        result = await create_place_bookmark(body=body, user_id=_USER_ID)

    assert result.bookmark_id == 1
    assert result.place_id == "place-uuid-001"


@pytest.mark.asyncio
async def test_create_db_failure_raises_422() -> None:
    """DB 오류 → 422."""
    pool = _pool_mock()
    pool.fetchrow = AsyncMock(side_effect=Exception("DB error"))

    body = PlaceBookmarkCreateRequest(place_id="place-uuid-001", name="경복궁")

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        with pytest.raises(HTTPException) as exc:
            await create_place_bookmark(body=body, user_id=_USER_ID)
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# DELETE 소프트 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_success() -> None:
    """정상 삭제 → 204 (None 반환)."""
    pool = _pool_mock()
    pool.execute = AsyncMock(return_value="UPDATE 1")

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        result = await delete_place_bookmark(bookmark_id=1, user_id=_USER_ID)

    assert result is None


@pytest.mark.asyncio
async def test_delete_not_found_raises_404() -> None:
    """없는 북마크 삭제 → 404."""
    pool = _pool_mock()
    pool.execute = AsyncMock(return_value="UPDATE 0")

    with patch("src.api.place_bookmarks.get_pool", return_value=pool):
        with pytest.raises(HTTPException) as exc:
            await delete_place_bookmark(bookmark_id=999, user_id=_USER_ID)
    assert exc.value.status_code == 404
