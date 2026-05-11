"""analysis_node 단위 테스트 — 7개 케이스.

순수 함수 직접 호출 + AsyncMock으로 pool.fetch / os_client.mget mock.
DB 실연결 없음.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# _extract_place_name
# ---------------------------------------------------------------------------


async def test_extract_place_name_from_processed_query() -> None:
    """processed_query.place_name 있으면 반환."""
    from src.graph.analysis_node import _extract_place_name  # pyright: ignore[reportMissingImports]

    result = _extract_place_name({"place_name": "스타벅스 홍대점"}, "스타벅스 분석")
    assert result == "스타벅스 홍대점"


async def test_extract_place_name_from_keywords() -> None:
    """place_name 없고 keywords[0] fallback."""
    from src.graph.analysis_node import _extract_place_name  # pyright: ignore[reportMissingImports]

    result = _extract_place_name({"keywords": ["블루보틀", "카페"]}, "블루보틀 분석")
    assert result == "블루보틀"


async def test_extract_place_name_none() -> None:
    """둘 다 없으면 None."""
    from src.graph.analysis_node import _extract_place_name  # pyright: ignore[reportMissingImports]

    result = _extract_place_name({}, "분석해줘")
    assert result is None


# ---------------------------------------------------------------------------
# _fetch_place_pg — 동명 다중 매칭
# ---------------------------------------------------------------------------


async def test_fetch_place_pg_multiple_match() -> None:
    """동명 3개 중 OS stars 최댓값 채택."""
    from src.graph.analysis_node import _fetch_place_pg  # pyright: ignore[reportMissingImports]

    rows: list[dict[str, Any]] = [
        {"place_id": "uuid-1", "name": "스타벅스 A", "category": "카페", "district": "강남구"},
        {"place_id": "uuid-2", "name": "스타벅스 B", "category": "카페", "district": "마포구"},
        {"place_id": "uuid-3", "name": "스타벅스 C", "category": "카페", "district": "종로구"},
    ]

    mock_pool = MagicMock()
    mock_pool.fetch = AsyncMock(return_value=rows)

    mock_os = MagicMock()
    mock_os.mget = AsyncMock(
        return_value={
            "docs": [
                {"found": True, "_source": {"place_id": "uuid-1", "stars": 3.5}},
                {"found": True, "_source": {"place_id": "uuid-2", "stars": 4.2}},
                {"found": True, "_source": {"place_id": "uuid-3", "stars": 4.0}},
            ]
        }
    )

    result = await _fetch_place_pg(mock_pool, "스타벅스", mock_os)
    assert result is not None
    assert result["place_id"] == "uuid-2"


# ---------------------------------------------------------------------------
# analysis_node — 정상 흐름
# ---------------------------------------------------------------------------


async def test_analysis_node_success() -> None:
    """정상 — text_stream + analysis_sources 블록 반환."""
    from src.graph.analysis_node import analysis_node  # pyright: ignore[reportMissingImports]

    mock_pool = MagicMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            {"place_id": "uuid-1", "name": "스타벅스 홍대점", "category": "카페", "district": "마포구"},
        ]
    )

    mock_os = MagicMock()
    mock_os.mget = AsyncMock(
        return_value={
            "docs": [
                {
                    "found": True,
                    "_source": {
                        "place_id": "uuid-1",
                        "_raw_scores": {
                            "satisfaction": 3.5,
                            "accessibility": 4.0,
                            "cleanliness": 3.8,
                            "value": 3.2,
                            "atmosphere": 4.5,
                            "expertise": 4.0,
                        },
                        "review_count": 45,
                    },
                }
            ]
        }
    )

    with (
        patch("src.db.postgres.get_pool", return_value=mock_pool),
        patch("src.db.opensearch.get_os_client", return_value=mock_os),
    ):
        state: dict[str, Any] = {
            "query": "스타벅스 홍대점 분석해줘",
            "processed_query": {"place_name": "스타벅스 홍대점"},
        }
        result = await analysis_node(state)

    blocks = result["response_blocks"]
    assert len(blocks) == 2

    ts = blocks[0]
    assert ts["type"] == "text_stream"
    assert "스타벅스 홍대점" in ts["prompt"]
    assert "system" in ts

    src = blocks[1]
    assert src["type"] == "analysis_sources"
    assert src["review_count"] == 45


# ---------------------------------------------------------------------------
# analysis_node — OS 점수 없음
# ---------------------------------------------------------------------------


async def test_analysis_node_no_reviews() -> None:
    """OS 문서 없음 → text_stream + analysis_sources(review_count=0)."""
    from src.graph.analysis_node import analysis_node  # pyright: ignore[reportMissingImports]

    mock_pool = MagicMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            {"place_id": "uuid-1", "name": "새로운카페", "category": "카페", "district": "강남구"},
        ]
    )

    mock_os = MagicMock()
    mock_os.mget = AsyncMock(return_value={"docs": [{"found": False}]})

    with (
        patch("src.db.postgres.get_pool", return_value=mock_pool),
        patch("src.db.opensearch.get_os_client", return_value=mock_os),
    ):
        state: dict[str, Any] = {
            "query": "새로운카페 분석해줘",
            "processed_query": {"place_name": "새로운카페"},
        }
        result = await analysis_node(state)

    blocks = result["response_blocks"]
    assert len(blocks) == 2
    assert blocks[0]["type"] == "text_stream"
    assert "리뷰 데이터: 없음" in blocks[0]["prompt"]
    assert blocks[1]["type"] == "analysis_sources"
    assert blocks[1]["review_count"] == 0


# ---------------------------------------------------------------------------
# _fetch_scores_os — review_count null 방어
# ---------------------------------------------------------------------------


async def test_fetch_scores_os_null_review_count() -> None:
    """OS 문서에 review_count=null → 0으로 방어."""
    from src.graph.analysis_node import _fetch_scores_os  # pyright: ignore[reportMissingImports]

    mock_os = MagicMock()
    mock_os.mget = AsyncMock(
        return_value={
            "docs": [
                {
                    "found": True,
                    "_source": {
                        "place_id": "uuid-1",
                        "_raw_scores": {"satisfaction": 3.5},
                        "review_count": None,
                    },
                }
            ]
        }
    )

    scores, count = await _fetch_scores_os(mock_os, "uuid-1")
    assert count == 0
    assert scores == {"satisfaction": 3.5}


# ---------------------------------------------------------------------------
# analysis_node — 장소 미발견
# ---------------------------------------------------------------------------


async def test_analysis_node_place_not_found() -> None:
    """PG 0건 → disambiguation."""
    from src.graph.analysis_node import analysis_node  # pyright: ignore[reportMissingImports]

    mock_pool = MagicMock()
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_os = MagicMock()

    with (
        patch("src.db.postgres.get_pool", return_value=mock_pool),
        patch("src.db.opensearch.get_os_client", return_value=mock_os),
    ):
        state: dict[str, Any] = {
            "query": "없는장소 분석해줘",
            "processed_query": {"place_name": "없는장소"},
        }
        result = await analysis_node(state)

    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "disambiguation"
    assert "찾을 수 없" in blocks[0]["message"]


# ---------------------------------------------------------------------------
# analysis_node — place_name 추출 실패
# ---------------------------------------------------------------------------


async def test_analysis_node_no_place_name() -> None:
    """place_name 추출 실패 → disambiguation."""
    from src.graph.analysis_node import analysis_node  # pyright: ignore[reportMissingImports]

    state: dict[str, Any] = {
        "query": "분석해줘",
        "processed_query": {},
    }
    result = await analysis_node(state)

    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "disambiguation"
    assert "장소명을 알려주세요" in blocks[0]["message"]
