"""WebSocket 응답 블록 16종 — Phase 1 skeleton (Pydantic 모델 stub).

기획서 §4.5 권위 — 변경 시 PM 합의 + langgraph-node 스킬 발동.
실제 필드는 Phase 1 작업에서 채움. 본 파일은 type/import 가능성만 보장.
"""

from typing import Optional

from pydantic import BaseModel


class IntentBlock(BaseModel):
    """1. intent — 분류 결과 통보."""

    type: str = "intent"
    intent: Optional[str] = None


class StatusBlock(BaseModel):
    """2. status — 진행 상태 (검색 중/분석 중)."""

    type: str = "status"
    message: Optional[str] = None


class TextBlock(BaseModel):
    """3. text — 단일 텍스트 응답."""

    type: str = "text"
    content: Optional[str] = None


class TextStreamBlock(BaseModel):
    """4. text_stream — 토큰 단위 스트리밍."""

    type: str = "text_stream"
    delta: Optional[str] = None


class PlaceBlock(BaseModel):
    """5. place — 단일 장소 카드."""

    type: str = "place"
    place_id: Optional[str] = None


class PlacesBlock(BaseModel):
    """6. places — 장소 리스트."""

    type: str = "places"
    place_ids: Optional[list[str]] = None


class EventsBlock(BaseModel):
    """7. events — 행사 리스트."""

    type: str = "events"
    event_ids: Optional[list[str]] = None


class CourseBlock(BaseModel):
    """8. course — 코스 타임라인."""

    type: str = "course"
    course_id: Optional[str] = None


class MapMarkersBlock(BaseModel):
    """9. map_markers — Leaflet 마커 (places용)."""

    type: str = "map_markers"
    markers: Optional[list[dict[str, float]]] = None


class MapRouteBlock(BaseModel):
    """10. map_route — OSRM 폴리라인 (course용)."""

    type: str = "map_route"
    polyline: Optional[str] = None


class ChartBlock(BaseModel):
    """11. chart — 레이더 차트 (REVIEW_COMPARE)."""

    type: str = "chart"
    chart_type: Optional[str] = None


class CalendarBlock(BaseModel):
    """12. calendar — Google Calendar event 카드."""

    type: str = "calendar"
    event_id: Optional[str] = None


class ReferencesBlock(BaseModel):
    """13. references — 추천 사유 인용 (PLACE_RECOMMEND)."""

    type: str = "references"
    sources: Optional[list[str]] = None


class AnalysisSourcesBlock(BaseModel):
    """14. analysis_sources — 분석 근거 출처 (ANALYSIS / REVIEW_COMPARE)."""

    type: str = "analysis_sources"
    sources: Optional[list[str]] = None


class DisambiguationBlock(BaseModel):
    """15. disambiguation — 동명/다중 후보 선택 UI."""

    type: str = "disambiguation"
    candidates: Optional[list[dict[str, str]]] = None


class DoneBlock(BaseModel):
    """16. done — 응답 종료 마커 (done | done_partial | error)."""

    type: str = "done"
    status: Optional[str] = None


# Phase 1 작업에서 다음을 추가:
#   - 각 모델의 실제 필드 (기획서 §4.5)
#   - intent별 블록 순서 검증 함수
#   - WS serialize/deserialize 헬퍼
