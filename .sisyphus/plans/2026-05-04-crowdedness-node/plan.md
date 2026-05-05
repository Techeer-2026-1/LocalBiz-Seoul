# CROWDEDNESS 노드 — population_stats 기반 혼잡도 분석

- Phase: P1 (PM 승인: josephwsjeong 2026-05-04)
- 요청자: josephwsjeong
- 작성일: 2026-05-04
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

기존 SSE 엔드포인트(`GET /api/v1/chat/stream`)에서 "혼잡/사람 많아/붐벼/한산" 류 자연어 질의를
처리할 수 있도록 CROWDEDNESS intent의 라우팅과 노드를 활성화한다.

현재 CROWDEDNESS는 `IntentType` enum에 정의돼 있으나 `PHASE1_INTENTS` / `_ROUTABLE_INTENTS` 미포함이라
GENERAL fallback 처리된다. `기획/기능 명세서 v2 (SSE) ...csv` L41 / `기획/API 명세서 v2 (SSE) ...csv` L152이
이미 CROWDEDNESS를 Phase 1으로 표기 — 본 plan은 legacy `서비스 통합 기획서 v2.md`를 CSV에 align하는 동기화다.

`population_stats` (278,880 row, append-only) 와 `administrative_districts` (427 row) JOIN으로
행정동별 시간대 인구 데이터를 조회하고, Gemini text_stream으로 혼잡도를 자연어 설명한다.

응답 시퀀스: `기획/_legacy/서비스 통합 기획서 v2.md` L178 기준 `intent → status → text_stream → done`.
※ API 명세서 v2 CSV L152는 `intent → text_stream → done`으로 status 미기재 — sse.py `_NODE_STATUS_MESSAGES`(L97)가 노드 진입 시 status를 자동 emit하므로 양립.

명확화된 가정:
- `time_slot`은 서버 KST 현재 시각의 hour(0~23) — `datetime.now(ZoneInfo("Asia/Seoul")).hour`
  (단위 테스트: `monkeypatch.setattr("src.graph.crowdedness_node.datetime", FrozenDatetime)` 방식으로 freeze)
- `base_date`는 전역 `MAX(base_date)` 사용 (global 기준, 적재 주기 단위)
- 데이터가 3일 이상 stale이면 응답 text_stream prompt에 기준 일자 경고 포함 (`기획/ETL_적재_현황.md` 기준 적재 주기 확인 후 3일 채택)
- 혼잡도 등급은 최근 30일(`base_date >= MAX(base_date) - INTERVAL '30 days'`) 동일 시간대 평균 대비 비율로 코드(`_classify_level`)에서 결정론적으로 산출
  - ratio < 0.7 → 한산
  - 0.7 ≤ ratio < 1.2 → 보통
  - 1.2 ≤ ratio < 1.5 → 혼잡
  - ratio ≥ 1.5 → 매우혼잡
  - avg_pop = 0 또는 NULL → 보통 등급 fallback
- 지역 매핑 (`_resolve_dong_code(neighborhood, district) -> Optional[str]`):
  1. `adm_dong_name ILIKE $1` (파라미터: `f"%{neighborhood}%"`) — population_stats JOIN으로 `total_pop` 산출, N건이면 `total_pop DESC LIMIT 1` 채택
     ```sql
     SELECT a.adm_dong_code
     FROM administrative_districts a
     LEFT JOIN (
       SELECT adm_dong_code, total_pop
       FROM population_stats
       WHERE base_date = (SELECT MAX(base_date) FROM population_stats)
         AND time_slot = $2
     ) p USING (adm_dong_code)
     WHERE a.adm_dong_name ILIKE $1
     ORDER BY p.total_pop DESC NULLS LAST
     LIMIT 1
     ```
  2. 0건이면 district(자치구) 기준으로 해당 구 전체 행정동 `SUM(total_pop)` 집계 후 대표 dong_code 하나 반환
  3. 그래도 0건이면 None → "지역 미인식" fallback
- `_fetch_population(pool, dong_code: Optional[str], district: Optional[str], time_slot: int) -> Optional[dict]`
  - dong_code 있으면 단일 행정동 기준 조회
  - dong_code=None, district 있으면 자치구 집계 조회
  - 둘 다 None이면 None 반환
