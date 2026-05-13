"""place_search_node 단위 테스트.

내부 함수 _search_pg / _search_os + _build_blocks를 직접 테스트.
노드 함수(place_search_node)는 DB/OS 의존성이 있으므로, 순수 함수만 검증.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


_PG_RESULTS: list[dict[str, Any]] = [
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

_OS_RESULTS: list[dict[str, Any]] = [
    {
        "place_id": "os-001",
        "name": "카페B",
        "category": "카페",
        "address": "서울 마포구",
        "district": "마포구",
        "lat": 37.557,
        "lng": 126.924,
        "score": 0.85,
    },
]


async def test_merge_pg_and_os() -> None:
    """PG + OS 결과 병합 → 중복 제거, 상위 5건."""
    from src.graph.place_search_node import _merge_results  # pyright: ignore[reportMissingImports]

    merged = _merge_results(_PG_RESULTS, _OS_RESULTS)
    assert len(merged) == 2
    # OS 결과 우선
    assert merged[0]["place_id"] == "os-001"
    assert merged[1]["place_id"] == "pg-001"


async def test_merge_dedup() -> None:
    """동일 place_id 중복 제거."""
    from src.graph.place_search_node import _merge_results  # pyright: ignore[reportMissingImports]

    dup = [{"place_id": "same-001", "name": "카페"}]
    merged = _merge_results(dup, dup)
    assert len(merged) == 1


async def test_build_blocks_with_results() -> None:
    """검색 결과 있을 때 → text_stream + places + map_markers 블록 생성."""
    from src.graph.place_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("홍대 카페", _PG_RESULTS + _OS_RESULTS, {})
    types = [b["type"] for b in blocks]
    assert "text_stream" in types
    assert "places" in types
    assert "map_markers" in types

    places_block = next(b for b in blocks if b["type"] == "places")
    assert places_block["total_count"] == 2


async def test_build_blocks_empty() -> None:
    """검색 결과 없을 때 → text_stream만, "검색 결과가 없습니다" 포함."""
    from src.graph.place_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("없는 장소", [], {})
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text_stream"
    assert "검색 결과가 없습니다" in blocks[0]["prompt"]


async def test_build_blocks_no_coordinates() -> None:
    """좌표 없는 결과 → map_markers 블록 미생성."""
    from src.graph.place_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    no_coord = [{"place_id": "x", "name": "테스트", "category": "카페", "lat": None, "lng": None}]
    blocks = _build_blocks("테스트", no_coord, {})
    types = [b["type"] for b in blocks]
    assert "text_stream" in types
    assert "places" in types
    assert "map_markers" not in types  # 좌표 없으면 마커 없음
