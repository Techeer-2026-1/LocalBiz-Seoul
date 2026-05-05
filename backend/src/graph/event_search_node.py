"""EVENT_SEARCH 노드 — DB 우선 → Naver fallback 행사 검색.

검색 흐름:
  1. processed_query에서 district/category/keywords/date_reference 추출
  2. PostgreSQL: events WHERE district/category/title ILIKE
     + date_end >= NOW() (지난 행사 자동 제외)
  3. PG 결과 충분(>=3건) → DB 결과만 반환
  4. PG 결과 부족(<3건) → Naver 블로그 검색 API fallback (graceful degradation)
  5. response_blocks: text_stream(요약) + events[] + references[]

불변식 #8: asyncpg $1,$2 바인딩
불변식 #13: DB 우선 → fallback (외부 API)
불변식 #19: 사용자 query / API 키 logger 진입 금지

Naver API:
  - Endpoint: https://openapi.naver.com/v1/search/blog.json
  - 인증: X-Naver-Client-Id, X-Naver-Client-Secret 헤더
  - 일 25,000회 호출 한도 (Phase 1은 caching 미구현)
  - timeout 5초
  - 실패 시 graceful degradation (빈 list 반환)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_EVENT_SEARCH_SYSTEM_PROMPT = (
    "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다. "
    "사용자의 행사 검색 결과를 친절하게 요약해주세요. "
    "검색 결과가 있으면 핵심 행사 2-3개를 간단히 소개하고, "
    "없으면 '검색 결과가 없습니다'라고 안내하세요."
)

_MAX_RESULTS = 5
_MIN_PG_RESULTS = 3  # PG 결과가 이 개수 미만이면 Naver fallback 호출
_PG_LIMIT = 10
_NAVER_DISPLAY = 5  # Naver API에서 가져올 최대 결과 수
_NAVER_TIMEOUT = 5.0  # 초
_NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"


# ---------------------------------------------------------------------------
# PostgreSQL 검색
# ---------------------------------------------------------------------------
async def _search_pg(
    pool: Any,
    district: Optional[str],
    category: Optional[str],
    keywords: list[str],
) -> list[dict[str, Any]]:
    """events 테이블에서 조건부 필터 검색. 지난 행사 제외 강제.

    필터 전략:
      - district: 자치구 정확 매칭 ("강남구")
      - category: 카테고리 ILIKE ("%전시회%")
      - keywords: 첫 번째 키워드로 title 검색 ("%재즈%")
      - date_end >= NOW(): 지난 행사 자동 제외 (Phase 1 단순화)
    """
    sql = (
        "SELECT event_id, title, category, place_name, address, district, "
        "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng, "
        "date_start, date_end, price, poster_url, detail_url, summary, source "
        "FROM events WHERE date_end >= NOW()"
    )
    params: list[Any] = []

    if district:
        params.append(district)
        sql += f" AND district = ${len(params)}"

    if category:
        params.append(f"%{category}%")
        sql += f" AND category ILIKE ${len(params)}"

    if keywords:
        # 키워드로 title 검색 (첫 번째만)
        params.append(f"%{keywords[0]}%")
        sql += f" AND title ILIKE ${len(params)}"

    params.append(_PG_LIMIT)
    sql += f" ORDER BY date_start ASC LIMIT ${len(params)}"

    try:
        rows = await pool.fetch(sql, *params)
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("PG event search failed")
        return []


# ---------------------------------------------------------------------------
# Naver 검색 API fallback
# ---------------------------------------------------------------------------
async def _search_naver(
    query: str,
    client_id: str,
    client_secret: str,
) -> list[dict[str, Any]]:
    """Naver 블로그 검색 API 호출. 실패 시 graceful degradation (빈 list).

    Args:
        query: 검색어 (사용자 query 또는 키워드 조합)
        client_id: NAVER_CLIENT_ID
        client_secret: NAVER_CLIENT_SECRET

    Returns:
        Naver items[] 원본 list (변환은 _naver_to_event_dict).

    실패 시 (timeout, 5xx, 인증 오류):
        빈 list 반환 + logger.warning. 사용자에겐 PG 결과만 노출.
    """
    if not client_id or not client_secret:
        logger.warning("naver search skipped: client_id or client_secret empty")
        return []

    import httpx  # pyright: ignore[reportMissingImports]

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": _NAVER_DISPLAY,
        "sort": "sim",  # 정확도순
    }

    try:
        async with httpx.AsyncClient(timeout=_NAVER_TIMEOUT) as client:
            resp = await client.get(_NAVER_BLOG_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        return list(data.get("items", []))
    except Exception:
        logger.exception("naver event search failed (graceful degradation)")
        return []


def _naver_to_event_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Naver 블로그 검색 응답 item → 우리 events dict 양식 변환.

    Naver 응답 양식:
      - title: 블로그 제목 (HTML <b> 태그 포함 가능)
      - link: 블로그 URL
      - description: 본문 일부 (HTML 태그 포함 가능)
      - bloggername: 블로거 이름
      - postdate: 게시일 (YYYYMMDD)

    우리 events 양식 (event_id 등 DB 필드는 None):
      - title, summary, detail_url, source 만 채움.
    """
    # <b> 태그 제거 (Naver 검색 결과 강조 표시)
    title_clean = re.sub(r"</?b>", "", item.get("title") or "")
    desc_clean = re.sub(r"</?b>", "", item.get("description") or "")

    return {
        "event_id": None,
        "title": title_clean,
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
        "detail_url": item.get("link"),
        "summary": desc_clean,
        "source": "naver_blog",
    }


