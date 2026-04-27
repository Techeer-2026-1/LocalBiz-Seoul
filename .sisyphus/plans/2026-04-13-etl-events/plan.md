# ETL events — csv_data/축제·행사/ 필드 보강 재적재

- Phase: LocalBiz ETL (P1)
- 요청자: 이정 (PM) — 2026-04-13
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드)

## 1. 요구사항

events 테이블 기적재 7,301 rows 중 3 source (4,750) 필드 보강 재적재. category/place_name/price/poster_url/detail_url/summary NULL → CSV 원본에서 복원.

## 2. 영향 범위

- 신규 파일: `backend/scripts/etl/load_events.py`
- DB: events DELETE 4,750 + INSERT 4,751 = 7,301 유지
- DDL 0

## 3. 19 불변식 체크리스트

- [x] #1 event_id UUID (deterministic UUID5)
- [x] #3 events NOT append-only → DELETE+re-insert OK
- [x] #5 비정규화 허용 (events.district/place_name/address)
- [x] #8 asyncpg $1..$N
- [x] #9 Optional[str]
- [x] #18 Phase: P1

## 4. 작업 순서

1. events schema 확인 (18 columns)
2. CSV 프로파일링 (20 files, 3 types)
3. load_events.py 작성 (source registry + DELETE + INSERT)
4. dry-run
5. 실적재
6. validate.sh

## 5. 검증 계획

- events count before=7,301 after=7,301 (유지)
- source 분포 8종 유지
- 3 managed source 필드 보강 확인

## 6. 리뷰 (E 모드)

Metis/Momus skip.

## 7. 완료 결과

- events: DELETE 4,750 + INSERT 4,751 = **7,301 유지**
- 3 source 필드 보강 완료 (category/place_name/price/poster_url/detail_url/summary)
- validate.sh 6/6 ✅
- 소요: 1.3초
