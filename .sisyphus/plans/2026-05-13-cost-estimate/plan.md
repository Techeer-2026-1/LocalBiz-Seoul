# 비용견적 기능 (COST_ESTIMATE 노드) 구현

- Phase: P1
- 요청자: josephwsjeong
- 작성일: 2026-05-13
- 상태: done
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

"강남 이탈리안 2인 얼마?" 같은 비용 문의 쿼리를 처리하는 `COST_ESTIMATE` intent 노드를 구현한다.
SSE 응답 흐름은 `intent → status → text_stream → done`이며 (status·done은 SSE 제어 이벤트, 노드 반환 대상 아님),
`processed_query.place_name` 유무에 따라 두 경로로 분기한다.

**경로 A — 특정 장소 있음** (예: "스파게티오 강남점 2인 얼마?")
1. Naver Blog Search API → `{place_name} 가격` 검색 → 정규식으로 금액 패턴 추출
2. 수집된 데이터를 컨텍스트로 Gemini text_stream 스트리밍

> price_level (Google Places API) 제외 이유: `places.google_place_id` 실측 0% (535,432행 전부 NULL),
> 런타임 Text Search + Details 2콜 추가 지연, 한국 식당 커버리지 불안정.

**경로 B — 특정 장소 없음** (예: "강남 이탈리안 2인 얼마?")
- Gemini 단독 스트리밍 (category + district + neighborhood + keywords 컨텍스트)
- 블로그 샘플링 불필요 — 여러 식당 가격이 뒤섞여 의미 없음

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/cost_estimate_node.py`
  - `backend/tests/test_cost_estimate_node.py`
- 수정 파일:
  - `backend/src/graph/intent_router_node.py` — `PHASE1_INTENTS`, `_ROUTABLE_INTENTS`, 양쪽 시스템 프롬프트
  - `backend/src/graph/real_builder.py` — 노드 import, `add_node`, `_route_by_intent`, `conditional_edges`, `add_edge`
  - `기획/API 명세서 v2 (SSE) 774222b0711e4db9a421ed770e45e621_all.csv` — COST_ESTIMATE Phase 2 → Phase 1 갱신
- DB 스키마 영향: 없음 (places 테이블 조회만, 신규 컬럼 없음)
- 응답 블록 16종 영향: 없음 (text_stream 기존 블록 재사용)
- intent 추가/변경: `COST_ESTIMATE` — Phase 2 stub → Phase 1 활성 전환
- 외부 API 호출:
  - Naver Blog Search API (기존 event_search_node.py `_search_naver()` 패턴 재사용, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`, 일 25,000회 한도, timeout 5s)
  - Google Places API 미사용 (price_level 폐지 — COST_ESTIMATE 노드 한정)
- FE 영향: 없음 (text_stream 블록 FE 기존 렌더링)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — places 조회만, 신규 테이블/PK 없음
- [x] PG↔OS 동기화 — 쓰기 없음, places 읽기만
- [x] append-only 4테이블 미수정 — messages/population_stats/feedback/langgraph_checkpoints 미접촉
- [x] 소프트 삭제 매트릭스 준수 — places 조회 시 `is_deleted = false` 필터 적용
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음 — 신규 컬럼 없음
- [x] 6 지표 스키마 보존 — 6 지표 미접촉
- [x] gemini-embedding-001 768d 사용 — 벡터 임베딩 불필요 (가격 추정 전용)
- [x] asyncpg 파라미터 바인딩 ($1, $2) — 동적 WHERE 구성 시 `"$" + str(len(params))` 방식 적용, f-string SQL 금지
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — text_stream 재사용, 신규 블록 타입 없음
- [x] intent별 블록 순서 (기획 §4.5) 준수 — COST_ESTIMATE: text_stream 단독
- [x] 공통 쿼리 전처리 경유 — `query_preprocessor` 거친 `processed_query` 사용
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 (checkpoint + messages) 보존 — 미접촉
- [x] 인증 매트릭스 (auth_provider) 준수 — 미접촉
- [x] 북마크 = 대화 위치 패러다임 준수 — 미접촉
- [x] 공유링크 인증 우회 범위 정확 — 미접촉
- [x] Phase 라벨 명시 — P1. 기획서 API 명세서 CSV Phase 컬럼도 동시 갱신 (Step 1)
- [x] 기획 문서 우선 — 기획서 갱신을 Step 1에 포함

