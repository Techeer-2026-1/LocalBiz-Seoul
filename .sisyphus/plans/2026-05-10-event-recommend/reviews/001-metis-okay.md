# Metis 리뷰 — SSE 행사 추천 노드 (Issue #46)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (페르소나 채택)
- 검토일: 2026-05-10
- plan: `.sisyphus/plans/2026-05-10-event-recommend/plan.md`
- 판정: **okay (단 권장사항 2건 검토 권장)**

## 검증 절차

본 plan을 다음 권위 source와 대조:

1. `기획/API 명세서 v2 (SSE) ...csv` L86 — EVENT_RECOMMEND 행
2. `기획/AGENTS.md` (있는 경우) + 기획서 §4.5 (블록 순서)
3. `.sisyphus/REFERENCE.md` 19 불변식 (특히 #11 블록 순서, #13 DB 우선)
4. EVENT_SEARCH #47 plan + Metis/Momus 리뷰 (같은 패턴 PR)
5. PLACE_RECOMMEND #52 머지본 (`backend/src/graph/place_recommend_node.py`) — 형제 노드 양식
6. dev 브랜치 fs 정찰 — stub 등록 위치, intent_router 매핑

## 갭 분석 결과

### §1 요구사항 정합

명세 CSV L86:
```
SSE: 행사 추천 (EVENT_RECOMMEND), 진행중, GET, Phase 1
request: GET /api/v1/chat/stream?query=주말에 갈 만한 전시회 추천해줘
response: intent → status → text_stream → events[] → references → done
url: /api/v1/chat/stream
담당자: 한정수
설명: 취향/맥락 기반 행사 추천 + 추천 사유
```

plan §1이 정확히 매핑:
- LangGraph 노드로 구현 ✅
- 응답 블록 5종 (intent/status/text_stream/events/references/done) — 기획 §4.5 권위 ✅
- DB 우선 → Naver fallback (#13 불변식) ✅
- 취향/맥락 기반 추천 사유 → 시스템 프롬프트 강화로 차별화 ✅

**범위 외 분리 명시**:
- vector k-NN → 후속 plan ✅
- 사용자 취향 ML → Phase 2 ✅
- LLM Rerank → 후속 ✅
- caching → 후속 ✅
- date 자연어 → query_preprocessor 강화 후 ✅

**갭 0**.

### §2 영향 범위 정합

plan은 "신규 2 + 수정 1".

- 신규 event_recommend_node.py: PLACE_RECOMMEND 양식 + EVENT_SEARCH 양식 혼합. 정합 ✅
- 신규 test_event_recommend.py: EVENT_SEARCH 테스트 mock 양식 차용 ✅
- 수정 real_builder.py: dev에 stub `_event_recommend_node` L42 + 매핑 L76 + add_node L106 등록됨. 본 PR이 stub→실 함수 교체 ✅
- intent_router 무수정: dev에 EVENT_RECOMMEND intent 등록됨 (intent_router_node.py L23/45/63/85) ✅
- config.py 무수정: NAVER_CLIENT_ID/SECRET 이미 #47 PR에서 추가됨 — **단 #47 미머지!**

**⚠️ fs 갭 1건 (Momus가 실측 검증해야)**: plan §2는 "config.py 수정 0건 (Naver Settings 이미 추가됨)"이라 명시. 그러나 #47이 dev에 미머지면 dev base의 config.py에는 `naver_client_id` / `naver_client_secret` **미존재** 가능성. Momus fs 실측 필수.

### §3 19 불변식 체크리스트

- **#1 PK 이원화** — events.event_id VARCHAR(36), Naver는 None ✅
- **#4 소프트 삭제** — is_deleted=FALSE 강제 (#47 CodeRabbit #2 학습 적용) ✅
- **#8 SQL 파라미터** — `$1, $2` 양식 + f-string 0건 (#47 CodeRabbit #3 학습) ✅
- **#9 Optional** — Optional[str] 명시 ✅
- **#10/11 SSE 16종/블록 순서** — 신규 블록 0건, 기획 §4.5 그대로 ✅
- **#13 DB 우선 → fallback** — 정확 매핑 ✅
- **#18 Phase 라벨** — P1 ✅
- **#19 PII 보호** — query/API 키 logger 금지 ✅

**갭 0**.

### §4 작업 순서 정합

6 atomic step. step 1 (event_recommend_node.py 생성)이 핵심, step 2 (real_builder.py stub 제거)는 step 1 의존. 순서 정공.

step 1의 5개 헬퍼(_search_pg, _search_naver, _naver_to_event_dict, _build_blocks, event_recommend_node)가 단일 책임 원칙 분리 — EVENT_SEARCH와 같은 패턴이라 일관성 확보.

**갭 0**.

### §5 검증 계획 정합

5건 단위 테스트:
- naver_to_event_dict_html_clean ✅
- naver_to_event_dict_missing_fields ✅
- build_blocks_db_only ✅
- build_blocks_naver_fallback ✅
- build_blocks_recommend_prompt ← 본 PR 차별화 검증 (EVENT_SEARCH 대비 추가) ✅

각 테스트가 §1 핵심 시나리오와 매핑. 특히 `build_blocks_recommend_prompt`가 EVENT_RECOMMEND 차별화(추천 사유) 검증 — 정공.

**갭 0**.

### §6 함정 회피 정합

EVENT_SEARCH #47 학습 8건 + 본 PR 신규 함정 7건 명시:

학습 누적:
- async I/O / 외부 API mock / PII / SQL 파라미터 / f-string 0건 / is_deleted / 컬럼 fs 확인 / stub grep ✅

신규 함정 (7건 모두 합리적):
1. EVENT_SEARCH와 코드 중복 → 시스템 프롬프트 차별화 ✅
2. #47 미머지 상태 작업 → 자체 _search_pg 구현 + rebase 양식 사전 명시 ✅
3. 추천 사유 LLM 프롬프트 단순화 (Phase 2 ML 분리) ✅
4. references 블록 항상 포함 (EVENT_SEARCH와 차이) ✅
5. _MIN_PG_RESULTS = 3 (EVENT_SEARCH와 동일 임계값) ✅
6. Naver timeout 5초 ✅
7. PostGIS geom NULL 처리 ✅

**갭 0**.

## 권장 (선택, reject 사유 아님)

### 권장 1 (중요): #47 미머지 상태에서 config.py Naver Settings 누락 가능성

plan §2는 "config.py 수정 0건"이라 명시했지만, dev base에서는 `naver_client_id` / `naver_client_secret`가 Settings에 **없을 수 있음** (#47에서 추가됐기 때문).

**제안**: Momus가 fs 실측으로 dev base의 `backend/src/config.py`를 확인해서 naver_* 변수 유무 보고. 없으면 본 PR에서 추가 필요 (수정 파일 +1, plan §2 갱신).

### 권장 2: references 블록 양식 명세

plan §1은 "references 블록 항상 포함"이라 명시. EVENT_SEARCH는 Naver fallback 시에만 포함. 본 PR이 DB 행사도 references에 포함하려면 다음 결정 필요:

- A. DB 행사: detail_url 있으면 references에 `{title, url, source: "events_db"}` 추가
- B. references는 Naver만, DB 행사는 events 블록의 detail_url로만

**제안**: A 옵션이 명세 정합성 높음 (references 항상 포함). plan §4 step 1 _build_blocks 구현 시 명시 권장. 또는 코드 작성 시 결정.

## 판정

**okay** — plan은 명세, 19 불변식, EVENT_SEARCH 학습, PLACE_RECOMMEND 양식 모두 정합. 본 PR은 EVENT_SEARCH와 PLACE_RECOMMEND의 패턴을 정확히 차용한 형제 노드 — 학습 누적 8건 + 신규 함정 7건 사전 명시.

위 권장 2건은 Momus fs 실측 후 결정 가능. 코드 작성 진입 권장 (Momus 통과 시).
