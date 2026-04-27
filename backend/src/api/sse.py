"""SSE 핸들러 — 기획서 section 4.5 권위.

토큰 단위 스트리밍 (text_stream), 16종 콘텐츠 블록 순차 전송,
intent별 블록 순서 고정. SSE(Server-Sent Events) 기반.

결정 근거: 기획/SSE_vs_WebSocket_결정.md

Phase 1 본작업에서 구현할 항목:
  1. JWT 인증 (@microsoft/fetch-event-source로 Bearer 헤더)
  2. LangGraph astream() 실행
  3. 블록 순서에 맞춘 SSE 이벤트 전송
  4. 에러/disconnect 처리 (request.is_disconnected())
  5. messages 테이블 append (불변식 #3: append-only)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.models.blocks import (  # pyright: ignore[reportMissingImports]
    DoneBlock,
    StatusFrame,
    serialize_block,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# SSE 이벤트 헬퍼
# ---------------------------------------------------------------------------
def format_sse_event(event_type: str, data: Any) -> str:
    """SSE 이벤트 문자열 생성.

    Args:
        event_type: 이벤트 타입 (intent, text_stream, places, done 등).
        data: JSON-serializable dict.

    Returns:
        SSE 포맷 문자열: ``event: {type}\\ndata: {json}\\n\\n``
    """
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_str}\n\n"


def format_block_event(block: Any) -> str:
    """Pydantic 블록 → SSE 이벤트 문자열."""
    if hasattr(block, "model_dump"):
        data = serialize_block(block)
    else:
        data = block
    event_type = data.get("type", "unknown")
    return format_sse_event(event_type, data)


def format_status_event(message: str, node: Optional[str] = None) -> str:
    """SSE 제어 이벤트 (status) 생성. messages에 저장하지 않음."""
    frame = StatusFrame(message=message, node=node)
    return format_block_event(frame)


def format_done_event(
    status: str = "done",
    error_message: Optional[str] = None,
) -> str:
    """done 이벤트 생성."""
    done = DoneBlock(status=status, error_message=error_message)
    return format_block_event(done)


# ---------------------------------------------------------------------------
# SSE 엔드포인트
# ---------------------------------------------------------------------------
@router.get("/api/v1/chat/stream")
async def chat_stream(
    request: Request,
    thread_id: str,
    query: str,
    token: Optional[str] = None,
) -> StreamingResponse:
    """메인 채팅 SSE 엔드포인트.

    Phase 1 본작업에서 다음 흐름으로 교체:
      1. JWT 검증 (Authorization 헤더 또는 token query param)
      2. LangGraph astream({"query": ..., "thread_id": ...})
      3. 각 노드 출력 블록을 intent별 순서에 맞춰 SSE 이벤트 전송
      4. 완료 시 done 이벤트 전송
      5. messages 테이블에 블록 목록 append (불변식 #3)
      6. 클라이언트 disconnect 시 request.is_disconnected()로 감지하여 중단

    Args:
        request: FastAPI Request (disconnect 감지용).
        thread_id: 대화 스레드 ID.
        query: 사용자 쿼리 텍스트.
        token: JWT 토큰 (query parameter fallback).
    """

    async def event_generator() -> AsyncIterator[str]:
        logger.info(
            "SSE stream started: thread_id=%s, query=%s, token=%s",
            thread_id,
            query[:100],
            "present" if token else "none",
        )

        try:
            # TODO: LangGraph astream() 실행 + 블록 순서 전송
            # 지금은 stub — done만 전송
            yield format_done_event(status="done")

        except Exception:
            logger.exception("SSE error: thread_id=%s", thread_id)
            yield format_done_event(status="error", error_message="Internal server error")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
