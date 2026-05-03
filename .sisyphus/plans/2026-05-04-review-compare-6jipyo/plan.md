# REVIEW_COMPARE — 장소 6지표 비교 (레이더 차트)

- Phase: P1
- 요청자: joseph054
- 작성일: 2026-05-04
- 상태: APPROVED

## 1. 요구사항

사용자가 "스타벅스 vs 블루보틀 비교"처럼 2개 이상의 장소를 비교 요청하면
OS `place_reviews._raw_scores` (6지표)를 조회하여 레이더 차트로 응답한다.

**엔드포인트**: `GET /api/v1/chat/stream?query=스타벅스 vs 블루보틀 비교`

**응답 블록 순서** (기획서 §4.5 REVIEW_COMPARE):
```
intent → status → text_stream → chart → analysis_sources → done
```

**chart 블록 스펙** (`기획/API 명세서 v2 (SSE)...csv` L157 준수):
```json
{
  "type": "chart",
  "chart_type": "radar",
  "places": [
    { "name": "스타벅스 홍대점", "scores": { "satisfaction": 3.5, "accessibility": 4.0, "cleanliness": 3.0, "value": 2.5, "atmosphere": 4.5, "expertise": 4.0 } },
    { "name": "블루보틀 삼청점", "scores": { "satisfaction": 4.2, "accessibility": 3.0, "cleanliness": 4.5, "value": 3.0, "atmosphere": 4.8, "expertise": 4.2 } }
  ]
}
```

**데이터 소스**: OS `place_reviews` 인덱스 (7,572건 — 2026-05-04 curl 직접 실측. `ETL_적재_현황.md` L46은 구버전 ~500건 기재, 이 plan에서 갱신 예정)

**장소명 1개만 입력 시**: `disambiguation` 블록 반환 — `message: "어느 장소와 비교하시겠어요?"`, `candidates: []` (후보 제시 없이 안내만). 2개 이상인 경우에만 정상 흐름.

**Phase 위치**: P1 — `기획/API 명세서 v2 (SSE)...csv` L155에 Phase 1로 명시. `intent_router_node.py` L29 enum 주석 "Phase 2"는 구버전이므로 이 plan에서 수정.

## 2. 영향 범위

- **신규 파일**:
  - `backend/src/graph/review_compare_node.py`
  - `backend/tests/test_review_compare_node.py`
- **수정 파일**:
  - `backend/src/models/blocks.py` — `ChartBlock` 구조 변경 (`datasets` → `places`, `ChartDataset` → `ChartPlaceScore`). 기획서 v2 SSE L157 준수.
  - `backend/src/graph/intent_router_node.py` — REVIEW_COMPARE 활성화, enum 주석 Phase 1로 정정
  - `backend/src/graph/real_builder.py` — REVIEW_COMPARE 라우팅 추가
  - `기획/ETL_적재_현황.md` — L46 ~500 → ~7,572 (실측 기준)
- **DB 스키마 영향**: 없음 (OS 읽기 전용)
- **응답 블록 16종 영향**: `chart` 블록 내부 스키마 변경 (기획서 v2 SSE L157 이미 정의). 16종 목록 자체는 유지.
- **intent 추가/변경**: `REVIEW_COMPARE` — `PHASE1_INTENTS` + `_ROUTABLE_INTENTS` 양쪽 추가
- **외부 API 호출**: OS `place_reviews` 인덱스 조회 (기존 OS client 재사용)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — places 조회 시 UUID 사용
- [x] PG↔OS 동기화 — place_id 기준 OS 조회, doc id = `review_{place_id}` (crawl_reviews.py L431 패턴)
- [x] append-only 4테이블 미수정 — place_reviews는 OS 인덱스, PG append-only 테이블 미접촉
- [x] 소프트 삭제 매트릭스 준수 — places PG 조회 시 `is_deleted=false` 필터 (OS는 해당 없음)
- [x] 의도적 비정규화 **3건** 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존 — 이름/개수 그대로 (satisfaction/accessibility/cleanliness/value/atmosphere/expertise)
- [x] gemini-embedding-001 768d 사용 — 임베딩 미호출
- [x] asyncpg 파라미터 바인딩 — places PG 조회 시 `$1`, `$2` 바인딩, f-string SQL 금지
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — chart, analysis_sources 기존 타입 사용
- [x] intent별 블록 순서 (기획 §4.5) 준수 — intent→status→text_stream→chart→analysis_sources→done
- [x] 공통 쿼리 전처리 경유 — processed_query에서 keywords/query로 장소명 추출
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 보존
- [x] 인증 매트릭스 준수
- [x] 북마크 패러다임 준수
- [x] 공유링크 인증 우회 범위 정확
- [x] Phase 라벨 명시 — P1 (파일 헤더 docstring 및 IntentType 주석)
- [x] 기획 문서 우선 — chart 내부 스키마는 기획서 v2 SSE L157 준수. ETL_적재_현황.md 실측 기준 갱신 포함

