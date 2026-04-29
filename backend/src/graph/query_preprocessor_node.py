"""공통 쿼리 전처리 노드 — 불변식 #12 구현.

Intent Router 직후, 모든 검색 기능 공통으로 실행.
Gemini 2.5 Flash JSON mode로 카테고리/지역/키워드 추출.

GENERAL intent는 전처리 불필요 → 빈 dict 반환.
Gemini 실패 시 빈 dict fallback (검색 노드가 원본 query로 동작).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 전처리 생략 대상 intent (검색 아닌 대화형)
_SKIP_INTENTS: frozenset[str] = frozenset({"GENERAL"})

_PREPROCESS_SYSTEM_PROMPT = """\
You are a query preprocessor for a Seoul local-life AI chatbot.
Extract structured information from the user's query in Korean.

Return a JSON object with these fields:
- "original_query": the original user query (string)
- "expanded_query": expanded/clarified version of the query in Korean (string)
  Examples: "카공" → "콘센트가 있는 카페", "이번 주말 전시" → "서울 무료 전시 2026년"
- "district": Seoul administrative district if mentioned, null otherwise (string or null)
  Examples: "마포구", "강남구", "종로구"
- "neighborhood": neighborhood or area name if mentioned, null otherwise (string or null)
  Examples: "홍대", "이태원", "성수동", "강남역"
- "category": place/event category if mentioned, null otherwise (string or null)
  Examples: "카페", "음식점", "전시회", "축제", "맛집"
- "keywords": list of key descriptive words (array of strings)
  Examples: ["분위기 좋은", "조용한"], ["가성비"], ["데이트"]
- "date_reference": date reference if mentioned, null otherwise (string or null)
  Examples: "이번 주말", "토요일", "내일", "3월"
- "time_reference": time reference if mentioned, null otherwise (string or null)
  Examples: "2시", "저녁", "오후"

Always respond with valid JSON only. No markdown, no explanation.
"""


async def _extract_query_fields(
    query: str,
    intent: Optional[str] = None,
) -> dict[str, Any]:
    """Gemini JSON mode로 쿼리에서 공통 필드 추출.

    Args:
        query: 사용자 원본 쿼리.
        intent: 분류된 intent (GENERAL이면 생략).

    Returns:
        공통 필드 dict. 실패 시 빈 dict.
    """
    if intent in _SKIP_INTENTS:
        return {}

    from langchain_google_genai import ChatGoogleGenerativeAI  # pyright: ignore[reportMissingImports]

    from src.config import get_settings  # pyright: ignore[reportMissingImports]

    settings = get_settings()
    if not settings.gemini_llm_api_key:
        logger.warning("query_preprocessor: GEMINI_LLM_API_KEY 미설정 → 빈 dict")
        return {}

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.gemini_llm_api_key,
            temperature=0,
        )

        messages: list[tuple[str, str]] = [
            ("system", _PREPROCESS_SYSTEM_PROMPT),
            ("human", query),
        ]

        response = await llm.ainvoke(messages)
        text = str(response.content).strip()

        # Gemini가 ```json ... ``` 래핑할 수 있음
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # 필수 필드 보장
        if not isinstance(result, dict):
            logger.warning("query_preprocessor: Gemini 응답이 dict 아님 → 빈 dict")
            return {}

        # original_query 보장
        result.setdefault("original_query", query)
        result.setdefault("expanded_query", query)
        result.setdefault("keywords", [])

        logger.info("query_preprocessor: intent=%s, result=%s", intent, json.dumps(result, ensure_ascii=False)[:200])
        return result

    except Exception:
        logger.exception("query_preprocessor failed → 빈 dict fallback")
        return {}


async def query_preprocessor_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph 공통 쿼리 전처리 노드 (불변식 #12).

    Args:
        state: AgentState dict.

    Returns:
        {"processed_query": dict} — 추출된 공통 필드 또는 빈 dict.
    """
    query = state.get("query", "")
    intent = state.get("intent")

    processed = await _extract_query_fields(query, intent)

    return {"processed_query": processed}
