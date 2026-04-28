# 대화 관리 REST API 5개

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-27
- 상태: approved
- 최종 결정: APPROVED

> GitHub Issue: feat/#3

## 1. 요구사항

대화 관리 REST API 5개 구현. 사이드바 채팅 목록, 대화 히스토리, 제목 수정, 삭제 기능의 백엔드.
인증(JWT)은 한정수 작업 중 — 인증 placeholder로 먼저 구현 후 연동.

| Method | URL | 기능 |
|---|---|---|
| GET | `/api/v1/chats` | 채팅 목록 조회 (cursor 페이지네이션) |
| GET | `/api/v1/chats/{thread_id}` | 채팅 상세 조회 (메타데이터) |
| GET | `/api/v1/chats/{thread_id}/messages` | 메시지 전체 조회 (cursor 페이지네이션) |
| PATCH | `/api/v1/chats/{thread_id}` | 대화 제목 수정 |
| DELETE | `/api/v1/chats/{thread_id}` | 대화 삭제 (소프트 삭제) |

## 2. 영향 범위

- 신규 파일:
  - `backend/src/api/chats.py` — FastAPI 라우터
  - `backend/src/api/deps.py` — 인증 placeholder (`get_current_user_id`)
  - `backend/src/models/chats.py` — Pydantic 요청/응답 모델
- 수정 파일:
  - `backend/src/main.py` — chats 라우터 등록
- DB 스키마 영향: 없음 (conversations, messages 이미 존재)
- 응답 블록 16종 영향: 없음 (REST API, SSE 아님)
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FE 영향: 사이드바 채팅 목록 + 대화 히스토리 로딩에 사용될 API

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — conversations BIGINT, messages BIGINT
- [x] PG↔OS 동기화 — 해당 없음 (대화 테이블은 OS 미연동)
- [x] append-only 4테이블 미수정 — messages SELECT만. INSERT는 이 PR 범위 밖 (SSE에서 담당)
- [x] 소프트 삭제 매트릭스 준수 — conversations.is_deleted = true로 소프트 삭제
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 ($1, $2) — 전 쿼리 적용
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — 해당 없음 (REST)
- [x] intent별 블록 순서 (기획 §4.5) 준수 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 보존 — messages(UI용 append-only) 읽기만. checkpoint 미접촉
- [x] 인증 매트릭스 준수 — placeholder로 구현, JWT 연동 시 교체
- [x] 북마크 = 대화 위치 패러다임 준수 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — API 명세서 v2 DB 기준

## 4. 작업 순서 (Atomic step)

1. `backend/src/models/chats.py` — Pydantic 요청/응답 모델
   - ChatListItem, ChatDetail, MessageItem
   - ChatListResponse (cursor 포함), MessageListResponse (cursor 포함)
   - ChatUpdateRequest (title)

2. `backend/src/api/deps.py` — 인증 placeholder
   - `get_current_user_id()` → 임시 user_id 반환
   - TODO 주석으로 JWT 교체 지점 명시

3. `backend/src/api/chats.py` — 라우터 5개
   - 공통: 모든 {thread_id} 엔드포인트에 소유권 검증 (user_id 일치 + is_deleted=false). 미소유/삭제됨 → 404
   - GET /api/v1/chats — conversations에서 user_id + is_deleted=false, updated_at DESC, cursor 페이지네이션
   - GET /api/v1/chats/{thread_id} — 단일 conversation 메타데이터. 미존재/삭제됨 → 404
   - GET /api/v1/chats/{thread_id}/messages — messages에서 thread_id, message_id 기반 cursor, ASC 정렬. conversation 삭제됨 → 404
   - PATCH /api/v1/chats/{thread_id} — title UPDATE + updated_at 갱신
   - DELETE /api/v1/chats/{thread_id} — is_deleted = true + updated_at 갱신
   - 모듈 docstring에 messages append-only 경고 포함

4. `backend/src/main.py` — chats_router include

5. `backend/tests/test_chats.py` — 최소 테스트 (200, 404, 소프트삭제 시나리오)

6. validate.sh 통과 확인

## 5. 검증 계획

- `./validate.sh` 통과 (ruff + pyright + pytest)
- `cd backend && source venv/bin/activate && python -m uvicorn src.main:app --reload` 후:
  - `curl localhost:8000/api/v1/chats` → 200 빈 목록
  - `curl -X PATCH localhost:8000/api/v1/chats/test-thread -d '{"title":"새제목"}'` → 동작 확인
- messages INSERT 쿼리 없음 (grep 확인)

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

APPROVED (001-metis-okay → 002-momus-approved)
