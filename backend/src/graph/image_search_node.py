"""IMAGE_SEARCH 노드 — Gemini Vision으로 이미지에서 장소 식별.

흐름:
  1. httpx로 이미지 URL 다운로드 → base64 변환
  2. Gemini Vision (gemini-2.5-flash) JSON-mode 분석
     → place_candidates / main_candidate / scene_description / is_identifiable
  3. 분기:
     A. is_identifiable=false → "찾을 수 없어요" text_stream
     B. place_candidates 있음 → PG name ILIKE 검색
        - 1건 또는 main_candidate 있음: text_stream + place 블록
        - 복수 + main_candidate null: text_stream + disambiguation 블록
        - PG 미스: scene_description k-NN fallback
     C. place_candidates 없음 → scene_description 768d 임베딩 → k-NN → places + map_markers

기획서 §4.5 SSE 블록 순서:
  식별 성공: intent → text_stream → place → done
  유사 추천: intent → text_stream → places[] → map_markers → done
  간판 복수: intent → text_stream → disambiguation → done

불변식 #7: gemini-embedding-001 768d
불변식 #8: asyncpg $1,$2 파라미터 바인딩
불변식 #9: Optional[str] 사용 (str | None 금지)
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_OS_TOP_K = 5
_OS_MIN_SCORE = 0.5

_VISION_SYSTEM_PROMPT = """\
당신은 서울 로컬 장소 검색 시스템의 이미지 분석 AI입니다.
이미지를 분석하고 지정된 JSON 형식으로만 응답합니다. 다른 텍스트는 절대 포함하지 마세요.
"""

_VISION_USER_PROMPT = """\
이미지를 분석하고 아래 JSON만 반환하세요.

{
  "place_candidates": ["가게명1", "가게명2"],
  "main_candidate": "가게명1",
  "scene_description": "장소 특징 설명",
  "is_identifiable": true
}

각 필드 규칙:
- place_candidates: 이미지에서 읽힌 가게명/브랜드명/랜드마크명/건물명. 없으면 []
  (간판, 로고, 영수증 텍스트, 지도 텍스트 포함)
- main_candidate: place_candidates 중 이미지 중심 또는 가장 크게 보이는 장소. 판단 불가 또는 후보 없으면 null
- scene_description: 장소 유형/분위기/인테리어/음식/건축 특징을 한국어로 서술. 항상 작성.
  예) "따뜻한 조명의 아늑한 카페, 원목 테이블과 화분 장식"
      "현대적 건물 외관, 1층 편의점 간판, 유리 외벽"
      "한식 음식 사진, 비빔밥과 반찬류"
- is_identifiable: 장소/가게를 찾을 가능성이 있으면 true.
  사람 얼굴이 중심인 셀카, 하늘만 찍힌 사진, 동물 사진은 false.
"""

_IMAGE_SEARCH_SYSTEM_PROMPT = (
    "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다. 이미지 기반 장소 검색 결과를 친절하고 자연스럽게 안내해주세요."
)


# ---------------------------------------------------------------------------
# 이미지 다운로드
# ---------------------------------------------------------------------------
async def _download_image(url: str) -> Optional[str]:
    """이미지 URL → base64 문자열. 실패 시 None."""
    import httpx  # pyright: ignore[reportMissingImports]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            if len(resp.content) > _MAX_IMAGE_BYTES:
                logger.warning("image_search: image too large (%d bytes)", len(resp.content))
                return None
            return base64.b64encode(resp.content).decode("utf-8")
    except Exception:
        logger.exception("image_search: download failed url=%s", url)
        return None


# ---------------------------------------------------------------------------
# Gemini Vision 분석
# ---------------------------------------------------------------------------
async def _analyze_vision(b64_image: str, api_key: str) -> dict[str, Any]:
    """Gemini Vision으로 이미지 분석 → JSON dict.

    실패 시 기본값 반환: place_candidates=[], is_identifiable=False.
    """
    from langchain_core.messages import HumanMessage, SystemMessage  # pyright: ignore[reportMissingImports]
    from langchain_google_genai import ChatGoogleGenerativeAI  # pyright: ignore[reportMissingImports]

    _default: dict[str, Any] = {
        "place_candidates": [],
        "main_candidate": None,
        "scene_description": "",
        "is_identifiable": False,
    }

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0,
        )
        response = await llm.ainvoke(
            [
                SystemMessage(content=_VISION_SYSTEM_PROMPT),
                HumanMessage(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                        },
                        {"type": "text", "text": _VISION_USER_PROMPT},
                    ]
                ),
            ]
        )
        text = str(response.content).strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        return {
            "place_candidates": result.get("place_candidates") or [],
            "main_candidate": result.get("main_candidate"),
            "scene_description": result.get("scene_description") or "",
            "is_identifiable": bool(result.get("is_identifiable", True)),
        }
    except Exception:
        logger.exception("image_search: vision analysis failed")
        return _default


# ---------------------------------------------------------------------------
# DB 검색 헬퍼
# ---------------------------------------------------------------------------
async def _search_pg(pool: Any, name: str) -> list[dict[str, Any]]:
    """장소명으로 places 테이블 검색. 불변식 #8."""
    try:
        rows = await pool.fetch(
            "SELECT place_id, name, category, address, district, "
            "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng "
            "FROM places WHERE is_deleted = false AND name ILIKE $1 LIMIT 5",
            f"%{name}%",
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("image_search: _search_pg failed name=%s", name)
        return []


async def _embed_768d(text: str, api_key: str) -> list[float]:
    """Gemini embedding-001 768d 임베딩. 불변식 #7."""
    import httpx  # pyright: ignore[reportMissingImports]

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
    body = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text[:2000]}]},
        "outputDimensionality": 768,
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data.get("embedding", {}).get("values", [0.0] * 768)


