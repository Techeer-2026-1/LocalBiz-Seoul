"""review_compare_node 단위 테스트 — 8개 케이스.

순수 함수 직접 호출 + AsyncMock으로 pool.fetch / os_client.mget mock.
DB 실연결 없음.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# _extract_place_names
# ---------------------------------------------------------------------------


async def test_extract_place_names_vs() -> None:
    from src.graph.review_compare_node import _extract_place_names  # pyright: ignore[reportMissingImports]

    result = _extract_place_names({}, "스타벅스 vs 블루보틀")
    assert result == ["스타벅스", "블루보틀"]


async def test_extract_place_names_wa() -> None:
    from src.graph.review_compare_node import _extract_place_names  # pyright: ignore[reportMissingImports]

    result = _extract_place_names({}, "스타벅스 와 블루보틀 비교")
    assert result == ["스타벅스", "블루보틀"]


async def test_extract_place_names_single() -> None:
    from src.graph.review_compare_node import _extract_place_names  # pyright: ignore[reportMissingImports]

    result = _extract_place_names({"keywords": ["스타벅스"]}, "스타벅스 리뷰")
    assert result == []


async def test_extract_place_names_disambiguous() -> None:
    """공백 포함 구분자 — 장소명 내 false positive 없음 확인."""
    from src.graph.review_compare_node import _extract_place_names  # pyright: ignore[reportMissingImports]

    result = _extract_place_names({}, "강남대로 vs 홍대")
    assert result == ["강남대로", "홍대"]


# ---------------------------------------------------------------------------
# _fetch_places_pg — 동명 다중 매칭
# ---------------------------------------------------------------------------


async def test_fetch_places_pg_multiple_match() -> None:
    """동명 3개 중 OS stars 최댓값 채택."""
    from src.graph.review_compare_node import _fetch_places_pg  # pyright: ignore[reportMissingImports]

    rows: list[dict[str, Any]] = [
        {"place_id": "uuid-1", "name": "스타벅스 A", "category": "카페", "district": "강남구"},
        {"place_id": "uuid-2", "name": "스타벅스 B", "category": "카페", "district": "마포구"},
        {"place_id": "uuid-3", "name": "스타벅스 C", "category": "카페", "district": "종로구"},
    ]

    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows)

    os_client = MagicMock()
    os_client.mget = AsyncMock(
        return_value={
            "docs": [
                {"found": True, "_source": {"place_id": "uuid-1", "stars": 3.5}},
                {"found": True, "_source": {"place_id": "uuid-2", "stars": 4.2}},
                {"found": True, "_source": {"place_id": "uuid-3", "stars": 4.0}},
            ]
        }
    )

    result = await _fetch_places_pg(pool, ["스타벅스"], os_client)
    assert len(result) == 1
    assert result[0]["place_id"] == "uuid-2"


# ---------------------------------------------------------------------------
# _build_compare_blocks
# ---------------------------------------------------------------------------


async def test_build_compare_blocks_success() -> None:
    """정상 케이스 — text_stream/chart/analysis_sources 구조 검증."""
    from src.graph.review_compare_node import _build_compare_blocks  # pyright: ignore[reportMissingImports]

    places: list[dict[str, Any]] = [
        {"place_id": "uuid-1", "name": "스타벅스 홍대점", "category": "카페"},
        {"place_id": "uuid-2", "name": "블루보틀 삼청점", "category": "카페"},
    ]
    scores_map = {
        "uuid-1": {
            "satisfaction": 3.5,
            "accessibility": 4.0,
            "cleanliness": 3.0,
            "value": 2.5,
            "atmosphere": 4.5,
            "expertise": 4.0,
        },
        "uuid-2": {
            "satisfaction": 4.2,
            "accessibility": 3.0,
            "cleanliness": 4.5,
            "value": 3.0,
            "atmosphere": 4.8,
            "expertise": 4.2,
        },
    }

    blocks = _build_compare_blocks("스타벅스 vs 블루보틀 비교", places, scores_map)

    assert len(blocks) == 3

    ts = blocks[0]
    assert ts["type"] == "text_stream"
    assert "system" in ts
    assert "prompt" in ts

    chart = blocks[1]
    assert chart["type"] == "chart"
    assert chart["chart_type"] == "radar"
    assert len(chart["places"]) == 2
    assert set(chart["places"][0]["scores"].keys()) == {
        "satisfaction",
        "accessibility",
        "cleanliness",
        "value",
        "atmosphere",
        "expertise",
    }

    src = blocks[2]
    assert src["type"] == "analysis_sources"
    assert src["review_count"] == 2


async def test_build_compare_blocks_no_scores() -> None:
    """OS 문서 없는 장소 → scores={} → 에러 없이 chart.places에 포함."""
    from src.graph.review_compare_node import _build_compare_blocks  # pyright: ignore[reportMissingImports]

    places: list[dict[str, Any]] = [
        {"place_id": "uuid-1", "name": "장소A", "category": "카페"},
        {"place_id": "uuid-2", "name": "장소B", "category": "카페"},
    ]

    blocks = _build_compare_blocks("장소A vs 장소B", places, {})

    chart = blocks[1]
    assert len(chart["places"]) == 2
    assert chart["places"][0]["scores"] == {}
    assert chart["places"][1]["scores"] == {}
    assert blocks[2]["review_count"] == 0


# ---------------------------------------------------------------------------
# review_compare_node — disambiguation
# ---------------------------------------------------------------------------


async def test_review_compare_node_disambiguation() -> None:
    """장소명 1개 입력 → disambiguation 블록 반환 (DB 호출 없음)."""
    from src.graph.review_compare_node import review_compare_node  # pyright: ignore[reportMissingImports]

    state: dict[str, Any] = {
        "query": "스타벅스 리뷰",
        "processed_query": {"keywords": ["스타벅스"]},
    }
    result = await review_compare_node(state)

    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "disambiguation"
    assert "어느 장소와 비교하시겠어요?" in blocks[0]["message"]
    assert blocks[0]["candidates"] == []
