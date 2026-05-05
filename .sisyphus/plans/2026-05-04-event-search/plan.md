# SSE 행사 검색 노드 — EVENT_SEARCH (Issue #47)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-05-04
- 의존: 회원가입~Google 로그인 인증 시리즈 (5종 머지 완료) + intent_router_node + place_search_node 양식
- 후속 의존성: 다음 PR(#46 EVENT_RECOMMEND)이 본 PR의 event_search_node를 import하여 추천 로직 추가

## 1. 요구사항

**기능 요구사항** (명세 v1.4 + 본인 채팅 시스템 명세):

- LangGraph 노드 `event_search_node(state)` 구현 — EVENT_SEARCH intent 분기 시 호출
- 입력: AgentState (query, processed_query, thread_id, user_id 등)
- 출력: `{"response_blocks": [...]}` 형식 dict
- response_blocks 구성:
  - `text_stream`: Gemini로 검색 결과 자연어 요약
  - `events[]`: 행사 정보 카드 (title, category, date_start/end, place_name, district 등)
  - `references[]`: Naver fallback 결과 시 출처 링크 (블로그/뉴스 URL)
- 검색 흐름 (DB 우선 → Naver fallback):
  1. processed_query에서 district / category / keywords / date_reference 추출
  2. PostgreSQL `events` 테이블 검색 (is_deleted=false 강제)
  3. PG 결과 충분 (>= 3건) → DB 결과만 반환
  4. PG 결과 부족 (< 3건) → Naver 검색 API 추가 호출 → 결과 변환 후 합산
- 외부 API: Naver 검색 API (블로그 또는 통합 검색)
- SSE 라우터 변경 0건 — 기존 `/api/v1/chat/stream`이 LangGraph 호출 시 자동 분기

**비기능 요구사항**:

- 동시성: SELECT 단일 SQL이라 race window 없음. Naver 호출은 사용자별 독립.
- 외부 API 비동기: Naver HTTP 호출은 async (httpx.AsyncClient). google-auth(동기)와 달리 처음부터 비동기 처리 — Google 로그인 PR에서 학습한 "async def 안의 동기 I/O 금지" 학습 적용.
- 보안: PII 보호 — query는 사용자 입력이므로 logger 진입 금지. Naver API 키는 settings.naver_client_id/secret에서만 접근.
- Rate Limiting: Naver API는 일 25,000 호출 한도. PG 우선 구조로 호출량 최소화. Phase 1은 caching 미구현 (별도 plan).

**범위 외 (다음 PR로 명시 분리)**:

- EVENT_RECOMMEND (#46) — 본 PR의 event_search_node 결과 위에서 추천 로직 추가. 별도 PR.
- 행사 vector 검색 (k-NN) — 본 PR은 SQL ILIKE만. OpenSearch events_vector 인덱스는 후속 plan.
- Naver API caching (Redis) — 후속 plan.
- 행사 사용자 평점/북마크 — 후속 plan.
- date_start/end 필터링 정확도 (자연어 → 날짜 변환) — Phase 2 (query_preprocessor 강화 필요).

**미래 의존성**:

- EVENT_RECOMMEND PR이 본 PR의 `event_search_node`를 helper로 사용하거나 별도 함수 분리 필요.
- 행사 vector PR이 본 PR의 노드에 OS k-NN step 추가.

## 2. 영향 범위

**신규 파일 (2개)**:

- `backend/src/graph/event_search_node.py` — 노드 함수 + 헬퍼 (~180줄)
- `backend/tests/test_event_search.py` — 테스트 4건 (~150줄, mock 사용)

**수정 파일 (2개)**:

- `backend/src/graph/real_builder.py` — `_event_search_node` stub 제거 + 진짜 함수 import + 매핑 갱신
- `backend/src/config.py` — Settings 클래스에 `naver_client_id`, `naver_client_secret` 추가 (~3줄)

**수정/신규 0건**:

- DB schema 변경 0건 (events 테이블 이미 존재, ETL이 채움)
- 의존성 변경 0건 (httpx 이미 사용 중 — place_search_node가 import)
- main.py / api/sse.py 수정 0건 (LangGraph가 매핑 자동 처리)
- .env / .env.example 변경 0건 (NAVER_CLIENT_ID/SECRET 키 이미 존재, 본인이 셋업 완료)

## 3. 19 불변식 체크리스트

- **#1 PK 이원화**: event_id (BIGSERIAL) — 검색 결과에 노출. 외부 ID(Naver link 등)는 references[]에만.
- **#2 timestamp**: 본 PR은 SELECT만. UPDATE/INSERT 없음 (events는 ETL이 관리).
- **#7 Gemini embedding 768d**: 본 PR은 SQL only, 벡터 검색 미사용 (후속 plan).
- **#8 SQL 파라미터 바인딩**: `WHERE district = $1 AND category ILIKE $2` 양식 준수.
- **#9 Optional 명시**: NULL 가능 컬럼 (price, poster_url 등) 처리 명시.
- **#13 DB 우선 → fallback**: PG events 결과 부족 시 Naver fallback. 본 plan §1과 정합.
- **#18 Phase 라벨**: P1.
- **#19 PII 보호**: 사용자 query는 logger 진입 금지. Naver API key는 logger 진입 금지.

## 4. 작업 순서

각 step은 atomic. 위에서 아래로 순차 실행.

1. **`config.py` 수정** — Settings 클래스에 Naver 변수 2개 추가 (Gemini 또는 Google Calendar 옆, 적절한 그룹).
   - `naver_client_id: str = ""`
   - `naver_client_secret: str = ""`

2. **`graph/event_search_node.py` 신규 작성** (place_search_node.py 양식 따라).
   - `_search_pg(pool, district, category, keywords, date_ref) -> list[dict]`: events 테이블 SELECT
   - `_search_naver(query, naver_client_id, naver_client_secret) -> list[dict]`: Naver 검색 API 호출 (httpx.AsyncClient)
   - `_naver_to_event_dict(item) -> dict`: Naver 응답 → 우리 events 양식 변환
   - `_build_blocks(events, references, summary_prompt) -> list[dict]`: response_blocks 조립
   - `event_search_node(state: dict[str, Any]) -> dict[str, Any]`: 메인 진입점, 위 헬퍼들 조합

3. **`real_builder.py` 수정** — `_event_search_node` stub 함수 제거 + 진짜 함수 import.
   - 위치 35-43 줄 부근 stub
   - import 추가: `from src.graph.event_search_node import event_search_node`
   - 매핑 그대로 사용 (이미 `"EVENT_SEARCH": "event_search"` 등록)

4. **`tests/test_event_search.py` 신규** — 4 테스트 (mock 사용).
   - test_event_search_pg_only_success: PG 결과 5건 (>=3) → Naver 호출 안 함, events 5건 반환
   - test_event_search_naver_fallback: PG 결과 1건 → Naver 호출 → 합산 결과 반환
   - test_event_search_pg_empty_naver_fallback: PG 0건 → Naver만 → references 포함
   - test_event_search_naver_api_error_graceful: Naver 호출 실패 → PG 결과만 (graceful degradation)

5. **`cd backend && pytest tests/test_event_search.py -v`** 로컬 검증.

6. **`./validate.sh`** 6단계 통과 확인 (exit 0).

7. **commit + push + GitHub PR 생성** (base: dev, Closes #47).

## 5. 검증 계획

### 5.1 단위 / 통합 테스트 (pytest)

| 테스트 | 입력 | 기대 출력 |
|---|---|---|
| pg_only_success | PG 5건 mock | events 5건, references 0건, Naver 호출 0회 |
| naver_fallback | PG 1건 + Naver 3건 mock | events 4건, references 3건, Naver 호출 1회 |
| pg_empty_naver_fallback | PG 0건 + Naver 5건 mock | events 5건, references 5건 |
| naver_api_error_graceful | PG 1건 + Naver mock raises | events 1건, references 0건 (5xx 안 던짐) |

### 5.2 보안 검증

- Naver API 키 logger 진입 0건 (코드 리뷰로 강제)
- 사용자 query 원문 logger 진입 0건 (mask 함수 또는 user_id로만 로깅)
- PG 검색 SQL 파라미터 분리 (#8 불변식)

### 5.3 19 불변식 검증

- `validate.sh`의 `[bonus 2] plan 무결성 체크` 본 plan 인식 (5 필수 섹션)
- `validate.sh`의 `[2/5] ruff check` SQL 파라미터/Optional 위반 검출

### 5.4 머지 후 검증 (manual)

- 실제 query "이번 주말 서울 전시회" → SSE 응답에 events[] 블록 + 자연어 요약 확인
- PG에 데이터 없는 카테고리(예: "강원도 행사") → Naver fallback 동작 확인
- query "주말에 갈 만한 전시회 추천해줘" → 본 PR이 아닌 EVENT_RECOMMEND 노드로 라우팅 확인

## 6. 함정 회피

**인증 시리즈 학습 누적 적용**:

- ✅ async def 안의 동기 I/O 금지 (Google 로그인 #42 학습) — Naver 호출은 처음부터 httpx.AsyncClient (async 네이티브)
- ✅ 외부 API mock 테스트 (Google 로그인 #42 학습) — monkeypatch로 `_search_naver` 함수 mock
- ✅ PII 보호 (#19 불변식) — query/API 키 logger 진입 금지
- ✅ SQL 파라미터 분리 (#8) — fetchrow/fetch 인자 분리

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ Naver API 호출 실패 시 graceful degradation — PG 결과라도 있으면 그것만 반환. Naver 5xx로 사용자에게 500 띄우면 안 됨.
- ⚠️ Naver 응답 schema 미정합 — Naver 응답이 우리 events 양식과 다름. `_naver_to_event_dict` 헬퍼로 명시적 변환. 누락 필드는 None.
- ⚠️ events 테이블 PostGIS geom 컬럼 — `ST_Y(geom)::float8 AS lat, ST_X(geom)::float8 AS lng` 양식 (place_search_node 동일). geom NULL 가능성 처리.
- ⚠️ date_reference 자연어 — "이번 주말", "5월 둘째 주" 같은 자연어를 SQL date 비교로 정확히 변환은 어려움. Phase 1은 명시적 단순화: date_reference가 있으면 LIKE 매칭 또는 무시. 정확한 날짜 필터는 query_preprocessor 강화 후 (후속 plan).
- ⚠️ PG 결과 충분 기준 — `>= 3건`이 hardcoded magic number. 상수 `_MIN_PG_RESULTS = 3`로 분리.
- ⚠️ Naver 호출 timeout — 기본 타임아웃 5초 명시 (httpx.AsyncClient(timeout=5.0)). 무한 대기 방지.
- ⚠️ events 테이블에 없는 컬럼 SELECT — fs로 schema 확인 (load_events.py에서 INSERT 컬럼 정확히): event_id, title, category, place_name, address, district, geom, date_start, date_end, price, poster_url, detail_url, summary, source, raw_data, is_deleted.
- ⚠️ stub 함수 제거 시 다른 호출 위치 확인 — real_builder.py 외 다른 곳에서 `_event_search_node` import하는 곳 없는지 grep 검증 (정찰 시 0건 확인).

## 7. 최종 결정

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 실제로 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 본 PR은 본인 첫 LangGraph 노드 + 외부 API fallback 구현.

APPROVED (Metis okay 001, Momus approved 002)
