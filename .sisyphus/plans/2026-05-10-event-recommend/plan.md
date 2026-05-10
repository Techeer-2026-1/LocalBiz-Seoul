# SSE 행사 추천 노드 — EVENT_RECOMMEND (Issue #46)

- Phase: P1
- 요청자: 한정수 (BE)
- 작성일: 2026-05-10
- 상태: approved
- 의존: feat/47-event-search PR #53 (dev 미머지) — 본 PR은 자체 `_search_pg` 구현으로 의존성 회피
- 관련: dev에 stub `_event_recommend_node` 등록 완료 (real_builder.py L42, L76 매핑, L106 add_node)

## 1. 요구사항

**기능 요구사항** (기획/API 명세서 v2 SSE.csv L86):

- LangGraph 노드 `event_recommend_node(state)` 구현 — EVENT_RECOMMEND intent 분기 시 호출
- 요청: `GET /api/v1/chat/stream?query=주말에 갈 만한 전시회 추천해줘`
- 응답 블록 순서 (기획서 §4.5 권위, 변경 금지):
  ```
  intent → status → text_stream → events[] → references → done
  ```
- 핵심 차별화 (EVENT_SEARCH #47 vs EVENT_RECOMMEND #46):
  - EVENT_SEARCH: 키워드 매칭 → 단순 결과 나열
  - EVENT_RECOMMEND: **추천 사유 강조** — Gemini 프롬프트가 각 행사별 "왜 이 행사를 추천하는지" 근거 포함 (취향/맥락/카테고리 적합도 등)
- 검색 흐름 (DB 우선 → Naver fallback, 불변식 #13):
  1. processed_query에서 district/category/keywords/date_reference 추출
  2. PostgreSQL `events` 테이블 검색 — `is_deleted=FALSE AND date_end>=NOW()`
  3. PG 결과 충분 (>=3건) → DB 결과만 반환
  4. PG 결과 부족 (<3건) → Naver 검색 API fallback → 합산
- references 블록: 항상 포함 (DB 행사의 detail_url + Naver fallback 결과)

**비기능 요구사항**:

- 동시성: SELECT 단일 SQL. Naver 호출은 사용자별 독립.
- 외부 API 비동기: httpx.AsyncClient (timeout 5초)
- 보안: query/Naver API 키 logger 진입 0건 (불변식 #19)
- Rate Limiting: Naver API 일 25,000회 한도. PG 우선으로 호출 최소화. caching은 후속 plan.

**범위 외 (다음 plan으로 분리)**:

- OpenSearch events_vector k-NN 의미 검색 — 본 PR은 SQL ILIKE만 (PLACE_RECOMMEND 양식 차용은 후속)
- 사용자 취향 ML (user_preferences 테이블 또는 history 기반) — Phase 2
- LLM Rerank (Gemini Flash 조건 적합도 재배치) — 후속
- Naver API caching (Redis) — 후속
- date_reference 자연어 → SQL date 정확 변환 — query_preprocessor 강화 후 (Phase 2)
- `event_search_node._search_pg` 공통 헬퍼 추출 (DRY 리팩토링) — #47 머지 후 별도 plan

**의존성 처리 결정** (중요):

- dev 브랜치에 `event_search_node.py` **미존재** (#47 PR #53 머지 대기 중)
- → 본 PR은 자체 `_search_pg` 구현. EVENT_SEARCH 코드 일부 패턴(SQL 구조, params 빌더) 차용은 OK
- #47 머지 후 본 PR도 dev pull/rebase 시 두 노드 모두 _search_pg 보유 → 그 시점에 별도 리팩토링 plan으로 공통 helper 추출

## 2. 영향 범위

**신규 파일 (2개)**:

- `backend/src/graph/event_recommend_node.py` — 노드 함수 + 헬퍼 (~250줄, EVENT_SEARCH 양식 + 추천 사유 차별화)
- `backend/tests/test_event_recommend.py` — 단위 테스트 5건 (mock 사용, EVENT_SEARCH 테스트 양식 차용)

**수정 파일 (2개)** — Momus fs 갭 반영:

- `backend/src/graph/real_builder.py`:
  - L42 stub `_event_recommend_node` 제거
  - import 추가: `from src.graph.event_recommend_node import event_recommend_node`
  - L106 add_node를 진짜 함수로 교체
- `backend/src/config.py` — **#47 미머지로 인한 fs 갭**:
  - Settings에 `naver_client_id: str = ""` 추가
  - Settings에 `naver_client_secret: str = ""` 추가
  - 다른 외부 API 그룹(Google/Gemini) 옆 일관 위치
  - **#47 머지 시 컨플릭트 발생 가능** — 양쪽 다 살리는 양식으로 머지 해결

**수정/신규 0건**:

- DB schema 변경 0건 (events 테이블 변경 없음)
- 의존성 변경 0건 (httpx 이미 사용)
- main.py / api/sse.py 수정 0건 (LangGraph가 매핑 자동)
- intent_router_node.py 수정 0건 (EVENT_RECOMMEND intent 이미 등록 — Momus 검증 L23/45/63/85)
- intent_router_logic.py 수정 0건 (매핑 이미 등록)
- .env 변경 0건 (NAVER_CLIENT_ID/SECRET 환경변수만 사용)
- 기획서 §4.5 변경 0건 (EVENT_RECOMMEND 블록 순서 그대로 사용)

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화 준수** — events.event_id (VARCHAR(36)) 검색 결과 노출. Naver 결과는 event_id=None
- [x] **#2 PG↔OS 동기화** — 본 PR은 PG only, OS 미사용 (vector는 후속 plan)
- [x] **#3 append-only 4테이블 미수정** — events는 append-only 아님. SELECT만
- [x] **#4 소프트 삭제 매트릭스 준수** — events.is_deleted=FALSE 강제 (#47 CodeRabbit #2 학습 적용)
- [x] **#5 의도적 비정규화** — events.{district, place_name, address} 사용 (기존 비정규화)
- [x] **#6 6 지표 보존** — 본 PR 무관 (place_analysis 미사용)
- [x] **#7 Gemini embedding 768d** — 본 PR SQL only, 벡터 미사용
- [x] **#8 asyncpg 파라미터 바인딩** — `WHERE district = $1 AND category ILIKE $2` 양식, f-string SQL 0건 (#47 CodeRabbit #3 학습)
- [x] **#9 Optional[str] 사용** — `Optional[str]` 명시, `str | None` 0건
- [x] **#10 SSE 16종 한도** — `text_stream/events/references` 3종만 사용, 신규 블록 0건
- [x] **#11 intent별 블록 순서** — `intent → status → text_stream → events[] → references → done` (기획서 §4.5 권위)
- [x] **#12 공통 쿼리 전처리 경유** — query_preprocessor_node가 processed_query 채움
- [x] **#13 행사 검색 DB 우선 → Naver fallback** — 본 PR 핵심 흐름과 정합
- [x] **#14 대화 이력 이원화 보존** — 본 PR 무관 (messages/checkpoint 미수정)
- [x] **#15 인증 매트릭스** — 본 PR 무관 (auth 미수정)
- [x] **#16 북마크 패러다임** — 본 PR 무관
- [x] **#17 공유링크 인증 우회 범위** — 본 PR 무관
- [x] **#18 Phase 라벨** — P1 명시
- [x] **#19 기획 우선** — 명세 v2 §EVENT_RECOMMEND 블록 순서 그대로 따름

## 4. 작업 순서 (Atomic step)

0. **`config.py` 수정** — Settings에 Naver 변수 2개 추가 (Momus fs 갭 반영)
   - `naver_client_id: str = ""`
   - `naver_client_secret: str = ""`
   - 다른 외부 API 그룹 옆 일관성

1. **`graph/event_recommend_node.py` 신규 작성** — EVENT_SEARCH(#47) 양식 차용 + 차별화
   - `_RECOMMEND_SYSTEM_PROMPT`: "당신은 ... 추천 이유를 구체적인 근거(카테고리 적합성, 일정 매칭, 위치 편의성)와 함께 친절하게 설명해주세요"
   - `_search_pg(pool, district, category, keywords) -> list[dict]`: events SELECT (is_deleted=FALSE + date_end>=NOW())
   - `_search_naver(query, client_id, client_secret) -> list[dict]`: Naver 블로그 검색 API
   - `_naver_to_event_dict(item) -> dict`: Naver 응답 → events 양식 변환
   - `_build_blocks(query, events) -> list[dict]`: text_stream(추천 사유 강조) + events[] + references[]
   - `event_recommend_node(state) -> dict`: 메인 진입점

2. **`real_builder.py` 수정**
   - L42 stub `_event_recommend_node` 제거
   - import 추가: `from src.graph.event_recommend_node import event_recommend_node`
   - L106 `graph.add_node("event_recommend", _event_recommend_node)` → `event_recommend_node`

3. **`tests/test_event_recommend.py` 신규** — 5 단위 테스트 (mock)
   - test_naver_to_event_dict_html_clean: HTML 태그 제거
   - test_naver_to_event_dict_missing_fields: NULL 필드 처리
   - test_build_blocks_db_only: PG 결과만 → text_stream + events + references(DB detail_url)
   - test_build_blocks_naver_fallback: PG 부족 + Naver → text_stream + events + references(naver_blog)
   - test_build_blocks_recommend_prompt_keywords: 추천 사유 키워드 ("추천", "이유" 등) 프롬프트 포함 검증

4. **로컬 검증** — `cd backend && pytest tests/test_event_recommend.py -v`

5. **로컬 통합 검증** (선택) — sample events INSERT → event_recommend_node 직접 호출 → cleanup. EVENT_SEARCH 검증과 같은 양식.

6. **commit + push** — base: dev. PR description에 "Closes #46" + EVENT_SEARCH(#47) 미머지로 인한 의존성 회피 사유 명시.

## 5. 검증 계획

### 5.1 단위 테스트 (pytest)

| 테스트 | 입력 | 기대 출력 |
|---|---|---|
| naver_to_event_dict_html_clean | `<b>`태그 포함 title | 태그 제거된 title |
| naver_to_event_dict_missing_fields | link/description 없음 | None 처리, 에러 0 |
| build_blocks_db_only | PG 5건 mock | text_stream + events(items=5) + references(DB detail_url) |
| build_blocks_naver_fallback | PG 1건 + Naver 3건 | text_stream + events(items=4) + references(items=3, naver_blog) |
| build_blocks_recommend_prompt | 임의 events | text_stream prompt에 "추천", "이유" 등 키워드 포함 |

### 5.2 19 불변식 검증

- ruff/format/pyright 0 errors
- 추가 수동 검증: Optional[str] 사용 (str \| None 0건), f-string SQL 0건, OpenAI 임베딩 0건

### 5.3 로컬 통합 검증 (선택)

EVENT_SEARCH 검증과 같은 패턴 — sample 5건 INSERT (전시회 3건 강남구 + 공연 1건 + 마포 1건) → event_recommend_node 호출 → 두 시나리오:

- 시나리오 A: PG-only (강남 전시회 매칭 3건) → events 블록 + references 블록(DB detail_url)
- 시나리오 B: PG 부족 → Naver fallback (마포 행사) → 두 출처 합산

→ DELETE WHERE source='naver_local_test' cleanup

### 5.4 머지 후 검증 (manual, staging)

- query "주말에 갈 만한 전시회 추천해줘" → text_stream에 "왜 추천하는지" 사유 포함 확인
- query "이번 주말 서울 행사 추천" → district 미명시 시 동작 확인 (전국 행사 검색)
- EVENT_SEARCH vs EVENT_RECOMMEND 응답 비교 — 차별화된 사유 강조 확인

## 6. 함정 회피

**EVENT_SEARCH(#47) 학습 누적 적용**:

- ✅ async def 안의 동기 I/O 금지 — Naver 호출 처음부터 httpx.AsyncClient (async 네이티브)
- ✅ 외부 API mock 테스트 — monkeypatch로 `_search_naver` 함수 mock
- ✅ PII 보호 (#19) — query/API 키 logger 진입 금지
- ✅ SQL 파라미터 분리 (#8) — fetch(*params) 인자 분리
- ✅ f-string SQL 0건 (CodeRabbit #3 학습) — placeholder는 `str(len(params))` concat
- ✅ is_deleted=FALSE 필터 (CodeRabbit #2 학습) — 운영 schema 정합
- ✅ events 컬럼 fs 확인 — event_id, title, ..., is_deleted, updated_at (운영 기준)
- ✅ stub 제거 시 다른 호출 위치 grep 검증

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ EVENT_SEARCH와 코드 중복 → 추천 사유 LLM 프롬프트로 차별화. 공통 helper 추출은 후속 리팩토링 plan
- ⚠️ #47 미머지 상태에서 작업 — 본 PR이 dev 기준 자체 _search_pg 구현. #47 머지 후 dev pull 시 두 노드 공존 (충돌 없음, real_builder.py만 양쪽 수정 → rebase 시 컨플릭트 가능 — 그때 양쪽 진짜 함수 모두 살리는 양식으로 해결)
- ⚠️ 추천 사유 LLM 프롬프트 — Phase 1은 단순화. user 취향 ML은 Phase 2. 프롬프트만 강화 (시스템 프롬프트에 "추천 이유 명시")
- ⚠️ references 블록 항상 포함 — EVENT_SEARCH는 PG-only 시 references 미생성. 본 PR은 명세 §4.5 따라 항상 references 포함 (DB 행사도 detail_url 있으면 references에 추가)
- ⚠️ Naver fallback 발동 임계값 — `_MIN_PG_RESULTS = 3` (EVENT_SEARCH와 동일)
- ⚠️ Naver timeout 5초 — `httpx.AsyncClient(timeout=5.0)`
- ⚠️ events 테이블 PostGIS geom — `ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng`. NULL 처리

## 7. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조 (대기 중)
- Momus (엄격한 검토): reviews/002-momus-*.md 참조 (대기 중)

> 본 plan은 Claude Code 메인 세션에서 페르소나 채택으로 리뷰 진행 (sisyphus 시스템 변형, EVENT_SEARCH #47과 같은 운영 양식).

## 8. 최종 결정

APPROVED (Metis okay 001 + Momus approved 002 + fs 갭 1건 §2/§4 반영 완료)
