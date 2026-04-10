"""LangGraph 그래프 빌더 — Phase 1 skeleton.

실제 노드 등록 (place_search_node, place_recommend_node, course_plan_node, ...) 은
Phase 1 작업에서 추가. 본 파일은 그래프 객체가 import 가능함을 보장하는 placeholder.
"""

from typing import Any, Optional


def build_graph(checkpointer: Optional[Any] = None) -> None:
    """Phase 1 stub — 실제 LangGraph StateGraph 구성은 후속 작업.

    Args:
        checkpointer: PostgresSaver 등 langgraph-checkpoint 인스턴스 (Phase 1 작업에서 주입).

    Returns:
        지금은 None. Phase 1 작업에서 compiled graph 반환으로 변경.
    """
    _ = checkpointer  # unused (placeholder)
    return None
