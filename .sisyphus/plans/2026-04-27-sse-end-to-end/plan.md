# SSE end-to-end 관통 — LangGraph astream + GENERAL intent

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-27
- 상태: approved
- 최종 결정: APPROVED

> 팀원 병목 해소: 정조셉(노드 구현), 이정원(FE SSE 연동)이 이 작업 완료 후 시작 가능.

## 1. 요구사항

"안녕" → Gemini가 SSE로 토큰 단위 응답하는 최소 동작 파이프라인.
모든 intent 노드의 기반이 되는 첫 번째 관통 테스트.

흐름:
```
GET /api/v1/chat/stream?thread_id=xxx&query=안녕
  → sse.py: conversations 없으면 auto-create + user 메시지 INSERT (role='user')
  → LangGraph astream() 호출
  → intent_router_node: GENERAL로 분류
  → query_preprocessor_node: stub (빈 dict 반환, 그래프 토폴로지 유지)
  → general_node: Gemini astream()으로 토큰 생성
  → response_builder_node: done 블록 추가
  → sse.py: event: intent → event: text_stream × N → event: done
  → assistant 메시지 INSERT (role='assistant', blocks=응답 블록)
```

전제 조건:
- messages.thread_id → conversations(thread_id) FK 존재
- conversations가 없으면 INSERT 실패 → sse.py에서 auto-create 처리
- user 메시지 + assistant 메시지 양쪽 모두 저장해야 대화 이력 성립

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/general_node.py` — GENERAL intent Gemini 스트리밍
  - `backend/src/graph/response_builder_node.py` — 블록 순서 검증 + done
- 수정 파일:
  - `backend/src/api/sse.py` — stub → LangGraph astream() 실제 연동
  - `backend/src/graph/real_builder.py` — stub 함수 → 실제 import 교체 (general, response_builder, intent_router)
  - `backend/src/graph/intent_router_node.py` — stub → Gemini JSON mode 분류
- DB 스키마 영향: 없음 (messages INSERT만, 테이블 이미 존재)
- 응답 블록 16종 영향: intent, text_stream, done 3종 사용 (기존 모델 그대로)
- intent 추가/변경: 없음 (13 intent 그대로, 분류 로직 구현)
- 외부 API 호출: Gemini 2.5 Flash (intent 분류 + 대화 응답)
- FE 영향: 이 작업 완료 후 SSE 수신 테스트 가능

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — messages BIGINT PK
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — messages INSERT만. UPDATE/DELETE 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음 (LLM 호출, 임베딩 아님)
- [x] asyncpg 파라미터 바인딩 ($1, $2) — messages INSERT에 적용
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — intent/text_stream/done 사용 (추가 없음)
- [x] intent별 블록 순서 (기획 §4.5) 준수 — GENERAL: intent → text_stream → done
- [x] 공통 쿼리 전처리 경유 — GENERAL은 전처리 불필요 (일반 대화)
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [ ] 대화 이력 이원화 보존 — **P1 범위 예외**: checkpointer=None으로 checkpoint 비활성. messages INSERT(UI용)만 동작. PostgresSaver 연동 시 해소 예정.
- [x] 인증 매트릭스 준수 — deps.py placeholder 사용
- [x] 북마크 = 대화 위치 패러다임 준수 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — 기획서 §4.5 GENERAL 블록 순서 준수

## 4. 작업 순서 (Atomic step)

1. `backend/src/graph/general_node.py` — 신규
   - Gemini 2.5 Flash 호출 (google-generativeai SDK)
   - text_stream 블록을 response_blocks에 append
   - 스트리밍이 아닌 단일 응답으로 먼저 구현 (토큰 스트리밍은 sse.py에서 처리)

2. `backend/src/graph/response_builder_node.py` — 신규
   - response_blocks에 done 블록 추가
   - intent별 블록 순서 검증 (GENERAL: intent → text_stream → done)

3. `backend/src/graph/intent_router_node.py` — 수정
   - stub → Gemini JSON mode로 13 intent 분류
   - 분류 결과를 state["intent"]에 저장
   - 실패 시 GENERAL fallback

4. `backend/src/graph/real_builder.py` — 수정
   - _general_node stub → actual general_node import
   - _response_builder_node stub → actual import
   - _intent_router_node stub → actual import

5. `backend/src/api/sse.py` — 수정
   - stub done 전송 → LangGraph astream() 실제 호출
   - seed user 보장: user_id=1이 users 테이블에 없으면 INSERT (개발용, 인증 연동 전까지)
   - conversations auto-create: thread_id로 조회 → 없으면 INSERT (user_id + thread_id)
   - user 메시지 INSERT: role='user', blocks=[{"type":"text","content":query}]
   - 각 노드 출력을 SSE 이벤트로 변환하여 전송
   - 완료 후 assistant 메시지 INSERT: role='assistant', blocks=response_blocks
   - INSERT 실패 시 로그만, 재시도/수정 없음 (append-only 정책)
   - request.is_disconnected() 체크
   - checkpointer: P1 최소 동작에서는 None (LangGraph checkpoint 미사용). 이후 PostgresSaver 연동.

6. validate.sh 통과 + curl 테스트

범위 제한:
- event_recommend/calendar conditional edges 누락은 기존 상태. 이 plan에서는 건드리지 않음.
  intent_router가 해당 intent를 분류해도 GENERAL fallback으로 처리.
- query_preprocessor는 stub 유지 (빈 dict 반환). GENERAL은 검색이 아니므로 전처리 불필요.

## 5. 검증 계획

- `./validate.sh` 통과
- `curl "localhost:8000/api/v1/chat/stream?thread_id=test&query=안녕"` → SSE 이벤트 스트리밍 확인
  - event: intent (type: GENERAL)
  - event: text_stream × N (Gemini 응답)
  - event: done
- messages 테이블에 블록 저장 확인 (postgres MCP로 SELECT)
- request disconnect 시 스트리밍 중단 확인

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

APPROVED (Metis 003-okay + Momus 005-approved, 2026-04-28)
