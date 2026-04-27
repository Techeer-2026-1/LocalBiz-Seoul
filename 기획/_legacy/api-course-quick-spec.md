# 코스 API 응답 — Quick Spec

> 상세 명세: `docs/api-course-response-spec.md`
> 이 문서는 BE 구현 시 빠르게 참고하는 요약본.

---

## 한 줄 요약

채팅 응답으로 `course` + `map_route` 두 블록을 보낸다. `course_id`로 묶이고, 각각 자체 완결.

---

## 응답 흐름

```
intent → text → course → map_route → references → done
```

WebSocket frame 1개 = 1 block. JSON.

---

## 블록 1: `course`

```ts
{
  type: 'course',
  schema_version: '1.0',
  content: {
    course_id: string;          // ULID
    title: string;
    description: string;
    emoji?: string;

    total_distance_m: number;
    total_duration_min: number;
    total_stay_min: number;
    total_transit_min: number;

    sections: [{
      id: 'morning' | 'afternoon' | 'evening' | 'night';
      label_ko: string;         // "오전"
      stop_orders: number[];    // [1, 2]
    }];

    stops: [{
      order: number;            // 1부터 시작
      arrival_time: string;     // "11:00"
      duration_min: number;

      place: {
        place_id: string;
        name: string;
        category: PlaceCategory;
        category_label: string; // "전통시장"
        address: string;
        district: string;
        location: { lat, lng };
        rating?: number;
        photo_url?: string;
        photo_attribution?: string; // photo_url 있으면 필수
        summary: string;
        business_hours_today?: string;
        is_open_now?: boolean;
        booking_url?: string;
      };

      transit_to_next: {        // 마지막 stop은 null
        mode: 'walk' | 'subway' | 'bus' | 'taxi';
        mode_ko: string;
        distance_m: number;
        duration_min: number;
      } | null;

      recommendation_reason?: string;
    }];

    actions?: {
      open_in_kakao_map?: string;
      share_url?: string;
    };
  }
}
```

## 블록 2: `map_route`

```ts
{
  type: 'map_route',
  schema_version: '1.0',
  content: {
    course_id: string;          // course와 동일

    bounds: {
      sw: { lat, lng };         // 좌하단
      ne: { lat, lng };         // 우상단
    };
    center: { lat, lng };
    suggested_zoom: number;

    markers: [{
      order: number;            // course.stops[].order와 매칭
      position: { lat, lng };
      label: string;            // place.name
      photo_url?: string;
      category: PlaceCategory;
    }];

    polyline: {
      type: 'straight' | 'road';
      segments: [{
        from_order: number;
        to_order: number;
        mode: 'walk' | 'subway' | 'bus' | 'taxi';
        coordinates: [number, number][]; // [[lng, lat], ...] GeoJSON 표준
        distance_m?: number;
        duration_min?: number;
      }];
    };
  }
}
```

---

## 좌표 규칙

| 형태 | 용도 |
|------|------|
| `{ lat, lng }` | 단일 점 (location, position, center, bounds) |
| `[lng, lat]` | 배열 (polyline coordinates) — GeoJSON 표준 |

---

## 검증 규칙 (필수)

1. `stops` 1개 이상
2. `stops[i].order = i + 1` (1부터, 연속)
3. 마지막 stop의 `transit_to_next = null`
4. `markers.length == stops.length`
5. `markers[i].order == stops[i].order`
6. `polyline.segments.length == stops.length - 1`
7. `total_duration_min == total_stay_min + total_transit_min`
8. 모든 좌표 한국 영역 (lat 33~39, lng 124~132)
9. `photo_url` 있으면 `photo_attribution` 필수
10. `arrival_time` 형식 = `^\d{2}:\d{2}$`

---

## 엣지 케이스

| 케이스 | 처리 |
|--------|------|
| 단일 stop | `transit_to_next: null`, `polyline.segments: []` |
| 사진 없음 | `photo_url` 필드 누락 (null 아님) |
| 영업시간 없음 | `business_hours_today` 누락 |
| 결과 0건 | `course` 블록 보내지 않음. `text` + `done`만 전송 |
| 부분 실패 | 누락 stop 제외하고 reorder. `metadata.dropped_count` 추가 |

---

## Phase 1 vs Phase 2

| 필드 | Phase 1 | Phase 2 (카카오 MCP) |
|------|---------|----------------------|
| `polyline.type` | `'straight'` | `'road'` |
| `polyline.segments[].coordinates` | 길이 2 | 길이 N (도로 따라) |
| `transit_to_next.steps` | 없음 | 대중교통 단계 |

**같은 스키마.** FE 변경 없음.

---

## 응답 예시 (최소)

```json
[
  { "type": "intent", "content": "COURSE_PLAN" },
  { "type": "text", "content": "도심 한나절 코스를 만들었어요!" },
  {
    "type": "course",
    "schema_version": "1.0",
    "content": {
      "course_id": "01HQA8KJ2N7B4PMXY3Z9R5VWST",
      "title": "도심 한나절 코스",
      "description": "광장시장 → 익선동 → 경복궁 도보 코스",
      "total_distance_m": 2400,
      "total_duration_min": 240,
      "total_stay_min": 210,
      "total_transit_min": 30,
      "sections": [
        { "id": "morning", "label_ko": "오전", "stop_orders": [1] },
        { "id": "afternoon", "label_ko": "오후", "stop_orders": [2, 3] }
      ],
      "stops": [
        {
          "order": 1,
          "arrival_time": "11:00",
          "duration_min": 60,
          "place": {
            "place_id": "kakao_8421",
            "name": "광장시장",
            "category": "food",
            "category_label": "전통시장",
            "address": "서울 종로구 창경궁로 88",
            "district": "종로구",
            "location": { "lat": 37.5701, "lng": 126.9996 },
            "rating": 4.6,
            "photo_url": "https://...jpg",
            "photo_attribution": "© Google",
            "summary": "100년 역사의 전통시장."
          },
          "transit_to_next": {
            "mode": "walk",
            "mode_ko": "도보",
            "distance_m": 800,
            "duration_min": 12
          }
        },
        {
          "order": 2,
          "arrival_time": "12:12",
          "duration_min": 90,
          "place": { "...": "..." },
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
          "duration_min": 60,
          "place": { "...": "..." },
          "transit_to_next": null
        }
      ]
    }
  },
  {
    "type": "map_route",
    "schema_version": "1.0",
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
          "photo_url": "https://...jpg",
          "category": "food"
        }
      ],
      "polyline": {
        "type": "straight",
        "segments": [
          {
            "from_order": 1,
            "to_order": 2,
            "mode": "walk",
            "coordinates": [[126.9996, 37.5701], [126.9912, 37.5743]]
          }
        ]
      }
    }
  },
  { "type": "done" }
]
```

---

## 핵심 원칙 5개

1. **자체 완결** — `place_id`만 보내지 말고 `place` 데이터 전체 포함
2. **두 블록 분리** — `course` (패널) + `map_route` (지도), `course_id`로 묶기
3. **좌표 표준** — 단일점 `{lat, lng}`, 배열 `[lng, lat]`
4. **1-indexed** — order는 1부터 시작
5. **Phase 호환** — straight → road 전환 시 스키마 변경 없음
