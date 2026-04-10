"""WebSocket 진입점 — Phase 1 skeleton.

기획서 §4.5 권위:
  - 토큰 단위 스트리밍 (text_stream 블록)
  - 16종 응답 블록 순차 전송
  - intent별 블록 순서 고정

본 파일은 라우터 객체 import만 가능한 placeholder. 실제 handler/connect/disconnect는 Phase 1.
"""

from typing import Optional

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/chat/{thread_id}")
async def chat_endpoint(websocket: WebSocket, thread_id: str, token: Optional[str] = None) -> None:
    """Phase 1 stub — accept → 즉시 close.

    Phase 1 작업에서 다음을 추가:
      1. JWT 인증 (token query param)
      2. LangGraph astream() 실행
      3. 16 응답 블록 순차 전송
      4. 에러/disconnect 처리
    """
    _ = thread_id  # unused (placeholder)
    _ = token  # unused (placeholder)
    await websocket.accept()
    await websocket.close(code=1000, reason="Phase 1 skeleton — not implemented")
