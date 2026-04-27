-- ============================================================================
-- 2026-04-12: Places Reclassify + Index Refactor
-- ============================================================================
--
-- File:      backend/scripts/migrations/2026-04-12_places_reclassify_and_index.sql
-- Plan:      .sisyphus/plans/2026-04-13-places-reclassify-and-index-refactor/plan.md
-- Authority: 기획/카테고리_분류표.md v0.1 §3/§4/§5 + EXPLAIN 실측 (322 ms 공간 검색 버그)
-- Why:
--   (1) places 531,183 row의 category='음식점' 단일값을 음식점/카페/주점 3분류로 분화
--       (분류표 v0.1 첫 강제 적용).
--   (2) 14 신규 카테고리 ETL 진입 전 인덱스 전략 강화:
--       - category btree + composite(category, district)
--       - GENERATED geography 컬럼 + GIST 인덱스 (geom::geography 캐스팅 안티패턴 해결)
--
-- 19 불변식 체크:
--   - #2 PG↔OS 동기화: places_vector OS 인덱스에 category 필드 있으면 재색인 필요
--                      (별도 plan으로 격리, plan.md §6 watch 항목).
--   - #3 append-only 4테이블: places는 목록 외, UPDATE 허용.
--   - #5 의도적 비정규화: geog는 geom의 type 변환 generated 컬럼, 비정규화 본질 아님.
--   - #8 파라미터 바인딩: 본 파일은 순수 SQL + 고정 enum 리스트, SQL injection 위험 0.
--   - #19 기획 우선: 분류표 v0.1 §3/§4/§5 verbatim.
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/scripts/migrations/2026-04-12_places_reclassify_and_index.sql
--
-- Rollback:
--   단일 트랜잭션. 실패 시 자동 ROLLBACK.
--   COMMIT 이후 수동 롤백:
--     DROP INDEX idx_places_geog, idx_places_cat_dist, idx_places_category;
--     ALTER TABLE places DROP COLUMN geog;
--     UPDATE places SET category='음식점' WHERE category IN ('카페','주점');
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Step 1: 카페 재분류 (기대 8,769 row)
-- ----------------------------------------------------------------------------
UPDATE places
   SET category = '카페',
       updated_at = NOW()
 WHERE sub_category IN (
     '까페',         -- 7,831
     '전통찻집',     -- 823
     '키즈카페',     -- 109
     '커피숍',       -- 4
     '다방',         -- 1
     '제과점영업'    -- 1 (사용자 결정: 베이커리는 카페)
 );


-- ----------------------------------------------------------------------------
-- Step 2: 주점 재분류 (기대 51,778 row)
-- ----------------------------------------------------------------------------
UPDATE places
   SET category = '주점',
       updated_at = NOW()
 WHERE sub_category IN (
     '호프/통닭',            -- 37,672
     '정종/대포집/소주방',   -- 13,077
     '감성주점',             -- 654
     '라이브카페',           -- 373 (사용자 결정: 카페 아닌 주점)
     '룸살롱',               -- 1
     '간이주점'              -- 1
 );
-- 음식점 default 유지: 31 sub_category (한식/분식/경양식/... + 빈 문자열 18 row)
--   → 470,636 row (531,183 - 8,769 - 51,778)


-- ----------------------------------------------------------------------------
-- Step 3: category btree 인덱스
--   14 카테고리 적재 후 "category IN (...)" 프리디케이트 최적화
-- ----------------------------------------------------------------------------
CREATE INDEX idx_places_category ON places(category);
COMMENT ON INDEX idx_places_category IS 'category 단일 필터 (low cardinality, 작은 카테고리에 유효)';


-- ----------------------------------------------------------------------------
-- Step 4: (category, district) composite btree
--   "자치구 + 카테고리" 쿼리 (예: 강남 카페) 주요 프리디케이트 패턴
-- ----------------------------------------------------------------------------
CREATE INDEX idx_places_cat_dist ON places(category, district);
COMMENT ON INDEX idx_places_cat_dist IS '(category, district) 복합 — 자치구별 카테고리 필터';


-- ----------------------------------------------------------------------------
-- Step 5: GENERATED geography 컬럼
--   geom::geography 런타임 캐스팅 안티패턴 제거.
--   Postgres 12+ 표준 기능. 저장 단계에서 자동 계산, 미래 INSERT/UPDATE 무관여.
-- ----------------------------------------------------------------------------
ALTER TABLE places
  ADD COLUMN geog GEOGRAPHY(Point, 4326)
  GENERATED ALWAYS AS (geom::geography) STORED;

COMMENT ON COLUMN places.geog IS
  'GENERATED from geom::geography. ST_DWithin(geog, point, meters) 권장 — 캐스팅 없이 GIST 사용.';


-- ----------------------------------------------------------------------------
-- Step 6: geography GIST 인덱스
-- ----------------------------------------------------------------------------
CREATE INDEX idx_places_geog ON places USING GIST(geog);
COMMENT ON INDEX idx_places_geog IS
  '반경 검색 전용. ST_DWithin(geog, point, meters) 쿼리에서 사용. idx_places_geom (geometry)과 공존';


-- ----------------------------------------------------------------------------
-- Step 7: Self-check (migration 내부 assertion)
--   분류표 §3/§4/§5 사전 계산값과 정확 일치 확인.
--   실패 시 RAISE EXCEPTION → 전체 트랜잭션 ROLLBACK.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    cnt_cafe INT;
    cnt_pub INT;
    cnt_restaurant INT;
    cnt_total INT;
    idx_cnt INT;
    geog_notnull INT;
BEGIN
    SELECT COUNT(*) INTO cnt_cafe FROM places WHERE category='카페';
    IF cnt_cafe <> 8769 THEN
        RAISE EXCEPTION '카페 재분류 실패: 기대 8769, 실측 %', cnt_cafe;
    END IF;

    SELECT COUNT(*) INTO cnt_pub FROM places WHERE category='주점';
    IF cnt_pub <> 51778 THEN
        RAISE EXCEPTION '주점 재분류 실패: 기대 51778, 실측 %', cnt_pub;
    END IF;

    SELECT COUNT(*) INTO cnt_restaurant FROM places WHERE category='음식점';
    IF cnt_restaurant <> 470636 THEN
        RAISE EXCEPTION '음식점 재분류 잔여 실패: 기대 470636, 실측 %', cnt_restaurant;
    END IF;

    SELECT COUNT(*) INTO cnt_total FROM places;
    IF cnt_total <> 531183 THEN
        RAISE EXCEPTION 'places 총 row count 변동: 기대 531183, 실측 %', cnt_total;
    END IF;

    -- 3 신규 인덱스 존재
    SELECT COUNT(*) INTO idx_cnt
      FROM pg_indexes
     WHERE schemaname='public'
       AND tablename='places'
       AND indexname IN ('idx_places_category','idx_places_cat_dist','idx_places_geog');
    IF idx_cnt <> 3 THEN
        RAISE EXCEPTION '신규 인덱스 % 개, 기대 3', idx_cnt;
    END IF;

    -- geog 컬럼 NOT NULL 전수(geom 있는 row 전부 generated)
    SELECT COUNT(geog) INTO geog_notnull FROM places;
    IF geog_notnull <> 531183 THEN
        RAISE EXCEPTION 'geog generated 실패: 기대 531183, 실측 %', geog_notnull;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- End of migration.
-- ============================================================================
