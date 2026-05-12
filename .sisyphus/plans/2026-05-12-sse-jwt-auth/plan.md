# SSE 핸들러 JWT 인증 적용 — user_id 불일치 버그 수정

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-12
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done

## 1. 요구사항

SSE 핸들러(`GET /api/v1/chat/stream`)가 JWT `token` 파라미터를 받지만 파싱하지 않고
항상 seed `user_id=1`로 conversation/message를 저장함.
이후 `GET /api/v1/chats` 등이 JWT에서 추출한 실제 user_id로 조회하므로 결과가 빈 배열/404.

**수정**: `token` query parameter를 `decode_access_token()`으로 파싱 → 실제 user_id 사용.
`_ensure_seed_user()` 호출 제거. 토큰 누락/무효 시 SSE error 이벤트 전송.

## 2. 영향 범위

- 수정 파일:
  - `backend/src/api/sse.py` — token 파싱 + user_id 추출, `_ensure_seed_user` 호출 제거
  - `backend/tests/test_sse.py` — 테스트에 token/user_id mock 반영 (있는 경우)
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 해당 없음
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — messages INSERT 유지, UPDATE/DELETE 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 기존 $1/$2 유지
- [x] Optional[str] 사용 — 기존 유지
- [x] SSE 이벤트 타입 16종 한도 준수 — 기존 error 이벤트 재사용
- [x] intent별 블록 순서 준수 — 변경 없음
- [x] 공통 쿼리 전처리 경유 — 변경 없음
- [x] 행사 검색 DB 우선 — 해당 없음
- [x] 대화 이력 이원화 보존 — 변경 없음
- [x] 인증 매트릭스 준수 — JWT sub → user_id 사용 (불변식 #15 정합)
- [x] 북마크 = 대화 위치 패러다임 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — SSE는 인증 필수 (우회 대상 아님)
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — 인증 매트릭스 준수

## 4. 작업 순서 (Atomic step)

1. `sse.py` 수정 — `event_generator()` 시작부에서 token 파싱:
   - `token` 없으면 → error 이벤트 + done(error) + return
   - `decode_access_token(token)` 실패 → error 이벤트 + done(error) + return
   - 성공 → `user_id = int(payload["sub"])`
   - `_ensure_seed_user(pool)` 호출 → `user_id` 직접 사용으로 교체
2. 기존 테스트 수정 — token/user_id mock 반영
3. 검증 — validate.sh (ruff/pyright/pytest)

## 5. 검증 계획

- validate.sh 통과
- 수동 시나리오: FE 이슈 재현 절차(curl) 반복 → thread/message 정상 저장 확인

## 6. 최종 결정

APPROVED
