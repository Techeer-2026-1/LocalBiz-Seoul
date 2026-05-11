# COURSE_PLAN 노드 구현 — 카테고리별 병렬 검색 → Greedy NN → course + map_route

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-05
- 상태: approved

## 1. 요구사항

API 명세서: `intent → text_stream → course → map_route → done`

"홍대 카페+맛집 코스 추천해줘" 같은 요청에 카테고리별 장소를 병렬 검색 → 거리 기반 경로 최적화 → 코스 타임라인 + 지도 경로 응답.

기능 명세서 정의: "카테고리별 병렬 검색 → ST_DWithin → Greedy NN → OSRM"

> **Phase 1 단순화:** OSRM은 외부 서비스 의존이므로 Phase 1에서는 straight-line 직선 거리 기반 Greedy NN으로 구현. polyline.type="straight". Phase 2에서 OSRM road polyline으로 교체 (스키마 변경 없음, 기획서 api-course-quick-spec.md §Phase 1 vs Phase 2 참조).

### 핵심 흐름

```text
processed_query (category[], district, neighborhood, keywords)
  → ① 카테고리별 PG + OS 병렬 검색 (place_recommend 패턴 재활용)
  → ② 후보 풀 병합 + 중복 제거
  → ③ Greedy NN 경로 최적화 (직선 거리 기반 최근접 이웃)
  → ④ LLM 코스 구성 (Gemini Flash — 시간대 배분 + 추천 사유)
  → ⑤ 블록 생성: text_stream + course + map_route
```

### 코스 응답 스키마 (기획서 api-course-quick-spec.md 준수)

- `course` 블록: stops[{order, place, duration_min, transit_to_next}], sections(시간대 그룹)
- `map_route` 블록: markers + polyline(straight segments) + bounds/center
- `course_id`로 두 블록 연결
- 좌표: 단일점 {lat, lng}, 배열 [lng, lat] (GeoJSON)
- 1-indexed order

## 2. 영향 범위

- 신규 파일: `backend/src/graph/course_plan_node.py`
- 수정 파일: `backend/src/graph/real_builder.py` (stub → 실제 import 교체)
- 수정 파일: `backend/src/graph/response_builder_node.py` (COURSE_PLAN 블록 순서 등록)
- 수정 파일: `backend/src/models/blocks.py` (CourseStop/CourseBlock/MapRouteBlock를 api-course-quick-spec.md 스키마에 맞게 재정의)
- DB 스키마 영향: 없음 (기존 places + places_vector 활용)
- 응답 블록 16종 영향: 기존 course + map_route 블록 사용 (신규 타입 없음). blocks.py Pydantic 모델을 spec에 맞게 확장하되 CONTENT_BLOCK_TYPES 레지스트리 호환 유지.
- intent 추가/변경: 없음 (COURSE_PLAN 이미 등록됨)
- 외부 API 호출: Gemini 2.5 Flash (코스 구성 + text_stream용, 1회당 1호출, 입력 ~3K tokens — 후보 장소 메타 + 사용자 조건. RPM 한도 초과 시 Greedy NN 순서 그대로 반환하는 graceful degradation)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — places는 UUID(VARCHAR(36))
- [x] PG↔OS 동기화 — place_id == places_vector._id
- [x] append-only 4테이블 미수정 — SELECT만 사용
- [x] 소프트 삭제 매트릭스 준수 — is_deleted=false 필터 (places 테이블 검증 필요 — init_db.sql 갭 인지)
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존 — 미사용
- [x] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [x] asyncpg 파라미터 바인딩 ($1, $2)
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — 기존 타입만 사용 (text_stream, course, map_route)
- [x] intent별 블록 순서 (기획 §4.5) 준수 — text_stream → course → map_route → done. Phase 1에서 references 미포함 (리뷰 인용 불필요, Phase 2 확장). map_route는 optional.
- [x] 공통 쿼리 전처리 경유 — query_preprocessor 결과 활용
- [ ] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [ ] 대화 이력 이원화 보존 — 해당 없음
- [ ] 인증 매트릭스 준수 — 해당 없음
- [ ] 북마크 = 대화 위치 패러다임 — 해당 없음
- [ ] 공유링크 인증 우회 범위 — 해당 없음
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — api-course-quick-spec.md 스키마 준수

## 4. 작업 순서 (Atomic step)

