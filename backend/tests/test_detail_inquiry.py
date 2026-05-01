"""detail_inquiry_node 단위 테스트.

순수 함수 _build_detail_blocks / _extract_search_term 테스트. DB 의존성 없음.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


_PLACE_ROW: dict[str, Any] = {
    "place_id": "test-001",
    "name": "스타벅스 종로3가점",
    "category": "카페",
    "address": "서울특별시 종로구 종로 100",
    "district": "종로구",
    "lat": 37.570,
    "lng": 126.990,
}


async def test_build_blocks_with_place() -> None:
    """장소 매칭 성공 → text_stream + place 블록 반환, place_id 포함."""
    from src.graph.detail_inquiry_node import _build_detail_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_detail_blocks("스타벅스 종로3가점 상세", _PLACE_ROW)
    types = [b["type"] for b in blocks]
    assert "text_stream" in types
    assert "place" in types

    place_block = next(b for b in blocks if b["type"] == "place")
    assert place_block["place_id"] == "test-001"
    assert place_block["name"] == "스타벅스 종로3가점"


async def test_build_blocks_no_match() -> None:
    """장소 매칭 실패 → text_stream fallback, place 블록 없음."""
    from src.graph.detail_inquiry_node import _build_detail_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_detail_blocks("없는 장소", None)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text_stream"
    assert "장소를 특정할 수 없습니다" in blocks[0]["prompt"]


async def test_extract_search_term_keywords_first() -> None:
    """keywords가 있으면 우선 사용 (장소명 매칭 목적)."""
    from src.graph.detail_inquiry_node import _extract_search_term  # pyright: ignore[reportMissingImports]

    pq: dict[str, Any] = {"neighborhood": "홍대", "keywords": ["스타벅스"], "expanded_query": "홍대 스타벅스"}
    assert _extract_search_term(pq, "원본") == "스타벅스"


async def test_extract_search_term_fallback() -> None:
    """아무 것도 없으면 fallback_query 반환."""
    from src.graph.detail_inquiry_node import _extract_search_term  # pyright: ignore[reportMissingImports]

    assert _extract_search_term({}, "원본 쿼리") == "원본 쿼리"


async def test_place_block_has_coordinates() -> None:
    """좌표가 있는 장소 → place 블록에 lat/lng 포함."""
    from src.graph.detail_inquiry_node import _build_detail_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_detail_blocks("테스트", _PLACE_ROW)
    place_block = next(b for b in blocks if b["type"] == "place")
    assert place_block["lat"] == 37.570
    assert place_block["lng"] == 126.990
