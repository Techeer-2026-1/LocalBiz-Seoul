-- ============================================================================
-- 2026-04-12: ERD ETL Blockers — administrative_districts + population_stats
-- ============================================================================
--
-- File:      backend/scripts/migrations/2026-04-12_erd_etl_blockers.sql
-- Plan:      .sisyphus/plans/2026-04-12-erd-etl-blockers/plan.md (APPROVED)
-- Authority:
--   - 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4.4 (administrative_districts)
--   - 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4.5 (population_stats)
--   - CLAUDE.md 19 데이터 모델 불변식
--
-- Why:
--   plan #7 g3 step 6. §A 사전 실측(postgres MCP, 2026-04-12)에서 두 테이블의
--   전면 부재를 확인했고, 후속 ETL(행정동 427건 + 유동인구 시계열) 적재의
--   필수 선행 조건이다. 현재 ERD 권위 스키마와 실 DB의 핵심 블로커 2종.
--
-- 19 불변식 체크:
--   - #1 PK 이원화:
--       administrative_districts = 자연키 (adm_dong_code VARCHAR(20)) — OK
--       population_stats         = BIGINT AI (BIGSERIAL) — OK
--       (UUID는 places/events/place_analysis 전용)
--   - #3 append-only 4테이블:
--       population_stats 는 append-only. updated_at / is_deleted 칼럼 없음.
--       UPDATE/DELETE 금지 (post_edit hook이 SQL 차단).
--   - #5 의도적 비정규화 화이트리스트:
--       population_stats.raw_data JSONB — 화이트리스트에 등재된 raw_data 패턴.
--
-- PostGIS:
--   이미 설치됨 (places.geom / events.geom 사용 중). 본 파일에서
--   CREATE EXTENSION 은 의도적으로 생략.
--
-- Authorized by: 이정 (PM, BE 리드) — 2026-04-12
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/scripts/migrations/2026-04-12_erd_etl_blockers.sql
--
-- Rollback:
--   본 파일은 단일 트랜잭션(BEGIN/COMMIT). 중간 실패 시 전체 자동 ROLLBACK.
--   이미 COMMIT 된 이후 수동 롤백이 필요하면 FK 역순으로:
--       DROP TABLE population_stats;
--       DROP TABLE administrative_districts;
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Table 1: administrative_districts
--   ERD §4.4 — 서울 행정동 마스터. 자연키(adm_dong_code) 기반.
--   427건 적재 예정 (행정안전부 2025 기준).
-- ----------------------------------------------------------------------------
CREATE TABLE administrative_districts (
    adm_dong_code VARCHAR(20) PRIMARY KEY,
    adm_dong_name VARCHAR(50) NOT NULL,
    district      VARCHAR(50) NOT NULL,
    geom          geometry(MultiPolygon, 4326),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  administrative_districts             IS 'ERD §4.4 — 서울 행정동 마스터 (자연키). 본 plan에서 427건 적재.';
COMMENT ON COLUMN administrative_districts.adm_dong_code IS '행정동 코드 (자연키, 불변식 #1 마스터 예외).';
COMMENT ON COLUMN administrative_districts.geom        IS 'MultiPolygon 4326. NULL 허용 — 후속 admin-code-reconcile 이 geom 없는 선등록 가능성 대비 (Metis M1).';

CREATE INDEX idx_adm_districts_geom     ON administrative_districts USING GIST (geom);
CREATE INDEX idx_adm_districts_district ON administrative_districts (district);


-- ----------------------------------------------------------------------------
-- Table 2: population_stats
--   ERD §4.5 — 행정동 × 시간대 유동인구 시계열.
--   append-only — UPDATE/DELETE 금지, updated_at/is_deleted 없음 (불변식 #3).
-- ----------------------------------------------------------------------------
CREATE TABLE population_stats (
    id            BIGSERIAL PRIMARY KEY,
    base_date     DATE NOT NULL,
    time_slot     SMALLINT NOT NULL CHECK (time_slot BETWEEN 0 AND 23),
    adm_dong_code VARCHAR(20) NOT NULL
                  REFERENCES administrative_districts(adm_dong_code)
                  ON DELETE RESTRICT,
    total_pop     INTEGER NOT NULL DEFAULT 0,
    raw_data      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  population_stats              IS 'ERD §4.5 — 유동인구 시계열. append-only (불변식 #3), UPDATE/DELETE 금지.';
COMMENT ON COLUMN population_stats.time_slot    IS '0-23시 정시 슬롯 (SMALLINT CHECK).';
COMMENT ON COLUMN population_stats.raw_data     IS '의도적 비정규화 화이트리스트 (불변식 #5) — 원천 수급 JSON 보존.';
COMMENT ON COLUMN population_stats.adm_dong_code IS 'FK → administrative_districts. ON DELETE RESTRICT (append-only 보호).';

CREATE INDEX idx_pop_stats_adm_time   ON population_stats (adm_dong_code, base_date, time_slot);
CREATE INDEX idx_pop_stats_base_date  ON population_stats (base_date);

COMMIT;

-- ============================================================================
-- End of migration.
-- 실패 시: 위 BEGIN/COMMIT 범위 전체 자동 ROLLBACK (psql -v ON_ERROR_STOP=1).
-- 수동 롤백 (COMMIT 이후): DROP TABLE population_stats; DROP TABLE administrative_districts;
-- ============================================================================
