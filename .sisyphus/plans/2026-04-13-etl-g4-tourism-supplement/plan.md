# ETL G4 관광지 보강 4 CSV — 사후 기록

- Phase: LocalBiz ETL (P1)
- 요청자: 이정 (PM)
- 작성일: 2026-04-12 (사후 작성: 2026-04-13)
- 상태: **COMPLETE** (2026-04-12, 하네스 밖 실행)
- 최종 결정: **autonomous-complete** (E 모드, plan.md 누락 상태로 실행됨 — 드리프트 정합 plan에서 사후 보완)

## 1. 요구사항

관광지 카테고리 보강. data/csv/관광지/ 4 CSV 적재.

## 2. 영향 범위

- 신규 파일: `backend/scripts/etl/load_g4_tourism.py` (419줄)
- DB: places INSERT ~14,377건 (관광지 카테고리, 4 source)
- DDL 0

## 3. 19 불변식 체크리스트

- [x] #1 place_id UUID (gen_random_uuid)
- [x] #3 places NOT append-only → INSERT OK
- [x] #5 비정규화 허용 (places.district)
- [x] #8 asyncpg $1..$N
- [x] #9 Optional[str]
- [x] #18 Phase: P1

## 4. 작업 순서

1. CSV 프로파일링 (도보여행 12,967 + 관광지복합 3,942 + K-무비 1,155 + 야경 51)
2. load_g4_tourism.py 작성
3. 실적재

## 5. 검증 계획

- 관광지 category count 확인
- 서울 좌표 범위 필터 확인

## 6. 리뷰 (E 모드)

Metis/Momus skip. 사후 기록.

## 7. 완료 결과 (DB 실측 2026-04-13)

- 관광지 카테고리: **25,990건** (7 source — sosang_biz 포함)
- 4 CSV 직접 source: seoul_walking_tour 9,794 + seoul_tourism_complex 3,919 + seoul_k_movie_tourism 613 + seoul_night_view 51
- load_g4_tourism.py 정상 동작 확인
