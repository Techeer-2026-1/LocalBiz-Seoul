"""LangGraph intent router 노드 — Phase 1 skeleton.

12+1 intent enum 만 정의. 실제 Gemini JSON-mode 분류 + edge 매핑은 Phase 1 작업에서 채움.
기획서 §3.1 권위 — 변경 시 PM 합의 + 기획서 동기화.
"""

from enum import StrEnum
from typing import Optional


class Intent(StrEnum):
    """기획서 §3.1 — 12 핵심 intent + 1 fallback (GENERAL). 변경 금지."""

    PLACE_SEARCH = "PLACE_SEARCH"
    PLACE_RECOMMEND = "PLACE_RECOMMEND"
    EVENT_SEARCH = "EVENT_SEARCH"
    COURSE_PLAN = "COURSE_PLAN"
    DETAIL_INQUIRY = "DETAIL_INQUIRY"
    BOOKING = "BOOKING"
    FAVORITE = "FAVORITE"
    # Phase 2
    REVIEW_COMPARE = "REVIEW_COMPARE"
    ANALYSIS = "ANALYSIS"
    COST_ESTIMATE = "COST_ESTIMATE"
    CROWDEDNESS = "CROWDEDNESS"
    IMAGE_SEARCH = "IMAGE_SEARCH"
    # Fallback
    GENERAL = "GENERAL"


def classify_intent(query: Optional[str] = None) -> Intent:
    """Phase 1 stub — 항상 GENERAL 반환.

    Phase 1 작업에서 Gemini 2.5 Flash JSON-mode 호출로 교체.
    """
    _ = query  # unused (placeholder)
    return Intent.GENERAL
