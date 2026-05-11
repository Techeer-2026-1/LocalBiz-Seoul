# ANALYSIS — 단일 장소 6지표 분석 (런타임 Gemini 채점)

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-06
- 상태: APPROVED

## 1. 요구사항

사용자가 "이 카페 분석해줘", "스타벅스 홍대점 리뷰 분석" 같은 **단일 장소** 분석 요청 시
OS `place_reviews._raw_scores` (6지표)를 조회하고, Gemini로 리뷰 기반 분석 텍스트를 스트리밍한다.

**엔드포인트**: `GET /api/v1/chat/stream?query=이 카페 분석해줘`

**응답 블록 순서** (기획서 §4.5 ANALYSIS):
```
intent → status → text_stream → analysis_sources → done
```

**analysis_sources 블록 스펙** (`blocks.py` L274-282 기존 모델):
```json
{
  "type": "analysis_sources",
  "review_count": 45,
  "blog_count": null,
  "official_count": null,
  "sources": []
}
```

**데이터 소스**: OS `place_reviews` 인덱스 (~7,572건)

**장소명 추출 실패 시**: `disambiguation` 블록 — `message: "어떤 장소를 분석할까요? 장소명을 알려주세요."`, `candidates: []`

**장소 미발견 시**: `disambiguation` 블록 — `message: "장소를 찾을 수 없어요. 정확한 장소명으로 다시 입력해주세요."`

**OS 점수 없는 장소**: text_stream으로 "아직 리뷰 데이터가 충분하지 않아요" 안내. analysis_sources `review_count: 0`.

**REVIEW_COMPARE와의 차이**: REVIEW_COMPARE는 2+ 장소 비교(chart 블록 포함). ANALYSIS는 단일 장소 심층 분석(chart 없음, text_stream이 주력).

## 2. 영향 범위

- **신규 파일**:
  - `backend/src/graph/analysis_node.py`
  - `backend/tests/test_analysis_node.py`
- **수정 파일**:
  - `backend/src/graph/intent_router_node.py` — ANALYSIS를 PHASE1_INTENTS + _ROUTABLE_INTENTS에 추가, _CLASSIFY_SYSTEM_PROMPT 업데이트
  - `backend/src/graph/real_builder.py` — analysis 노드 import + 등록 + 라우팅
  - `backend/src/api/sse.py` — _NODE_STATUS_MESSAGES에 `"analysis"` 추가
- **DB 스키마 영향**: 없음 (PG SELECT + OS 읽기 전용)
- **응답 블록 16종 영향**: `analysis_sources` 기존 타입 사용. 16종 목록 변경 없음.
- **intent 추가/변경**: `ANALYSIS` — enum 기정의(L31). PHASE1_INTENTS + _ROUTABLE_INTENTS 양쪽 추가
- **외부 API 호출**: OS `place_reviews` 인덱스 mget + Gemini 2.5 Flash 스트리밍 (기존 text_stream 패턴)

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — places 조회 시 UUID place_id 사용
- [x] #2 PG↔OS 동기화 — place_id 기준, doc id = `review_{place_id}`
- [x] #3 append-only 4테이블 미수정 — PG SELECT만, INSERT/UPDATE/DELETE 없음
- [x] #4 소프트 삭제 — places 조회 시 `is_deleted = false` 필터
- [x] #5 비정규화 3건 외 신규 없음
- [x] #6 6지표 스키마 보존 — satisfaction/accessibility/cleanliness/value/atmosphere/expertise
- [x] #7 임베딩 통일 — 임베딩 미호출 (OS 기적재 데이터 조회만)
- [x] #8 asyncpg 파라미터 바인딩 — `$1` 바인딩, f-string SQL 금지
- [x] #9 Optional[str] 사용 (str | None 금지)
- [x] #10 SSE 이벤트 타입 16종 한도 — analysis_sources 기존 타입
- [x] #11 intent별 블록 순서 — intent→status→text_stream→analysis_sources→done (§4.5)
- [x] #12 공통 쿼리 전처리 경유 — processed_query에서 place_name 추출
- [x] #13 행사 검색 순서 — 해당 없음
- [x] #14 대화 이력 이원화 보존
- [x] #15 인증 매트릭스 준수
- [x] #16 북마크 패러다임 준수
- [x] #17 공유링크 인증 우회 범위 정확
- [x] #18 Phase 라벨 명시 — P1 (파일 헤더 docstring)
- [x] #19 기획 문서 우선 — API 명세서 v2 SSE 준수

## 4. 작업 순서 (Atomic step)

### g1 — analysis_node.py 신규 작성

**step 1**: `_extract_place_name(processed_query, query) → Optional[str]`
- `processed_query.get("place_name")` 우선 사용
- fallback: `processed_query.get("keywords")` 리스트 첫 번째 요소
- 둘 다 없으면 `None` 반환 → 노드에서 disambiguation

