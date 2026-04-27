"""LangGraph 그래프 빌더 — 노드/엣지 인터페이스 스텁.

StateGraph(AgentState)를 구성하고 compiled graph를 반환.
각 노드의 실제 로직은 별도 *_node.py 파일에서 구현.

그래프 구조 (Phase 1):
  __start__ → intent_router → (조건부 분기) → [각 intent 노드] → response_builder → __end__

노드 추가/변경 시 코드리뷰 체크리스트 확인 필수.
"""

from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, StateGraph

from src.graph.state import AgentState


# ---------------------------------------------------------------------------
# 노드 함수 스텁 — 각 *_node.py에서 실제 구현 후 import 교체
# ---------------------------------------------------------------------------
async def _intent_router_node(state: AgentState) -> dict[str, Any]:
    """Intent 분류 노드 stub. 실제 구현: intent_router_node.py."""
    # TODO: from src.graph.intent_router_node import classify_intent
    return {"intent": "GENERAL"}


async def _query_preprocessor_node(state: AgentState) -> dict[str, Any]:
    """공통 쿼리 전처리 노드 stub (불변식 #12).

    Intent Router 직후, 모든 검색 노드 공통으로 실행.
    Gemini JSON mode로 카테고리/지역/키워드 추출.
    """
    # TODO: Gemini JSON-mode 호출
    return {"processed_query": {}}


async def _place_search_node(state: AgentState) -> dict[str, Any]:
    """장소 검색 노드 stub (SQL + Vector + LLM Rerank 3단계)."""
    return {"response_blocks": []}


async def _place_recommend_node(state: AgentState) -> dict[str, Any]:
    """장소 추천 노드 stub."""
    return {"response_blocks": []}


async def _event_search_node(state: AgentState) -> dict[str, Any]:
    """행사 검색 노드 stub (DB 우선 → Naver fallback, 불변식 #13)."""
    return {"response_blocks": []}


async def _event_recommend_node(state: AgentState) -> dict[str, Any]:
    """행사 추천 노드 stub (events[] + references, EVENT_SEARCH 대칭)."""
    return {"response_blocks": []}


async def _course_plan_node(state: AgentState) -> dict[str, Any]:
    """코스 계획 노드 stub."""
    return {"response_blocks": []}


async def _general_node(state: AgentState) -> dict[str, Any]:
    """일반 대화 노드 stub (Gemini 호출)."""
    return {"response_blocks": []}


async def _detail_inquiry_node(state: AgentState) -> dict[str, Any]:
    """상세 조회 노드 stub."""
    return {"response_blocks": []}


async def _booking_node(state: AgentState) -> dict[str, Any]:
    """예약 딥링크 노드 stub."""
    return {"response_blocks": []}


async def _calendar_node(state: AgentState) -> dict[str, Any]:
    """일정 추가 노드 stub (Google Calendar MCP)."""
    return {"response_blocks": []}


async def _response_builder_node(state: AgentState) -> dict[str, Any]:
    """응답 빌더 노드 — intent별 블록 순서 검증 + done 블록 추가."""
    return {"response_blocks": []}


# ---------------------------------------------------------------------------
# 조건부 라우팅 함수
# ---------------------------------------------------------------------------
def _route_by_intent(state: AgentState) -> str:
    """intent 값에 따라 다음 노드 결정.

    Returns:
        노드 이름 문자열. intent별 매핑:
        - PLACE_SEARCH → "place_search"
        - PLACE_RECOMMEND → "place_recommend"
        - EVENT_SEARCH → "event_search"
        - EVENT_RECOMMEND → "event_recommend"
        - COURSE_PLAN → "course_plan"
        - DETAIL_INQUIRY → "detail_inquiry"
        - BOOKING → "booking"
        - CALENDAR → "calendar"
        - GENERAL (fallback) → "general"
        - Phase 2 intents → "general" (Phase 2에서 확장)
    """
    intent = state.get("intent", "GENERAL")
    mapping: dict[str, str] = {
        "PLACE_SEARCH": "place_search",
        "PLACE_RECOMMEND": "place_recommend",
        "EVENT_SEARCH": "event_search",
        "EVENT_RECOMMEND": "event_recommend",
        "COURSE_PLAN": "course_plan",
        "DETAIL_INQUIRY": "detail_inquiry",
        "BOOKING": "booking",
        "CALENDAR": "calendar",
    }
    return mapping.get(str(intent), "general")


# ---------------------------------------------------------------------------
# 그래프 빌드
# ---------------------------------------------------------------------------
def build_graph(checkpointer: Optional[Any] = None) -> Any:
    """StateGraph(AgentState) 구성 + 컴파일.

    Args:
        checkpointer: PostgresSaver 등 langgraph-checkpoint 인스턴스.

    Returns:
        CompiledGraph. astream() / ainvoke()로 실행 가능.
    """
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("intent_router", _intent_router_node)
    graph.add_node("query_preprocessor", _query_preprocessor_node)
    graph.add_node("place_search", _place_search_node)
    graph.add_node("place_recommend", _place_recommend_node)
    graph.add_node("event_search", _event_search_node)
    graph.add_node("event_recommend", _event_recommend_node)
    graph.add_node("course_plan", _course_plan_node)
    graph.add_node("general", _general_node)
    graph.add_node("detail_inquiry", _detail_inquiry_node)
    graph.add_node("booking", _booking_node)
    graph.add_node("calendar", _calendar_node)
    graph.add_node("response_builder", _response_builder_node)

    # 엣지 설정
    graph.set_entry_point("intent_router")
    graph.add_edge("intent_router", "query_preprocessor")

    # 전처리 후 intent에 따라 분기
    graph.add_conditional_edges(
        "query_preprocessor",
        _route_by_intent,
        {
            "place_search": "place_search",
            "place_recommend": "place_recommend",
            "event_search": "event_search",
            "course_plan": "course_plan",
            "detail_inquiry": "detail_inquiry",
            "booking": "booking",
            "general": "general",
        },
    )

    # 모든 intent 노드 → response_builder → END
    for node_name in [
        "place_search",
        "place_recommend",
        "event_search",
        "course_plan",
        "general",
        "detail_inquiry",
        "booking",
    ]:
        graph.add_edge(node_name, "response_builder")

    graph.add_edge("response_builder", END)

    return graph.compile(checkpointer=checkpointer)