async def _search_knn(os_client: Any, vector: list[float]) -> list[str]:
    """places_vector k-NN HNSW 검색 → place_id 목록."""
    try:
        body: dict[str, Any] = {
            "size": _OS_TOP_K,
            "query": {"knn": {"embedding": {"vector": vector, "k": _OS_TOP_K}}},
            "min_score": _OS_MIN_SCORE,
        }
        result = await os_client.search(index="places_vector", body=body)
        return [h.get("_id", "") for h in result.get("hits", {}).get("hits", [])]
    except Exception:
        logger.exception("image_search: k-NN search failed")
        return []


async def _fetch_places_by_ids(pool: Any, place_ids: list[str]) -> list[dict[str, Any]]:
    """place_id 목록 → places 상세 조회. 불변식 #8."""
    if not place_ids:
        return []
    try:
        rows = await pool.fetch(
            "SELECT place_id, name, category, address, district, "
            "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng "
            "FROM places WHERE place_id = ANY($1::text[]) AND is_deleted = false",
            place_ids,
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("image_search: _fetch_places_by_ids failed")
        return []


# ---------------------------------------------------------------------------
# 블록 생성 헬퍼
# ---------------------------------------------------------------------------
def _text_stream_block(prompt: str) -> dict[str, Any]:
    return {"type": "text_stream", "system": _IMAGE_SEARCH_SYSTEM_PROMPT, "prompt": prompt}


def _place_to_block(place: dict[str, Any]) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "place",
        "place_id": place.get("place_id", ""),
        "name": place.get("name", ""),
    }
    for key in ("category", "address", "district"):
        if place.get(key):
            block[key] = place[key]
    if place.get("lat") is not None:
        block["lat"] = place["lat"]
    if place.get("lng") is not None:
        block["lng"] = place["lng"]
    return block


# ---------------------------------------------------------------------------
# k-NN 흐름 (케이스 B/C 공통)
# ---------------------------------------------------------------------------
async def _run_knn(
    query_text: str,
    api_key: str,
    pool: Any,
    os_client: Optional[Any],
) -> list[dict[str, Any]]:
    """scene_description → 임베딩 → k-NN → places + map_markers 블록."""
    if os_client is None:
        return [
            _text_stream_block("비슷한 장소를 찾으려 했지만 검색 서비스를 이용할 수 없어요. 잠시 후 다시 시도해주세요.")
        ]

    try:
        vector = await _embed_768d(query_text, api_key)
    except Exception:
        logger.exception("image_search: embedding failed")
        return [_text_stream_block("이미지 분석은 완료됐지만 유사 장소 검색 중 오류가 발생했어요. 다시 시도해주세요.")]

    place_ids = await _search_knn(os_client, vector)
    places = await _fetch_places_by_ids(pool, place_ids)

    if not places:
        return [
            _text_stream_block(
                "이미지와 비슷한 분위기의 장소를 찾지 못했어요. "
                "'비슷한 장소를 찾지 못했어요. 장소명을 직접 알려주시면 더 잘 찾아드릴 수 있어요!'라고 안내해주세요."
            )
        ]

    result_summary = "\n".join(
        f"- {p.get('name', '')} ({p.get('category', '')}, {p.get('district', '')})" for p in places
    )
    blocks: list[dict[str, Any]] = [
        _text_stream_block(
            f"이미지 특징: {query_text}\n\n"
            f"비슷한 분위기의 장소:\n{result_summary}\n\n"
            "사진과 비슷한 분위기의 장소들을 친절하게 소개해주세요."
        ),
        {
            "type": "places",
            "items": [_place_to_block(p) for p in places],
            "total_count": len(places),
        },
    ]

    markers = [
        {
            "place_id": p.get("place_id", ""),
            "lat": p["lat"],
            "lng": p["lng"],
            "label": p.get("name", ""),
        }
        for p in places
        if p.get("lat") is not None and p.get("lng") is not None
    ]
    if markers:
        blocks.append({"type": "map_markers", "markers": markers})

    return blocks