**step 2**: `_fetch_place_pg(pool, place_name, os_client) → Optional[dict]`
- `SELECT place_id, name, category, district FROM places WHERE is_deleted = false AND name ILIKE $1` (asyncpg `$1`)
- 동명 다중 매칭: review_compare_node._fetch_places_pg 패턴 재사용 — OS mget stars 최댓값 채택
- 0건 → `None`

**step 3**: `_fetch_scores_os(os_client, place_id) → dict[str, float]`
- doc id = `review_{place_id}`, OS mget 1회
- `_source._raw_scores` 추출. 문서 없으면 `{}`

**step 4**: `_build_analysis_blocks(query, place, scores, review_count) → list[dict]`
- `text_stream` 블록 (raw dict):
  ```python
  {
      "type": "text_stream",
      "system": _ANALYSIS_SYSTEM_PROMPT,
      "prompt": f"사용자 질문: {query}\n\n장소: {place['name']} ({place.get('category', '')})\n6지표: {scores_text}\n리뷰 수: {review_count}"
  }
  ```
- `analysis_sources` 블록 (raw dict):
  ```python
  {"type": "analysis_sources", "review_count": review_count}
  ```

**step 5**: `analysis_node(state) → dict` — LangGraph 노드
- place_name 추출 실패 → disambiguation ("어떤 장소를 분석할까요?")
- PG 조회 0건 → disambiguation ("장소를 찾을 수 없어요.")
- OS 점수 없음 → text_stream "리뷰 데이터 부족" 안내 + analysis_sources review_count=0
- 정상: text_stream + analysis_sources

> verify: `ruff check src/graph/analysis_node.py && pyright src/graph/analysis_node.py`

### g2 — intent_router_node.py 활성화

1. `PHASE1_INTENTS`에 `IntentType.ANALYSIS` 추가 (L40-54)
2. `_ROUTABLE_INTENTS`에 `IntentType.ANALYSIS` 추가 (L58-71)
3. `_CLASSIFY_SYSTEM_PROMPT` — Phase 2 목록에서 ANALYSIS 제거, Phase 1 active 목록에 추가:
   `"- ANALYSIS: analyzing a single place with 6 metrics (satisfaction/accessibility/cleanliness/value/atmosphere/expertise)"`

> verify: `pytest tests/ -k "intent" -v`

### g3 — real_builder.py 라우팅 추가

1. `from src.graph.analysis_node import analysis_node` import 추가
2. `graph.add_node("analysis", analysis_node)` 등록
3. `_route_by_intent` mapping에 `"ANALYSIS": "analysis"` 추가
4. `add_conditional_edges` dict에 `"analysis": "analysis"` 추가
5. response_builder 엣지 리스트에 `"analysis"` 추가

> verify: `python -c "from src.graph.real_builder import build_graph; build_graph()"`

### g4 — sse.py status 메시지 추가

1. `_NODE_STATUS_MESSAGES`에 `"analysis": "장소를 분석하고 있어요..."` 추가

> verify: `ruff check src/api/sse.py && pyright src/api/sse.py`

### g5 — 단위 테스트

`tests/test_analysis_node.py` — mock: `unittest.mock.AsyncMock`으로 `pool.fetch`, `os_client.mget` mock.

- `test_extract_place_name_from_processed_query`: processed_query.place_name 있으면 반환
- `test_extract_place_name_from_keywords`: place_name 없고 keywords[0] fallback
- `test_extract_place_name_none`: 둘 다 없으면 None
- `test_analysis_node_success`: 정상 흐름 — text_stream + analysis_sources 블록 반환
- `test_analysis_node_no_reviews`: OS 문서 없음 → text_stream + analysis_sources(review_count=0)
- `test_analysis_node_place_not_found`: PG 0건 → disambiguation
- `test_analysis_node_no_place_name`: place_name 추출 실패 → disambiguation

> verify: `pytest tests/test_analysis_node.py -v`

### g6 — 전체 검증

> verify: `./validate.sh`

## 5. 검증 계획

- `./validate.sh` 전체 통과
- `pytest tests/test_analysis_node.py -v` — 7개 케이스 모두 통과
- 수동 시나리오:
  1. `GET /api/v1/chat/stream?query=스타벅스 홍대점 분석해줘` → SSE에서 text_stream 스트리밍 + analysis_sources 블록 확인
  2. OS에 없는 장소명 → text_stream "리뷰 데이터 부족" + analysis_sources.review_count=0
  3. 존재하지 않는 장소 → disambiguation 블록

## 6. 최종 결정

APPROVED — 2026-05-06 PM 승인. 구현 진입.
