# SSE 응답 중단 (Interrupt) — cancelled done + 부분 저장

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: COMPLETE
- 최종 결정: APPROVED → COMPLETE (2026-04-29)

## 1. 요구사항

클라이언트 disconnect 시:
1. `event: done {status: "cancelled"}` 전송 시도
2. 부분 응답이 있으면 assistant 메시지로 저장 (append-only)
3. LangGraph 파이프라인 중단 — **best-effort**: async iterator 소비 중단 (`break`). LangGraph/Gemini 백엔드의 진행 중인 요청은 자체적으로 완료될 수 있음. 확정적 취소가 아닌 리소스 절약 최선 노력.

기획서: "ESC 키 또는 중단 버튼 클릭 시 FE가 abort() → 서버가 request.is_disconnected()로 감지 → 파이프라인 중단"

참고: `partial` 필드는 DoneBlock 스키마에 없으며, 기획서 §4.5의 done 블록 정의에도 없음. `status: "cancelled"`로 FE가 부분 응답임을 판단할 수 있으므로 별도 필드 추가하지 않음.

## 2. 영향 범위

- 수정: `backend/src/api/sse.py` — disconnect 처리 로직 개선
- DB: messages INSERT (부분 응답 저장, append-only 준수)
- DoneBlock 스키마 변경: 없음

## 3. 19 불변식 체크리스트

- [x] append-only — INSERT only
- [x] SSE 16종 — done은 기존 블록, 스키마 변경 없음
- [x] asyncpg 바인딩 — $1, $2, $3
- [x] 대화 이력 이원화 (#14) — checkpointer=None, messages만 INSERT. 기존 패턴 유지.
- [x] 나머지 — 해당 없음

## 4. 작업 순서 (Atomic step)

1. `sse.py` — astream 루프의 `return` 2곳을 `cancelled = True; break` 패턴으로 교체
   - 검증: ruff + pyright 통과

2. `sse.py` — astream 루프 종료 후 cancelled 시 `format_done_event(status="cancelled")` yield
   - 검증: ruff 통과

3. `sse.py` — 부분 응답(`assistant_blocks`)이 있으면 `_insert_message()` 호출
   - 검증: ruff 통과

4. validate.sh 전체 통과

5. 수동 테스트: curl로 SSE 스트림 시작 → Ctrl+C로 disconnect → 서버 로그에서 "Client disconnected" 확인

## 5. 검증 계획

- `./validate.sh` 통과
- curl disconnect 시나리오: `curl -N ... &` → `kill %1` → 서버 로그 확인
- DB 확인: disconnect 후 messages 테이블에 부분 응답 저장 여부

## 6. Metis/Momus 리뷰

- 001-metis-reject: partial 필드 / 중단 의미 / step 분해 → 본 수정에서 반영

## 7. 최종 결정

PENDING (Metis 재검토 필요)
