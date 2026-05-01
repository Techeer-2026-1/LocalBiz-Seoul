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
If conversation history is provided, use it to resolve references like "여기", "거기", "그곳" and to extract missing information (e.g. dates mentioned in a previous turn).

Return a JSON object with these fields:
- "original_query": the original user query (string)
- "expanded_query": expanded/clarified version of the query in Korean (string)
  Examples: "카공" → "콘센트가 있는 카페", "이번 주말 전시" → "서울 무료 전시 2026년"
- "district": Seoul administrative district if mentioned, null otherwise (string or null)
  Examples: "마포구", "강남구", "종로구"
- "neighborhood": neighborhood or area name if mentioned, null otherwise (string or null)
  Examples: "홍대", "이태원", "성수동", "강남역"
- "category": place/event category if mentioned, null otherwise (string or null)
  Examples: "카페", "음식점", "전시회", "축제", "맛집", "숙박", "호텔", "모텔"
- "keywords": list of key descriptive words (array of strings)
  Examples: ["분위기 좋은", "조용한"], ["가성비"], ["데이트"]
- "date_reference": date reference if mentioned, null otherwise (string or null)
  Examples: "이번 주말", "토요일", "내일", "3월"
- "time_reference": time reference if mentioned, null otherwise (string or null)
  Examples: "2시", "저녁", "오후"
- "place_name": specific place name if mentioned in current query or conversation history, null otherwise (string or null)
  Examples: "스타벅스 강남점", "롯데호텔 서울", "한강공원", "A모텔"
- "check_in": check-in date for accommodation if mentioned in current query or conversation history, null otherwise (string or null)
  Format: "YYYY-MM-DD" if exact date, otherwise the raw expression. Examples: "2026-05-10", "5월 10일"
- "check_out": check-out date for accommodation if mentioned in current query or conversation history, null otherwise (string or null)
  Format: "YYYY-MM-DD" if exact date, otherwise the raw expression. Examples: "2026-05-12", "5월 12일"

Always respond with valid JSON only. No markdown, no explanation.
"""


async def _extract_query_fields(
    query: str,
    intent: Optional[str] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """Gemini JSON mode로 쿼리에서 공통 필드 추출.

    Args:
        query: 사용자 원본 쿼리.
        intent: 분류된 intent (GENERAL이면 생략).
        conversation_history: 이전 대화 이력 (place_name/날짜 등 문맥 파싱용).

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
        ]

        # 최근 5턴 대화 이력 포함 — place_name/날짜 문맥 파싱에 활용
        if conversation_history:
            for msg in conversation_history[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                lc_role = "human" if role == "user" else "ai"
                messages.append((lc_role, content))

        messages.append(("human", query))

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

        # PII 유출 방지를 위해 결과의 키 목록과 intent만 로깅
        logger.info("query_preprocessor: intent=%s, extracted_keys=%s", intent, list(result.keys()))
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
    conversation_history = state.get("conversation_history")

    processed = await _extract_query_fields(query, intent, conversation_history)

    return {"processed_query": processed}
