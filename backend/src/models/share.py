"""공유 링크 Pydantic 모델 — 불변식 #17.

/shared/{share_token} GET만 인증 우회. POST/DELETE는 JWT 필수.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRange(BaseModel):
    """공유 메시지 범위. null이면 전체 대화."""

    from_message_id: Optional[int] = None
    to_message_id: Optional[int] = None


class ShareCreateRequest(BaseModel):
    """공유 링크 생성 요청."""

    message_range: Optional[MessageRange] = None


class ShareCreateResponse(BaseModel):
    """공유 링크 생성 응답."""

    share_token: str
    share_url: str
    expires_at: Optional[str] = None


class SharedMessage(BaseModel):
    """공유 대화의 개별 메시지."""

    role: str
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str


class SharedConversationResponse(BaseModel):
    """공유 대화 조회 응답 (인증 불필요)."""

    thread_title: Optional[str] = None
    messages: list[SharedMessage] = Field(default_factory=list)