- fallback 응답 계약:
  - `dong_code=None` (지역 미인식): text_stream "질문하신 지역을 인식하지 못했습니다. 지역명을 포함해 다시 질문해 주세요."
  - `population_row=None` (데이터 없음): text_stream "해당 지역의 생활인구 데이터가 없습니다."
  - `MAX(base_date) IS NULL` → population_row=None 동일 처리

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/crowdedness_node.py`
  - `backend/tests/test_crowdedness_node.py`
- 수정 파일:
  - `backend/src/graph/intent_router_node.py` — `PHASE1_INTENTS` / `_ROUTABLE_INTENTS`에 `IntentType.CROWDEDNESS` 추가, `_CLASSIFY_SYSTEM_PROMPT` Phase 1 섹션 이동 + Phase 2 주석(L94)에서 제거
  - `backend/src/graph/real_builder.py` — 아래 4군데:
    1. `from src.graph.crowdedness_node import crowdedness_node` import 추가
    2. `graph.add_node("crowdedness", crowdedness_node)` 추가
    3. `_route_by_intent` mapping dict에 `"CROWDEDNESS": "crowdedness"` 추가
    4. `add_conditional_edges` map에 `"crowdedness": "crowdedness"` + response_builder edge 루프 리스트에 `"crowdedness"` 추가
  - `backend/src/api/sse.py` — `_NODE_STATUS_MESSAGES`(L97)에 `"crowdedness": "혼잡도를 분석하고 있어요..."` 추가 (키 이름은 `add_node("crowdedness", ...)` 와 정확히 일치)
  - `기획/_legacy/서비스 통합 기획서 v2.md` — §3.2 Phase 2 목록에서 CROWDEDNESS 제거, Phase 1 목록에 추가 기재
- DB 스키마 영향: 없음 (SELECT 전용). population_stats `(adm_dong_code, base_date, time_slot)` 인덱스 존재 여부 확인 필요 — 없으면 별도 마이그레이션 plan 작성.
- 응답 블록 16종 영향: 없음 (intent/text_stream 재사용, status/done은 SSE 제어)
- intent 추가/변경: CROWDEDNESS Phase 2 → P1 격상 (enum 항목은 기존 유지)
- 외부 API 호출: Gemini 2.5 Flash (text_stream용, 기존 패턴)
- FE 영향: 신규 블록 타입 없음. intent 한국어 라벨 필요 시 FE 자체 처리.

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — SELECT 전용, 신규 테이블 없음
- [x] PG↔OS 동기화 — OS 신규 write 없음 (해당 없음)
- [x] append-only 4테이블 미수정 — population_stats SELECT만, §2 "DB 스키마 영향: 없음"
- [x] 소프트 삭제 매트릭스 준수 — DELETE 없음 (해당 없음)
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 신규 칼럼 없음
- [x] 6 지표 스키마 보존 — score 칼럼 접근 없음 (해당 없음)
- [x] gemini-embedding-001 768d 사용 — 임베딩 미사용 (해당 없음)
- [x] asyncpg 파라미터 바인딩 ($1, $2) — §1 SQL 전체 $1/$2 명시, f-string 없음
- [x] Optional[str] 사용 (str | None 금지) — §1 시그니처 `Optional[str]` 명시
- [x] SSE 블록 16종 한도 준수 — intent/text_stream 재사용, §2 "응답 블록 16종 영향: 없음"
- [x] intent별 블록 순서 (기획 §4.5) 준수 — intent → status → text_stream → done 순수 준수
- [x] 공통 쿼리 전처리 경유 — query_preprocessor 이후 crowdedness 라우팅
- [x] 행사 검색 DB 우선 → Naver fallback — 행사 검색 미관여 (해당 없음)
- [x] 대화 이력 이원화 (checkpoint + messages) 보존 — 이력 구조 변경 없음 (해당 없음)
- [x] 인증 매트릭스 (auth_provider) 준수 — 인증 변경 없음 (해당 없음)
- [x] 북마크 = 대화 위치 패러다임 준수 — 북마크 변경 없음 (해당 없음)
- [x] 공유링크 인증 우회 범위 정확 — URL 변경 없음 (해당 없음)
- [x] Phase 라벨 명시 — plan 헤더 "Phase: P1"
- [x] 기획 문서 우선 — step 1에서 기획서 §3.2 갱신 선행

## 4. 작업 순서 (Atomic step)

1. **기획서 §3.2 갱신** — `기획/_legacy/서비스 통합 기획서 v2.md` §3.2 Phase 2 목록에서 CROWDEDNESS 제거, Phase 1 목록에 추가. (불변식 #19 선행)
2. **헬퍼 함수 작성** — `_resolve_dong_code` / `_classify_level` / `_build_crowdedness_blocks`. 검증: `pytest tests/test_crowdedness_node.py::test_resolve_dong_code_neighborhood_match tests/test_crowdedness_node.py::test_resolve_dong_code_multiple_matches tests/test_crowdedness_node.py::test_resolve_dong_code_district_fallback tests/test_crowdedness_node.py::test_resolve_dong_code_none tests/test_crowdedness_node.py::test_classify_level_한산 tests/test_crowdedness_node.py::test_classify_level_보통 tests/test_crowdedness_node.py::test_classify_level_혼잡 tests/test_crowdedness_node.py::test_classify_level_매우혼잡 tests/test_crowdedness_node.py::test_classify_level_zero_avg tests/test_crowdedness_node.py::test_build_blocks_match tests/test_crowdedness_node.py::test_build_blocks_stale tests/test_crowdedness_node.py::test_build_blocks_no_match -v` PASS.
3. **`_fetch_population` + `crowdedness_node` 진입점 작성** — `ZoneInfo("Asia/Seoul")` KST hour. 검증: `pytest tests/test_crowdedness_node.py::test_node_skips_db_when_no_location tests/test_crowdedness_node.py::test_node_uses_kst_hour -v` PASS.
4. **`intent_router_node.py` 수정** — CROWDEDNESS를 PHASE1_INTENTS/\_ROUTABLE_INTENTS에 추가, `_CLASSIFY_SYSTEM_PROMPT` 이동.
5. **`real_builder.py` + `sse.py` 수정** — 4군데 + `_NODE_STATUS_MESSAGES` 키.
6. **통합 테스트 + validate.sh** — `pytest tests/test_crowdedness_node.py::test_sse_event_sequence -v` PASS + validate.sh 6단계 PASS.

## 5. 검증 계획

- validate.sh 통과
- 단위 테스트 (step 2: 12개, step 3: 2개):
  - `test_resolve_dong_code_neighborhood_match`
  - `test_resolve_dong_code_multiple_matches`
  - `test_resolve_dong_code_district_fallback`
  - `test_resolve_dong_code_none`
  - `test_classify_level_한산` — ratio=0.5
  - `test_classify_level_보통` — ratio=1.0
  - `test_classify_level_혼잡` — ratio=1.3
  - `test_classify_level_매우혼잡` — ratio=1.6
  - `test_classify_level_zero_avg`
  - `test_build_blocks_match`
  - `test_build_blocks_stale` — base_date 4일 전
  - `test_build_blocks_no_match`
  - `test_node_skips_db_when_no_location`
  - `test_node_uses_kst_hour` — monkeypatch `src.graph.crowdedness_node.datetime`
- 통합 테스트 (step 6):
  - `test_sse_event_sequence` — httpx.AsyncClient → `intent → status → text_stream → done` 시퀀스 assert
- 수동 시나리오:
  - `홍대 지금 사람 많아?` → CROWDEDNESS, 등급 포함 text_stream
  - `우주정거장 사람 많아?` → CROWDEDNESS, "데이터 없음" fallback
  - `안녕` → GENERAL (회귀 없음)

## 6. Metis/Momus 리뷰

- Metis 1차: reviews/001-metis-reject.md
- Metis 2차: reviews/002-metis-request-changes.md
- Momus 1차: reviews/003-momus-reject.md (Metis okay 부재로 reject)
- Metis 3차: reviews/004-metis-*.md 참조
- Momus 2차: reviews/005-momus-reject.md
- Momus 3차: reviews/006-momus-approve.md

## 7. 최종 결정

APPROVED (Metis 3차 004-metis-okay.md / Momus 3차 006-momus-approve.md)
