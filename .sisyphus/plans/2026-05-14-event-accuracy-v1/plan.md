# EVENT 검색 정확도 강화 v1 — expanded_query + date_range 활용 (Issue #76)

- Phase: P1
- 요청자: 한정수 (BE)
- 작성일: 2026-05-14
- 상태: approved
- 선행: #47 EVENT_SEARCH (머지) / #46 EVENT_RECOMMEND (머지) / query_preprocessor (이미 expanded_query·keywords·date_reference 추출 중)
- 후속: EVENT 정확도 v2 (OpenSearch vector + LLM Rerank, 별도 plan)

## 1. 요구사항

**배경**: query_preprocessor는 이미 강력한 구조화 추출 (expanded_query, keywords, date_reference)을 하지만, event_search_node / event_recommend_node가 **거의 활용 못 함**:

- `keywords[0]` 한 개만 ILIKE 매칭 ([event_search_node.py:96-98](backend/src/graph/event_search_node.py#L96-L98), event_recommend_node.py 동일)
- `date_reference` 무시 — "이번 주말" 검색해도 `date_end >= NOW()`만 적용 (모든 미래 행사 반환)
- `expanded_query` 미활용

**목표**: "이번 주말 강남 전시회" 같은 자연어 쿼리가 진짜 이번 주말 강남 행사만 정확히 반환.

**작업 범위**:

1. **query_preprocessor 강화** (#12 공통 쿼리 전처리)
   - Gemini JSON 응답에 2개 필드 추가:
     - `date_start_resolved`: ISO date 문자열 또는 None ("이번 주말" → "2026-05-16")
     - `date_end_resolved`: ISO date 문자열 또는 None ("이번 주말" → "2026-05-17")
   - 시스템 프롬프트에 변환 예시 추가 ("이번 주말" / "토요일" / "내일" / "3월" 등)
   - 변환 불가 시 둘 다 None (기존 date_reference 라우 텍스트는 유지)

2. **event_search_node._search_pg 강화**
   - `keywords` 배열 **전체** OR 매칭 — `(title ILIKE $kw1 OR title ILIKE $kw2 ...)`
   - date 범위 필터 추가:
     - `date_start_resolved`/`date_end_resolved` 있으면 `date_end >= $start AND date_start <= $end` (overlap 매칭)
     - 둘 다 None이면 기존 `date_end >= NOW()` 유지 (Phase 1 단순화 fallback)

3. **event_recommend_node._search_pg 동일 적용** — EVENT_SEARCH와 같은 양식

**범위 외 (후속 plan)**:

- OpenSearch events_vector k-NN — Plan 2
- LLM Rerank — Plan 2
- KOPIS ETL (데이터 양 증가) — 별도 plan
- expanded_query 자체를 SQL 매칭에 추가 (keywords로 충분 + Gemini가 expanded_query 만들 때 keywords 추출도 같이 함)

**비기능 요구사항**:

- query_preprocessor는 기존 Gemini 호출에 필드만 추가 → API 비용/지연 증가 0건
- 모든 SQL은 asyncpg `$1, $2` 파라미터 바인딩 (#8)
- 새 필드 `Optional[str]` 명시 (#9)
- 변환 실패 시 graceful — 기존 동작(`date_end >= NOW()`)으로 fallback
- 사용자 query / API 키 logger 진입 0건 (#19)

## 2. 영향 범위

**수정 파일 (3개)**:

- `backend/src/graph/query_preprocessor_node.py`:
  - `_PREPROCESS_SYSTEM_PROMPT`에 date 변환 예시 + 2개 필드 추가
  - `result.setdefault("date_start_resolved", None)` / `date_end_resolved` 추가
- `backend/src/graph/event_search_node.py`:
  - `_search_pg` 시그니처에 `date_start_resolved`, `date_end_resolved` 파라미터 추가
  - SQL: keywords OR 매칭 + date 범위 필터
  - 호출부(`event_search_node`)에서 processed_query에서 2개 필드 전달
- `backend/src/graph/event_recommend_node.py`: 위와 동일 양식

**신규 파일 (1개)**:

- `backend/tests/test_event_accuracy_v1.py` — 단위 테스트 6건 (mock)

**수정 0건**:

- DB 스키마 변경 0건
- intent_router / real_builder 수정 0건
- response_blocks / blocks.py 수정 0건
- config.py 수정 0건
- 의존성 추가 0건

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화** — events.event_id 무관 (SELECT만)
- [x] **#2 PG↔OS 동기화** — OS 미사용 (vector는 v2)
- [x] **#3 append-only** — events SELECT만, UPDATE/DELETE 0건
- [x] **#4 소프트 삭제** — 기존 `is_deleted = FALSE` 유지
- [x] **#5 의도적 비정규화** — 변경 0건
- [x] **#6 6 지표** — 무관
- [x] **#7 임베딩 768d** — 본 PR은 SQL만, 벡터 미사용
- [x] **#8 asyncpg 바인딩** — `$1, $2` 양식 + f-string SQL 금지 (multi-keyword OR도 placeholder concat)
- [x] **#9 Optional[str]** — 새 필드 `date_start_resolved: Optional[str]` 명시
- [x] **#10 SSE 16종** — 응답 블록 변경 0건
- [x] **#11 블록 순서** — 변경 0건
- [x] **#12 공통 쿼리 전처리** — **핵심 영역** — query_preprocessor가 권위. 모든 검색 노드 경유 보장
- [x] **#13 DB 우선 → Naver fallback** — 로직 유지 (PG 결과 부족 시 Naver)
- [x] **#14 대화 이력 이원화** — 무관
- [x] **#15-17** — 무관 (auth/북마크/공유)
- [x] **#18 Phase 라벨** — P1
- [x] **#19 기획 우선 + PII** — query/API 키 logger 진입 0건

## 4. 작업 순서 (Atomic step)

1. **`query_preprocessor_node.py` 수정**
   - `_PREPROCESS_SYSTEM_PROMPT`에 추가:
     ```
     - "date_start_resolved": ISO date "YYYY-MM-DD" 또는 null
     - "date_end_resolved": ISO date "YYYY-MM-DD" 또는 null
     변환 기준: 오늘 = {current_date}. "이번 주말" → 가장 가까운 토~일.
     ```
   - 함수 시그니처에 `current_date: Optional[str] = None` 추가 (테스트 결정성)
   - `result.setdefault("date_start_resolved", None)` / `date_end_resolved` 추가
   - **ISO 형식 검증 layer** (Metis 권장 1): Gemini 응답이 잘못된 형식("2026/05/16", "다음 주" 등)이면 None으로 정정:
     ```python
     ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
     for key in ("date_start_resolved", "date_end_resolved"):
         val = result.get(key)
         if val is not None and (not isinstance(val, str) or not ISO_DATE.match(val)):
             result[key] = None
     ```

2. **`event_search_node._search_pg` 수정**
   - 시그니처: `date_start_resolved: Optional[str], date_end_resolved: Optional[str]` 추가
   - SQL 변경:
     - keywords 전체 OR: `(title ILIKE $a OR title ILIKE $b OR ...)`
     - date 범위 분기:
       - 둘 다 있음: `date_end >= $start AND date_start <= $end` (overlap)
       - 둘 다 None: 기존 `date_end >= NOW()` fallback
   - 호출부: `pg.get("date_start_resolved"), pg.get("date_end_resolved")` 전달

3. **`event_recommend_node._search_pg` 동일 적용** — 양쪽 일관성

4. **`tests/test_event_accuracy_v1.py` 신규** — 6 테스트
   - `test_search_pg_multi_keywords_or`: keywords=["전시", "재즈"] → SQL에 OR 2개 조건
   - `test_search_pg_date_range_filter`: date_start_resolved/end 있음 → SQL에 date_start/end 범위 조건
   - `test_search_pg_date_fallback_to_now`: 둘 다 None → `date_end >= NOW()` 유지
   - `test_search_pg_no_keywords_no_date`: 조건 0건 → 기본 SQL
   - `test_preprocessor_date_resolved_weekend`: "이번 주말" → 2일 범위
   - `test_preprocessor_date_resolved_unparseable`: "언젠가" 같은 모호 표현 → 둘 다 None

5. **로컬 검증** — `cd backend && pytest tests/test_event_accuracy_v1.py tests/test_event_search.py tests/test_event_recommend.py -v` + ruff/format/pyright

6. **commit + push** — base: dev. PR description "Closes #76".

## 5. 검증 계획

### 5.1 단위 테스트 (pytest)

| 테스트 | 입력 | 기대 결과 |
|---|---|---|
| multi_keywords_or | keywords=["전시", "재즈"] | SQL에 `title ILIKE $a OR title ILIKE $b` 2개 placeholder + params 2개 |
| date_range_filter | start="2026-05-16", end="2026-05-17" | SQL에 `date_end >= $s AND date_start <= $e` |
| date_fallback_to_now | start=None, end=None | SQL에 `date_end >= NOW()` 유지 |
| no_keywords_no_date | 모든 옵션 None | 기본 SQL (district/category만) |
| preprocessor_weekend | "이번 주말" + current_date 토요일 mock | date_start/end 둘 다 ISO date |
| preprocessor_unparseable | "언젠가" | 둘 다 None |

### 5.2 19 불변식 검증
- ruff/format/pyright 0 errors
- f-string SQL 0건 (#8) — placeholder는 `str(len(params))` concat
- Optional[str] 사용 (#9)

### 5.3 로컬 통합 검증 (선택)
EVENT_SEARCH/RECOMMEND 검증 양식과 동일 — sample 행사 INSERT → 노드 호출 → 결과의 date 범위/keywords 매칭 확인 → DELETE cleanup.

### 5.4 머지 후 검증 (manual, staging)
- "이번 주말 강남 전시회" → 진짜 이번 주말 + 강남 행사만 반환
- "재즈 페스티벌" → keywords=["재즈", "페스티벌"] OR 매칭으로 title 부분 일치 강화
- date 변환 실패 케이스: "다음 분기 공연" → fallback `date_end >= NOW()`

## 6. 함정 회피

**EVENT_SEARCH(#47) / EVENT_RECOMMEND(#46) 학습 누적**:

- ✅ async I/O / 외부 API mock / PII / SQL 파라미터 / f-string 0건
- ✅ is_deleted = FALSE 필터 (#47 CodeRabbit #2)
- ✅ stub→실 함수 교체 시 import + add_node + 매핑 확인

**본 PR 신규 함정**:

- ⚠️ **multi-keyword OR placeholder 빌더 복잡도** — keywords 배열 길이별로 동적 OR. test로 양식 검증
- ⚠️ **date 변환 한국어 자연어** — Gemini가 "이번 주말"의 기준 토요일 잘못 판단 가능. 시스템 프롬프트에 `current_date` 명시 + few-shot 예시
- ⚠️ **변환 실패 fallback** — Gemini가 null 반환 / 잘못된 형식 반환 시 None 처리. dateutil parse로 형식 검증 권장
- ⚠️ **date overlap 매칭 의미** — 이벤트 기간(date_start~date_end)이 검색 범위(start~end)와 **겹치면** 매칭 (포함이 아님). 예: 5/10-5/20 행사를 "5/15 토요일" 검색 시 매칭 (정공)
- ⚠️ **expanded_query는 미활용** — keywords 배열로 충분 (Gemini가 expanded_query에서 keywords 추출). 본 PR은 keywords만 사용
- ⚠️ **date_reference raw text 유지** — 기존 필드는 그대로 (다른 노드 호환). `*_resolved` 필드만 추가
- ⚠️ **테스트 결정성** — `current_date` 파라미터 추가로 "오늘" 기준 mock 가능
- ⚠️ **date_start/date_end NULL 행사** (Momus 추가): SQL `date_end >= $s AND date_start <= $e`는 NULL 행사를 자연 제외 (false 매칭). **의도된 동작** — date 정보 없는 행사는 "이번 주말" 같은 범위 검색에 안 나옴. 단 date 범위 안 줄 때는 기존 `date_end >= NOW()` fallback이라 NULL은 동일하게 제외됨

## 7. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md (대기 중)
- Momus (엄격한 검토): reviews/002-momus-*.md (대기 중)

> 본 plan은 Claude Code 메인 세션에서 페르소나 채택으로 리뷰 (sisyphus 시스템 변형, EVENT_SEARCH/RECOMMEND와 같은 양식).

## 8. 최종 결정

APPROVED (Metis okay 001 + Momus approved 002 + 권장 2건 §4/§6 반영 완료)
