"""event_search_node 단위 테스트.

내부 헬퍼 함수 _naver_to_event_dict + _build_blocks를 직접 테스트.
노드 함수(event_search_node)는 DB/Naver 의존성이 있으므로 머지 후 manual 검증.
place_search_node 테스트 양식과 일관.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# _naver_to_event_dict — Naver 응답 변환
# ---------------------------------------------------------------------------
async def test_naver_to_event_dict_html_clean() -> None:
    """Naver 검색 결과의 <b> 태그 강조 표시 → 평문 변환."""
    from src.graph.event_search_node import _naver_to_event_dict  # pyright: ignore[reportMissingImports]

    item = {
        "title": "<b>전시회</b> 후기 - 이번 주말 추천",
        "link": "https://blog.naver.com/example/123",
        "description": "<b>전시회</b>는 정말 좋았어요...",
        "bloggername": "test_blogger",
        "postdate": "20260501",
    }
    event = _naver_to_event_dict(item)

    assert event["title"] == "전시회 후기 - 이번 주말 추천"
    assert event["summary"] == "전시회는 정말 좋았어요..."
    assert event["detail_url"] == "https://blog.naver.com/example/123"
    assert event["source"] == "naver_blog"
    # DB 전용 필드는 None
    assert event["event_id"] is None
    assert event["category"] is None
    assert event["address"] is None


async def test_naver_to_event_dict_missing_fields() -> None:
    """Naver 응답에 일부 필드 누락 시 None으로 안전 처리."""
    from src.graph.event_search_node import _naver_to_event_dict  # pyright: ignore[reportMissingImports]

    item = {"title": "단순 제목"}  # link, description 등 없음
    event = _naver_to_event_dict(item)

    assert event["title"] == "단순 제목"
    assert event["summary"] == ""
    assert event["detail_url"] is None
    assert event["source"] == "naver_blog"


# ---------------------------------------------------------------------------
# _build_blocks — 결과 → 블록 변환
# ---------------------------------------------------------------------------
_DB_EVENTS: list[dict[str, Any]] = [
    {
        "event_id": "01234567-89ab-cdef-0123-456789abcdef",
        "title": "재즈 페스티벌",
        "category": "공연",
        "place_name": "올림픽공원",
        "address": "서울 송파구",
        "district": "송파구",
        "lat": 37.520,
        "lng": 127.121,
        "date_start": "2026-05-10",
        "date_end": "2026-05-12",
        "price": 50000,
        "poster_url": "https://example.com/poster.jpg",
        "detail_url": "https://example.com/event/1",
        "summary": "재즈 음악 축제",
        "source": "서울시문화행사",
    },
]

_NAVER_EVENTS: list[dict[str, Any]] = [
    {
        "event_id": None,
        "title": "전시회 추천 블로그",
        "category": None,
        "place_name": None,
        "address": None,
        "district": None,
        "lat": None,
        "lng": None,
        "date_start": None,
        "date_end": None,
        "price": None,
        "poster_url": None,
        "detail_url": "https://blog.naver.com/example",
        "summary": "이번 주말 갈만한 전시회 모음",
        "source": "naver_blog",
    },
]


async def test_build_blocks_with_db_events_only() -> None:
    """DB events만 있을 때: text_stream + events 블록 (references 없음)."""
    from src.graph.event_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("이번 주말 송파구 행사", _DB_EVENTS)

    block_types = [b["type"] for b in blocks]
    assert "text_stream" in block_types
    assert "events" in block_types
    assert "references" not in block_types  # DB 결과만이라 references 없음

    # events 블록 내용 검증
    events_block = next(b for b in blocks if b["type"] == "events")
    assert events_block["total_count"] == 1
    item = events_block["items"][0]
    assert item["title"] == "재즈 페스티벌"
    assert item["category"] == "공연"
    assert item["district"] == "송파구"
    assert item["price"] == 50000


async def test_build_blocks_with_naver_fallback() -> None:
    """Naver fallback 결과 포함 시: references 블록 추가."""
    from src.graph.event_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    merged = _DB_EVENTS + _NAVER_EVENTS
    blocks = _build_blocks("주말 전시회", merged)

    block_types = [b["type"] for b in blocks]
    assert "text_stream" in block_types
    assert "events" in block_types
    assert "references" in block_types

    # references는 Naver 결과만 포함
    refs_block = next(b for b in blocks if b["type"] == "references")
    assert len(refs_block["items"]) == 1
    assert refs_block["items"][0]["url"] == "https://blog.naver.com/example"
    assert refs_block["items"][0]["source"] == "naver_blog"


async def test_build_blocks_empty_results() -> None:
    """검색 결과 0건: text_stream 블록만 생성 (events / references 없음)."""
    from src.graph.event_search_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("결과 없는 쿼리", [])

    block_types = [b["type"] for b in blocks]
    assert "text_stream" in block_types
    assert "events" not in block_types
    assert "references" not in block_types

    # text_stream에 "검색 결과가 없습니다" 안내
    ts_block = next(b for b in blocks if b["type"] == "text_stream")
    assert "검색 결과가 없습니다" in ts_block["prompt"]
