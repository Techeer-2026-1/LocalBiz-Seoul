"""SSE 핸들러 — 기획서 section 4.5 권위.

토큰 단위 스트리밍 (text_stream), 16종 콘텐츠 블록 순차 전송,
intent별 블록 순서 고정. SSE(Server-Sent Events) 기반.

결정 근거: 기획/SSE_vs_WebSocket_결정.md

흐름:
  1. seed user 보장 (개발용)
  2. conversations auto-create
  3. user 메시지 INSERT
  4. LangGraph astream() 실행
  5. 각 노드 출력 블록을 SSE 이벤트로 전송
  6. text_stream 블록 → Gemini astream()으로 토큰 스트리밍
  7. assistant 메시지 INSERT (블록 목록)
  8. done 이벤트 전송
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.config import get_settings  # pyright: ignore[reportMissingImports]
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
# 노드별 status 메시지 (SSE 제어 이벤트, DB 미저장)
# ---------------------------------------------------------------------------
_NODE_STATUS_MESSAGES: dict[str, str] = {
    "intent_router": "의도를 분석하고 있어요...",
    "query_preprocessor": "질문을 정리하고 있어요...",
    "place_search": "장소를 검색하고 있어요...",
    "place_recommend": "장소를 추천하고 있어요...",
    "event_search": "행사를 검색하고 있어요...",
    "event_recommend": "행사를 추천하고 있어요...",
    "course_plan": "코스를 계획하고 있어요...",
    "general": "답변을 생성하고 있어요...",
    "detail_inquiry": "상세 정보를 조회하고 있어요...",
    "booking": "예약 정보를 확인하고 있어요...",
    "calendar": "일정을 추가하고 있어요...",
}


# ---------------------------------------------------------------------------
# DB 헬퍼 — seed user, conversations, messages
# ---------------------------------------------------------------------------
async def _ensure_seed_user(pool: Any) -> int:
    """개발용 seed user 보장. user_id=1 없으면 INSERT.

    Returns:
        user_id (int).
    """
    row = await pool.fetchrow("SELECT user_id FROM users WHERE user_id = $1", 1)
    if row:
        return int(row["user_id"])

    await pool.execute(
        "INSERT INTO users (user_id, email, auth_provider, password_hash) "
        "VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO NOTHING",
        1,
        "dev@localhost",
        "email",
        "dev_placeholder_hash",
    )
    logger.info("Seed user created: user_id=1, email=dev@localhost")
    return 1


async def _ensure_conversation(pool: Any, thread_id: str, user_id: int) -> None:
    """conversations 테이블에 thread_id가 없으면 auto-create.

    ON CONFLICT DO NOTHING으로 동시 요청 race condition 방지.
    """
    await pool.execute(
        "INSERT INTO conversations (thread_id, user_id, title) VALUES ($1, $2, $3) ON CONFLICT (thread_id) DO NOTHING",
        thread_id,
        user_id,
        "새 대화",
    )


async def _insert_message(
    pool: Any,
    thread_id: str,
    role: str,
    blocks: list[dict[str, Any]],
) -> None:
    """messages 테이블에 INSERT (append-only, 불변식 #3).

    message_id는 BIGSERIAL auto-increment (불변식 #1).
    """
    blocks_json = json.dumps(blocks, ensure_ascii=False)
    await pool.execute(
        "INSERT INTO messages (thread_id, role, blocks) VALUES ($1, $2, $3::jsonb)",
        thread_id,
        role,
        blocks_json,
    )


# ---------------------------------------------------------------------------
# Gemini 토큰 스트리밍
# ---------------------------------------------------------------------------
async def _stream_gemini(system_prompt: str, user_prompt: str) -> AsyncIterator[str]:
    """Gemini 2.5 Flash로 토큰 단위 스트리밍.

    Yields:
        각 토큰 문자열 (delta).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI  # pyright: ignore[reportMissingImports]

    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_llm_api_key,
        temperature=0.7,
        streaming=True,
    )

    messages: list[tuple[str, str]] = [
        ("system", system_prompt),
        ("human", user_prompt),
    ]

    async for chunk in llm.astream(messages):
        content = chunk.content
        if content:
            yield str(content)


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

    Args:
        request: FastAPI Request (disconnect 감지용).
        thread_id: 대화 스레드 ID.
        query: 사용자 쿼리 텍스트.
        token: JWT 토큰 (query parameter fallback).
    """

    async def event_generator() -> AsyncIterator[str]:
        from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
        from src.graph.real_builder import build_graph  # pyright: ignore[reportMissingImports]

        logger.info(
            "SSE stream started: thread_id=%s, query_len=%d",
            thread_id,
            len(query),
        )

        try:
            # 1. DB 준비 — seed user + conversation
            pool = get_pool()
            user_id = await _ensure_seed_user(pool)
            await _ensure_conversation(pool, thread_id, user_id)

            # 2. user 메시지 INSERT
            user_blocks: list[dict[str, Any]] = [{"type": "text", "content": query}]
            await _insert_message(pool, thread_id, "user", user_blocks)

            # 3. LangGraph astream() 실행
            graph = build_graph(checkpointer=None)
            input_state: dict[str, Any] = {
                "query": query,
                "thread_id": thread_id,
                "user_id": user_id,
                "conversation_history": [],
            }

            assistant_blocks: list[dict[str, Any]] = []

            cancelled = False

            async for event in graph.astream(input_state):
                if await request.is_disconnected():
                    logger.info("Client disconnected: thread_id=%s", thread_id)
                    cancelled = True
                    break

                # event는 {node_name: node_output} 형태
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    # 노드 전환 시 status 이벤트 전송 (DB 미저장)
                    status_msg = _NODE_STATUS_MESSAGES.get(node_name)
                    if status_msg:
                        yield format_status_event(status_msg, node=node_name)

                    blocks = node_output.get("response_blocks", [])
                    for block in blocks:
                        if not isinstance(block, dict):
                            continue

                        block_type = block.get("type", "")

                        if block_type == "text_stream":
                            # Gemini 토큰 스트리밍
                            system_prompt = block.get("system", "")
                            user_prompt = block.get("prompt", query)
                            full_text = ""

                            async for delta in _stream_gemini(system_prompt, user_prompt):
                                if await request.is_disconnected():
                                    cancelled = True
                                    break
                                full_text += delta
                                yield format_sse_event("text_stream", {"type": "text_stream", "delta": delta})

                            # 부분이든 전체든 저장
                            if full_text:
                                assistant_blocks.append({"type": "text_stream", "content": full_text})

                            if cancelled:
                                break
                        else:
                            # 다른 블록은 그대로 전송 + 저장
                            yield format_sse_event(block_type, block)
                            assistant_blocks.append(block)

                    if cancelled:
                        break

            # 4. cancelled done 전송 (클라이언트가 이미 끊겼어도 시도)
            if cancelled:
                yield format_done_event(status="cancelled")

            # 5. assistant 메시지 INSERT (부분 응답 포함)
            if assistant_blocks:
                try:
                    await _insert_message(pool, thread_id, "assistant", assistant_blocks)
                except Exception:
                    logger.exception("assistant message INSERT failed: thread_id=%s", thread_id)

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
