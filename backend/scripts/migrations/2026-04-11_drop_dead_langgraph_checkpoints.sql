-- ============================================================================
-- 2026-04-11: Drop dead langgraph_checkpoints table.
-- ============================================================================
--
-- Why:
--   plan #1 (.sisyphus/plans/2026-04-10-erd-p1-foundation/) step 18 smoke test
--   결과, ERD §4.12 명세대로 사전 생성한 langgraph_checkpoints 테이블이
--   langgraph-checkpoint-postgres 2.0.8 라이브러리에 의해 사용되지 않는 것이
--   확인됨. 라이브러리는 자체 4 테이블을 만들어 사용한다:
--     - checkpoints              (실제 체크포인트 저장)
--     - checkpoint_writes        (write 로그)
--     - checkpoint_blobs         (BLOB 저장소)
--     - checkpoint_migrations    (라이브러리 자체 마이그레이션 추적, 9 row 적재됨)
--
--   우리 langgraph_checkpoints는 0 row + 라이브러리 미사용 = dead table.
--   유지 시 신규 팀원이 ERD ↔ 실제 동작 괴리에 혼란.
--
-- Authority:
--   - .sisyphus/plans/2026-04-10-erd-p1-foundation/plan.md §E "risk fallback"
--     명시: "충돌 시 본 테이블 DROP + 라이브러리에 양보"
--   - 사용자 결정 (2026-04-11): 옵션 A (DROP), 시점 가 (즉시)
--
-- Authorized by: 이정 (PM, BE 리드) — 2026-04-11
--
-- Reversibility: 0 row dead table. 데이터 손실 0. CASCADE는 안전망 (다른 테이블이
--                참조하지 않는 게 정상 — conversations.thread_id를 FK로 갖지 않음).
--
-- Followup (별도 작업 예약):
--   - ERD docx §4.12 명세를 라이브러리 실제 4 테이블로 정정
--   - "라이브러리 자동 관리, 수동 개입 금지" 비고 강화
--   - ERD_v6.1_to_v6.2_변경사항.md §4 (langgraph_checkpoints) 섹션 갱신
--   - 처리 시점: plan #2 (erd-audit-feedback) 또는 별도 ERD 정정 plan
--
-- ============================================================================

BEGIN;

DROP TABLE IF EXISTS langgraph_checkpoints CASCADE;

COMMIT;
