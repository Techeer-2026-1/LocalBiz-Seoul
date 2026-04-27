"""LangGraph intent router 노드 — 15 intent 분류.

기획서 section 3.1 권위. 14 핵심 intent + 1 fallback (GENERAL).
Gemini 2.5 Flash JSON-mode로 분류 (Phase 1 본작업에서 구현).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Optional


class IntentType(StrEnum):
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
    # Phase 2
    REVIEW_COMPARE = "REVIEW_COMPARE"
    ANALYSIS = "ANALYSIS"
    COST_ESTIMATE = "COST_ESTIMATE"
    CROWDEDNESS = "CROWDEDNESS"
    IMAGE_SEARCH = "IMAGE_SEARCH"
    # Fallback
    GENERAL = "GENERAL"


# Phase 1 intent만 활성 라우팅 대상
PHASE1_INTENTS: frozenset[IntentType] = frozenset(
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
        IntentType.GENERAL,
    }
)


async def classify_intent(
    query: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> tuple[IntentType, float]:
    """사용자 쿼리 → (IntentType, confidence) 분류.

    Phase 1 stub: 항상 (GENERAL, 1.0) 반환.
    본작업에서 Gemini 2.5 Flash JSON-mode 호출로 교체.

    Args:
        query: 사용자 원본 쿼리.
        conversation_history: 이전 대화 이력 (multi-turn 문맥용).

    Returns:
        (intent, confidence) 튜플.
    """
    _ = query
    _ = conversation_history
    return (IntentType.GENERAL, 1.0)


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
