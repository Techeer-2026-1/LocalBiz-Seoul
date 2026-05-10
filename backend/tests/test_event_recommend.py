"""event_recommend_node 단위 테스트.

내부 헬퍼 함수 _naver_to_event_dict + _build_blocks를 직접 테스트.
노드 함수(event_recommend_node)는 DB/Naver 의존성이 있으므로 머지 후 manual 검증.
event_search_node 테스트 양식과 일관 + EVENT_RECOMMEND 차별화 검증 추가.
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
    from src.graph.event_recommend_node import _naver_to_event_dict  # pyright: ignore[reportMissingImports]

    item = {
        "title": "<b>전시회</b> 추천 - 주말 갈 만한 곳",
        "link": "https://blog.naver.com/example/456",
        "description": "<b>전시회</b>는 정말 좋았어요...",
        "bloggername": "test_blogger",
        "postdate": "20260501",
    }
    event = _naver_to_event_dict(item)

    assert event["title"] == "전시회 추천 - 주말 갈 만한 곳"
    assert event["summary"] == "전시회는 정말 좋았어요..."
    assert event["detail_url"] == "https://blog.naver.com/example/456"
    assert event["source"] == "naver_blog"
    assert event["event_id"] is None
    assert event["category"] is None
    assert event["address"] is None


async def test_naver_to_event_dict_missing_fields() -> None:
    """Naver 응답에 일부 필드 누락 시 None으로 안전 처리."""
    from src.graph.event_recommend_node import _naver_to_event_dict  # pyright: ignore[reportMissingImports]

    item = {"title": "단순 제목"}
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
    """DB events만 있을 때 — EVENT_RECOMMEND 차별화: references에 DB detail_url 포함."""
    from src.graph.event_recommend_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("이번 주말 송파구 행사 추천", _DB_EVENTS)

    block_types = [b["type"] for b in blocks]
    assert "text_stream" in block_types
    assert "events" in block_types
    # EVENT_SEARCH와 차별화: DB 행사도 detail_url 있으면 references에 포함
    assert "references" in block_types

    events_block = next(b for b in blocks if b["type"] == "events")
    assert events_block["total_count"] == 1
    item = events_block["items"][0]
    assert item["title"] == "재즈 페스티벌"
    assert item["category"] == "공연"
    assert item["district"] == "송파구"

    refs_block = next(b for b in blocks if b["type"] == "references")
    assert len(refs_block["items"]) == 1
    assert refs_block["items"][0]["url"] == "https://example.com/event/1"
    assert refs_block["items"][0]["source"] == "서울시문화행사"


async def test_build_blocks_with_naver_fallback() -> None:
    """DB + Naver 통합 시 references 블록에 양쪽 출처 모두 포함."""
    from src.graph.event_recommend_node import _build_blocks  # pyright: ignore[reportMissingImports]

    merged = _DB_EVENTS + _NAVER_EVENTS
    blocks = _build_blocks("주말 전시회 추천", merged)

    block_types = [b["type"] for b in blocks]
    assert "text_stream" in block_types
    assert "events" in block_types
    assert "references" in block_types

    refs_block = next(b for b in blocks if b["type"] == "references")
    assert len(refs_block["items"]) == 2
    sources = {r["source"] for r in refs_block["items"]}
    assert sources == {"서울시문화행사", "naver_blog"}


async def test_build_blocks_recommend_prompt_keywords() -> None:
    """EVENT_RECOMMEND 차별화: text_stream prompt에 추천 사유 강조 키워드 포함."""
    from src.graph.event_recommend_node import _build_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_blocks("강남 전시회 추천", _DB_EVENTS)

    ts_block = next(b for b in blocks if b["type"] == "text_stream")
    prompt = ts_block["prompt"]
    system = ts_block["system"]

    # 추천 사유 강조 키워드가 prompt 또는 system에 등장
    assert "추천" in prompt or "추천" in system
    assert "이유" in prompt or "이유" in system

    # 빈 결과 시에도 안내 메시지에 추천 단어 포함
    empty_blocks = _build_blocks("결과 없는 쿼리", [])
    empty_ts = next(b for b in empty_blocks if b["type"] == "text_stream")
    assert "추천" in empty_ts["prompt"] or "다른 조건" in empty_ts["prompt"]
