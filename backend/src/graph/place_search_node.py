"""PLACE_SEARCH 노드 — SQL + Vector k-NN 하이브리드 검색.

검색 흐름:
  1. processed_query에서 district/category/keywords 추출
  2. PostgreSQL: places WHERE district/category/name ILIKE + is_deleted=false
  3. OpenSearch: places_vector k-NN HNSW top-10 (min_score 0.5)
  4. 병합: PG + OS → place_id 중복 제거 → 상위 5건
  5. response_blocks: text_stream(요약) + places[] + map_markers

불변식 #2: place_id == places_vector._id
불변식 #7: gemini-embedding-001 768d
불변식 #8: asyncpg $1,$2 바인딩
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_PLACE_SEARCH_SYSTEM_PROMPT = (
    "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다. "
    "사용자의 장소 검색 결과를 친절하게 요약해주세요. "
    "검색 결과가 있으면 핵심 장소 2-3개를 간단히 소개하고, "
    "없으면 '검색 결과가 없습니다'라고 안내하세요."
)

_MAX_RESULTS = 5
_OS_TOP_K = 10
_OS_MIN_SCORE = 0.5
_PG_LIMIT = 10


# ---------------------------------------------------------------------------
# PostgreSQL 검색
# ---------------------------------------------------------------------------
async def _search_pg(
    pool: Any,
    district: Optional[str],
    category: Optional[str],
    keywords: list[str],
    neighborhood: Optional[str],
) -> list[dict[str, Any]]:
    """places 테이블에서 조건부 필터 검색. is_deleted=false 필수.

    필터 전략:
      - district: 자치구 정확 매칭 ("강남구")
      - category: 카테고리 ILIKE ("%카페%")
      - neighborhood: 동/지역명으로 address 또는 name 검색 ("%홍대%")
      - keywords: 첫 번째 키워드로 name 검색 ("%분위기%")
    """
    sql = (
        "SELECT place_id, name, category, address, district, "
        "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng "
        "FROM places WHERE is_deleted = false"
    )
    params: list[Any] = []

    if district:
        params.append(district)
        sql += f" AND district = ${len(params)}"

    if category:
        params.append(f"%{category}%")
        sql += f" AND category ILIKE ${len(params)}"

    if neighborhood:
        # 동/지역명으로 주소 또는 상호명 검색
        params.append(f"%{neighborhood}%")
        sql += f" AND (address ILIKE ${len(params)} OR name ILIKE ${len(params)})"

    if keywords:
        # 키워드로 name 검색 (첫 번째만)
        params.append(f"%{keywords[0]}%")
        sql += f" AND name ILIKE ${len(params)}"

    params.append(_PG_LIMIT)
    sql += f" LIMIT ${len(params)}"

    try:
        rows = await pool.fetch(sql, *params)
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("PG place search failed")
        return []


# ---------------------------------------------------------------------------
# OpenSearch k-NN 검색
# ---------------------------------------------------------------------------
async def _embed_query_768d(query: str, api_key: str) -> list[float]:
    """Gemini embedding-001 768d 단건 임베딩 (async). 불변식 #7."""

    import httpx  # pyright: ignore[reportMissingImports]

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
    body = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": query[:2000]}]},
        "outputDimensionality": 768,
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data.get("embedding", {}).get("values", [0.0] * 768)