## 4. 작업 순서 (Atomic step)

### Step 1 — 기획서 API 명세서 Phase 컬럼 갱신 [category: quick]
파일: `기획/API 명세서 v2 (SSE) 774222b0711e4db9a421ed770e45e621_all.csv`

COST_ESTIMATE 행의 Phase 컬럼 값을 `Phase 2` → `Phase 1`로 수정.
불변식 #18·#19 준수 — 코드 변경 전 기획서 선행 갱신.

검증: CSV 파일에서 COST_ESTIMATE 행 Phase 컬럼이 `Phase 1`임을 확인.

---

### Step 2 — `intent_router_node.py` 활성화 [category: quick]
파일: `backend/src/graph/intent_router_node.py`

2-A. `PHASE1_INTENTS`에 `IntentType.COST_ESTIMATE` 추가.
2-B. `_ROUTABLE_INTENTS`에 `IntentType.COST_ESTIMATE` 추가.
2-C. `_CLASSIFY_SYSTEM_PROMPT`에서 Phase 2 섹션 정리 (실측 라인 기준):
  - line 107-108 (`Phase 2 (not yet active...): COST_ESTIMATE, CROWDEDNESS`) 블록 삭제
    - CROWDEDNESS: 이미 PHASE1_INTENTS(line 52) + _ROUTABLE_INTENTS(line 72) + real_builder 등록 완료된 활성 노드. 시스템 프롬프트만 동기화 안 된 잔재이므로 제거.
  - line 101-105 블록에서 `COST_ESTIMATE` 제거, Phase 1 active 목록으로 이동
    - 설명: `"COST_ESTIMATE: asking about expected cost or price range for a place, restaurant, or activity"`
    - line 105 `- GENERAL: general conversation...` 중복(line 99와 동일 내용) 제거
    - IMAGE_SEARCH는 이미 Phase 1 active이므로 line 102 Phase 2 잔재에서도 제거
2-D. `_CLASSIFY_MULTI_SYSTEM_PROMPT` 동일 방식 수정 (line 133-134: COST_ESTIMATE, CROWDEDNESS 잔재 제거).

검증: `ruff check . && pyright src` 통과.

---

### Step 3 — `cost_estimate_node.py` 신규 작성 [category: deep]
파일: `backend/src/graph/cost_estimate_node.py`

**함수 구조:**
```
cost_estimate_node(state)
  ├── _has_specific_place(processed_query) → bool
  ├── [경로 A] _fetch_blog_prices(place_name, nid, secret) → list[int]   # Naver Blog + 정규식
  └── _build_prompt(query, processed_query, blog_prices) → str
```

**경로 A 구현 — `_fetch_blog_prices`:**
- `place_name` 출처: `state.get("processed_query", {}).get("place_name")`
- `event_search_node._search_naver()` 패턴 그대로 사용 (`_NAVER_BLOG_URL`, httpx, timeout=5s, display=5)
- 검색어: `f"{place_name} 가격"` (place_name만 사용, 지역+카테고리 무관)
- 각 item의 `description`에서 금액 패턴 추출:
  ```python
  re.findall(r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:만\s*원|천\s*원|원)', text)
  ```
- 원 단위 정규화 후 유효 범위(1,000원~500,000원) 내 값만 수집 → list[int] 반환.
- 추출 실패 시 빈 list 반환.

**`_build_prompt` — 경로 A:**
```
"{place_name}의 가격 정보입니다:
- 블로그 가격 데이터: {min}~{max}원 (N건 수집) or '정보 없음'
{party_size_hint}
모든 메뉴 가격을 나열하지 말고, 위 데이터를 참고해 '약 X~Y만원대' 형식의 가격 구간으로 친절하게 안내해주세요."
```
- `party_size_hint`: query에 "N인" 패턴(`\d인`) 있으면 `f"'{query}'의 인원 정보를 반영해주세요."` 추가

