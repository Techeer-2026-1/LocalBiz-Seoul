"""대화 관리 API — Pydantic 요청/응답 모델.

Pydantic이란?
  - Python 데이터 검증 라이브러리. FastAPI와 같이 쓴다.
  - BaseModel을 상속받아 필드를 정의하면:
    1) 요청 body를 자동으로 파싱 + 타입 검증 (잘못되면 422 에러)
    2) 응답을 자동으로 JSON 직렬화
  - FastAPI의 response_model에 넣으면 Swagger 문서도 자동 생성

conversations, messages 테이블 기반.
messages는 append-only (불변식 #3) — 이 모듈에서 INSERT/UPDATE/DELETE 모델 없음.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 채팅 목록 조회 (GET /api/v1/chats)
# ---------------------------------------------------------------------------
class ChatListItem(BaseModel):
    """채팅 목록에서 한 줄 = 이 모델 하나.

    사이드바에 표시할 최소 정보만 담는다:
      - thread_id: 대화 고유 식별자 (클릭 시 상세 조회에 사용)
      - title: 대화 제목 (자동 생성 또는 사용자 수정)
      - last_message: 마지막 메시지 미리보기 (아직 미구현, SSE 연동 후 추가)
      - updated_at: 마지막 활동 시간 (정렬 기준)
    """

    thread_id: str
    title: Optional[str] = None  # 제목 없는 새 대화는 null
    last_message: Optional[str] = None  # 아직 미구현
    updated_at: datetime


class ChatListResponse(BaseModel):
    """채팅 목록 API의 전체 응답.

    cursor 페이지네이션:
      - items: 이번 페이지의 채팅 목록
      - next_cursor: 다음 페이지 요청 시 사용할 값. null이면 마지막 페이지.
    """

    items: list[ChatListItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None  # null이면 마지막 페이지


# ---------------------------------------------------------------------------
# 채팅 상세 조회 (GET /api/v1/chats/{thread_id})
# ---------------------------------------------------------------------------
class ChatDetailResponse(BaseModel):
    """채팅 메타데이터. 메시지는 포함하지 않음 (별도 API).

    FE가 대화를 열 때:
      1) 이 API로 제목/시간 로딩
      2) /messages API로 메시지 별도 로딩
    """

    thread_id: str
    title: Optional[str] = None
    created_at: datetime  # 대화 생성 시각
    updated_at: datetime  # 마지막 활동 시각


# ---------------------------------------------------------------------------
# 메시지 조회 (GET /api/v1/chats/{thread_id}/messages)
# ---------------------------------------------------------------------------
class MessageItem(BaseModel):
    """단일 메시지 = 이 모델 하나.

    필드:
      - message_id: DB PK (BIGSERIAL). cursor 페이지네이션에 사용.
      - role: "user" (사용자 입력) 또는 "assistant" (AI 응답)
      - blocks: 응답 블록 배열. JSONB로 저장된 16종 블록 (place, events, chart 등).
                예: [{"type": "text_stream", "content": "홍대에는..."}, {"type": "places", "items": [...]}]
      - created_at: 메시지 생성 시각
    """

    message_id: int
    role: str  # "user" | "assistant"
    blocks: list[dict[str, Any]] = Field(default_factory=list)  # JSONB 블록 배열
    created_at: datetime


class MessageListResponse(BaseModel):
    """메시지 목록 API의 전체 응답.

    ChatListResponse와 같은 cursor 패턴:
      - next_cursor가 null이면 마지막 페이지
      - 있으면 다음 요청에 ?cursor=값 으로 넘김
    """

    items: list[MessageItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None  # message_id를 문자열로 변환한 값


# ---------------------------------------------------------------------------
# 대화 제목 수정 (PATCH /api/v1/chats/{thread_id})
# ---------------------------------------------------------------------------
class ChatUpdateRequest(BaseModel):
    """대화 제목 수정 요청 body.

    FE에서 보내는 JSON: {"title": "새 제목"}
    Pydantic이 자동으로 파싱하고, title이 없거나 타입이 다르면 422 반환.
    """

    title: str


class ChatUpdateResponse(BaseModel):
    """대화 제목 수정 후 응답.

    UPDATE ... RETURNING으로 DB에서 바로 가져온 결과.
    """

    thread_id: str
    title: str
    updated_at: datetime  # now()로 갱신된 시각