# ---------------------------------------------------------------------------
# place_candidates 처리 (케이스 B)
# ---------------------------------------------------------------------------
async def _handle_candidates(
    pool: Any,
    candidates: list[str],
    main_candidate: Optional[str],
    scene_description: str,
    api_key: str,
    os_client: Optional[Any],
) -> list[dict[str, Any]]:
    """place_candidates 있을 때 PG 검색 → place / disambiguation / k-NN fallback."""
    # main_candidate 우선, 나머지 순서로 PG 검색
    search_order = []
    if main_candidate:
        search_order.append(main_candidate)
    for c in candidates:
        if c != main_candidate:
            search_order.append(c)

    pg_results: list[dict[str, Any]] = []
    matched_name = ""
    for name in search_order:
        rows = await _search_pg(pool, name)
        if rows:
            pg_results = rows
            matched_name = name
            break

    # PG 미스 → k-NN fallback
    if not pg_results:
        logger.info("image_search: PG miss for candidates=%s, fallback to k-NN", candidates)
        knn_query = scene_description or (main_candidate or candidates[0])
        return await _run_knn(knn_query, api_key, pool, os_client)

    # 1건 또는 main_candidate 있음 → place 블록
    if len(pg_results) == 1 or main_candidate:
        place = pg_results[0]
        return [
            _text_stream_block(
                f"사용자가 이미지를 보냈습니다. "
                f"'{place.get('name', matched_name)}'을(를) 찾았습니다. "
                f"장소 정보: {place.get('name', '')}, {place.get('category', '')}, {place.get('address', '')}. "
                "이 장소를 친절하게 소개해주세요."
            ),
            _place_to_block(place),
        ]

    # 복수 + main_candidate null → disambiguation
    return [
        _text_stream_block(
            f"이미지에서 여러 장소 후보가 보입니다: {', '.join(r['name'] for r in pg_results)}. "
            "어떤 장소를 찾으시는지 물어봐주세요."
        ),
        {
            "type": "disambiguation",
            "message": "사진에서 여러 장소가 보여요. 어떤 곳이 궁금하신가요?",
            "candidates": [
                {
                    "place_id": r.get("place_id"),
                    "name": r.get("name", ""),
                    "address": r.get("address"),
                    "category": r.get("category"),
                }
                for r in pg_results
            ],
        },
    ]


# ---------------------------------------------------------------------------
# LangGraph 노드
# ---------------------------------------------------------------------------
async def image_search_node(state: dict[str, Any]) -> dict[str, Any]:
    """IMAGE_SEARCH 노드 — 이미지 URL에서 장소 식별.

    Args:
        state: AgentState dict.

    Returns:
        {"response_blocks": [...]}.
    """
    from src.config import get_settings  # pyright: ignore[reportMissingImports]
    from src.db.opensearch import get_os_client  # pyright: ignore[reportMissingImports]
    from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]

    query = state.get("query", "")
    settings = get_settings()
    pool = get_pool()

    os_client: Optional[Any] = None
    try:
        os_client = get_os_client()
    except RuntimeError:
        logger.warning("image_search: OpenSearch client not initialized")

    # 1. 이미지 다운로드
    b64 = await _download_image(query)
    if not b64:
        return {"response_blocks": [_text_stream_block("이미지를 불러오지 못했어요. 다시 시도해주세요.")]}

    # 2. Gemini Vision 분석
    vision = await _analyze_vision(b64, settings.gemini_llm_api_key)
    candidates: list[str] = vision.get("place_candidates") or []
    main_candidate: Optional[str] = vision.get("main_candidate")
    scene_description: str = vision.get("scene_description") or ""
    is_identifiable: bool = bool(vision.get("is_identifiable", True))

    logger.info(
        "image_search: candidates=%s main=%s identifiable=%s",
        candidates,
        main_candidate,
        is_identifiable,
    )

    # 케이스 A: 장소 찾기 불가 이미지
    if not is_identifiable:
        return {
            "response_blocks": [
                _text_stream_block(
                    "이 사진에서는 장소를 찾기 어려워요. "
                    "'가게 간판이나 장소가 보이는 사진을 보내주시면 찾아드릴게요!'라고 친절하게 안내해주세요."
                )
            ]
        }

    # 케이스 B: place_candidates 있음 → PG 검색
    if candidates:
        blocks = await _handle_candidates(
            pool, candidates, main_candidate, scene_description, settings.gemini_llm_api_key, os_client
        )
        return {"response_blocks": blocks}

    # 케이스 C: place_candidates 없음 → scene_description k-NN
    if not scene_description:
        return {
            "response_blocks": [
                _text_stream_block(
                    "이미지에서 장소를 찾을 수 없어요. 가게 간판이나 특징적인 장소가 보이는 사진을 보내주세요."
                )
            ]
        }

    blocks = await _run_knn(scene_description, settings.gemini_llm_api_key, pool, os_client)
    return {"response_blocks": blocks}