**`_build_prompt` — 경로 B:**
```
"다음 조건의 예상 비용을 알려주세요:
- 지역: {district or neighborhood or '서울'}
- 종류: {category or '음식점'} / {keywords}
- 쿼리: {query}
모든 메뉴를 나열하지 말고, '약 X~Y만원대' 형식의 가격 구간으로 친절하게 안내해주세요."
```

**노드 반환:** `{"response_blocks": [{"type": "text_stream", "system": _SYSTEM_PROMPT, "prompt": prompt}]}`

**PG 쿼리 없음:** 경로 B는 Gemini만 사용. 경로 A도 Google/Naver API 사용하므로 places 테이블 조회 불필요.

asyncpg 동적 WHERE 예시 (향후 PG 추가 시 참고):
```python
conditions: list[str] = []
params: list[Any] = []
if district:
    params.append(district)
    conditions.append("district = $" + str(len(params)))
```

---

### Step 4 — `real_builder.py` 등록 [category: quick]
파일: `backend/src/graph/real_builder.py`

4-A. `from src.graph.cost_estimate_node import cost_estimate_node` import 추가.
4-B. `graph.add_node("cost_estimate", cost_estimate_node)` 추가.
4-C. `_route_by_intent` mapping에 `"COST_ESTIMATE": "cost_estimate"` 추가.
4-D. `conditional_edges` dict에 `"cost_estimate": "cost_estimate"` 추가.
4-E. `add_edge` 루프 리스트에 `"cost_estimate"` 추가.
4-F. `_route_by_intent` docstring (line 43-58) 반환값 주석에 `- COST_ESTIMATE → "cost_estimate"` 추가.

검증: `python -c "from src.graph.real_builder import build_graph; build_graph()"` 성공.

---

### Step 5 — 테스트 작성 [category: deep]
파일: `backend/tests/test_cost_estimate_node.py`

- `test_has_specific_place_true()`: `processed_query`에 `place_name` 있을 때 경로 A 분기 확인.
- `test_has_specific_place_false()`: `place_name` 없을 때 경로 B 분기 확인.
- `test_blog_price_regex()`: 샘플 블로그 description에서 금액 패턴 정규식 추출 검증.
  - 예: `"1인 15,000원 코스"` → `[15000]`
  - 예: `"2만원짜리 파스타"` → `[20000]`
  - 예: `"광고 배너입니다"` → `[]`
- `test_cost_estimate_node_path_b(monkeypatch)`: place_name 없을 때 text_stream 블록 반환, prompt에 category·district 포함 확인.
- `test_intent_router_cost_estimate_routable()`: `COST_ESTIMATE`가 `_ROUTABLE_INTENTS`에 포함 확인.

## 5. 검증 계획

- `validate.sh` 6단계 통과
- 단위 테스트: `pytest tests/test_cost_estimate_node.py -v` 5건 전체 pass
- 수동 시나리오:
  - **경로 B**: `curl "http://localhost:8000/api/v1/chat/stream?query=강남+이탈리안+2인+얼마"` → text_stream 스트리밍 확인
  - **경로 A**: `curl "http://localhost:8000/api/v1/chat/stream?query=스파게티오+강남점+2인+얼마"` → Naver Blog 가격 데이터 포함 text_stream 확인
  - **API 키 없을 때**: `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 미설정 → 경로 A도 경로 B 수준 프롬프트로 graceful degradation 확인

## 6. Metis/Momus 리뷰

- Metis 1차: reviews/001-metis-reject.md (초안 reject)
- Metis 2차: reviews/002-metis-okay.md (pass)
- Momus: reviews/003-momus-*.md 참조

## 7. 최종 결정

APPROVED (Metis 2차 pass · Momus pass — 2026-05-13)
