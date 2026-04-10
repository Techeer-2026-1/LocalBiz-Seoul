-- 2026-04-10: Drop legacy tables removed by ERD v6.1 redesign.
--
-- Why:
--   - user_favorites: 즐겨찾기(장소 저장) 패러다임은 폐기됨.
--     ERD v6.1 §4.9에서 bookmarks(대화 위치 저장, 5종 핀)로 대체.
--   - reviews:        독립 reviews 테이블은 ERD v6.1에서 사라짐.
--     리뷰 분석 결과는 place_analysis 테이블 + place_reviews(OpenSearch) 인덱스로 이관.
--
-- Authority: 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4
-- Authorized by: 이정 (PM, BE 리드) — Phase 2 진입 사전 정리
-- Reversibility: 두 테이블 모두 row count 0이었음. 데이터 손실 없음.
--
-- Pre-state (2026-04-10 측정):
--   public.user_favorites  0 rows
--   public.reviews         0 rows

BEGIN;

DROP TABLE IF EXISTS public.user_favorites CASCADE;
DROP TABLE IF EXISTS public.reviews CASCADE;

COMMIT;
