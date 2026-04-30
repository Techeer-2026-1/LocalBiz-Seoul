"""response_builder 노드 — done 블록 추가 + intent별 블록 순서 검증.

LangGraph 그래프의 마지막 노드. 모든 intent 노드가 response_blocks에
블록을 누적한 뒤, 이 노드가:
  1. done 블록 추가 (에러 시 status="error")
  2. intent별 블록 순서 검증 (불변식 #11, 기획서 section 4.5)
  3. 검증 실패 시 logger.warning만 (블록 제거하지 않음)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# intent별 기대 블록 순서 (기획서 section 4.5)
# ---------------------------------------------------------------------------
# 현재 GENERAL만 확정. 나머지 intent는 각 노드 구현 완료 후 추가.
# TODO: PLACE_SEARCH, PLACE_RECOMMEND, EVENT_SEARCH, EVENT_RECOMMEND,
#       COURSE_PLAN, DETAIL_INQUIRY, BOOKING, CALENDAR
_EXPECTED_BLOCK_ORDER: dict[str, list[str]] = {
    "GENERAL": ["intent", "text_stream", "done"],
    "PLACE_SEARCH": ["intent", "text_stream", "places", "map_markers", "done"],
}


# ---------------------------------------------------------------------------
# 블록 순서 검증 헬퍼
# ---------------------------------------------------------------------------
def _validate_block_order(
    intent: Optional[str],
    block_types: list[str],
) -> Optional[str]:
    """intent별 기대 순서와 실제 블록 type 시퀀스를 비교.

    Args:
        intent: 분류된 intent 문자열. None이면 검증 스킵.
        block_types: response_blocks의 type 시퀀스 (done 포함).

    Returns:
        불일치 시 경고 메시지 문자열, 일치 시 None.
    """
    if intent is None:
        return "intent가 None — 블록 순서 검증 스킵"

    expected = _EXPECTED_BLOCK_ORDER.get(intent)
    if expected is None:
        # 아직 순서가 정의되지 않은 intent — 검증 스킵
        return None

    if block_types != expected:
        return f"블록 순서 불일치 [{intent}]: expected={expected}, actual={block_types}"

    return None


# ---------------------------------------------------------------------------
# 노드 함수
# ---------------------------------------------------------------------------
async def response_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    """response_blocks에 done 블록 추가 + 블록 순서 검증.

    Args:
        state: AgentState dict. response_blocks / intent / error 참조.

    Returns:
        {"response_blocks": [done_block]}
        Annotated[list, operator.add]에 의해 기존 블록 뒤에 append.
    """
    error: Optional[str] = state.get("error")

    # 1) done 블록 생성
    if error:
        done_block: dict[str, Any] = {
            "type": "done",
            "status": "error",
            "error_message": error,
        }
    else:
        done_block = {
            "type": "done",
            "status": "done",
        }

    # 2) 블록 순서 검증 (done 포함한 최종 시퀀스)
    existing_blocks: list[dict[str, Any]] = state.get("response_blocks", [])
    block_types = [b.get("type", "") for b in existing_blocks]
    block_types.append("done")  # done은 아직 append 전이므로 수동 추가

    intent: Optional[str] = state.get("intent")
    warning = _validate_block_order(intent, block_types)
    if warning is not None:
        logger.warning("response_builder: %s", warning)

    return {"response_blocks": [done_block]}
