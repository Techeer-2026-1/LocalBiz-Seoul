# Metis 리뷰 — SSE 행사 검색 노드 (Issue #47)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (페르소나 채택, 본 PR Claude Code 미설치)
- 검토일: 2026-05-04
- plan: `.sisyphus/plans/2026-05-04-event-search/plan.md` (9823 bytes, 7 섹션)
- 판정: **okay (단 권장사항 3건 검토 권장)**

## 검증 절차

본 plan을 다음 권위 source와 대조 검증:

1. `기획/AnyWay 백엔드 명세 v1.4.docx` — SSE 채팅 명세
2. `기획/AnyWay 백엔드 ERD v6.3.docx` — events 테이블 schema
3. `.sisyphus/REFERENCE.md` — 19 불변식 (특히 #13 DB 우선 → fallback)
4. 기존 머지본: place_search_node.py (가장 유사한 양식)
5. real_builder.py — stub 함수 위치
6. 인증 시리즈 5종 PR — async/외부 API mock 학습

## 갭 분석 결과

### §1 요구사항 정합

명세상 EVENT_SEARCH 동작:

```http
GET /api/v1/chat/stream?query=이번 주말 서울 전시회
→ intent → status → text_stream
→ DB 우선 → Naver fallback 행사 검색
```

plan §1이 정확히 매핑:
- LangGraph 노드 함수로 구현 (`event_search_node`) ✅
- response_blocks 3종(text_stream, events[], references[]) ✅
- DB 우선 → Naver fallback 흐름 (#13 불변식) ✅
- SSE 라우터는 변경 안 함 (LangGraph가 매핑 자동) ✅

**범위 외 항목 검증**:
- EVENT_RECOMMEND (#46) → 별도 PR ✅
- vector 검색 → 후속 plan ✅
- caching → 후속 plan ✅
- 자연어 날짜 정확 변환 → query_preprocessor 강화 후 (Phase 2) ✅

특히 plan 작성자가:
- date_reference 자연어 처리 한계 명시 (Phase 1 단순화) ✅
- Naver API 일 25,000 한도 명시 ✅
- 사용자 query / API 키 logger 진입 금지 명시 ✅

**갭 0**.

### §2 영향 범위 정합

plan은 "신규 2 + 수정 2"라 명시.

- 신규 event_search_node.py: place_search_node.py 양식 따라가는 게 정공 ✅
- 신규 test_event_search.py: 인증 시리즈 mock fixture 양식 재사용 ✅
- 수정 real_builder.py: stub 제거 + 진짜 함수 import (정찰 결과 L41-43에서 확인됨) ✅
- 수정 config.py: Settings에 naver_client_id/secret 추가 (정찰 시 미존재 확인) ✅

**갭 0**.

### §3 19 불변식 체크리스트

- **#1 PK 이원화** — event_id (BIGSERIAL) 외부 ID 분리 ✅
- **#2 timestamp** — SELECT만, 적용 무관 ✅
- **#7 embedding** — 본 PR은 SQL only, 적용 무관 (후속 plan) ✅
- **#8 SQL 파라미터** — `$1, $2` 양식 명시 ✅
- **#9 Optional** — NULL 가능 컬럼 처리 명시 ✅
- **#13 DB 우선 → fallback** — 정확히 #1 §1과 매핑 ✅
- **#18 Phase 라벨** — P1 ✅
- **#19 PII 보호** — query/API 키 logger 금지 ✅

**갭 0**.

### §4 작업 순서 정합

7개 atomic step. step 1 (config.py)이 가장 먼저 — 의존성 순서 정확. 후속 step들이 모두 settings 사용하므로 첫 단계에 위치한 게 정공.

step 2 (event_search_node.py)의 5개 헬퍼(_search_pg, _search_naver, _naver_to_event_dict, _build_blocks, event_search_node)가 단일 책임 원칙 잘 분리. 코드 작성 시 함정 회피 명확.

**갭 0**.

### §5 검증 계획 정합

5.1 단위/통합 테스트 4건:
- pg_only_success ✅
- naver_fallback ✅
- pg_empty_naver_fallback ✅
- naver_api_error_graceful ✅

각 테스트가 §1 핵심 시나리오와 1:1 매핑. 특히 `naver_api_error_graceful`은 본 PR의 핵심 비기능 요구사항(graceful degradation) 검증.

**갭 0**.

### §6 함정 회피 정합

plan §6이 인증 시리즈 학습 4건 + 본 PR 신규 함정 8건 명시:

학습 누적:
- async def 안의 동기 I/O 금지 (Google #42 학습) ✅
- 외부 API mock (Google #42 학습) ✅
- PII 보호 (#19) ✅
- SQL 파라미터 분리 (#8) ✅

신규 함정 (8건 모두 합리적):
1. graceful degradation ✅
2. Naver schema 미정합 변환 ✅
3. PostGIS geom NULL 처리 ✅
4. date_reference 자연어 단순화 ✅
5. magic number `>= 3` 상수 분리 ✅
6. Naver timeout 5초 ✅
7. events 컬럼 fs 확인 (정찰 시 했음) ✅
8. stub 호출 위치 grep ✅

**갭 0**.

### §7 결정

PENDING — Metis/Momus 통과 시 APPROVED. plan 양식 정공.

## 권장 (선택, reject 사유 아님)

### 권장 1 (중요): Naver API 응답 양식 사전 정의

plan §6 함정 #2에 "Naver schema 미정합 변환"이라 명시했지만, 정확한 Naver 검색 API 응답 양식은 plan에 없음. Momus 페르소나가 fs 검증 시 Naver 공식 문서로 확인 권장:

- 블로그 검색: `https://openapi.naver.com/v1/search/blog.json`
  - 응답: `items[]` 배열 (각 item: title, link, description, bloggername, postdate)
- 통합 검색: 카테고리별 다른 endpoint (cafearticle, news, kin 등)

본 PR이 어느 endpoint 사용할지(블로그? 통합? 뉴스?) plan에 명시 없음. 코드 작성 시 결정 필요.

**제안**: plan §1 또는 §4 step 2에 "Naver 검색 API endpoint = `/v1/search/blog.json` (행사 정보 풍부도)" 명시 권장. 또는 코드 작성 시 결정하고 본 권장은 무시.

### 권장 2: PG 검색 SQL의 date 필터 명시

plan §6 함정 #4에 "date_reference Phase 1 단순화"라 명시했지만, 구체적으로 어떻게 처리할지 코드 작성 시 결정 필요. 두 가지 옵션:

- A. date_reference 무시, 모든 행사 반환 (단순)
- B. `WHERE date_end >= NOW()` (지난 행사 자동 제외) — 운영상 의미 있음

**제안**: §4 step 2 또는 §6에 "Phase 1 단순화: `WHERE date_end >= NOW()`로 지난 행사만 자동 제외, date_reference는 무시" 명시 권장.

### 권장 3: Settings 변수 default 값과 빈 값 처리

plan §4 step 1에서 `naver_client_id: str = ""` 추가 명시. 본인 .env에 값 채워졌으나 CI 환경에서는 비어있을 수 있음. 본 PR 코드가 빈 값일 때 어떻게 동작할지(Naver 호출 skip? 또는 401 에러?) plan에 명시 없음.

**제안**: §6 함정에 "naver_client_id 빈 값 시 Naver 호출 skip + PG 결과만 반환" 한 줄 추가 권장. 안전한 default 동작.

## 판정

**okay** — plan은 명세, ERD, 19 불변식, 인증 시리즈 학습, place_search_node 양식과 모두 정합. 본인 첫 LangGraph 노드 + 외부 API fallback 구현으로서 plan §6 함정 회피 8건 사전 명시. Momus(fs 검증)로 진행 권장.

위 권장 3건은 코드 작성 시 결정해도 무방하나, plan 단계에서 명시하면 후속 PR 작성자 + 본인 미래 self가 의도 파악 쉬움.