# ---------------------------------------------------------------------------
# 블록 생성
# ---------------------------------------------------------------------------
def _build_blocks(
    query: str,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """검색 결과 → text_stream + events + references 블록.

    events 중 source='naver_blog' 항목은 references[] 블록에 추가 노출 (출처 링크).
    """
    blocks: list[dict[str, Any]] = []

    # 1. text_stream: Gemini 요약 프롬프트
    if events:
        result_summary = "\n".join(
            f"- {e.get('title', '')} ({e.get('category') or '카테고리 미정'}, "
            f"{e.get('district') or e.get('source', '')})"
            for e in events
        )
        prompt = f"사용자 질문: {query}\n\n검색 결과:\n{result_summary}\n\n위 결과를 친절하게 요약해주세요."
    else:
        prompt = f"사용자 질문: {query}\n\n검색 결과가 없습니다. 다른 검색어를 제안해주세요."

    blocks.append(
        {
            "type": "text_stream",
            "system": _EVENT_SEARCH_SYSTEM_PROMPT,
            "prompt": prompt,
        }
    )

    # 2. events 블록 (DB + Naver 통합)
    event_items: list[dict[str, Any]] = []
    for e in events:
        item: dict[str, Any] = {
            "type": "event",
            "title": e.get("title", ""),
        }
        # DB 행사만 가지는 필드 (Naver는 None)
        if e.get("event_id") is not None:
            item["event_id"] = e["event_id"]
        if e.get("category"):
            item["category"] = e["category"]
        if e.get("place_name"):
            item["place_name"] = e["place_name"]
        if e.get("address"):
            item["address"] = e["address"]
        if e.get("district"):
            item["district"] = e["district"]
        if e.get("lat") is not None:
            item["lat"] = e["lat"]
        if e.get("lng") is not None:
            item["lng"] = e["lng"]
        if e.get("date_start") is not None:
            item["date_start"] = str(e["date_start"])
        if e.get("date_end") is not None:
            item["date_end"] = str(e["date_end"])
        if e.get("price") is not None:
            item["price"] = e["price"]
        if e.get("poster_url"):
            item["poster_url"] = e["poster_url"]
        if e.get("detail_url"):
            item["detail_url"] = e["detail_url"]
        if e.get("summary"):
            item["summary"] = e["summary"]
        if e.get("source"):
            item["source"] = e["source"]
        event_items.append(item)

    if event_items:
        blocks.append(
            {
                "type": "events",
                "items": event_items,
                "total_count": len(event_items),
            }
        )

    # 3. references 블록 (Naver fallback 결과만 — 출처 링크)
    references: list[dict[str, Any]] = []
    for e in events:
        if e.get("source") == "naver_blog" and e.get("detail_url"):
            references.append(
                {
                    "title": e.get("title", ""),
                    "url": e["detail_url"],
                    "source": "naver_blog",
                }
            )

    if references:
        blocks.append(
            {
                "type": "references",
                "items": references,
            }
        )

    return blocks


# ---------------------------------------------------------------------------
# LangGraph 노드
# ---------------------------------------------------------------------------
async def event_search_node(state: dict[str, Any]) -> dict[str, Any]:
    """EVENT_SEARCH 노드 — DB 우선 → Naver fallback 행사 검색.

    Args:
        state: AgentState dict (query, processed_query 등).

    Returns:
        {"response_blocks": [text_stream, events, references?]}.
    """
    from src.config import get_settings  # pyright: ignore[reportMissingImports]
    from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]

    query = state.get("query", "")
    pq = state.get("processed_query") or {}

    district = pq.get("district")
    category = pq.get("category")
    keywords = pq.get("keywords", [])

    settings = get_settings()
    pool = get_pool()

    # 1) PostgreSQL 검색 (DB 우선)
    pg_events = await _search_pg(pool, district, category, keywords)

    # 2) PG 결과 부족 시 Naver fallback
    naver_events: list[dict[str, Any]] = []
    if len(pg_events) < _MIN_PG_RESULTS:
        # 검색어 조합: keywords 우선, 없으면 query 자체 (앞 100자)
        naver_query = " ".join(keywords) if keywords else query[:100]
        naver_items = await _search_naver(
            naver_query,
            settings.naver_client_id,
            settings.naver_client_secret,
        )
        naver_events = [_naver_to_event_dict(item) for item in naver_items]

    # 3) 통합 (DB 결과 + Naver fallback) — 상위 _MAX_RESULTS건
    merged = (pg_events + naver_events)[:_MAX_RESULTS]

    # 4) 블록 생성
    blocks = _build_blocks(query, merged)

    logger.info(
        "event_search: pg=%d, naver=%d, merged=%d (district=%s, category=%s)",
        len(pg_events),
        len(naver_events),
        len(merged),
        district,
        category,
    )

    return {"response_blocks": blocks}
