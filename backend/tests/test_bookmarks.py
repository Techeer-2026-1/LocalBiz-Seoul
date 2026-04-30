"""북마크 API 테스트 — GET(목록/필터/cursor) / POST(생성) / DELETE(소프트삭제).

DB를 AsyncMock으로 대체. handler 함수를 직접 호출하는 패턴 (test_share.py 동일).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _make_pool(
    fetch_return: Any = None,
    fetchrow_side_effect: Any = None,
    execute_return: str = "UPDATE 1",
) -> AsyncMock:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    if fetchrow_side_effect is not None:
        pool.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    else:
        pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value=execute_return)
    return pool


def _bookmark_row(
    bookmark_id: int = 1,
    thread_id: str = "thread-abc",
    message_id: int = 10,
    pin_type: str = "place",
    preview_text: Any = None,
) -> dict:
    return {
        "bookmark_id": bookmark_id,
        "thread_id": thread_id,
        "message_id": message_id,
        "pin_type": pin_type,
        "preview_text": preview_text,
        "created_at": _NOW,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/users/me/bookmarks — 빈 목록
# ---------------------------------------------------------------------------
async def test_list_bookmarks_empty() -> None:
    pool = _make_pool(fetch_return=[])

    with (
        patch("src.api.bookmarks.get_pool", return_value=pool),  # pyright: ignore[reportMissingImports]
        patch("src.api.bookmarks.get_current_user_id", return_value=1),  # pyright: ignore[reportMissingImports]
    ):
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        result = await list_bookmarks(thread_id=None, pin_type=None, cursor=None, limit=20, user_id=1)

    assert result.items == []
    assert result.next_cursor is None


# ---------------------------------------------------------------------------
# GET — 결과 있음
# ---------------------------------------------------------------------------
async def test_list_bookmarks_returns_items() -> None:
    rows = [_bookmark_row(i) for i in range(1, 4)]
    pool = _make_pool(fetch_return=rows)

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        result = await list_bookmarks(thread_id=None, pin_type=None, cursor=None, limit=20, user_id=1)

    assert len(result.items) == 3
    assert result.items[0].bookmark_id == 1


# ---------------------------------------------------------------------------
# GET — cursor 페이지네이션: has_more=True → next_cursor 설정
# ---------------------------------------------------------------------------
async def test_list_bookmarks_next_cursor() -> None:
    # limit=2, 3개 반환 → has_more=True
    rows = [_bookmark_row(i) for i in range(3, 0, -1)]  # 3, 2, 1
    pool = _make_pool(fetch_return=rows)

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        result = await list_bookmarks(thread_id=None, pin_type=None, cursor=None, limit=2, user_id=1)

    assert len(result.items) == 2
    assert result.next_cursor == "2"  # items[-1].bookmark_id = 2


# ---------------------------------------------------------------------------
# GET — cursor 값이 잘못된 형식
# ---------------------------------------------------------------------------
async def test_list_bookmarks_bad_cursor() -> None:
    from fastapi import HTTPException

    with patch("src.api.bookmarks.get_pool", return_value=AsyncMock()):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await list_bookmarks(thread_id=None, pin_type=None, cursor="not-a-number", limit=20, user_id=1)

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET — pin_type 필터
# ---------------------------------------------------------------------------
async def test_list_bookmarks_filter_pin_type() -> None:
    rows = [_bookmark_row(pin_type="event")]
    pool = _make_pool(fetch_return=rows)

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        result = await list_bookmarks(thread_id=None, pin_type="event", cursor=None, limit=20, user_id=1)

    assert result.items[0].pin_type == "event"


# ---------------------------------------------------------------------------
# GET — thread_id 필터
# ---------------------------------------------------------------------------
async def test_list_bookmarks_filter_thread_id() -> None:
    rows = [_bookmark_row(thread_id="specific-thread")]
    pool = _make_pool(fetch_return=rows)

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import list_bookmarks  # pyright: ignore[reportMissingImports]

        result = await list_bookmarks(thread_id="specific-thread", pin_type=None, cursor=None, limit=20, user_id=1)

    assert result.items[0].thread_id == "specific-thread"


# ---------------------------------------------------------------------------
# POST /api/v1/users/me/bookmarks — 생성 성공
# ---------------------------------------------------------------------------
async def test_create_bookmark_success() -> None:
    inserted_row = _bookmark_row(bookmark_id=99)
    pool = _make_pool(fetchrow_side_effect=[inserted_row])

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import create_bookmark  # pyright: ignore[reportMissingImports]
        from src.models.bookmarks import BookmarkCreateRequest  # pyright: ignore[reportMissingImports]

        req = BookmarkCreateRequest(
            thread_id="thread-abc",
            message_id=10,
            pin_type="place",
            preview_text="미리보기",
        )
        result = await create_bookmark(body=req, user_id=1)

    assert result.bookmark_id == 99
    assert result.pin_type == "place"
    pool.fetchrow.assert_called_once()


# ---------------------------------------------------------------------------
# POST — DB 오류 시 422
# ---------------------------------------------------------------------------
async def test_create_bookmark_db_error() -> None:
    from fastapi import HTTPException

    pool = _make_pool()
    pool.fetchrow = AsyncMock(side_effect=Exception("FK violation"))

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import create_bookmark  # pyright: ignore[reportMissingImports]
        from src.models.bookmarks import BookmarkCreateRequest  # pyright: ignore[reportMissingImports]

        req = BookmarkCreateRequest(thread_id="t", message_id=1, pin_type="general")
        with pytest.raises(HTTPException) as exc_info:
            await create_bookmark(body=req, user_id=1)

    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/me/bookmarks/{bookmark_id} — 성공
# ---------------------------------------------------------------------------
async def test_delete_bookmark_success() -> None:
    pool = _make_pool(execute_return="UPDATE 1")

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import delete_bookmark  # pyright: ignore[reportMissingImports]

        await delete_bookmark(bookmark_id=1, user_id=1)

    pool.execute.assert_called_once()


# ---------------------------------------------------------------------------
# DELETE — 없는 북마크 → 404
# ---------------------------------------------------------------------------
async def test_delete_bookmark_not_found() -> None:
    from fastapi import HTTPException

    pool = _make_pool(execute_return="UPDATE 0")

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import delete_bookmark  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await delete_bookmark(bookmark_id=999, user_id=1)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# DELETE — 다른 사용자 북마크 → 404 (소유권 검증)
# ---------------------------------------------------------------------------
async def test_delete_bookmark_wrong_user() -> None:
    from fastapi import HTTPException

    # user_id=2가 소유한 북마크를 user_id=1이 삭제 시도
    # WHERE user_id=$2 조건 미충족 → execute UPDATE 0
    pool = _make_pool(execute_return="UPDATE 0")

    with patch("src.api.bookmarks.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.bookmarks import delete_bookmark  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await delete_bookmark(bookmark_id=1, user_id=1)

    assert exc_info.value.status_code == 404