## 4. 작업 순서 (Atomic step)

### g1 — blocks.py ChartBlock 스키마 수정 (quick)
1. `ChartDataset` → `ChartPlaceScore` rename:
   - 기존 flat 필드 제거
   - `name: str`
   - `scores: dict[str, float]` (6지표 키 그대로)
2. `ChartBlock.datasets: list[ChartDataset]` → `ChartBlock.places: list[ChartPlaceScore]`
3. `CONTENT_BLOCK_TYPES` 등록 유지 (타입명 "chart" 불변)
4. 라운드트립 확인: `deserialize_block({"type":"chart","chart_type":"radar","places":[{"name":"X","scores":{"satisfaction":4.0,...}}]})` ValidationError 없음

> verify: `ruff check src && pyright src`

### g2 — review_compare_node.py 신규 작성 (deep)

**step 1**: `_extract_place_names(processed_query, query) → list[str]` 순수 함수
- **1차**: 원본 query에서 ` vs ` / ` VS ` / ` 와 ` 토큰으로 split (공백 포함 — "강남대로" 등 false positive 방지)
- **2차 fallback**: processed_query.keywords 리스트가 2개 이상이면 사용
- 결과 2개 미만 → `[]` 반환 → 노드에서 disambiguation 블록 반환

**step 2**: `_fetch_places_pg(pool, names: list[str]) → list[dict]`
- 각 name에 대해 `SELECT place_id, name, category, district FROM places WHERE is_deleted=false AND name ILIKE $1 LIMIT 10` (asyncpg `$1` 바인딩)
- 동명 다중 매칭 시 결정 규칙: 동일 함수 내에서 `place_id` 후보 목록을 가지고 OS mget 호출 → `stars` 최댓값 1건 채택. OS 문서 없으면 PG 결과 첫 번째 row 사용. (step 3의 mget과 중복되지 않도록 이 내부 OS 조회는 `place_id` 목록 → doc id 변환 → mget 1회로 처리)

**step 3**: `_fetch_scores_os(os_client, place_ids: list[str]) → dict[str, dict]`
- doc id = `review_{place_id}` (crawl_reviews.py L431 패턴)
- OS mget API 1회 호출: `{"ids": ["review_<id1>", "review_<id2>"]}`
- `_source._raw_scores` 추출. 문서 없으면 해당 place_id는 `scores = {}`

**step 4**: `_build_compare_blocks(query, places, scores_map) → list[dict]`
- `text_stream` 블록 — **raw dict** (sse.py는 `block["system"]`/`block["prompt"]` 키를 직접 읽음. `TextStreamBlock` Pydantic 인스턴스 사용 금지):
  ```python
  {
    "type": "text_stream",
    "system": _COMPARE_SYSTEM_PROMPT,
    "prompt": f"사용자 질문: {query}\n\n장소 비교:\n{비교_텍스트}"
  }
  ```
- `chart` 블록 (raw dict):
  ```python
  {
    "type": "chart",
    "chart_type": "radar",
    "places": [{"name": p["name"], "scores": scores_map.get(p["place_id"], {})} for p in places]
  }
  ```
- `analysis_sources` 블록 (raw dict):
  ```python
  {"type": "analysis_sources", "review_count": len([p for p in places if scores_map.get(p["place_id"])])}
  ```