async def _search_os(
    os_client: Any,
    query: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """places_vector k-NN HNSW 검색. 쿼리 임베딩 → 유사도 top-K."""
    try:
        query_vector = await _embed_query_768d(query, api_key)

        body: dict[str, Any] = {
            "size": _OS_TOP_K,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_vector,
                        "k": _OS_TOP_K,
                    }
                }
            },
            "min_score": _OS_MIN_SCORE,
        }

        result = await os_client.search(index="places_vector", body=body)
        hits = result.get("hits", {}).get("hits", [])

        places: list[dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source", {})
            places.append(
                {
                    "place_id": hit.get("_id", ""),
                    "name": source.get("name", ""),
                    "category": source.get("category", ""),
                    "address": source.get("address", ""),
                    "district": source.get("district", ""),
                    "lat": source.get("lat"),
                    "lng": source.get("lng"),
                    "score": hit.get("_score", 0),
                }
            )
        return places

    except Exception:
        logger.exception("OS place search failed")
        return []


# ---------------------------------------------------------------------------
# 결과 병합
# ---------------------------------------------------------------------------
def _merge_results(
    pg_results: list[dict[str, Any]],
    os_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """PG + OS 결과 병합. place_id 중복 제거, 상위 N건."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    # OS 결과 우선 (유사도 순)
    for place in os_results:
        pid = place.get("place_id", "")
        if pid and pid not in seen:
            seen.add(pid)
            merged.append(place)

    # PG 결과 추가
    for place in pg_results:
        pid = place.get("place_id", "")
        if pid and pid not in seen:
            seen.add(pid)
            merged.append(place)

    return merged[:_MAX_RESULTS]


# ---------------------------------------------------------------------------
# 블록 생성
# ---------------------------------------------------------------------------
def _build_blocks(
    query: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """검색 결과 → text_stream + places + map_markers 블록."""
    blocks: list[dict[str, Any]] = []

    # 1. text_stream: Gemini 요약 프롬프트
    if results:
        result_summary = "\n".join(
            f"- {r.get('name', '')} ({r.get('category', '')}, {r.get('district', '')})" for r in results
        )
        prompt = f"사용자 질문: {query}\n\n검색 결과:\n{result_summary}\n\n위 결과를 친절하게 요약해주세요."
    else:
        prompt = f"사용자 질문: {query}\n\n검색 결과가 없습니다. 다른 검색어를 제안해주세요."

    blocks.append(
        {
            "type": "text_stream",
            "system": _PLACE_SEARCH_SYSTEM_PROMPT,
            "prompt": prompt,
        }
    )

    # 2. places 블록
    place_items: list[dict[str, Any]] = []
    for r in results:
        item: dict[str, Any] = {
            "type": "place",
            "place_id": r.get("place_id", ""),
            "name": r.get("name", ""),
        }
        if r.get("category"):
            item["category"] = r["category"]
        if r.get("address"):
            item["address"] = r["address"]
        if r.get("district"):
            item["district"] = r["district"]
        if r.get("lat") is not None:
            item["lat"] = r["lat"]
        if r.get("lng") is not None:
            item["lng"] = r["lng"]
        if r.get("congestion"):
            item["congestion"] = r["congestion"]
        place_items.append(item)

    if place_items:
        blocks.append(
            {
                "type": "places",
                "items": place_items,
                "total_count": len(place_items),
            }
        )

    # 3. map_markers 블록 (좌표 있는 결과만)
    markers: list[dict[str, Any]] = []
    for r in results:
        if r.get("lat") is not None and r.get("lng") is not None:
            markers.append(
                {
                    "place_id": r.get("place_id", ""),
                    "lat": r["lat"],
                    "lng": r["lng"],
                    "label": r.get("name", ""),
                }
            )

    if markers:
        blocks.append(
            {
                "type": "map_markers",
                "markers": markers,
            }
        )

    return blocks


# ---------------------------------------------------------------------------
# LangGraph 노드
# ---------------------------------------------------------------------------
async def place_search_node(state: dict[str, Any]) -> dict[str, Any]:
    """PLACE_SEARCH 노드 — PG + OS 하이브리드 검색.

    Args:
        state: AgentState dict.

    Returns:
        {"response_blocks": [text_stream, places, map_markers]}.
    """
    from src.config import get_settings  # pyright: ignore[reportMissingImports]
    from src.db.opensearch import get_os_client  # pyright: ignore[reportMissingImports]
    from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]

    query = state.get("query", "")
    pq = state.get("processed_query") or {}

    district = pq.get("district")
    category = pq.get("category")
    keywords = pq.get("keywords", [])
    neighborhood = pq.get("neighborhood")
    expanded_query = pq.get("expanded_query")

    settings = get_settings()

    import asyncio

    # PG + OS 병렬 검색
    pool = get_pool()
    pg_task = _search_pg(pool, district, category, keywords, neighborhood)

    os_task: Optional[asyncio.Task[list[dict[str, Any]]]] = None
    if settings.gemini_llm_api_key:
        try:
            os_client = get_os_client()
            search_text = expanded_query or query
            os_task = asyncio.create_task(_search_os(os_client, search_text, settings.gemini_llm_api_key))
        except RuntimeError:
            logger.warning("OpenSearch client not initialized, skipping vector search")

    pg_results = await pg_task

    os_results: list[dict[str, Any]] = []
    if os_task is not None:
        os_results = await os_task

    # 병합
    results = _merge_results(pg_results, os_results)

    # congestion 주입 (district 기준 area_proxy, 실패 시 무시)
    try:
        from src.graph.crowdedness_node import fetch_congestion_by_district  # pyright: ignore[reportMissingImports]

        districts = list({r["district"] for r in results if r.get("district")})
        if districts:
            congs = await asyncio.gather(
                *(fetch_congestion_by_district(pool, d) for d in districts),
                return_exceptions=True,
            )
            cong_map = {d: c for d, c in zip(districts, congs, strict=True) if isinstance(c, dict)}
            for r in results:
                d = r.get("district")
                if d and d in cong_map:
                    r["congestion"] = cong_map[d]
    except Exception:
        logger.warning("congestion fetch skipped")

    # 블록 생성
    blocks = _build_blocks(query, results)

    logger.info("place_search: pg=%d, os=%d, merged=%d", len(pg_results), len(os_results), len(results))

    return {"response_blocks": blocks}
