"""공유 링크 API 테스트 — 생성/조회/해제.

DB mock으로 shared_links CRUD를 검증.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 헬퍼: pool mock 생성
# ---------------------------------------------------------------------------
def _make_pool_mock(
    fetchrow_side_effect: Any = None,
    fetch_return: Any = None,
) -> AsyncMock:
    """asyncpg pool mock."""
    pool = AsyncMock()
    if fetchrow_side_effect is not None:
        pool.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    else:
        pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    pool.execute = AsyncMock()
    return pool


# ---------------------------------------------------------------------------
# POST /api/v1/chats/{thread_id}/share
# ---------------------------------------------------------------------------
async def test_create_share_link() -> None:
    """공유 링크 생성 → share_token 반환."""
    conv_row = {"thread_id": "test-thread"}
    pool = _make_pool_mock(fetchrow_side_effect=[conv_row])

    with (
        patch("src.api.share.get_pool", return_value=pool),  # pyright: ignore[reportMissingImports]
        patch("src.api.share.get_current_user_id", return_value=1),  # pyright: ignore[reportMissingImports]
    ):
        from src.api.share import create_share_link  # pyright: ignore[reportMissingImports]

        result = await create_share_link(thread_id="test-thread", user_id=1)

        assert result.share_token
        assert len(result.share_token) == 32  # uuid4 hex
        assert result.share_url == f"/shared/{result.share_token}"
        pool.execute.assert_called_once()


# ---------------------------------------------------------------------------
# GET /shared/{share_token}
# ---------------------------------------------------------------------------
async def test_get_shared_conversation() -> None:
    """공유 대화 조회 → messages 반환."""
    import datetime

    link_row = {
        "thread_id": "test-thread",
        "from_message_id": None,
        "to_message_id": None,
        "expires_at": None,
    }
    conv_row = {"title": "테스트 대화"}
    msg_rows = [
        {
            "role": "user",
            "blocks": [{"type": "text", "content": "안녕"}],
            "created_at": datetime.datetime(2026, 4, 30, tzinfo=datetime.UTC),
        },
        {
            "role": "assistant",
            "blocks": [{"type": "text_stream", "content": "반가워요"}],
            "created_at": datetime.datetime(2026, 4, 30, tzinfo=datetime.UTC),
        },
    ]

    pool = _make_pool_mock(
        fetchrow_side_effect=[link_row, conv_row],
        fetch_return=msg_rows,
    )

    with patch("src.api.share.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.share import get_shared_conversation  # pyright: ignore[reportMissingImports]

        result = await get_shared_conversation(share_token="abc123")  # noqa: S106

        assert result.thread_title == "테스트 대화"
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"


# ---------------------------------------------------------------------------
# DELETE /api/v1/chats/{thread_id}/share
# ---------------------------------------------------------------------------
async def test_delete_share_link() -> None:
    """공유 링크 해제 → 소프트 삭제 실행."""
    conv_row = {"thread_id": "test-thread"}
    pool = _make_pool_mock(fetchrow_side_effect=[conv_row])

    with (
        patch("src.api.share.get_pool", return_value=pool),  # pyright: ignore[reportMissingImports]
        patch("src.api.share.get_current_user_id", return_value=1),  # pyright: ignore[reportMissingImports]
    ):
        from src.api.share import delete_share_link  # pyright: ignore[reportMissingImports]

        result = await delete_share_link(thread_id="test-thread", user_id=1)

        assert result.status_code == 204
        pool.execute.assert_called_once()
        call_args = pool.execute.call_args
        assert "is_deleted = true" in call_args[0][0]


async def test_delete_nonexistent_thread_returns_404() -> None:
    """존재하지 않는 대화 삭제 시도 → 404."""
    pool = _make_pool_mock(fetchrow_side_effect=[None])

    with (
        patch("src.api.share.get_pool", return_value=pool),  # pyright: ignore[reportMissingImports]
        patch("src.api.share.get_current_user_id", return_value=1),  # pyright: ignore[reportMissingImports]
    ):
        from fastapi import HTTPException

        from src.api.share import delete_share_link  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await delete_share_link(thread_id="no-thread", user_id=1)

        assert exc_info.value.status_code == 404


async def test_get_deleted_link_returns_404() -> None:
    """삭제된 공유 링크 조회 → 404."""
    pool = _make_pool_mock(fetchrow_side_effect=[None])  # is_deleted=true인 건 SELECT에서 제외

    with patch("src.api.share.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from fastapi import HTTPException

        from src.api.share import get_shared_conversation  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await get_shared_conversation(share_token="deleted-token")  # noqa: S106

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 만료된 링크 → 410 Gone
# ---------------------------------------------------------------------------
async def test_expired_link_returns_gone() -> None:
    """만료된 공유 링크 → HTTPException 410."""
    import datetime

    expired_link = {
        "thread_id": "test-thread",
        "from_message_id": None,
        "to_message_id": None,
        "expires_at": datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
    }
    pool = _make_pool_mock(fetchrow_side_effect=[expired_link])

    with patch("src.api.share.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from fastapi import HTTPException

        from src.api.share import get_shared_conversation  # pyright: ignore[reportMissingImports]

        with pytest.raises(HTTPException) as exc_info:
            await get_shared_conversation(share_token="expired-token")  # noqa: S106

        assert exc_info.value.status_code == 410


# ---------------------------------------------------------------------------
# message_range 필터링
# ---------------------------------------------------------------------------
async def test_message_range_filter() -> None:
    """from/to_message_id 지정 시 SQL에 범위 조건 포함."""

    link_row = {
        "thread_id": "test-thread",
        "from_message_id": 5,
        "to_message_id": 10,
        "expires_at": None,
    }
    conv_row = {"title": "범위 테스트"}
    pool = _make_pool_mock(
        fetchrow_side_effect=[link_row, conv_row],
        fetch_return=[],
    )

    with patch("src.api.share.get_pool", return_value=pool):  # pyright: ignore[reportMissingImports]
        from src.api.share import get_shared_conversation  # pyright: ignore[reportMissingImports]

        await get_shared_conversation(share_token="range-token")  # noqa: S106

        # fetch가 호출됐는지 확인 + SQL에 범위 조건 포함
        fetch_call = pool.fetch.call_args
        sql = fetch_call[0][0]
        assert "message_id >=" in sql
        assert "message_id <=" in sql
