-- ============================================================================
-- 2026-04-12: Admin Code Aliases — 9 구 행정동 코드 → 11 신 코드 매핑
-- ============================================================================
--
-- File:      backend/scripts/migrations/2026-04-12_admin_code_aliases.sql
-- Plan:      .sisyphus/plans/2026-04-13-admin-code-reconcile/plan.md
-- Authority: plan #7 issues.md 2026-04-12 mismatch 엔트리 + 메인 Claude 분석
-- Why:
--   plan #7에서 population_stats 적재 시 9개 구 행정동 코드(CSV 202603)가
--   admin_districts(ver20260201)에 부재해 6,048 row가 skip 되었다. 본 마이그레이션은
--   구→신 코드 매핑 테이블을 생성해 혼잡도 intent가 구 코드로도 질의할 수 있게 한다.
--   population_stats 자체는 건드리지 않는다 (1→N 분할 시 인구 배분은 추정 오염).
--
-- 매핑 근거 (메인 Claude 자체 분석, E 모드 autonomous):
--   - 자치구 필터 교차검증 + naming + 숫자 근접성 (단조 + 소폭 offset)
--   - confidence=high 11건 (authoritative 출처 0건, 행안부 공식 변경이력은 future work)
--   - 11530800 항동(구로구)은 완전 신설 → old_code 없음 → 본 테이블에 엔트리 없음
--
-- 19 불변식 체크:
--   - #1: aliases는 marker 테이블, 복합 자연키 (old_code, new_code) —
--         administrative_districts 자연키 관례 따름
--   - #3: append-only 4테이블 외, 정정 가능 (updated_at 없음, is_deleted 없음)
--   - #18: LocalBiz Phase 라벨 (plan #7 후속)
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/scripts/migrations/2026-04-12_admin_code_aliases.sql
--
-- Rollback:
--   단일 트랜잭션(BEGIN/COMMIT). 실패 시 전체 자동 ROLLBACK.
--   COMMIT 이후 수동 롤백: DROP TABLE admin_code_aliases;
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Table: admin_code_aliases
-- ----------------------------------------------------------------------------
CREATE TABLE admin_code_aliases (
    old_code    VARCHAR(20) NOT NULL,
    new_code    VARCHAR(20) NOT NULL
                REFERENCES administrative_districts(adm_dong_code) ON DELETE RESTRICT,
    change_type VARCHAR(20) NOT NULL
                CHECK (change_type IN ('rename', 'split', 'merge', 'new')),
    change_note TEXT,
    confidence  VARCHAR(10) NOT NULL
                CHECK (confidence IN ('authoritative', 'high', 'medium', 'low')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (old_code, new_code)
);

COMMENT ON TABLE  admin_code_aliases             IS '구 행정동 코드 → 신 코드 매핑 (plan #7 mismatch 해소). 1→N 다대다 허용.';
COMMENT ON COLUMN admin_code_aliases.old_code    IS 'CSV 202603 등 구 데이터에서 사용되던 행정동 코드 (admin_districts에 부재 가능).';
COMMENT ON COLUMN admin_code_aliases.new_code    IS '현재 admin_districts에 존재하는 신 코드. FK RESTRICT.';
COMMENT ON COLUMN admin_code_aliases.change_type IS 'rename=1:1 재코딩 / split=1:N 분할 / merge=N:1 통합 / new=신설(old_code 없는 경우 별도 방식 필요)';
COMMENT ON COLUMN admin_code_aliases.confidence  IS 'authoritative=행안부 공식 / high=naming+numeric 분석 / medium=naming만 / low=추측';
COMMENT ON COLUMN admin_code_aliases.change_note IS '자유 서술 근거. 추론 근거 또는 공식 출처 URL.';

CREATE INDEX idx_admin_code_aliases_new ON admin_code_aliases(new_code);


-- ----------------------------------------------------------------------------
-- Seed: 9 old_code → 11 new_code mappings (plan #7 issues.md 해소)
-- ----------------------------------------------------------------------------

-- 동대문구: 11230536 (구 통합) → 신설동(11230515) + 용두동(11230533) 1→2 분할
INSERT INTO admin_code_aliases (old_code, new_code, change_type, confidence, change_note) VALUES
('11230536', '11230515', 'split', 'high', 'plan #7 자체 분석: 동대문구 CSV-only 1건 vs admin-only 2건(신설동·용두동), 1→2 분할 추정'),
('11230536', '11230533', 'split', 'high', 'plan #7 자체 분석: 동대문구 CSV-only 1건 vs admin-only 2건(신설동·용두동), 1→2 분할 추정');

-- 강북구: 6개 구 코드 → 6개 신 코드 1:1 rename (번1/2/3동 + 수유1/2/3동)
-- 단조 순서 + 숫자 근접 (+2~+5) 패턴으로 결정
INSERT INTO admin_code_aliases (old_code, new_code, change_type, confidence, change_note) VALUES
('11305590', '11305595', 'rename', 'high', 'plan #7 분석: 강북구 번1동, 단조 근접 (+5)'),
('11305600', '11305603', 'rename', 'high', 'plan #7 분석: 강북구 번2동, 단조 근접 (+3)'),
('11305606', '11305608', 'rename', 'high', 'plan #7 분석: 강북구 번3동, 단조 근접 (+2)'),
('11305610', '11305615', 'rename', 'high', 'plan #7 분석: 강북구 수유1동, 단조 근접 (+5)'),
('11305620', '11305625', 'rename', 'high', 'plan #7 분석: 강북구 수유2동, 단조 근접 (+5)'),
('11305630', '11305635', 'rename', 'high', 'plan #7 분석: 강북구 수유3동, 단조 근접 (+5)');

-- 강남구: 11680740 (구) → 11680675 개포3동 1:1 rename
-- 강남구 유일한 1:1 mismatch
INSERT INTO admin_code_aliases (old_code, new_code, change_type, confidence, change_note) VALUES
('11680740', '11680675', 'rename', 'high', 'plan #7 분석: 강남구 유일 1:1, 개포3동 신설');

-- 강동구: 11740520 (구 상일동) → 11740525 상일1동 + 11740526 상일2동 1→2 분할
INSERT INTO admin_code_aliases (old_code, new_code, change_type, confidence, change_note) VALUES
('11740520', '11740525', 'split', 'high', 'plan #7 분석: 강동구 상일동 1→2 분할(상일1동)'),
('11740520', '11740526', 'split', 'high', 'plan #7 분석: 강동구 상일동 1→2 분할(상일2동)');


-- ----------------------------------------------------------------------------
-- Assertion (migration 내부, 실패 시 트랜잭션 ROLLBACK)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    cnt INT;
    old_cnt INT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM admin_code_aliases;
    IF cnt <> 11 THEN
        RAISE EXCEPTION 'admin_code_aliases insert 실패: 기대 11, 실측 %', cnt;
    END IF;

    SELECT COUNT(DISTINCT old_code) INTO old_cnt FROM admin_code_aliases;
    IF old_cnt <> 9 THEN
        RAISE EXCEPTION 'admin_code_aliases DISTINCT old_code 불일치: 기대 9, 실측 %', old_cnt;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- End of migration.
-- 실패 시: 위 BEGIN/COMMIT 범위 전체 자동 ROLLBACK (psql -v ON_ERROR_STOP=1).
-- 수동 롤백 (COMMIT 이후): DROP TABLE admin_code_aliases;
-- ============================================================================
