# SSE 에러 처리 — error 블록 + recoverable 플래그

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: approved
- 최종 결정: APPROVED (Metis 002-okay + Momus 004-approved, 2026-04-29)

## 1. 요구사항

기획서: "API 실패/LLM 타임아웃 시 event: error 이벤트 전송. recoverable=true이면 '다시 시도' 버튼 표시."

현재 상태: 모든 예외를 `event: done {status: "error"}` 하나로 처리.
목표: 에러 종류별 분기 + `event: error` 블록 전송 + recoverable 플래그.

### 에러 시나리오 + 코드

| 시나리오 | code | recoverable | FE 동작 |
|---|---|---|---|
| Gemini API 실패 (분류/응답) | `GEMINI_API_ERROR` | true | "다시 시도" 버튼 |
| DB pool 미획득 | `DB_POOL_UNAVAILABLE` | false | 고정 에러 메시지 |
| 예상 못한 에러 | `INTERNAL_ERROR` | true | "다시 시도" 버튼 |

※ assistant INSERT 실패는 현재 로그만 (sse.py L295-298). 별도 error 블록 미전송 — 사용자 응답은 이미 스트리밍 완료 후이므로 FE UX 영향 없음. 후속 plan에서 필요 시 추가.

### SSE 이벤트 시퀀스 (에러 시)

```text
event: error → {"type": "error", "code": "GEMINI_API_ERROR", "message": "AI 응답 생성에 실패했습니다.", "recoverable": true}
event: done  → {"type": "done", "status": "error", "error_message": "AI 응답 생성에 실패했습니다."}
```

### error 블록 DB 저장 정책

- error 블록은 **SSE 전송만, DB 미저장**. 이유:
  - error는 일시적 상태이며 재시도 시 성공할 수 있음
  - pool 미획득 시 저장 자체가 불가능
  - 에러 로그(logger.exception)가 서버 측 기록 역할
- 부분 응답(assistant_blocks)은 기존 패턴대로 저장 시도

## 2. 영향 범위

- 수정 파일:
  - `backend/src/api/sse.py` — 에러 처리 분기 + error 블록 전송 + ErrorBlock import 추가
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종: error 블록 기존 정의 사용 (blocks.py ErrorBlock)
- FE 영향: `event: error`의 `recoverable` 필드로 "다시 시도" 버튼 표시 여부 결정

## 3. 19 불변식 체크리스트

- [x] PK 이원화 — 해당 없음
- [x] append-only — 에러 시에도 INSERT만 (부분 응답 저장). error 블록은 DB 미저장.
- [x] SSE 16종 — error는 기존 16종 중 하나
- [x] asyncpg 바인딩 — 기존 패턴 유지
- [x] Optional[str] — str | None 미사용
- [x] 대화 이력 이원화 (#14) — checkpointer=None 기존 패턴
- [x] 나머지 — 해당 없음

## 4. 작업 순서 (Atomic step)

1. `sse.py` — ErrorBlock import 추가
   - 검증: ruff 통과

2. `sse.py` — Gemini 스트리밍 실패 catch
   - `_stream_gemini()` 호출을 try/except로 감싸기
   - 실패 시: `event: error {code: GEMINI_API_ERROR, recoverable: true}` yield
   - expected output: `event: error → event: done(error)`
   - 검증: ruff 통과 + Gemini API 키 제거 후 서버 실행 → error 이벤트 확인

3. `sse.py` — DB pool 실패 분기
   - `get_pool()` 호출을 try/except RuntimeError로 감싸기
   - 실패 시: `event: error {code: DB_POOL_UNAVAILABLE, recoverable: false}` + done(error) yield
   - expected output: `event: error → event: done(error)`
   - 검증: ruff 통과

4. `sse.py` — 최외곽 except 개선
   - 기존 `done(error)`만 → `error 블록 + done(error)` 순서로 전송
   - code: `INTERNAL_ERROR`, recoverable: true
   - expected output: `event: error → event: done(error)`
   - 검증: ruff 통과

5. validate.sh 전체 통과

## 5. 검증 계획

- `./validate.sh` 통과
- Gemini 에러: API 키 제거 후 curl → `event: error {code: GEMINI_API_ERROR}` 확인
- DB 에러: DB 미연결 상태에서 curl → `event: error {code: DB_POOL_UNAVAILABLE}` 확인

## 6. Metis/Momus 리뷰

- 001-metis-reject: 에러 코드 / 저장 정책 / 용어 / 검증 → 본 수정에서 반영

## 7. 최종 결정

APPROVED (Metis 002-okay + Momus 004-approved, 2026-04-29)
