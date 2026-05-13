"""장소 북마크 API — Pydantic 요청/응답 모델 (feat/#80, Phase 2)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlaceBookmarkCreateRequest(BaseModel):
    place_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    district: Optional[str] = Field(None, max_length=50)
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=500)
    source_thread_id: Optional[str] = Field(None, max_length=100)
    source_message_id: Optional[int] = None


class PlaceBookmarkItem(BaseModel):
    bookmark_id: int
    place_id: str
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    summary: Optional[str] = None
    source_thread_id: Optional[str] = None
    source_message_id: Optional[int] = None
    created_at: datetime


class PlaceBookmarkListResponse(BaseModel):
    items: list[PlaceBookmarkItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class PlaceBookmarkCreateResponse(BaseModel):
    bookmark_id: int
    place_id: str
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    summary: Optional[str] = None
    source_thread_id: Optional[str] = None
    source_message_id: Optional[int] = None
    created_at: datetime
