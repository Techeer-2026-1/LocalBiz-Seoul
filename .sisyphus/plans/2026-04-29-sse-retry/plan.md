# SSE 응답 재생성 (Retry)

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: approved
- 최종 결정: APPROVED (Metis 001-okay + Momus 003-okay, 2026-04-29)

## 1. 요구사항

기획서: "다시 생성 버튼 클릭 시 마지막 assistant 메시지를 삭제하고 동일 query로 새 SSE 스트림 재요청."

### 불변식 #3 충돌 해소

messages는 append-only 테이블 (DELETE 금지). 따라서:
- 기존 assistant 메시지는 유지 (append-only 준수)
- 새 assistant 메시지를 추가 INSERT
- FE가 `retry=true` 파라미터를 보내면 서버가 동일 thread + query로 새 SSE 스트림 실행
- FE는 마지막 assistant 블록을 시각적으로 교체 (DB에는 둘 다 존재)

### retry 방어 로직

retry=true 시 해당 thread에 user 메시지가 존재하는지 확인:
- 존재하면 → user INSERT 생략 + 정상 astream 실행
- 미존재하면 → retry=false로 fallback (일반 요청처럼 user INSERT 포함)

### 동작 흐름

```text
GET /api/v1/chat/stream?thread_id=xxx&query=안녕&retry=true
  → thread에 user 메시지 존재 확인
    → 있으면: user INSERT 생략 → LangGraph astream() → assistant INSERT
    → 없으면: fallback → user INSERT → LangGraph astream() → assistant INSERT
```

## 2. 영향 범위

- 수정 파일:
  - `backend/src/api/sse.py` — retry 파라미터 + user 존재 확인 + INSERT 분기
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종: 변경 없음
- FE 영향: retry=true 쿼리 파라미터 전송 + 마지막 assistant 시각적 교체. 이력 조회 시 superseded assistant 렌더링 규칙은 FE 후속 정의 필요.

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — messages BIGSERIAL, 해당 없음
- [x] #2 PG↔OS 동기화 — 벡터 인덱스 미사용
- [x] #3 append-only — **핵심**: DELETE 없음, INSERT만. 기존 메시지 유지.
- [x] #4 소프트 삭제 — messages는 append-only, 소프트 삭제 대상 아님
- [x] #5 비정규화 3건 — 신규 비정규화 없음
- [x] #6 6 지표 고정 — 해당 없음
- [x] #7 임베딩 768d — 해당 없음
- [x] #8 asyncpg 바인딩 — 기존 `_insert_message()` 재사용 ($1,$2,$3)
- [x] #9 Optional[str] — str | None 미사용
- [x] #10 SSE 16종 — 변경 없음
- [x] #11 블록 순서 — retry도 동일 시퀀스 (intent → text_stream → done)
- [x] #12 공통 쿼리 전처리 — retry도 동일 LangGraph 흐름 경유
- [x] #13 행사 DB 우선 — 해당 없음
- [x] #14 대화 이력 이원화 — checkpointer=None 기존 패턴
- [x] #15 이중 인증 — seed user placeholder, 해당 없음
- [x] #16 북마크 — P2 범위
- [x] #17 공유링크 — P2 범위
- [x] #18 Phase 라벨 — P1 명시
- [x] #19 기획 문서 우선 — 기획서 "삭제" → append-only 대안으로 구현. APPROVED 후 기능 명세서 문구 정정 필요.

## 4. 작업 순서 (Atomic step)

1. `sse.py` — `chat_stream()` 파라미터에 `retry: bool = False` 추가
   - 검증: ruff 통과

2. `sse.py` — retry=true 시 user 메시지 존재 확인 + INSERT 분기
   - `pool.fetchrow("SELECT 1 FROM messages WHERE thread_id=$1 AND role='user' ORDER BY message_id DESC LIMIT 1", thread_id)`
   - 존재하면 user INSERT 생략, 미존재하면 fallback (일반 INSERT)
   - 검증: ruff + pyright 통과

3. validate.sh 전체 통과

4. 수동 테스트: curl retry=true → user 중복 없이 새 assistant 확인

## 5. 검증 계획

- `./validate.sh` 통과
- curl 정상: `?thread_id=x&query=안녕` → user + assistant INSERT
- curl retry: `?thread_id=x&query=안녕&retry=true` → assistant만 INSERT
- curl retry 미존재 thread: `?thread_id=new&query=안녕&retry=true` → fallback, user + assistant INSERT
- DB 확인: messages에 user 1건 + assistant 2건

## 6. Metis/Momus 리뷰

- 001-metis-okay, 002-momus-reject (방어 로직 / 체크리스트 / 테스트)

## 7. 최종 결정

PENDING
