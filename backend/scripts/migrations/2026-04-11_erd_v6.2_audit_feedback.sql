-- ============================================================================
-- 2026-04-11: ERD v6.2 Audit & Feedback Migration
-- ============================================================================
--
-- Why:
--   plan #1 (erd-p1-foundation)이 P1 영속화 5 테이블을 적용한 후 잔여 작업.
--   ERD v6.2 권위 (`기획/ERD_v6.1_to_v6.2_변경사항.md`)와 실 DB의 **3 테이블**
--   불일치를 정합 + 팀 피드백 4건 중 DB 변경분 처리:
--
--   1. place_analysis (4건):
--      a) google_place_id 컬럼 제거 — 팀 피드백 #3 + 불변식 #5 회복
--         (place_analysis는 비정규화 4건 목록에 google_place_id 없음)
--      b) score_taste/score_service rename → score_satisfaction/score_expertise
--         — 불변식 #6 (6 지표 고정) 회복
--      c) place_id uuid → varchar(36) — 불변식 #1 PK 이원화 정합 (places와 통일)
--      d) FK 신설 → places (UNIQUE 1:1, ON DELETE CASCADE) — ERD §FK Table 14
--
--   2. places.last_modified DROP — ERD §4.1에 존재하지 않는 legacy 컬럼
--
--   3. events 컬럼 추가 — ERD §4.2 명세에 있는 updated_at, is_deleted
--
-- Authority:
--   - 기획/ERD_v6.1_to_v6.2_변경사항.md (v6.2 권위)
--   - 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4.1/§4.2/§4.3
--   - .sisyphus/plans/2026-04-11-erd-audit-feedback/plan.md (본 plan, APPROVED)
--
-- Authorized by: 이정 (PM, BE 리드) — 2026-04-11
--   - place_analysis 17 row orphan: 옵션 A (DROP), trace log 백업
--   - 데이터 보존 정책: orphan/이상치는 보존 없이 DROP, ETL 재적재로 복원
--   - CASCADE 정책: ERD §FK Table 14 명시대로 (장소 삭제 → 분석 자동 삭제)
--
-- Reversibility:
--   - place_analysis 17 row DELETE: trace log
--     (~/Desktop/anyway-erd-audit-2026-04-11.txt) 에 백업 보존.
--     batch_review_analysis.py 재실행으로 재생성 가능 (place_id 정확 매핑은
--     별도 plan 2026-04-12-etl-place-analysis-rebuild에서 처리).
--   - place_id uuid → varchar(36) ALTER USING ::text: 0 row 후 안전.
--   - DROP COLUMN google_place_id: 컬럼 데이터 손실. 어차피 PoC.
--   - RENAME COLUMN: 데이터 보존, 컬럼 이름만 변경.
--   - FK ADD CONSTRAINT: 0 row이라 검증 안 거침.
--   - places DROP COLUMN last_modified: 53만 row의 해당 컬럼 데이터 손실.
--     ERD에 없는 legacy. ETL 재실행 시 사라짐.
--   - events ADD COLUMN: 7301 row 모두 NOW() / FALSE 일괄 적용. 손실 0.
--   - 전체 BEGIN/COMMIT: 어떤 단계 실패 시 ROLLBACK.
--
-- Pre-state (2026-04-11 postgres MCP 측정):
--   public.places          531,183 rows (PK varchar(36), last_modified 컬럼 존재)
--   public.events            7,301 rows (PK varchar(36), updated_at/is_deleted 부재)
--   public.place_analysis       17 rows (PK varchar(36), place_id uuid,
--                                        google_place_id/score_taste/score_service 존재,
--                                        모두 places PK 매칭 0건 = orphan)
--
-- 19 불변식 회복:
--   #1 PK 이원화: place_analysis.place_id를 varchar(36)으로 통일.
--   #5 비정규화 4건: google_place_id 제거로 4건 한도 회복.
--   #6 6 지표 고정: score_taste/service → score_satisfaction/expertise rename.
--   #19 기획 우선: ERD v6.2 권위 그대로 따름.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- §B+§C. place_analysis 정합 (4 변경 묶음)
-- ============================================================================

-- 1. orphan 17 row DELETE (사용자 정책: 데이터 문제 시 보존 없이 DROP)
--    trace log 백업: ~/Desktop/anyway-erd-audit-2026-04-11.txt step 4+5 표
DELETE FROM place_analysis;

-- 2. place_id uuid → varchar(36) (이제 0 row, 변환 안전)
--    plan #1에서 analysis_id만 변환하고 place_id는 누락. 본 plan에서 정정.
ALTER TABLE place_analysis
    ALTER COLUMN place_id TYPE VARCHAR(36) USING place_id::text;

-- 3. google_place_id 컬럼 DROP (불변식 #5 회복)
--    팀 피드백 #3: 장소 분석/장소 테이블 google_place_id 중복.
--    ERD Table 15 비정규화 허용 목록에 place_analysis.place_name만 있고
--    google_place_id는 빠짐. 본 plan에서 모순 해소.
ALTER TABLE place_analysis DROP COLUMN google_place_id;

-- 4. score_taste → score_satisfaction (불변식 #6)
ALTER TABLE place_analysis RENAME COLUMN score_taste TO score_satisfaction;

-- 5. score_service → score_expertise (불변식 #6)
--    'expertise'(전문성)는 카테고리별로 LLM이 해석:
--    카페=음료 품질, 공원=경관/편의시설, 도서관=장서/프로그램 등
ALTER TABLE place_analysis RENAME COLUMN score_service TO score_expertise;

-- 6. UNIQUE 제약 추가 (FK 신설 사전 + 1:1 관계 강제)
--    ERD §4.3: place_analysis는 장소당 1건 (1:1).
ALTER TABLE place_analysis
    ADD CONSTRAINT place_analysis_place_id_unique UNIQUE (place_id);

-- 7. FK 신설 → places (ON DELETE CASCADE)
--    ERD §FK Table 14 권위. places 삭제 시 분석 자동 삭제.
--    새 데이터 정책 (DROP freely)과 결합: places 일괄 DROP 시
--    place_analysis도 자동 cleanup. 의도된 부수 효과.
ALTER TABLE place_analysis
    ADD CONSTRAINT place_analysis_place_id_fk
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE;


-- ============================================================================
-- §C. places.last_modified DROP
-- ============================================================================
-- ERD §4.1에 존재하지 않는 legacy 컬럼. ETL 재실행 시 사라질 운명이지만
-- 본 plan에서 명시적 정리.
ALTER TABLE places DROP COLUMN last_modified;


-- ============================================================================
-- §D. events 컬럼 추가
-- ============================================================================
-- ERD §4.2 events 테이블 명세에 updated_at, is_deleted 존재.
-- 현 DB에 부재. 본 plan에서 추가.
--
-- 7301 row에 NOW() / FALSE 일괄 적용. updated_at의 의미("마지막 수정")는
-- 적재 시각과 미스매치이지만, 향후 update 시점부터 정확해짐.

ALTER TABLE events
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE events
    ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;


COMMIT;

-- ============================================================================
-- 마이그레이션 끝
--
-- 검증 (별도 step 9~11):
--   - postgres MCP information_schema로 6개 컬럼 변경 확인
--   - row count: places=531183 / events=7301 / place_analysis=0 (의도)
--   - FK CASCADE smoke test (place_analysis ↔ places)
-- ============================================================================
