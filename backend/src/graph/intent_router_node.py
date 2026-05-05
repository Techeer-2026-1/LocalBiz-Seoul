"""LangGraph intent router 노드 — 15 intent 분류.

기획서 section 3.1 권위. 14 핵심 intent + 1 fallback (GENERAL).
Gemini 2.5 Flash JSON-mode로 분류 (Phase 1 본작업에서 구현).
"""

from __future__ import annotations

import logging
from enum import StrEnum  # pyright: ignore[reportAttributeAccessIssue]
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IntentType(StrEnum):  # pyright: ignore[reportAttributeAccessIssue]
    """기획서 section 3.1 — 15 intent (14+1). 추가/변경 시 PM 합의 + 기획서 동기화."""

    # Phase 1
    PLACE_SEARCH = "PLACE_SEARCH"
    PLACE_RECOMMEND = "PLACE_RECOMMEND"
    EVENT_SEARCH = "EVENT_SEARCH"
    EVENT_RECOMMEND = "EVENT_RECOMMEND"
    COURSE_PLAN = "COURSE_PLAN"
    DETAIL_INQUIRY = "DETAIL_INQUIRY"
    BOOKING = "BOOKING"
    CALENDAR = "CALENDAR"
    FAVORITE = "FAVORITE"
    # Phase 1 (기획서 v2 SSE L155)
    REVIEW_COMPARE = "REVIEW_COMPARE"
    ANALYSIS = "ANALYSIS"
    COST_ESTIMATE = "COST_ESTIMATE"
    CROWDEDNESS = "CROWDEDNESS"
    IMAGE_SEARCH = "IMAGE_SEARCH"
    # Fallback
    GENERAL = "GENERAL"


# Phase 1 intent (기획서 기준 전체 목록)
PHASE1_INTENTS: frozenset[IntentType] = frozenset(  # pyright: ignore[reportAssignmentType]
    {
        IntentType.PLACE_SEARCH,
        IntentType.PLACE_RECOMMEND,
        IntentType.EVENT_SEARCH,
        IntentType.EVENT_RECOMMEND,
        IntentType.COURSE_PLAN,
        IntentType.DETAIL_INQUIRY,
        IntentType.BOOKING,
        IntentType.CALENDAR,
        IntentType.FAVORITE,
        IntentType.REVIEW_COMPARE,
        IntentType.IMAGE_SEARCH,
        IntentType.GENERAL,
    }
)

# 실제 그래프에 라우팅 가능한 intent (real_builder.py conditional_edges 기준)
# 여기에 없는 Phase 1 intent는 GENERAL fallback 처리
_ROUTABLE_INTENTS: frozenset[IntentType] = frozenset(  # pyright: ignore[reportAssignmentType]
    {
        IntentType.PLACE_SEARCH,
        IntentType.PLACE_RECOMMEND,
        IntentType.EVENT_SEARCH,
        IntentType.EVENT_RECOMMEND,
        IntentType.COURSE_PLAN,
        IntentType.DETAIL_INQUIRY,
        IntentType.BOOKING,
        IntentType.CALENDAR,
        IntentType.REVIEW_COMPARE,
        IntentType.IMAGE_SEARCH,
        IntentType.GENERAL,
    }
)


_GENERAL_FALLBACK: IntentType = IntentType.GENERAL  # pyright: ignore[reportAssignmentType]


_CLASSIFY_SYSTEM_PROMPT = """\
You are an intent classifier for a Seoul local-life AI chatbot.
Classify the user query into exactly ONE of these intents:

Phase 1 (active):
- PLACE_SEARCH: searching for specific places (restaurants, cafes, etc.)
- PLACE_RECOMMEND: asking for place recommendations
- EVENT_SEARCH: searching for cultural events, festivals, exhibitions
- EVENT_RECOMMEND: asking for event recommendations
- COURSE_PLAN: planning a course/itinerary with multiple stops
- DETAIL_INQUIRY: asking detailed info about a specific place or event
- BOOKING: requesting a reservation or booking link
- CALENDAR: adding an event to calendar
- FAVORITE: bookmarking or favoriting something
- REVIEW_COMPARE: comparing two or more places by 6 metrics (satisfaction/accessibility/cleanliness/value/atmosphere/expertise)
- IMAGE_SEARCH: user sends an image URL (http/https link ending in image extension or storage URL) to identify a place or find similar places
- GENERAL: general conversation, greetings, or anything else

Phase 2 (not yet active, classify as GENERAL for now):
- ANALYSIS, COST_ESTIMATE, CROWDEDNESS

Respond in JSON: {"intent": "INTENT_NAME", "confidence": 0.0-1.0}
"""


async def classify_intent(
    query: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> tuple[IntentType, float]:
    """사용자 쿼리 → (IntentType, confidence) 분류.

    Gemini 2.5 Flash JSON-mode로 15 intent 중 하나를 분류.
    실패 시 (GENERAL, 0.0) fallback.

    Args:
        query: 사용자 원본 쿼리.
        conversation_history: 이전 대화 이력 (multi-turn 문맥용).

    Returns:
        (intent, confidence) 튜플.
    """
    import json

    from langchain_google_genai import ChatGoogleGenerativeAI

    from src.config import get_settings  # pyright: ignore[reportMissingImports]

    settings = get_settings()
    if not settings.gemini_llm_api_key:
        logger.warning("classify_intent: GEMINI_LLM_API_KEY 미설정 → GENERAL fallback")
        return (_GENERAL_FALLBACK, 0.0)

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.gemini_llm_api_key,
            temperature=0,
        )

        messages: list[tuple[str, str]] = [("system", _CLASSIFY_SYSTEM_PROMPT)]

        # 대화 이력 포함 (최근 5턴)
        if conversation_history:
            for msg in conversation_history[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                lc_role = "human" if role == "user" else "ai"
                messages.append((lc_role, content))

        messages.append(("human", query))

        response = await llm.ainvoke(messages)
        text = str(response.content).strip()

        # JSON 파싱
        # Gemini가 ```json ... ``` 래핑할 수 있음
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        intent_str = result.get("intent", "GENERAL")
        confidence = float(result.get("confidence", 0.0))

        # Phase 2 intent → GENERAL fallback
        try:
            intent = IntentType(intent_str)
        except ValueError:
            logger.warning("classify_intent: 알 수 없는 intent=%s → GENERAL", intent_str)
            return (_GENERAL_FALLBACK, 0.0)

        if intent not in PHASE1_INTENTS:
            logger.info("classify_intent: Phase 2 intent=%s → GENERAL", intent.value)
            return (_GENERAL_FALLBACK, confidence)

        # 라우팅 맵에 없는 intent는 GENERAL fallback (노드 미구현)
        if intent not in _ROUTABLE_INTENTS:
            logger.info("classify_intent: 라우팅 불가 intent=%s → GENERAL", intent.value)
            return (_GENERAL_FALLBACK, confidence)

        return (intent, confidence)

    except Exception:
        logger.exception("classify_intent failed → GENERAL fallback")
        return (_GENERAL_FALLBACK, 0.0)


async def intent_router_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph 노드 함수 — intent 분류 결과를 state에 기록.

    Args:
        state: AgentState (TypedDict).

    Returns:
        {"intent": str, "response_blocks": [IntentBlock dict]}.
    """
    query = state.get("query", "")
    history = state.get("conversation_history")

    intent, confidence = await classify_intent(query, history)

    return {
        "intent": intent.value,
        "response_blocks": [
            {
                "type": "intent",
                "intent": intent.value,
                "confidence": confidence,
            }
        ],
    }
