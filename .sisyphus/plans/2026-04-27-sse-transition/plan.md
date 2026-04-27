# SSE 전환 — WebSocket 스켈레톤 정리 + 기획 문서 동기화

- Phase: P1 / Infra
- 요청자: 이정
- 작성일: 2026-04-27
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

SSE 전환 결정(`기획/SSE_vs_WebSocket_결정.md`)에 따라:
- 기획 문서(API 명세서 CSV, 기능 명세서 CSV)의 WS 참조를 SSE로 재작성
- WS 지향 스켈레톤 코드(`websocket.py`) → SSE 스켈레톤(`sse.py`)으로 전환
- 프로젝트 전반 문서(CLAUDE.md, AGENTS.md, README.md, blocks.py docstring) WS→SSE 용어 동기화
- **데드라인**: 2026-04-28(월) 코어타임 전까지

### 전환 근거 (결정문 요약)
- 실제 통신 패턴이 단방향 스트리밍 중심 (12 intent 모두 쿼리→응답)
- 단일 GCE 서버 구조 — WS의 분산 장점 불필요
- 인프라/디버깅/재연결 단순성
- LLM 생태계(OpenAI/Anthropic/Gemini) SSE 정렬
- 개발 진입 전이라 변경 비용 최소

## 2. 영향 범위

- 신규 파일: `backend/src/api/sse.py` (SSE 핸들러 스켈레톤)
- 삭제 파일: `backend/src/api/websocket.py`
- 수정 파일:
  - `backend/src/main.py` (라우터 교체: ws_router → sse_router)
  - `backend/src/models/blocks.py` (docstring "WebSocket" → "SSE" 용어 교체, 모델 변경 없음)
  - `backend/src/graph/state.py` (docstring "WS" → "SSE" 용어)
  - `CLAUDE.md` (WebSocket/WS 참조 → SSE)
  - `backend/AGENTS.md` (동일)
  - `README.md` (동일)
  - `기획/API 명세서 424797f5eaec40c2bc66463118857814.csv` (WS 20 엔드포인트 → SSE)
  - `기획/API 명세서 424797f5eaec40c2bc66463118857814_all.csv` (동일)
  - `기획/기능 명세서 4669814b7a624c29b5422a85efcda2b1.csv` (WS 참조 14건)
  - `기획/기능 명세서 4669814b7a624c29b5422a85efcda2b1_all.csv` (동일)
  - `.claude/skills/localbiz-langgraph-node/REFERENCE.md` (websocket.py → sse.py, "WS 블록" 용어)
  - `.claude/skills/localbiz-langgraph-node/SKILL.md` ("WS 블록" 트리거 키워드)
  - `.claude/skills/localbiz-plan/REFERENCE.md` ("WS 블록 16종" 용어)
  - `.claude/skills/localbiz-erd-guard/REFERENCE.md` ("WS 블록 16종 추가/제거" 용어)
  - `.claude/agents/fe-visual.md` ("WS 블록 렌더링 팁", "WS 블록 16종 한도" 용어)
- DB 스키마 영향: **없음** (프로토콜 레이어만, messages.blocks JSON 구조 불변)
- 응답 블록 16종 영향: **없음** (블록 모델 자체 변경 없음, 전송 방식만 WS→SSE)
- intent 추가/변경: **없음**
- 외부 API 호출: **없음**
- FE 영향: **인지만** — `EventSource` / `@microsoft/fetch-event-source` 사용 안내 (결정문 §구현가이드에 스켈레톤 포함)
- 의식적 제외:
  - `backend/_archive/` (레거시 참조전용) — WS 용어 잔존하나 수정 불필요
  - `기획/_legacy/서비스 통합 기획서 v2.md` (legacy) — 동일
  - `.claude/hooks/*.sh` — "수정 금지" 규칙 (CLAUDE.md). 기존 "ws 블록" 트리거 키워드가 하위 호환으로 동작하므로 즉시 갱신 불필요

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 변경 없음
- [x] PG↔OS 동기화 — 변경 없음
- [x] append-only 4테이블 미수정 — 변경 없음
- [x] 소프트 삭제 매트릭스 준수 — 변경 없음
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음 — 변경 없음
- [x] 6 지표 스키마 보존 — 변경 없음
- [x] gemini-embedding-001 768d 사용 — 변경 없음
- [x] asyncpg 파라미터 바인딩 — 변경 없음
- [x] Optional[str] 사용 — 코드 작성 시 준수
- [x] ~~WS 블록~~ SSE 이벤트 타입 16종 한도 준수 — 블록 모델 변경 없음, 전송 방식만 변경
- [x] intent별 블록 순서 (기획 §4.5) 준수 — 순서 변경 없음
- [x] 공통 쿼리 전처리 경유 — 변경 없음
- [x] 행사 검색 DB 우선 → Naver fallback — 변경 없음
- [x] 대화 이력 이원화 보존 — 변경 없음
- [x] 인증 매트릭스 준수 — SSE에서 `@microsoft/fetch-event-source`로 JWT Bearer 유지 (결정문 §인증)
- [x] 북마크 = 대화 위치 패러다임 준수 — 변경 없음
- [x] 공유링크 인증 우회 범위 정확 — 변경 없음
- [x] Phase 라벨 명시 — P1/Infra
- [x] 기획 문서 우선 — 기획 CSV를 직접 수정하여 동기화

## 4. 작업 순서 (Atomic step)

### Step 1. SSE 스켈레톤 코드 작성 (category: deep)

