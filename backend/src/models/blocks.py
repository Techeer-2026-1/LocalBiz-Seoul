"""SSE 응답 블록 16종 — Pydantic 모델 (기획서 section 4.5 권위).

16종 콘텐츠 블록 (messages.blocks JSON에 저장):
  intent / text / text_stream / place / places / events / course /
  map_markers / map_route / chart / calendar / references /
  analysis_sources / disambiguation / done / error

SSE 제어 이벤트 (런타임 한정, messages 미저장):
  - status: 노드 전환 진행 표시 (StatusFrame으로 별도 정의)
  - done_partial: multi-intent 구분자

변경 시 PM 합의 + 기획서 동기화 필수.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. intent — 분류 결과 통보
# ---------------------------------------------------------------------------
class IntentBlock(BaseModel):
    """사용자 쿼리의 intent 분류 결과."""

    type: str = "intent"
    intent: str
    confidence: Optional[float] = None


# ---------------------------------------------------------------------------
# 2. text — 완성된 텍스트 응답 (비스트리밍)
# ---------------------------------------------------------------------------
class TextBlock(BaseModel):
    """단일 텍스트 응답. 스트리밍 완료 후 최종본 저장 용도로도 사용."""

    type: str = "text"
    content: str = ""


# ---------------------------------------------------------------------------
# 3. text_stream — 토큰 단위 스트리밍
# ---------------------------------------------------------------------------
class TextStreamBlock(BaseModel):
    """Gemini 스트리밍 토큰. delta를 순차 전송."""

    type: str = "text_stream"
    delta: str = ""


# ---------------------------------------------------------------------------
# 4. place — 단일 장소 카드
# ---------------------------------------------------------------------------
class PlaceBlock(BaseModel):
    """단일 장소 상세 정보."""

    type: str = "place"
    place_id: str  # UUID (VARCHAR(36)), 불변식 #1
    name: str = ""
    category: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None  # 의도적 비정규화, 불변식 #5
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    summary: Optional[str] = None  # LLM 요약 (선택)


# ---------------------------------------------------------------------------
# 5. places — 장소 리스트
# ---------------------------------------------------------------------------
class PlacesBlock(BaseModel):
    """장소 목록 (검색/추천 결과)."""

    type: str = "places"
    items: list[PlaceBlock] = Field(default_factory=list)
    total_count: Optional[int] = None


# ---------------------------------------------------------------------------
# 6. events — 행사 리스트
# ---------------------------------------------------------------------------
class EventItem(BaseModel):
    """단일 행사 정보."""

    event_id: str  # UUID (VARCHAR(36)), 불변식 #1
    title: str = ""
    district: Optional[str] = None  # 의도적 비정규화
    place_name: Optional[str] = None  # 의도적 비정규화
    address: Optional[str] = None  # 의도적 비정규화
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    homepage_url: Optional[str] = None


class EventsBlock(BaseModel):
    """행사 목록."""

    type: str = "events"
    items: list[EventItem] = Field(default_factory=list)
    total_count: Optional[int] = None


# ---------------------------------------------------------------------------
# 7. course — 코스 타임라인
# ---------------------------------------------------------------------------
class CourseStop(BaseModel):
    """코스 내 단일 정거장."""

    order: int
    place_id: str  # UUID
    name: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    duration_minutes: Optional[int] = None  # 체류 시간
    memo: Optional[str] = None  # LLM 추천 사유


class CourseBlock(BaseModel):
    """코스 타임라인 (COURSE_PLAN intent)."""

    type: str = "course"
    title: Optional[str] = None
    stops: list[CourseStop] = Field(default_factory=list)
    total_duration_minutes: Optional[int] = None


# ---------------------------------------------------------------------------
# 8. map_markers — Leaflet 마커 (places 용)
# ---------------------------------------------------------------------------
class MarkerItem(BaseModel):
    """지도 마커 하나."""

    place_id: str
    lat: float
    lng: float
    label: Optional[str] = None


class MapMarkersBlock(BaseModel):
    """Leaflet 마커 목록."""

    type: str = "map_markers"
    markers: list[MarkerItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 9. map_route — OSRM 폴리라인 (course 용)
# ---------------------------------------------------------------------------
class MapRouteBlock(BaseModel):
    """OSRM encoded polyline + 경유 좌표."""

    type: str = "map_route"
    polyline: Optional[str] = None
    waypoints: Optional[list[dict[str, float]]] = None
    distance_meters: Optional[int] = None
    duration_seconds: Optional[int] = None


# ---------------------------------------------------------------------------
# 10. chart — 레이더 차트 (REVIEW_COMPARE / ANALYSIS)
# ---------------------------------------------------------------------------
class ChartDataset(BaseModel):
    """차트 한 데이터셋 (장소 1개 분량)."""

    label: str
    # 6 지표 고정 (불변식 #6)
    score_satisfaction: Optional[float] = None
    accessibility: Optional[float] = None
    cleanliness: Optional[float] = None
    value: Optional[float] = None
    atmosphere: Optional[float] = None
    expertise: Optional[float] = None


class ChartBlock(BaseModel):
    """레이더 차트 (6 지표 비교)."""

    type: str = "chart"
    chart_type: str = "radar"  # 현재 radar만 지원
    datasets: list[ChartDataset] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 11. calendar — Google Calendar event 카드
# ---------------------------------------------------------------------------
class CalendarBlock(BaseModel):
    """Google Calendar 이벤트 생성 결과."""

    type: str = "calendar"
    title: Optional[str] = None
    start_time: Optional[str] = None  # ISO 8601
    end_time: Optional[str] = None
    location: Optional[str] = None
    calendar_link: Optional[str] = None  # 딥링크


# ---------------------------------------------------------------------------
# 12. references — 추천 사유 인용 (PLACE_RECOMMEND)
# ---------------------------------------------------------------------------
class ReferenceItem(BaseModel):
    """인용 출처 하나."""

    source_type: str = ""  # "review" | "blog" | "official"
    source_id: Optional[str] = None
    snippet: str = ""
    url: Optional[str] = None


class ReferencesBlock(BaseModel):
    """추천 사유 인용 목록."""

    type: str = "references"
    items: list[ReferenceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 13. analysis_sources — 분석 근거 출처 (ANALYSIS / REVIEW_COMPARE)
# ---------------------------------------------------------------------------
class AnalysisSourcesBlock(BaseModel):
    """분석에 사용된 데이터 출처."""

    type: str = "analysis_sources"
    review_count: Optional[int] = None
    blog_count: Optional[int] = None
    official_count: Optional[int] = None
    sources: list[ReferenceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 14. disambiguation — 동명/다중 후보 선택 UI
# ---------------------------------------------------------------------------
class DisambiguationCandidate(BaseModel):
    """후보 하나."""

    place_id: Optional[str] = None
    event_id: Optional[str] = None
    name: str = ""
    address: Optional[str] = None
    category: Optional[str] = None


class DisambiguationBlock(BaseModel):
    """동음이의/다중 후보 선택."""

    type: str = "disambiguation"
    message: Optional[str] = None
    candidates: list[DisambiguationCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 15. done — 응답 종료 마커
# ---------------------------------------------------------------------------
class DoneBlock(BaseModel):
    """응답 종료. status로 done/error/cancelled 구분.

    error 발생 시 status="error" + error_message에 상세 내용.
    기획서 기준 done 블록이 error 역할도 수행.
    """

    type: str = "done"
    status: str = "done"  # "done" | "error" | "cancelled"
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# 16. error — 에러 상세 (done status="error" 시 보조)
# ---------------------------------------------------------------------------
class ErrorBlock(BaseModel):
    """에러 상세 정보. done 블록의 보조 블록."""

    type: str = "error"
    code: Optional[str] = None
    message: str = ""
    recoverable: bool = True


# ---------------------------------------------------------------------------
# SSE 제어 이벤트 (messages 미저장, 16종 콘텐츠 블록이 아님)
# ---------------------------------------------------------------------------
class StatusFrame(BaseModel):
    """SSE 제어 이벤트 — 노드 전환 진행 표시.

    16종 콘텐츠 블록이 아님 (messages.blocks에 저장하지 않음).
    런타임 SSE 전송 전용.
    """

    type: str = "status"
    message: str = ""
    node: Optional[str] = None  # 현재 실행 중인 노드 이름


class DonePartialFrame(BaseModel):
    """SSE 제어 이벤트 — multi-intent 구분자.

    16종 콘텐츠 블록이 아님 (messages.blocks에 저장하지 않음).
    """

    type: str = "done_partial"
    completed_intent: Optional[str] = None


# ---------------------------------------------------------------------------
# Block type mapping (직렬화/역직렬화 헬퍼)
# ---------------------------------------------------------------------------
CONTENT_BLOCK_TYPES: dict[str, type[BaseModel]] = {
    "intent": IntentBlock,
    "text": TextBlock,
    "text_stream": TextStreamBlock,
    "place": PlaceBlock,
    "places": PlacesBlock,
    "events": EventsBlock,
    "course": CourseBlock,
    "map_markers": MapMarkersBlock,
    "map_route": MapRouteBlock,
    "chart": ChartBlock,
    "calendar": CalendarBlock,
    "references": ReferencesBlock,
    "analysis_sources": AnalysisSourcesBlock,
    "disambiguation": DisambiguationBlock,
    "done": DoneBlock,
    "error": ErrorBlock,
}


def serialize_block(block: BaseModel) -> dict[str, Any]:
    """블록 → JSON-serializable dict."""
    return block.model_dump(exclude_none=True)


def deserialize_block(data: dict[str, Any]) -> BaseModel:
    """dict → 적절한 블록 인스턴스. 알 수 없는 type이면 ValueError."""
    block_type = data.get("type", "")
    cls = CONTENT_BLOCK_TYPES.get(block_type)
    if cls is None:
        raise ValueError(f"알 수 없는 블록 type: {block_type!r}")
    return cls.model_validate(data)
