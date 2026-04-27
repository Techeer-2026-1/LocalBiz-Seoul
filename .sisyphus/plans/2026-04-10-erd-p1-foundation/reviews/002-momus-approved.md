# Review 002 — Momus (self-bootstrap)

> 다음 plan부터 진짜 momus 서브에이전트 호출.

## 검토자

momus (self-bootstrap)

## 검토 일시

2026-04-10

## 검토 대상

../plan.md, ./001-metis-okay.md

## 판정

approved

## 검토 전제 조건

- ✅ Metis okay 검토 (`001-metis-okay.md`) 존재.
- ✅ Metis 권장사항 3건 모두 *실행 단계 흡수 가능* 으로 명시.

## 근거 — fs 검증 결과

| 항목 | 검증 방법 | 결과 |
|---|---|---|
| ERD docx 권위 | `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` Table 7~13 본 plan과 컬럼 1:1 비교 | ✅ 일치 (users 9, conversations 7, messages 5, langgraph 6 — 모두 ERD대로) |
| 현 DB 실측 | postgres MCP information_schema | ✅ users(0), conversations(0), events(7301), place_analysis(17), places(531183) 확인됨 |
| FK 의존성 사전 확인 | `SELECT ... constraint_type='FOREIGN KEY'` | ✅ 단 1개 (conversations.user_id → users), 본 plan §C8 에서 명시적 DROP |
| 19 불변식 #1 (PK 이원화) | places(varchar 36)/events(→varchar 36)/place_analysis(→varchar 36) UUID, users/conversations/messages BIGINT | ✅ |
| 19 불변식 #3 (append-only) | messages, langgraph_checkpoints의 ERD 명세에 updated_at/is_deleted 없음 | ✅ 본 plan SQL에서 두 테이블 모두 누락 (의도) |
| 19 불변식 #14 (대화 이력 이원화) | messages (UI 영속) + langgraph_checkpoints (LLM 컨텍스트) 분리 | ✅ 두 테이블 별도 생성 |
| 19 불변식 #15 (인증 매트릭스) | `users_email_or_google_chk` CHECK 제약 | ✅ ERD §4.6 비고 정확히 강제 |
| Phase 라벨 | P1 (영속화) + Infra (정합) | ✅ |
| 작업 순서 atomic | 22 step 모두 단일 책임 + 단일 명령 | ✅ |
| 검증 계획 fs 가능성 | postgres MCP / langgraph smoke / row count / validate.sh | ✅ |
| 트랜잭션 안전 | §F15 마이그레이션 SQL은 BEGIN/COMMIT 명시 | ✅ |
| 백업 절차 | §A2 pg_dump (사용자 권한) | ⚠️ Metis 권장 #2 — 실행 단계 confirm 필요 |
| 라이브러리 호환 risk | §E14 + §G18 smoke test | ✅ risk 명시 + 양보 path 정의 |

## 결함

없음.

## Metis 권장사항 3건의 처리 책임

본 Momus는 다음을 메인 Claude에게 위임:
1. (실행 §B 직전) ON DELETE CASCADE 의도 PM 한 줄 확인 — conversations.user_id 가 CASCADE 면 사용자 탈퇴 시 대화 cascade. ERD §FK Table 14 권위, 따르는 게 정공.
2. (실행 §A 진입) pg_dump 백업 confirm — 사용자가 본인 자리에서 백업 완료 후에 §B5 ALTER 진입.
3. (이미 부록 명시) init_db.sql 동기화는 후속 plan에서.

## 부트스트랩 한계

- 본 리뷰는 momus 서브에이전트가 *Agent 도구로 호출되기 전* 메인 Claude 페르소나로 작성.
- 다음 plan부터 진짜 자율 사이클.

## 판정 근거

모든 fs 검증 통과 + ERD docx 권위 정확 매핑 + 19 불변식 위반 0 + 작업 순서 atomic + risk 명시 + Metis okay 통과.

→ **APPROVED**.

메인 Claude는 plan.md 마지막 줄을 `최종 결정: APPROVED` 로 갱신하고, 사용자에게 다음을 confirm 후 §A→§G 순차 실행:
1. ON DELETE CASCADE 의도 동의
2. pg_dump 백업 확인 (또는 본 작업 동안 사용자 manual)
