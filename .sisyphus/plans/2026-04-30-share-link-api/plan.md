# 대화 공유 링크 API 3종 — 생성/조회/해제

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-30
- 상태: approved
- 최종 결정: APPROVED (Metis 003-okay + Momus 004-approved, 2026-04-30)

> Phase 라벨 참고: ERD v6.3과 CLAUDE.md #18은 공유를 P2로 분류하나, 현행 API/기능 명세서 v2 (SSE)에서 P1으로 변경됨. PM(이정) 확인 완료. ERD/CLAUDE.md Phase 라벨 정정은 후속 처리.

## 1. 요구사항

대화를 공유 링크로 공유하는 REST API 3개 구현.
불변식 #17: `/shared/{share_token}` GET만 인증 우회. 그 외 모두 JWT.

### API 목록

| 기능 | Method | URL | 인증 | 응답 |
|---|---|---|---|---|
| 공유 링크 생성 | POST | `/api/v1/chats/{thread_id}/share` | JWT | 201 + share_token |
| 공유 대화 조회 | GET | `/shared/{share_token}` | 없음 | 200 + messages |
| 공유 링크 해제 | DELETE | `/api/v1/chats/{thread_id}/share` | JWT | 204 |

### DB 테이블 (이미 존재, 스키마 변경 없음)

`shared_links`:
- share_id: BIGSERIAL PK
- share_token: VARCHAR UNIQUE
- thread_id: VARCHAR (FK 없음 — ERD 실측 확인. 코드에서 conversations 존재 검증)
- user_id: BIGINT → users FK
- from_message_id: BIGINT → messages FK (null이면 전체 대화)
- to_message_id: BIGINT → messages FK (null이면 전체 대화)
- expires_at: TIMESTAMPTZ (null이면 영구)
- is_deleted: BOOLEAN (소프트 삭제)

### 다중 링크 정책

- 같은 thread_id로 POST 여러 번 호출 시 **매번 새 share_token 생성** (message_range가 다를 수 있으므로)
- DELETE `/api/v1/chats/{thread_id}/share` → 해당 thread의 **모든** 활성 공유 링크 소프트 삭제

### 요청/응답 스키마

**POST /api/v1/chats/{thread_id}/share**
```json
// Request
{ "message_range": { "from_message_id": null, "to_message_id": null } }

// Response 201
{ "share_token": "abc123def456", "share_url": "/shared/abc123def456", "expires_at": null }
```

share_token: uuid4 hex (32자, URL-safe, VARCHAR(100) 범위 내)

**GET /shared/{share_token}**
```json
// Response 200 (인증 불필요)
{
  "thread_title": "홍대 카페 추천",
  "messages": [
    { "role": "user", "blocks": [...], "created_at": "ISO8601" },
    { "role": "assistant", "blocks": [...], "created_at": "ISO8601" }
  ]
}
```

message_range 필터링:
- from_message_id / to_message_id 둘 다 null → 전체 messages
- non-null → `WHERE message_id >= $from AND message_id <= $to`

검증: is_deleted=false AND (expires_at IS NULL OR expires_at > now())

**DELETE /api/v1/chats/{thread_id}/share**
```
204 No Content
UPDATE shared_links SET is_deleted=true, updated_at=now() WHERE thread_id=$1 AND user_id=$2 AND is_deleted=false
```

## 2. 영향 범위

- 신규 파일:
  - `backend/src/api/share.py` — 라우터 3개
  - `backend/src/models/share.py` — Pydantic 모델
  - `backend/tests/test_share.py` — 단위 테스트
- 수정 파일:
  - `backend/src/main.py` — share 라우터 등록
- DB 스키마 영향: 없음 (shared_links 테이블 이미 존재)
- 응답 블록 16종: 변경 없음
- FE 영향: 공유 링크 URL 렌더링 + 읽기 전용 뷰. 응답 구조는 채팅 상세 조회와 동일 패턴.
- 외부 API: 없음

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — shared_links BIGSERIAL PK (UUID 아님)
- [x] #2 PG↔OS 동기화 — 해당 없음
- [x] #3 append-only — shared_links는 append-only 4테이블 아님. UPDATE(소프트 삭제) 허용.
- [x] #4 소프트 삭제 — is_deleted + updated_at 사용. ERD §3 매트릭스 준수.
- [x] #5 비정규화 3건 — 신규 비정규화 없음
- [x] #6 6 지표 고정 — 해당 없음
- [x] #7 임베딩 768d — 해당 없음
- [x] #8 asyncpg 바인딩 — $1, $2 파라미터 바인딩 필수
- [x] #9 Optional[str] — str | None 미사용
- [x] #10 SSE 16종 — 해당 없음 (REST API)
- [x] #11 블록 순서 — 해당 없음
- [x] #12 공통 쿼리 전처리 — 해당 없음
- [x] #13 행사 DB 우선 — 해당 없음
- [x] #14 대화 이력 이원화 — messages SELECT만 (공유 조회 시)
- [x] #15 이중 인증 — 해당 없음
- [x] #16 북마크 — 해당 없음
- [x] #17 공유링크 — **핵심**: /shared/{share_token} GET만 인증 우회. POST/DELETE는 JWT.
- [x] #18 Phase 라벨 — P1 (PM 확인. ERD/CLAUDE.md 후속 정정 필요)
- [x] #19 기획 문서 우선 — 현행 API/기능 명세서 v2 (SSE) 준수. ERD Phase 라벨 불일치는 인지 + 후속 정정.

## 4. 작업 순서 (Atomic step)

1. `backend/src/models/share.py` — Pydantic 모델 신규
   - ShareCreateRequest, ShareCreateResponse, SharedConversationResponse
   - 검증: ruff + pyright 통과

2. `backend/src/api/share.py` — 라우터 3개 신규
   - POST: share_token(uuid4 hex) 생성 → shared_links INSERT. 소유권 검증(user_id).
   - GET: is_deleted=false + 만료 미도래 확인 → messages SELECT (message_range 필터링 포함)
   - DELETE: 해당 thread의 모든 활성 링크 소프트 삭제 (UPDATE is_deleted=true)
   - 검증: ruff + pyright 통과

3. `backend/src/main.py` — share 라우터 등록
   - 검증: ruff 통과

4. `backend/tests/test_share.py` — 단위 테스트
   - test_create_share_link — 생성 → share_token 반환
   - test_get_shared_conversation — 조회 → messages 반환 (인증 없이)
   - test_delete_share_link — 해제 → 204 + 이후 조회 404
   - test_expired_link_returns_gone — 만료 링크 → 410
   - test_message_range_filter — from/to 지정 시 범위 내 messages만 반환
   - 검증: pytest 통과

5. validate.sh 전체 통과

## 5. 검증 계획

- `pytest tests/test_share.py` — 5건 통과
- `./validate.sh` 전체 통과
- curl 테스트:
  - POST 생성 → share_token 확인
  - GET /shared/{token} → 인증 없이 messages 확인
  - GET /shared/{token}?from=1&to=3 → 범위 필터링 확인
  - DELETE 해제 → 204
  - 해제 후 GET → 404

## 6. Metis/Momus 리뷰

- 001-metis-reject: Phase 충돌 / DELETE 정책 / message_range
- 002-momus-reject: Phase 불일치 / thread_id FK 미존재
- 본 수정에서 전부 반영

## 7. 최종 결정

APPROVED (Metis 003-okay + Momus 004-approved, 2026-04-30)