**step 5**: `review_compare_node(state) → dict` — LangGraph 노드
- 장소명 추출 2개 미만 → `{"response_blocks": [{"type": "disambiguation", "message": "어느 장소와 비교하시겠어요?", "candidates": []}]}`
- PG 조회 후 `len(places) == 0` → disambiguation ("장소를 찾을 수 없어요. 정확한 장소명으로 다시 입력해주세요.")
- PG 조회 후 `len(places) == 1` → text_stream으로 찾은 장소 소개 ("X는 찾을 수 없었어요. 대신 Y를 소개해드릴게요.")
- 정상 흐름: _extract → _fetch_places_pg → _fetch_scores_os → _build_compare_blocks 순 호출

> verify: `pytest tests/test_review_compare_node.py -v`

### g3 — intent_router_node.py 활성화 (quick)
1. `PHASE1_INTENTS`에 `IntentType.REVIEW_COMPARE` 추가 (**핵심**: L166 게이트 통과)
2. `_ROUTABLE_INTENTS`에 `IntentType.REVIEW_COMPARE` 추가
3. `_CLASSIFY_SYSTEM_PROMPT` — "Phase 2 (not yet active)" 목록에서 REVIEW_COMPARE 제거 → Phase 1 active 목록에 추가: `"REVIEW_COMPARE: comparing two or more places by 6 metrics"`
4. `IntentType` enum L29 주석 `# Phase 2` → `# Phase 1 (기획서 v2 SSE L155)` 수정

> verify: `pytest tests/ -k "intent" -v`

### g4 — real_builder.py 라우팅 추가 (langgraph-node)
1. `review_compare_node` import
2. `add_node("review_compare", review_compare_node)`
3. `conditional_edges`에 `"REVIEW_COMPARE": "review_compare"` 추가

> verify: `python -c "from src.graph.real_builder import build_graph; build_graph()"`

### g5 — 단위 테스트 (deep)
`tests/test_review_compare_node.py` — **mock 전략**: `unittest.mock.AsyncMock`으로 `pool.fetch`, `pool.fetchrow`, `os_client.mget` mock.

- `test_extract_place_names_vs`: "스타벅스 vs 블루보틀" → ["스타벅스", "블루보틀"]
- `test_extract_place_names_wa`: "스타벅스 와 블루보틀 비교" → ["스타벅스", "블루보틀"]
- `test_extract_place_names_single`: "스타벅스 리뷰" → [] (disambiguation 트리거)
- `test_extract_place_names_disambiguous`: "강남대로 vs 홍대" → ["강남대로", "홍대"] (공백 포함 패턴 검증)
- `test_fetch_places_pg_multiple_match`: 동명 3개 매칭 중 OS stars 최대값 채택 검증 (AsyncMock으로 PG 3행, OS mget 3건 반환)
- `test_build_compare_blocks_success`: places 2개 + scores 있을 때 text_stream/chart/analysis_sources raw dict 구조 검증, chart.places 배열 2개 + scores 6키 확인
- `test_build_compare_blocks_no_scores`: OS 문서 없는 장소 → `scores = {}` → chart.places에 포함, 에러 아님
- `test_review_compare_node_disambiguation`: 장소명 1개 → disambiguation 블록 반환

> verify: `pytest tests/test_review_compare_node.py -v`

### g6 — ETL_적재_현황.md 갱신 (quick)
- `기획/ETL_적재_현황.md` L46: `~500` → `~7,572` (2026-05-04 OS curl 실측)

> verify: `grep "7,572" 기획/ETL_적재_현황.md`

## 5. 검증 계획

- `./validate.sh` 전체 통과
- `pytest tests/test_review_compare_node.py -v` — 8개 케이스 모두 통과
- 수동 시나리오:
  1. `GET /api/v1/chat/stream?query=스타벅스 vs 블루보틀 비교` → SSE에서 `chart.places` 배열 2개 + `scores` 6키 확인
  2. OS에 없는 장소명 → `chart.places[n].scores = {}` (에러 아님)
  3. 장소명 1개 입력 → `disambiguation` 블록 반환 확인

## 6. 최종 결정

APPROVED — Metis v3 okay (003) + Momus v3 approved (004). 구현 진입 가능.
