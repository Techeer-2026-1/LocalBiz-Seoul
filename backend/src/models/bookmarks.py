"""북마크 API — Pydantic 요청/응답 모델.

bookmarks 테이블 기반 (ERD §4.9, Phase 2).
불변식 #16: 북마크 = (thread_id, message_id, pin_type) 5종 핀.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

PinType = Literal["place", "event", "course", "analysis", "general"]


class BookmarkItem(BaseModel):
    bookmark_id: int
    thread_id: str
    message_id: int
    pin_type: PinType
    preview_text: Optional[str] = None
    created_at: datetime


class BookmarkListResponse(BaseModel):
    items: list[BookmarkItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class BookmarkCreateRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, max_length=100)
    message_id: int
    pin_type: PinType
    preview_text: Optional[str] = Field(None, max_length=500)


class BookmarkCreateResponse(BaseModel):
    bookmark_id: int
    thread_id: str
    message_id: int
    pin_type: PinType
    preview_text: Optional[str] = None
    created_at: datetime
