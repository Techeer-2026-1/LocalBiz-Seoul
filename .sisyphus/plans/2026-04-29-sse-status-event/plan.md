# SSE 처리 상태 표시 — event: status 노드 전환 알림

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: COMPLETE
- 최종 결정: APPROVED → COMPLETE (2026-04-29)

## 1. 요구사항

LangGraph 노드 전환 시마다 `event: status` SSE 이벤트를 전송하여 FE에 진행 상태를 표시한다.
기획서 §4.5: "노드 전환 시마다 SSE로 event: status 이벤트 전송. text_stream 시작 시 로딩 해제."

예시:
```text
event: status  → {"type": "status", "message": "의도를 분석하고 있어요...", "node": "intent_router"}
event: intent  → ...
event: status  → {"type": "status", "message": "답변을 생성하고 있어요...", "node": "general"}
event: text_stream → ...
event: done    → ...
```

status는 SSE 제어 이벤트 — messages.blocks에 저장하지 않음 (불변식 #10 16종 콘텐츠 블록 외).

## 2. 영향 범위

- 수정 파일:
  - `backend/src/api/sse.py` — astream 루프에서 노드 전환 시 status 이벤트 yield
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음 (status는 제어 이벤트, 콘텐츠 블록 아님)
- FE 영향: 로딩 UI 표시 가능

## 3. 19 불변식 체크리스트

- [x] PK 이원화 — 해당 없음
- [x] append-only — 해당 없음 (status는 DB 미저장)
- [x] SSE 이벤트 타입 16종 — status는 제어 이벤트, 16종 외
- [x] 블록 순서 — status는 콘텐츠 블록 사이에 삽입되지만 블록 순서 검증에서 제외
- [x] 나머지 불변식 — 해당 없음

## 4. 작업 순서 (Atomic step)

1. `backend/src/api/sse.py` 수정
   - astream 루프에서 `_node_name` 기준으로 노드별 status 메시지 매핑
   - response_blocks 처리 전에 `format_status_event()` yield
   - status 이벤트는 assistant_blocks에 추가하지 않음 (DB 미저장)

2. validate.sh 통과 + curl 테스트

## 5. 검증 계획

- `./validate.sh` 통과
- curl 테스트: status 이벤트가 intent/text_stream 앞에 출현 확인

## 6. Metis/Momus 리뷰

- 단일 파일, 5줄 이내 변경. 리뷰 필요 시 수행.

## 7. 최종 결정

APPROVED (2026-04-29, 단일 파일 소규모 변경)
