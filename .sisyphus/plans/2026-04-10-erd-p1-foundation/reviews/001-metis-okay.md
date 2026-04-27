# Review 001 — Metis (self-bootstrap)

> 다음 plan부터 진짜 metis 서브에이전트 호출 (Claude Code 재시작 후).

## 검토자

metis (self-bootstrap)

## 검토 일시

2026-04-10

## 검토 대상

../plan.md

## 판정

okay

## 근거 — 6 영역 분석

### 갭 (Gap)

- ✅ 영향 범위가 *5 테이블 변경*으로 명확히 한정. 후속 plan으로 분리할 7 테이블이 명시됨.
- ⚠️ **누락 가능성 1**: ERD §FK 표 (Table 14)에서 conversations.user_id의 ON DELETE는 CASCADE로 명시. 실제 현재 DB는 SET NULL. 본 plan은 ERD 따라 CASCADE로 재생성. 단, *왜 CASCADE인가*에 대한 설명은 없음 — 사용자 탈퇴 시 대화 같이 삭제하는 의도가 맞는지 PM 확인 권장.
- ⚠️ **누락 가능성 2**: ERD §4.10 shared_links의 from_message_id/to_message_id가 messages.message_id를 참조하지만, 본 plan은 shared_links를 다루지 않음. 즉 messages.message_id 만들면 future-proof하지만, 후속 plan에서 messages 데이터가 들어간 *후*에 FK를 추가하면 정합 어려움. 권장: 후속 plan에서 shared_links 신규 시 ALTER ADD CONSTRAINT.
- ⚠️ **누락 가능성 3**: `init_db.sql` 동기화가 미루어짐. 신규 팀원이 zero-state에서 셋업할 때 init_db.sql이 ERD와 안 맞으면 본 마이그레이션이 적용 안 된 상태가 됨. → 후속 plan과 함께 정리하되, 본 plan에 그 사실을 명확히.

### 숨은 의도

- 사용자 표면 요청: "기획 기준대로 가". 진짜 목표: **ERD 권위를 코드/DB가 강제 따르는 상태**. plan은 이를 정확히 반영 (현 DB의 잘못된 UUID PK를 BIGINT로 되돌림 + 누락 컬럼 모두 추가 + last_message 같은 ERD 외 폐기).
- 사용자가 langgraph_checkpoints를 docx에 명시한 것은 *팀 가시성*을 위해서. 본 plan은 ERD 명세대로 사전 생성하되 라이브러리 충돌 시 양보하는 위험 관리 포함.

### AI Slop

- 없음. 22 atomic step 모두 단일 책임 + 검증 가능.
- CHECK 제약 (`auth_provider IN ('email','google')`, `messages_role_chk`) 추가는 ERD 명세에 *명시는 안 됐지만* 의미적으로 자연스러움. 권위 위반 아님 (ERD가 금지한 적 없음).

### 오버엔지니어링

- 없음. **부록의 "안 하는 것" 6건**이 명확. places PK 통일, 후속 5테이블, init_db.sql 동기화, 라이브러리 양보 모두 의식적 미루기.
- 단 `users_email_or_google_chk` CHECK가 다소 복잡 — 19 불변식 #15 (이중 인증) 강제. 합리적, 유지.

### 19 불변식 위반 위험

- ✅ 본 plan은 *오히려 정합*을 만든다. PK 이원화(#1), append-only(#3), 인증 매트릭스(#15), 대화 이력 이원화(#14) 모두 정확히 적용.
- 단 한 가지 fragility: **post_edit_python.sh의 append-only SQL 가드**가 messages, langgraph_checkpoints만 인식 (population_stats, feedback도 인식하지만 본 plan 범위 외). 가드 패턴 확인 필요 — 본 plan에서 메시지 INSERT 코드 작성하지 않으므로 즉시 영향 없음.

### 검증 가능성

- ✅ 작업 #18 (langgraph smoke test), #19 (postgres MCP 재실측), #20 (row count), #21 (validate.sh) 모두 객관적.
- ⚠️ 작업 #2 (pg_dump 백업)은 사용자 권한 필요. 본 plan은 사용자 manual 단계로 표시. 백업이 안 되면 #5 ALTER가 위험. **권장**: 사용자가 백업 완료 confirm 후에만 #5 진입.

## 요구 수정사항

1. (권장) ON DELETE CASCADE 의도 PM 확인 — conversations.user_id가 CASCADE면 사용자 탈퇴 = 대화/메시지/체크포인트 모두 삭제. ERD가 그렇게 명시했으니 따르되, 사용자 동의 한 줄 받기.
2. (권장) 작업 #2 pg_dump 백업이 실패 가능성 있으므로, 작업 #5 ALTER 진입 전 별도 confirm step 추가 — 본 plan 본문 §A에 추가하는 게 좋음. 또는 실행 단계에서 메인 Claude가 챙김.
3. (강제 아님) `init_db.sql` 동기화가 후속 plan에서 같이 다뤄질 거라는 사실을 본 plan §부록에 명시 — 이미 부록에 있음. ✅

## 다음 액션

- okay 판정 → Momus 검토 호출
- 권장 1, 2는 실행 단계에서 메인 Claude가 흡수
