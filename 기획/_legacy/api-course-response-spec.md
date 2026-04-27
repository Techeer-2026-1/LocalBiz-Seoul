# 코스 응답 API 명세

> 채팅 에이전트가 코스 추천 결과를 FE로 전달하는 응답 스키마.
> 기획서 v4 §4.2 (typed 블록 스트리밍) 기반.
> 적용 대상: `course_plan_node`, `place_recommend_node` 응답 흐름.

---

## 0. 목차

1. [목표와 원칙](#1-목표와-원칙)
2. [기존 자산 분석](#2-기존-자산-분석)
3. [블록 스트림 프로토콜](#3-블록-스트림-프로토콜)
4. [핵심 타입 정의](#4-핵심-타입-정의)
5. [블록 스키마](#5-블록-스키마)
   - 5.1 `course` 블록
   - 5.2 `map_route` 블록
6. [검증 규칙](#6-검증-규칙)
7. [엣지 케이스](#7-엣지-케이스)
8. [실제 응답 예시](#8-실제-응답-예시)
9. [Phase 별 변화](#9-phase-별-변화)
10. [에러 응답](#10-에러-응답)
11. [버전 관리](#11-버전-관리)
12. [FE 렌더링 의사 코드](#12-fe-렌더링-의사-코드)
13. [성능 및 캐싱](#13-성능-및-캐싱)
14. [BE 구현 체크리스트](#14-be-구현-체크리스트)

---

## 1. 목표와 원칙

### 1.1 목표

채팅에서 사용자가 코스를 요청했을 때, **FE가 추가 API 호출 없이 한 번의 WebSocket 응답만으로** 다음을 모두 렌더링할 수 있어야 한다:

- 우측 사이드 패널 (`ItineraryDetailPanel`) — 시간대별 그룹화된 카드
- 카카오맵 (`KakaoMap` itineraryMode) — 포토 핀 + 폴리라인
- 메시지 본문 텍스트 (`MessageBubble`)
- 출처 표시 (`ReferencesPills`)

### 1.2 설계 원칙

| 원칙 | 이유 |
|------|------|
| **자체 완결 (Self-contained)** | 각 블록은 추가 조회 없이 단독으로 렌더 가능. `place_id`만 전달하고 FE가 다시 조회하는 패턴 금지. |
| **관심사 분리 (SoC)** | `course` (데이터/패널) ↔ `map_route` (시각화). 같은 데이터를 두 블록이 중복으로 들고 있어도 됨. 둘은 `course_id`로 묶임. |
| **GeoJSON 좌표 표준** | 모든 좌표 배열은 `[lng, lat]` 순서. RFC 7946. Kakao SDK만 `(lat, lng)`이지만 변환은 1줄. |
| **단일 좌표 객체는 `{ lat, lng }`** | 단일 점은 가독성 우선. 배열은 표준 우선. |
| **모든 시간은 KST 기준 명시** | `arrival_time` (HH:mm), `arrival_at` (ISO 8601 with timezone). 서버는 항상 둘 다 제공. |
| **번호는 1부터 (1-indexed)** | 사용자에게 표시되는 모든 순서는 `①②③`. 0-index 금지. |
| **선택 필드는 optional, 누락 가능** | `?` 표시. FE는 누락 시 graceful degradation. |
| **확장 필드는 `metadata` JSONB** | 스키마 변경 없이 BE가 임시 데이터 추가 가능. FE는 모름. |
| **버저닝은 envelope에** | `schema_version: "1.0"`. Breaking change 시 증가. |
| **로케일 문자열은 BE에서 결정** | `mode_ko`, `label_ko` 등. FE는 i18n 안 함. |

### 1.3 비목표 (이번 명세에 포함하지 않는 것)

- 실시간 위치 추적 (WebSocket 외 별도 채널)
- 코스 편집 (사용자가 경유지 추가/삭제)
- 다중 사용자 동기화
- 오프라인 캐싱

---

## 2. 기존 자산 분석

### 2.1 현재 FE 타입 (`src/types/index.ts`)

```ts
// 현재 정의
interface Itinerary {
  id: string;
  title: string;
  date: string;
  stops: ItineraryStop[];
}

interface ItineraryStop {
  order: number;
  placeId: string;
  placeName: string;
  arrivalTime: string;
  duration: number;
  transportToNext: TransportMode;
  travelTimeToNext: number;
}

interface Place {
  id: string;
  name: string;
  category: PlaceCategory;
  address: string;
  lat: number;
  lng: number;
  hours: string;
  rating: number;
  summary: string;
  image?: string;
}
```

**문제점:**
- `ItineraryStop`이 `placeId`만 들고 있어 별도 `Place` 조회 필요 (현재 mock에서는 `mapStore.startNavigation`이 직접 매칭)
- `transportToNext`가 enum만 있고 거리/단계 정보 없음
- 폴리라인 좌표가 없음 (직선 보간만 가능)
- 시간대 그룹화 정보 없음
- 좌표가 `lat/lng` 순서, GeoJSON과 불일치

### 2.2 기획서 v4 §4.2 typed 블록 목록

```
intent, text, place, places, events, course, map_markers, map_route,
chart, calendar, references, analysis_sources, done
```

### 2.3 현재 사용 중인 컴포넌트 데이터 흐름

```
streamResponse() (Mock)
  → ChatStore.sendMessage
  → MessageBubble + ItineraryCard
  → "3D 경로 보기" 클릭
  → mapStore.startNavigation(itinerary)
  → MapPanel → KakaoMap (itineraryMode) + ItineraryDetailPanel
```

목표: **`startNavigation`이 받는 데이터를 BE 응답으로 직접 채울 수 있어야 함.**

---

## 3. 블록 스트림 프로토콜

### 3.1 WebSocket 프레임

```
wss://api.localbiz.example.com/ws/chat/{chat_id}

Client → Server:
{
  "type": "user_message",
  "message": "도심 한나절 코스 추천해줘",
  "user_id": "uuid",
  "timestamp": "2026-04-07T10:30:00+09:00"
}

Server → Client (each frame is one block):
{ "schema_version": "1.0", "type": "intent",     "content": ... }
{ "schema_version": "1.0", "type": "text",       "content": ... }
{ "schema_version": "1.0", "type": "course",     "content": ... }
{ "schema_version": "1.0", "type": "map_route",  "content": ... }
{ "schema_version": "1.0", "type": "references", "content": ... }
{ "schema_version": "1.0", "type": "done" }
```

### 3.2 블록 순서 보장

| 보장 | 설명 |
|------|------|
| **순차 전송** | 한 응답 내 블록은 순서대로 전송. FE는 순서 의존 가능. |
| **`text`는 토큰 단위 스트리밍 가능** | `text` 블록은 여러 프레임에 걸쳐 누적 전송 가능 (`streaming: true`) |
| **데이터 블록은 atomic** | `course`, `map_route` 등은 한 프레임에 완성된 객체로 전송 |
| **`done` 블록 = 응답 종료 신호** | FE는 `done` 수신 후 입력창 활성화 |

### 3.3 권장 전송 순서 (코스 응답)

```
1. intent       → 의도 분류 뱃지 즉시 표시
2. text         → 응답 텍스트 토큰 스트리밍
3. course       → 사이드 패널 렌더 (가장 정보량 많음)
4. map_route    → 지도 폴리라인 렌더
5. references   → 출처 pills
6. done         → 종료
```

`course`와 `map_route`는 같은 데이터를 참조하지만 분리 전송. FE는 둘을 `course_id`로 매칭.

---

## 4. 핵심 타입 정의

### 4.1 공통 enum

```ts
type PlaceCategory =
  | 'tourism'      // 관광
  | 'food'         // 음식점
  | 'cafe'         // 카페
  | 'culture'      // 문화/전시/공연
  | 'shopping'     // 쇼핑
  | 'performance'  // 공연
  | 'festival'     // 축제
  | 'public'       // 공공시설
  | 'accommodation'; // 숙박

type TransitMode =
  | 'walk'      // 도보
  | 'subway'    // 지하철
  | 'bus'       // 버스
  | 'taxi'      // 택시
  | 'car'       // 자가용
  | 'bicycle';  // 자전거

type DayPeriod = 'morning' | 'afternoon' | 'evening' | 'night';

type IntentType =
  | 'GENERAL' | 'PLACE_SEARCH' | 'PLACE_RECOMMEND'
  | 'EVENT_SEARCH' | 'COURSE_PLAN' | 'DETAIL_INQUIRY'
  | 'BOOKING' | 'CROWDEDNESS' | 'COST_ESTIMATE'
  | 'ANALYSIS' | 'REVIEW_COMPARE' | 'IMAGE_SEARCH' | 'FAVORITE';
```

### 4.2 좌표 표현

```ts
// 단일 점 — 가독성 우선
interface LatLng {
  lat: number;  // 위도 (Y)
  lng: number;  // 경도 (X)
}

// 배열 — GeoJSON 표준 [lng, lat]
type Coordinate = [number, number]; // [longitude, latitude]

interface Bounds {
  sw: LatLng;  // South-West (좌하단)
  ne: LatLng;  // North-East (우상단)
}
```

### 4.3 응답 envelope

```ts
interface BlockEnvelope<T extends BlockType> {
  schema_version: string;     // "1.0"
  type: T;
  content: BlockContent<T>;
  metadata?: Record<string, unknown>;  // 확장 필드
}

type BlockType =
  | 'intent' | 'text' | 'place' | 'places' | 'events'
  | 'course' | 'map_markers' | 'map_route' | 'chart'
  | 'calendar' | 'references' | 'analysis_sources' | 'done';
```

---

## 5. 블록 스키마

### 5.1 `course` 블록 (사이드 패널용)

```ts
interface CourseBlockContent {
  // ─── 식별 ───
  course_id: string;              // ULID 권장 (ex: "01HQA8KJ2N7B4PMXY3Z9R5VWST")
  schema_version: '1.0';

  // ─── 표시 ───
  title: string;                  // "도심 한나절 코스" (max 50자)
  description: string;            // 1~2문장 (max 200자)
  emoji?: string;                 // "🍜" (단일 이모지 1글자)

  // ─── 메타 정보 ───
  total_distance_m: number;       // 총 이동 거리 (m)
  total_duration_min: number;     // 총 소요 시간 (체류 + 이동, 분)
  total_stay_min: number;         // 체류 시간 합계
  total_transit_min: number;      // 이동 시간 합계
  // 위 두 값의 합 = total_duration_min (검증용)

  // ─── 일정 ───
  date?: string;                  // "2026-04-08" (ISO 8601 date, 선택)
  start_time?: string;            // "11:00" (HH:mm) — date와 함께 제공 시 의미 있음

  // ─── 비용 (Phase 2) ───
  estimated_cost?: {
    min: number;                  // 예상 최저 (KRW)
    max: number;                  // 예상 최고 (KRW)
    currency: 'KRW';              // 향후 확장
    confidence: 'high' | 'medium' | 'low';
    source: string;               // "Google price_level + 블로그 추정"
  };

  // ─── 시간대 그룹화 (BE에서 미리 분류) ───
  sections: CourseSection[];

  // ─── 경유지 ───
  stops: CourseStop[];            // 1개 이상

  // ─── 외부 액션 ───
  actions?: {
    open_in_kakao_map?: string;   // 카카오맵 길찾기 URL
    open_in_google_maps?: string; // 구글맵 URL
    share_url?: string;           // 코스 공유 페이지
  };

  // ─── 추천 근거 (선택) ───
  reasoning?: {
    summary: string;              // "도보 위주, 점심 시간대 혼잡 회피"
    factors: string[];            // ["도보 동선 최적화", "11시 오픈 직후"]
  };
}

interface CourseSection {
  id: DayPeriod;                  // "morning"
  label_ko: string;               // "오전"
  label_en?: string;              // "Morning" (i18n 대비)
  stop_orders: number[];          // [1] — 이 섹션에 속한 stops의 order
}

interface CourseStop {
  order: number;                  // 1, 2, 3 ... (1-indexed, 연속, gap 없음)

  // ─── 도착/체류 정보 ───
  arrival_time: string;           // "11:00" (HH:mm)
  arrival_at?: string;            // "2026-04-08T11:00:00+09:00" (ISO 8601, date 있을 때)
  duration_min: number;           // 체류 시간 (분)

  // ─── 장소 (자체 완결, 추가 조회 불필요) ───
  place: CoursePlace;

  // ─── 다음 경유지로 이동 (마지막 stop은 null) ───
  transit_to_next: TransitInfo | null;

  // ─── 추천 이유 (카드 하단에 표시) ───
  recommendation_reason?: string; // "오픈 직후가 가장 한적해요" (max 60자)

  // ─── 우선순위 (선택) ───
  priority?: 'must' | 'recommended' | 'optional';
}

interface CoursePlace {
  // ─── 식별 ───
  place_id: string;               // 외부 참조용 (FE는 표시 안 함)
  name: string;                   // "광장시장"
  name_en?: string;               // "Gwangjang Market" (외국인용, 선택)

  // ─── 분류 ───
  category: PlaceCategory;
  category_label: string;         // "전통시장" (BE가 결정한 한국어)
  sub_category?: string;          // "재래시장"

  // ─── 위치 ───
  address: string;                // "서울 종로구 창경궁로 88"
  address_short?: string;         // "종로구" (마커 라벨용, 선택)
  district: string;               // "종로구"
  location: LatLng;

  // ─── 평가 ───
  rating?: number;                // 0.0 ~ 5.0 (1자리 소수)
  review_count?: number;          // 정수
  rating_source?: 'google' | 'naver' | 'kakao';

  // ─── 미디어 ───
  photo_url?: string;             // 대표 사진 1장 (Google Places Photos API)
  photo_attribution?: string;     // "© Google" (필수: photo_url 있을 때)

  // ─── 설명 ───
  summary: string;                // 1~2문장 (max 100자)
  description?: string;           // 상세 설명 (선택, max 500자)

  // ─── 영업 정보 ───
  business_hours_today?: string;  // "09:00 - 22:00"
  is_open_now?: boolean;          // 응답 시점 기준
  next_open_time?: string;        // 닫혀있을 때 다음 오픈

  // ─── 가격 (Phase 2) ───
  price_level?: 1 | 2 | 3 | 4;    // Google price_level
  price_estimate?: string;        // "1인 약 8,000~15,000원"

  // ─── 액션 ───
  booking_url?: string;           // 카테고리별 딥링크
  phone?: string;                 // E.164 형식: "+82-2-1234-5678"
  website_url?: string;
}

interface TransitInfo {
  mode: TransitMode;
  mode_ko: string;                // "도보" | "지하철" | "버스" | "택시"
  distance_m: number;             // 이동 거리 (m)
  duration_min: number;           // 이동 시간 (분)

  // 대중교통 단계 (Phase 2, 카카오 내비 MCP)
  steps?: TransitStep[];

  // Phase 2 환승/요금
  fare?: {
    amount: number;               // 1450
    currency: 'KRW';
  };
}

interface TransitStep {
  type: 'walk' | 'subway' | 'bus';
  description: string;            // "5호선 광화문역 승차"
  duration_min: number;
  // 지하철/버스
  line_name?: string;             // "5호선"
  line_color?: string;            // "#996CAC"
  from_station?: string;          // "광화문역"
  to_station?: string;            // "을지로4가역"
  num_stops?: number;             // 3
}
```

### 5.2 `map_route` 블록 (지도 시각화용)

```ts
interface MapRouteBlockContent {
  // ─── 연결 ───
  course_id: string;              // course 블록과 동일

  // ─── 뷰포트 ───
  bounds: Bounds;                 // BE가 PostGIS ST_Extent로 미리 계산
  center: LatLng;                 // bounds 중심
  suggested_zoom: number;         // 1~20 (Kakao 기준)

  // ─── 마커 ───
  markers: MapMarker[];           // course.stops와 1:1 대응 (order 매칭)

  // ─── 폴리라인 ───
  polyline: MapPolyline;

  // ─── 지도 스타일 힌트 (선택) ───
  style?: {
    theme?: 'default' | 'dark' | 'satellite';
    show_traffic?: boolean;
    show_transit?: boolean;
  };
}

interface MapMarker {
  order: number;                  // course.stops[].order와 매칭
  position: LatLng;               // place.location 복제
  label: string;                  // place.name (마커 하단 표시)
  photo_url?: string;             // 포토 핀 썸네일 (place.photo_url 복제)
  category: PlaceCategory;        // 사진 없을 때 색상 fallback
  badge_text?: string;            // 번호 외 추가 뱃지 (예: "♥")
}

interface MapPolyline {
  // ─── Phase 구분 ───
  type: 'straight' | 'road';
  // straight: 두 점 사이 직선 (Phase 1)
  // road: 실제 도로 따라 N개 점 (Phase 2, OSRM/카카오 내비)

  // ─── 구간별 분리 ───
  segments: PolylineSegment[];
  // 빈 배열 가능 (stops가 1개일 때)
}

interface PolylineSegment {
  from_order: number;             // 출발 stop order
  to_order: number;               // 도착 stop order
  mode: TransitMode;              // 이 구간의 이동 수단

  // 좌표 배열 — GeoJSON [lng, lat]
  coordinates: Coordinate[];
  // straight: 항상 길이 2 (출발 + 도착)
  // road: 길이 N (도로 따라)

  // ─── 시각 스타일 (FE 기본값 있음, BE는 override만) ───
  style?: {
    color?: string;               // "#4A90E2"
    weight?: number;              // 6 (px)
    opacity?: number;             // 0.85
    dash_pattern?: number[];      // [5, 5] — 지하철 점선 등
  };

  // ─── 메타 (선택) ───
  distance_m?: number;            // 이 구간 거리
  duration_min?: number;          // 이 구간 시간
}
```

### 5.3 모드별 기본 폴리라인 스타일 (FE 기본값)

```ts
const POLYLINE_STYLES: Record<TransitMode, PolylineStyle> = {
  walk:    { color: '#4A90E2', weight: 6, opacity: 0.85 },
  subway:  { color: '#7C3AED', weight: 6, opacity: 0.85, dash_pattern: [4, 4] },
  bus:     { color: '#EA580C', weight: 6, opacity: 0.85, dash_pattern: [8, 4] },
  taxi:    { color: '#FBBF24', weight: 6, opacity: 0.85 },
  car:     { color: '#6B7280', weight: 6, opacity: 0.85 },
  bicycle: { color: '#10B981', weight: 6, opacity: 0.85 },
};
```

BE는 `style`을 비워두고 FE 기본값에 위임하는 것을 권장. 특별한 강조가 필요할 때만 override.

---

## 6. 검증 규칙

BE는 응답 전 반드시 다음을 검증:

| # | 규칙 | 위반 시 |
|---|------|--------|
| 1 | `course.stops.length >= 1` | 빈 코스 응답 불가. 검색 결과 없음으로 처리. |
| 2 | `stops[i].order` = i + 1 (연속, 1부터) | gap 있으면 reorder |
| 3 | 마지막 stop의 `transit_to_next` = null | 강제 null |
| 4 | 마지막 stop 외 모든 stop은 `transit_to_next != null` | 누락 시 walk/0 fallback |
| 5 | `total_duration_min == total_stay_min + total_transit_min` | 검증 후 보정 |
| 6 | `markers.length == stops.length` | 1:1 매칭 강제 |
| 7 | `markers[i].order == stops[i].order` | 순서 동일 |
| 8 | `polyline.segments.length == stops.length - 1` | stops가 1개면 segments 0개 |
| 9 | 모든 좌표는 한국 영역 내 (33 ≤ lat ≤ 39, 124 ≤ lng ≤ 132) | 외부 좌표 차단 |
| 10 | `photo_url` 있으면 `photo_attribution` 필수 | 저작권 표기 |
| 11 | `arrival_time` 형식 = `^\d{2}:\d{2}$` | 정규식 검증 |
| 12 | `course_id`는 ULID 또는 UUID | 형식 검증 |

---

## 7. 엣지 케이스

### 7.1 단일 경유지 코스

```json
{
  "course_id": "...",
  "stops": [{ "order": 1, ..., "transit_to_next": null }],
  "sections": [{ "id": "morning", "stop_orders": [1], ... }],
  "total_distance_m": 0,
  "total_transit_min": 0
}
```

```json
{
  "type": "map_route",
  "content": {
    "markers": [{ "order": 1, ... }],
    "polyline": { "type": "straight", "segments": [] }
  }
}
```

FE는 `segments` 비어있으면 폴리라인 렌더 스킵, 마커만 표시.

### 7.2 같은 장소 연속 방문 (드물지만 가능)

`stops[i].place.place_id == stops[i+1].place.place_id` 허용.
이 경우 marker는 두 번 렌더 (order만 다름). 폴리라인은 0 길이가 됨.

### 7.3 매우 긴 코스 (10+ stops)

| 항목 | 처리 |
|------|------|
| stops 배열 | 제한 없음. BE 권장 max 12. |
| 사이드 패널 | 가상 스크롤 불필요 (12개 이하) |
| 마커 | Kakao map clustering 미적용 (코스는 모든 마커 보여야 함) |
| 폴리라인 | 직선 = 좌표 12쌍, 도로 = 수백 점 — 카카오 polyline 1만 점까지 OK |

### 7.4 좌표가 매우 가까운 stops (200m 이내)

마커가 겹침 → FE에서 zIndex로 처리. BE는 그대로 전송.

### 7.5 장소 사진 누락

```json
{
  "place": {
    "name": "동네 카페",
    "photo_url": null  // 또는 필드 자체 누락
  }
}
```

FE 처리:
- 카드 썸네일: 카테고리 색상 배경 + 카테고리 첫 글자
- 마커: 카테고리 색상 원 + 번호 뱃지

### 7.6 영업시간 정보 없음

`business_hours_today`, `is_open_now` 모두 누락 → 카드에 영업 정보 줄 자체 숨김.

### 7.7 코스 생성 실패 (검색 결과 0건)

`course` 블록 보내지 않음. 대신:

```json
{ "type": "text", "content": "조건에 맞는 장소를 찾지 못했어요. 다른 키워드로 시도해보세요." }
{ "type": "done" }
```

### 7.8 부분 실패 (3개 중 1개 좌표 없음)

해당 stop은 코스에서 제외하고 order 재정렬. `course.metadata.dropped_count: 1` 추가.

### 7.9 응답 중 사용자가 새 메시지 전송

서버는 `course_plan_node` 진행 중이라면 cancel하고 새 메시지 처리. FE는 미완성 블록 무시.

---

## 8. 실제 응답 예시

### 8.1 일반적인 코스 (3 stops, 도보 위주)

```json
[
  {
    "schema_version": "1.0",
    "type": "intent",
    "content": "COURSE_PLAN"
  },
  {
    "schema_version": "1.0",
    "type": "text",
    "content": "서울 도심을 둘러보는 한나절 코스를 만들었어요! 광장시장에서 점심으로 시작해서 익선동과 경복궁까지 도보로 즐길 수 있는 동선이에요."
  },
  {
    "schema_version": "1.0",
    "type": "course",
    "content": {
      "course_id": "01HQA8KJ2N7B4PMXY3Z9R5VWST",
      "schema_version": "1.0",
      "title": "도심 한나절 코스",
      "description": "광장시장 → 익선동 → 경복궁. 도보 위주로 서울 도심을 즐기는 4시간 코스입니다.",
      "emoji": "🍜",
      "total_distance_m": 2400,
      "total_duration_min": 240,
      "total_stay_min": 210,
      "total_transit_min": 30,
      "date": "2026-04-08",
      "start_time": "11:00",
      "estimated_cost": {
        "min": 15000,
        "max": 30000,
        "currency": "KRW",
        "confidence": "medium",
        "source": "Google price_level + 블로그 추정"
      },
      "sections": [
        { "id": "morning", "label_ko": "오전", "stop_orders": [1] },
        { "id": "afternoon", "label_ko": "오후", "stop_orders": [2, 3] }
      ],
      "stops": [
        {
          "order": 1,
          "arrival_time": "11:00",
          "arrival_at": "2026-04-08T11:00:00+09:00",
          "duration_min": 60,
          "place": {
            "place_id": "kakao_place_8421",
            "name": "광장시장",
            "name_en": "Gwangjang Market",
            "category": "food",
            "category_label": "전통시장",
            "address": "서울 종로구 창경궁로 88",
            "address_short": "종로구",
            "district": "종로구",
            "location": { "lat": 37.5701, "lng": 126.9996 },
            "rating": 4.6,
            "review_count": 1245,
            "rating_source": "google",
            "photo_url": "https://lh3.googleusercontent.com/places/...",
            "photo_attribution": "© Google",
            "summary": "100년 역사의 전통시장. 빈대떡, 마약김밥, 육회의 성지.",
            "business_hours_today": "09:00 - 22:00",
            "is_open_now": true,
            "price_level": 1,
            "price_estimate": "1인 약 8,000~15,000원",
            "phone": "+82-2-2267-0291"
          },
          "transit_to_next": {
            "mode": "walk",
            "mode_ko": "도보",
            "distance_m": 800,
            "duration_min": 12
          },
          "recommendation_reason": "오픈 직후가 가장 한적해요"
        },
        {
          "order": 2,
          "arrival_time": "12:12",
          "arrival_at": "2026-04-08T12:12:00+09:00",
          "duration_min": 90,
          "place": {
            "place_id": "kakao_place_3214",
            "name": "익선동 한옥마을",
            "category": "culture",
            "category_label": "한옥마을",
            "address": "서울 종로구 익선동",
            "district": "종로구",
            "location": { "lat": 37.5743, "lng": 126.9912 },
            "rating": 4.5,
            "review_count": 892,
            "rating_source": "google",
            "photo_url": "https://lh3.googleusercontent.com/places/...",
            "photo_attribution": "© Google",
            "summary": "한옥 골목 사이 카페와 갤러리가 모인 힙플레이스."
          },
          "transit_to_next": {
            "mode": "walk",
            "mode_ko": "도보",
            "distance_m": 1200,
            "duration_min": 18
          }
        },
        {
          "order": 3,
          "arrival_time": "14:00",
          "arrival_at": "2026-04-08T14:00:00+09:00",
          "duration_min": 60,
          "place": {
            "place_id": "kakao_place_1001",
            "name": "경복궁",
            "name_en": "Gyeongbokgung Palace",
            "category": "tourism",
            "category_label": "고궁",
            "address": "서울 종로구 사직로 161",
            "district": "종로구",
            "location": { "lat": 37.5796, "lng": 126.977 },
            "rating": 4.8,
            "review_count": 8421,
            "rating_source": "google",
            "photo_url": "https://lh3.googleusercontent.com/places/...",
            "photo_attribution": "© Google",
            "summary": "조선 왕조의 정궁. 근정전과 경회루가 핵심.",
            "business_hours_today": "09:00 - 18:00",
            "is_open_now": true,
            "price_level": 1,
            "price_estimate": "성인 3,000원"
          },
          "transit_to_next": null,
          "recommendation_reason": "오후 햇살에 가장 예뻐요"
        }
      ],
      "actions": {
        "open_in_kakao_map": "https://map.kakao.com/?...",
        "share_url": "https://localbiz.app/share/01HQA8KJ2N7B4PMXY3Z9R5VWST"
      },
      "reasoning": {
        "summary": "도보 위주, 점심 시간대 혼잡 회피",
        "factors": ["광장시장 11시 오픈 직후 한적", "오후 햇살에 경복궁 촬영 적기"]
      }
    }
  },
  {
    "schema_version": "1.0",
    "type": "map_route",
    "content": {
      "course_id": "01HQA8KJ2N7B4PMXY3Z9R5VWST",
      "bounds": {
        "sw": { "lat": 37.5701, "lng": 126.977 },
        "ne": { "lat": 37.5796, "lng": 126.9996 }
      },
      "center": { "lat": 37.5748, "lng": 126.9883 },
      "suggested_zoom": 15,
      "markers": [
        {
          "order": 1,
          "position": { "lat": 37.5701, "lng": 126.9996 },
          "label": "광장시장",
          "photo_url": "https://lh3.googleusercontent.com/places/...",
          "category": "food"
        },
        {
          "order": 2,
          "position": { "lat": 37.5743, "lng": 126.9912 },
          "label": "익선동 한옥마을",
          "photo_url": "https://lh3.googleusercontent.com/places/...",
          "category": "culture"
        },
        {
          "order": 3,
          "position": { "lat": 37.5796, "lng": 126.977 },
          "label": "경복궁",
          "photo_url": "https://lh3.googleusercontent.com/places/...",
          "category": "tourism"
        }
      ],
      "polyline": {
        "type": "straight",
        "segments": [
          {
            "from_order": 1,
            "to_order": 2,
            "mode": "walk",
            "coordinates": [[126.9996, 37.5701], [126.9912, 37.5743]],
            "distance_m": 800,
            "duration_min": 12
          },
          {
            "from_order": 2,
            "to_order": 3,
            "mode": "walk",
            "coordinates": [[126.9912, 37.5743], [126.977, 37.5796]],
            "distance_m": 1200,
            "duration_min": 18
          }
        ]
      }
    }
  },
  {
    "schema_version": "1.0",
    "type": "references",
    "content": [
      { "label": "Google Places", "url": "https://maps.google.com/?cid=..." },
      { "label": "카카오맵", "url": "https://map.kakao.com/..." }
    ]
  },
  { "schema_version": "1.0", "type": "done" }
]
```

### 8.2 혼합 교통수단 코스 (도보 + 지하철)

`polyline.segments`에서 두 번째 segment의 mode가 `subway`인 경우:

```json
{
  "from_order": 1,
  "to_order": 2,
  "mode": "subway",
  "coordinates": [[127.0276, 37.4979], [126.9826, 37.5172]],
  "style": { "dash_pattern": [4, 4] },
  "distance_m": 6500,
  "duration_min": 18
}
```

대응 `course.stops[0].transit_to_next`:

```json
{
  "mode": "subway",
  "mode_ko": "지하철",
  "distance_m": 6500,
  "duration_min": 18,
  "steps": [
    { "type": "walk", "description": "강남역까지 도보", "duration_min": 3 },
    {
      "type": "subway",
      "description": "2호선 강남역 → 을지로입구역",
      "duration_min": 12,
      "line_name": "2호선",
      "line_color": "#00A84D",
      "from_station": "강남역",
      "to_station": "을지로입구역",
      "num_stops": 7
    },
    { "type": "walk", "description": "을지로입구역 → 도착", "duration_min": 3 }
  ],
  "fare": { "amount": 1450, "currency": "KRW" }
}
```

---

## 9. Phase 별 변화

| 필드 | Phase 1 (현재) | Phase 2 (카카오 MCP) |
|------|---------------|----------------------|
| `polyline.type` | `'straight'` | `'road'` |
| `polyline.segments[].coordinates` | 길이 2 | 길이 N (도로 따라) |
| `transit_to_next.steps` | 없음 | 채워짐 |
| `transit_to_next.fare` | 없음 | 채워짐 |
| `total_duration_min` | LLM 추정 | 실시간 교통 반영 |
| `is_open_now` | 응답 시점 1회 | 동일 |
| `estimated_cost` | LLM 추정 (low confidence) | 블로그 분석 (medium) |

**스키마는 동일.** FE 코드 변경 없음. BE만 더 정확한 데이터 채워주면 됨.

---

## 10. 에러 응답

### 10.1 코스 생성 실패

```json
[
  { "schema_version": "1.0", "type": "intent", "content": "COURSE_PLAN" },
  { "schema_version": "1.0", "type": "text", "content": "조건에 맞는 코스를 만들지 못했어요. 카테고리나 지역을 조금 더 구체적으로 알려주실 수 있나요?" },
  { "schema_version": "1.0", "type": "done" }
]
```

### 10.2 부분 데이터 누락

```json
{
  "type": "course",
  "content": {
    "stops": [...],
    "metadata": {
      "dropped_count": 2,
      "dropped_reason": "좌표 정보 누락"
    }
  }
}
```

### 10.3 시스템 에러 (LLM/API 실패)

WebSocket frame:
```json
{
  "schema_version": "1.0",
  "type": "error",
  "content": {
    "code": "LLM_TIMEOUT",
    "message": "응답 생성에 시간이 너무 오래 걸려요. 다시 시도해주세요.",
    "retryable": true
  }
}
```

FE는 에러 토스트 표시 + "다시 시도" 버튼.

---

## 11. 버전 관리

### 11.1 schema_version 정책

- **Major (1.0 → 2.0)**: Breaking change. FE/BE 동시 배포 필요.
  - 필드 삭제, 타입 변경, 필수 필드 추가
- **Minor (1.0 → 1.1)**: Backward compatible.
  - 새 optional 필드 추가, enum 값 추가

### 11.2 deprecated 필드 처리

```json
{
  "schema_version": "1.1",
  "type": "course",
  "content": {
    "old_field": "...",  // deprecated
    "new_field": "...",  // 사용 권장
    "_deprecations": {
      "old_field": { "removed_in": "2.0", "use_instead": "new_field" }
    }
  }
}
```

### 11.3 FE에서 수신 시 처리

```ts
function handleBlock(envelope: BlockEnvelope) {
  const [major] = envelope.schema_version.split('.');
  if (major !== '1') {
    console.error('Unsupported schema version:', envelope.schema_version);
    return;
  }
  // 처리 진행
}
```

---

## 12. FE 렌더링 의사 코드

```ts
// 1. 블록 수신
ws.onmessage = (event) => {
  const block: BlockEnvelope = JSON.parse(event.data);

  switch (block.type) {
    case 'intent':
      setIntent(block.content);
      break;

    case 'text':
      appendText(block.content);
      break;

    case 'course': {
      const course = block.content as CourseBlockContent;

      // mapStore의 navigation 상태 업데이트
      mapStore.startNavigation({
        id: course.course_id,
        title: course.title,
        date: course.date ?? '',
        // CoursePlace → Place 변환
        stops: course.stops.map((s) => ({
          order: s.order,
          placeId: s.place.place_id,
          placeName: s.place.name,
          arrivalTime: s.arrival_time,
          duration: s.duration_min,
          transportToNext: s.transit_to_next?.mode ?? 'walk',
          travelTimeToNext: s.transit_to_next?.duration_min ?? 0,
        })),
      });

      // 장소 데이터를 별도로 캐싱 (사이드 패널이 직접 조회)
      placeCache.setMany(
        course.stops.map((s) => convertCoursePlaceToPlace(s.place))
      );
      break;
    }

    case 'map_route': {
      const route = block.content as MapRouteBlockContent;

      // markers는 mapStore.markers와 별도. 폴리라인 좌표를 따로 저장.
      mapStore.setRoutePolyline({
        bounds: route.bounds,
        center: route.center,
        zoom: route.suggested_zoom,
        segments: route.polyline.segments,
      });
      break;
    }

    case 'references':
      setReferences(block.content);
      break;

    case 'done':
      setStreaming(false);
      enableInput();
      break;
  }
};

// 2. KakaoMap에서 폴리라인 그리기
function drawPolyline(segments: PolylineSegment[]) {
  segments.forEach((seg) => {
    const path = seg.coordinates.map(([lng, lat]) => new kakao.maps.LatLng(lat, lng));
    const style = seg.style ?? POLYLINE_STYLES[seg.mode];
    new kakao.maps.Polyline({
      path,
      strokeWeight: style.weight ?? 6,
      strokeColor: style.color ?? '#4A90E2',
      strokeOpacity: style.opacity ?? 0.85,
      strokeStyle: style.dash_pattern ? 'dash' : 'solid',
    }).setMap(map);
  });
}
```

---

## 13. 성능 및 캐싱

### 13.1 응답 크기 추정

| 항목 | 크기 |
|------|------|
| 1개 stop (사진 URL 포함) | ~1.5KB |
| `course` 블록 (3 stops) | ~5KB |
| `map_route` 블록 (3 stops, straight) | ~1KB |
| `map_route` 블록 (3 stops, road N=200) | ~10KB |
| 전체 응답 (3 stops, Phase 1) | ~10KB |
| 전체 응답 (3 stops, Phase 2 도로) | ~20KB |

WebSocket 프레임 크기 제한 없으나, 단일 frame 100KB 이하 권장.

### 13.2 BE 캐싱 키

```
course:{user_id_hash}:{query_hash}:{date}
```

같은 사용자가 같은 쿼리를 같은 날짜에 다시 요청하면 캐시 히트. TTL 1시간.

### 13.3 photo_url 캐싱

Google Places Photos API URL은 매번 새로 생성됨 → BE가 7일 캐시 후 재발급.

### 13.4 FE 렌더 성능

- `course.stops` 12개 이하 → 가상화 불필요
- 폴리라인 좌표 1만 점 이하 → Kakao 정상 렌더
- 마커 50개 이하 → clustering 불필요 (코스는 모든 마커 표시)

---

## 14. BE 구현 체크리스트

### 14.1 응답 생성 전

- [ ] `course_id`는 ULID/UUID로 생성
- [ ] `stops`를 거리 기반 greedy nearest-neighbor로 정렬
- [ ] 시간대 그룹화 (`sections`) BE에서 미리 계산
- [ ] `total_duration_min == total_stay_min + total_transit_min` 검증
- [ ] PostGIS `ST_Extent`로 `bounds` 계산
- [ ] `bounds` 중심으로 `center` 계산
- [ ] `suggested_zoom`은 bounds 크기에 비례 (대각선 < 1km → 16, < 5km → 14)

### 14.2 좌표 검증

- [ ] 모든 좌표 한국 영역 내 (33 ≤ lat ≤ 39, 124 ≤ lng ≤ 132)
- [ ] `[lng, lat]` 순서 (GeoJSON 표준)
- [ ] 단일 점은 `{ lat, lng }` 객체

### 14.3 photo_url 처리

- [ ] Google Places `photo_reference`로 URL 생성
- [ ] `photo_attribution` 필수 표기 ("© Google")
- [ ] 이미지 없는 장소는 `photo_url` 필드 자체 누락 (null 아님)

### 14.4 시간 처리

- [ ] 모든 시간 KST (`+09:00`) 명시
- [ ] `arrival_time`은 `HH:mm` 정규식 검증
- [ ] `arrival_at`은 ISO 8601 with timezone

### 14.5 검증 후 전송

- [ ] §6 검증 규칙 12개 모두 통과
- [ ] 블록 순서: intent → text → course → map_route → references → done
- [ ] `done` 블록 마지막에 반드시 전송

### 14.6 에러 처리

- [ ] 빈 결과 → `text` + `done`만 전송 (`course` 블록 없음)
- [ ] 부분 실패 → `metadata.dropped_count` 표시
- [ ] 시스템 에러 → `error` 블록 전송 (retryable 표시)

---

## 부록 A: 카테고리별 booking_url 도메인

| category | 권장 도메인 |
|----------|------------|
| food | `naver.com/booking`, `catchtable.co.kr` |
| performance | `interpark.com`, `yes24.com`, `kopis.or.kr` |
| culture | `seoul.go.kr/seoulpass`, 해당 시설 사이트 |
| public | `yeyak.seoul.go.kr` |
| accommodation | `goodchoice.kr`, `yanolja.com` |
| tourism | 해당 시설 사이트 |

## 부록 B: PlaceCategory ↔ category_label 매핑

| category | category_label 예시 |
|----------|---------------------|
| tourism | "고궁", "박물관", "전망대" |
| food | "한식", "전통시장", "노포" |
| cafe | "카페", "디저트" |
| culture | "한옥마을", "전시관", "갤러리" |
| shopping | "쇼핑몰", "거리상권" |
| performance | "뮤지컬", "콘서트" |
| festival | "축제" |
| public | "공원", "도서관" |
| accommodation | "호텔", "게스트하우스" |

`category_label`은 BE가 한국어로 정해서 보내고, FE는 그대로 표시.

---

## 부록 C: 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-04-07 | 최초 작성 |