1. **blocks.py CourseStop/CourseBlock/MapRouteBlock 재정의** (category: `deep`)
   - CourseStop: order, arrival_time, duration_min, place{place_id, name, category, category_label, address, district, location{lat,lng}, rating(Optional), summary}, transit_to_next{mode, mode_ko, distance_m, duration_min}|null, recommendation_reason
   - Phase 1 포함 place 필드: place_id, name, category, category_label, address, district, location, summary
   - Phase 1 Optional place 필드: rating (DB 데이터 있으면 포함)
   - Phase 1 생략 place 필드 (Optional 선언): photo_url, photo_attribution, business_hours_today, is_open_now, booking_url
   - CourseBlock: type="course", course_id(UUID4), title, description, total_distance_m, total_duration_min, total_stay_min, total_transit_min, stops: list[CourseStop]. Phase 1 생략 필드: sections, emoji, actions, schema_version, photo_url/attribution/business_hours (Optional로 선언)
   - MapRouteBlock: type="map_route", course_id, bounds{sw,ne}, center{lat,lng}, suggested_zoom, markers[{order, position{lat,lng}, label, category}], polyline{type:"straight", segments[{from_order, to_order, mode, coordinates[[lng,lat],...]}]}
   - CONTENT_BLOCK_TYPES 레지스트리 호환 유지
   - Pydantic 모델은 기존 blocks.py flat 패턴 유지 (spec의 `{type, schema_version, content:{...}}` wrapper는 적용하지 않음 — 기존 16종 블록 전부 flat 구조이며, FE가 flat 구조를 직접 소비)

2. **course_plan_node.py 신규 작성** (category: `langgraph-node`)
   - `_parse_course_categories()`: 쿼리에서 복수 카테고리 추출 ("카페+맛집" → ["카페", "맛집"])
   - `_search_places_by_category()`: 카테고리별 PG+OS 병렬 검색 (place_recommend 패턴 재활용). `_embed_query_768d()` 복제 (3번째 — TODO: Phase 1 이후 공유 유틸 추출 검토).
   - `_greedy_nn_route()`: 직선 거리 기반 Greedy Nearest Neighbor 경로 최적화. Haversine 거리 계산.
   - `_llm_course_compose()`: Gemini Flash로 시간대 배분 + 체류시간 + 추천 사유 생성. 실패 시 균등 배분 fallback.
   - `_build_course_blocks()`: course + map_route 블록 생성 (api-course-quick-spec.md 스키마). course_id는 UUID4 (spec은 ULID이나, 기존 프로젝트 PK 패턴과 일관성 유지 위해 UUID4 채택. spec api-course-quick-spec.md 갱신 예정: ULID→UUID4).
   - `_build_text_stream_block()`: 코스 소개 프롬프트 생성.
   - `course_plan_node()`: LangGraph 노드 엔트리 (state → response_blocks)

3. **real_builder.py 수정** (category: `quick`)
   - `_course_plan_node` stub 제거
   - `from src.graph.course_plan_node import course_plan_node` 추가
   - `graph.add_node("course_plan", course_plan_node)` 교체

4. **response_builder_node.py 수정** (category: `quick`)
   - `_EXPECTED_BLOCK_ORDER`에 COURSE_PLAN: `["intent", "text_stream", "course", "done"]` 등록
   - `_OPTIONAL_BLOCKS`에 `map_route` 추가 (이미 `references`는 PLACE_RECOMMEND에서 추가됨)
   - Phase 1에서 references 블록 미포함 (코스 추천은 리뷰 인용 불필요). spec의 `references`는 Phase 2 확장 시 추가.

5. **단위 테스트 작성** (category: `deep`)
   - `tests/test_course_plan_node.py`
   - 케이스: 정상 3-stop 코스, 단일 카테고리, 후보 0건(빈 결과), Greedy NN 경로 순서 검증, LLM 실패 fallback, course/map_route 블록 스키마 검증

## 5. 검증 계획

- `validate.sh` 6단계 통과
- 단위 테스트: `pytest tests/test_course_plan_node.py -v`
- 수동 시나리오:
  - "홍대 카페+맛집 코스" → course(stops 3-5개) + map_route(markers + straight polyline)
  - "강남역 근처 데이트 코스" → district 필터 + 시간대 배분
  - "카페 한 곳만" → 단일 stop 코스 (transit_to_next: null)
- smoke: `python -c "from src.graph.real_builder import build_graph; build_graph()"`
- course 블록 검증: stops order 1-indexed 연속, 마지막 transit_to_next null, markers.length == stops.length

## 6. 최종 결정

APPROVED (2026-05-05, Metis okay + Momus approved)
