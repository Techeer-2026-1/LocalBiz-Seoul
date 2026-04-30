"""place_search_node 단위 테스트.

PG + OS mock으로 하이브리드 검색 로직을 검증.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _mock_settings() -> MagicMock:
    """fake settings with API key."""
    s = MagicMock()
    s.gemini_llm_api_key = "fake-key"
    return s


def _mock_pool(rows: list[dict[str, Any]]) -> AsyncMock:
    """asyncpg pool mock."""
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=rows)
    return pool


def _mock_os_client(hits: list[dict[str, Any]]) -> AsyncMock:
    """OpenSearch client mock."""
    client = AsyncMock()
    client.search = AsyncMock(return_value={"hits": {"hits": hits}})
    return client


_PG_ROWS = [
    {
        "place_id": "pg-001",
        "name": "카페A",
        "category": "카페",
        "address": "서울 마포구",
        "district": "마포구",
        "lat": 37.556,
        "lng": 126.923,
    },
]

_OS_HITS = [
    {
        "_id": "os-001",
        "_score": 0.85,
        "_source": {
            "name": "카페B",
            "category": "카페",
            "address": "서울 마포구",
            "district": "마포구",
            "lat": 37.557,
            "lng": 126.924,
        },
    },
]


async def test_pg_and_os_results() -> None:
    """PG + OS 모두 성공 → places + map_markers 블록 반환."""
    with (
        patch("src.config.get_settings", return_value=_mock_settings()),  # pyright: ignore[reportMissingImports]
        patch("src.db.postgres.get_pool", return_value=_mock_pool(_PG_ROWS)),  # pyright: ignore[reportMissingImports]
        patch("src.db.opensearch.get_os_client", return_value=_mock_os_client(_OS_HITS)),  # pyright: ignore[reportMissingImports]
        patch("src.graph.place_search_node._embed_query_768d", return_value=[0.1] * 768),  # pyright: ignore[reportMissingImports]
    ):
        from src.graph.place_search_node import place_search_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "홍대 카페",
            "intent": "PLACE_SEARCH",
            "processed_query": {
                "district": "마포구",
                "category": "카페",
                "keywords": [],
                "expanded_query": "홍대 카페",
            },
        }
        result = await place_search_node(state)

        blocks = result["response_blocks"]
        types = [b["type"] for b in blocks]
        assert "text_stream" in types
        assert "places" in types
        assert "map_markers" in types


async def test_pg_fails_os_only() -> None:
    """PG 실패 → OS 결과만으로 동작."""
    fail_pool = AsyncMock()
    fail_pool.fetch = AsyncMock(side_effect=Exception("DB error"))

    with (
        patch("src.config.get_settings", return_value=_mock_settings()),  # pyright: ignore[reportMissingImports]
        patch("src.db.postgres.get_pool", return_value=fail_pool),  # pyright: ignore[reportMissingImports]
        patch("src.db.opensearch.get_os_client", return_value=_mock_os_client(_OS_HITS)),  # pyright: ignore[reportMissingImports]
        patch("src.graph.place_search_node._embed_query_768d", return_value=[0.1] * 768),  # pyright: ignore[reportMissingImports]
    ):
        from src.graph.place_search_node import place_search_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "강남 맛집",
            "intent": "PLACE_SEARCH",
            "processed_query": {"expanded_query": "강남 맛집"},
        }
        result = await place_search_node(state)
        blocks = result["response_blocks"]
        assert any(b["type"] == "text_stream" for b in blocks)


async def test_os_fails_pg_only() -> None:
    """OS 실패 → PG 결과만으로 동작."""
    with (
        patch("src.config.get_settings", return_value=_mock_settings()),  # pyright: ignore[reportMissingImports]
        patch("src.db.postgres.get_pool", return_value=_mock_pool(_PG_ROWS)),  # pyright: ignore[reportMissingImports]
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("OS not init")),  # pyright: ignore[reportMissingImports]
    ):
        from src.graph.place_search_node import place_search_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "이태원 맛집",
            "intent": "PLACE_SEARCH",
            "processed_query": {"expanded_query": "이태원 맛집"},
        }
        result = await place_search_node(state)
        blocks = result["response_blocks"]
        assert any(b["type"] == "text_stream" for b in blocks)
        assert any(b["type"] == "places" for b in blocks)


async def test_both_fail_empty() -> None:
    """PG + OS 둘 다 실패 → text_stream "검색 결과가 없습니다" fallback."""
    fail_pool = AsyncMock()
    fail_pool.fetch = AsyncMock(side_effect=Exception("DB error"))

    with (
        patch("src.config.get_settings", return_value=_mock_settings()),  # pyright: ignore[reportMissingImports]
        patch("src.db.postgres.get_pool", return_value=fail_pool),  # pyright: ignore[reportMissingImports]
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("OS not init")),  # pyright: ignore[reportMissingImports]
    ):
        from src.graph.place_search_node import place_search_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "없는 장소",
            "intent": "PLACE_SEARCH",
            "processed_query": {},
        }
        result = await place_search_node(state)
        blocks = result["response_blocks"]
        # text_stream만 있고 places/map_markers 없어야 함
        assert len(blocks) == 1
        assert blocks[0]["type"] == "text_stream"
        assert "검색 결과가 없습니다" in blocks[0]["prompt"]