1-1. `backend/src/api/sse.py` 신규 작성
  - 결정문 §FastAPI 구현 스켈레톤을 기반으로
  - `GET /api/v1/chat/stream` — SSE 스트리밍 엔드포인트 (query param: thread_id, query)
  - `POST /api/v1/chat/disambiguation/reply` — disambiguation 답변 (옵션 B)
  - `send_event()` 헬퍼: `event: {type}\ndata: {json}\n\n` 포맷
  - `request.is_disconnected()` 기반 중단 감지
  - Phase 1 stub: intent_router 미연동, done 이벤트만 전송
  - 타입 힌트: `Optional[str]` 사용 (불변식 #9)

1-2. `backend/src/main.py` 수정
  - `from src.api.sse import router as sse_router` 로 교체
  - `app.include_router(sse_router)` 로 교체
  - docstring "WebSocket" → "SSE"

1-3. `backend/src/api/websocket.py` 삭제

1-4. `backend/src/models/blocks.py` docstring 갱신
  - "WebSocket 응답 블록" → "SSE 응답 블록"
  - "WS 제어 프레임" → "SSE 제어 이벤트"
  - StatusFrame/DonePartialFrame docstring "WS" → "SSE"
  - **모델 구조 변경 없음**

1-5. `backend/src/graph/state.py` docstring 갱신
  - `response_blocks` 설명 "WS로 전송" → "SSE로 전송"

### Step 2. 기획 문서 수정 (category: quick)

2-1. `기획/API 명세서 *.csv` — WS 엔드포인트 20개 → SSE로 재작성
  - Method: `WS` → `GET` (스트리밍), `POST` (disambiguation)
  - URL: `/api/v1/chat/ws` → `/api/v1/chat/stream` + `/api/v1/chat/disambiguation/reply`
  - Request: Client→Server JSON → query params (GET) 또는 request body (POST)
  - Response: Server→Client WS frame → SSE event 포맷 (`event: type\ndata: {json}\n\n`)
  - 에러 처리: WS disconnect → `request.is_disconnected()` / `AbortController`
  - 재연결: WS 수동 → 브라우저 `Last-Event-ID` 자동
  - 중단: WS `{type:cancel}` → `EventSource.close()` / `AbortController.abort()`

2-2. `기획/기능 명세서 *.csv` — WS 참조 14건 수정
  - "WS 연결" → "SSE 스트림"
  - "WS로 전송" → "SSE 이벤트로 전송"
  - "WS 블록 순서" → "SSE 이벤트 순서"
  - 에러 처리/재연결 설명 SSE 방식으로 교체

### Step 3. 프로젝트 문서 동기화 (category: quick)

3-1. `CLAUDE.md` 수정
  - "WebSocket 핸들러" → "SSE 핸들러"
  - `src/api/websocket.py` → `src/api/sse.py`
  - 불변식 #10 원문: "WS 블록 16종 고정" → "SSE 이벤트 타입 16종 고정", "WS 제어 프레임" → "SSE 제어 이벤트"
  - 코드리뷰 체크리스트: "WS 블록 추가/제거 시" → "SSE 이벤트 타입 추가/제거 시"
  - Architecture 섹션 LangGraph Flow 설명 갱신
  - 갱신 후 기획 CSV(Step 2)의 SSE 용어와 정확히 일치하는지 교차 확인

3-2. `backend/AGENTS.md` 수정
  - `src/api/websocket.py` → `src/api/sse.py`
  - "WebSocket" 용어 → "SSE"

3-3. `README.md` 수정
  - "WebSocket" 참조 → "SSE"
  - FE 관련 안내: `EventSource` / `@microsoft/fetch-event-source` 언급

### Step 4. Skills/Agents 용어 갱신 (category: quick)

> `.claude/hooks/` 트리거 키워드 갱신은 "수정 금지" 규칙에 따라 이 plan 범위에서 제외.
> 기존 "ws 블록" 키워드가 하위 호환으로 동작하므로 즉시 수정 불필요.

4-1. `.claude/skills/` 및 `.claude/agents/` 내 WS 참조 갱신
  - `localbiz-langgraph-node/REFERENCE.md` — websocket.py → sse.py, "WS 블록" → "SSE 이벤트"
  - `localbiz-langgraph-node/SKILL.md` — "WS 블록" 트리거 키워드 갱신
  - `localbiz-plan/REFERENCE.md` — "WS 블록 16종" 용어 갱신
  - `localbiz-erd-guard/REFERENCE.md` — "WS 블록 16종 추가/제거" 용어 갱신
  - `.claude/agents/fe-visual.md` — "WS 블록 렌더링 팁", "WS 블록 16종 한도" 용어 갱신

### Step 5. validate.sh 실행 + 최종 확인 (category: quick)

5-1. `./validate.sh` 6단계 통과 확인
5-2. `python -m uvicorn src.main:app` smoke test (import 에러 없음)
5-3. 프로젝트 전체에서 WS 잔존 참조 grep 확인 (`grep -r "websocket\|WebSocket" . --include="*.md" --include="*.py" --include="*.sh"` — `_archive/`, `_legacy/` 제외)

## 5. 검증 계획

- `./validate.sh` 통과 (ruff check + format + pyright + pytest + 기획무결성 + plan무결성)
- `pyright src/api/sse.py` — 타입 에러 0
- `grep -r "websocket\|WebSocket\|WS 블록\|WS 제어" . --include="*.md" --include="*.py" --include="*.sh" --exclude-dir=_archive --exclude-dir=_legacy --exclude-dir=venv` — 참조 0건
- `python -c "from src.main import app"` — import smoke test
- CLAUDE.md 불변식 #10 용어와 기획 CSV SSE 용어 일치 교차 확인

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

APPROVED (001-metis-okay → 002-momus-reject → 003-momus-reject → 004-momus-approved)
