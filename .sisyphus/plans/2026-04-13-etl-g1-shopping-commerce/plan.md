# ETL G1 — 소상공인 상가(상권) 202512 fresh load (δ)

- Phase: LocalBiz ETL (G1 first — profile §4.2 priority 1)
- 요청자: 이정 (PM) — 2026-04-13
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드, δ 확정)
- 선행 plan: `2026-04-13-category-table-v0.2-bump` (plan #12) ✅
- E 모드: 2026-04-12 확정. Metis/Momus skip, 사후 보고.

## 1. 요구사항

### 1.1 사용자 지시 (원문)
> "plan #13 (etl-g1-shopping-commerce) 진입. E 모드 유지. 문제 소지 있을 때만 컨펌."
> Q1 = A (340K, v0.2 10 대분류 매핑) 확정
> Q2 = **δ**: 기존 531K DROP + 소상공인 340K fresh load ("중복 허용 X, 최신 데이터로 갱신")
> Q3 = place_id = 상가업소번호 그대로 사용 확정

### 1.2 목표
- **소상공인시장진흥공단 상가(상권) 202512 서울 CSV (534,978 row)** 를 places에 fresh load
- 기존 531,183 row (`source='seoul_restaurant_inheoga'`) **TRUNCATE 후 치환**
- v0.2 18 대분류 중 10개에 매핑 (음식점/카페/주점/쇼핑/미용·뷰티/교육/체육시설/관광지/의료/숙박)
- v0.2 매핑 불가 194K row는 skip (과학·기술/부동산/시설관리·임대/수리·개인 비미용)

### 1.3 수급 파일
- `csv_data/소상공인시장진흥공단_상가(상권)_정보(서울)(CSV)(202512)/소상공인시장진흥공단_상가(상권)정보_서울_202512.csv`
- 인코딩: **UTF-8** (인허가 CP949와 달리 utf-8 native)
- 39 컬럼, 좌표 100%, 상가업소번호 unique 534,978 (max 20자)

## 2. 영향 범위

### 2.1 신규 파일
- `backend/scripts/etl/load_sosang_biz.py` (신규 loader, 약 250줄)
- `.sisyphus/plans/2026-04-13-etl-g1-shopping-commerce/plan.md` (본 파일)

### 2.2 수정 파일
- 없음 (validate_category.py는 plan #12에서 확정된 그대로 사용)

### 2.3 DB 영향
- **places**: 531,183 DELETE → ~340K INSERT (순 증감 약 -190K, 카테고리 커버리지 5 → 10 확대)
- **place_analysis**: FK CASCADE, 현재 0 row → 영향 없음
- **기타**: 변경 없음
- DDL: **0** (스키마 불변)

### 2.4 카테고리 매핑 표 (v0.2 10 대분류)

| 소상공인 대분류 | 소상공인 중분류 | v0.2 category | 예상 row |
|---|---|---|---:|
| 음식 | (비알코올/주점 제외 8종) | 음식점 | ~98,722 |
| 음식 | 비알코올 | 카페 | 21,624 |
| 음식 | 주점 | 주점 | 15,538 |
| 소매 | (15종 전체) | 쇼핑 | 111,632 |
| 보건의료 | 의원/병원/기타 보건 | 의료 | 18,840 |
| 숙박 | 일반숙박/기타숙박 | 숙박 | 8,841 |
| 교육 | 일반교육/기타교육/교육지원 | 교육 | 45,158 |
| 수리·개인 | 이용·미용 | 미용·뷰티 | 30,617 |
| 예술·스포츠 | 스포츠 서비스 | 체육시설 | 9,062 |
| 예술·스포츠 | 유원지·오락 + 도서관·사적지 | 관광지 | 11,384 |
| **합계 (적재)** | | | **~371,418** |
| 과학·기술 | 전체 | SKIP | 93,261 |
| 부동산 | 전체 | SKIP | 25,059 |
| 시설관리·임대 | 전체 | SKIP | 24,231 |
| 수리·개인 | 이용·미용 제외 | SKIP | 21,009 |
| **합계 (skip)** | | | **~163,560** |
| **총계** | | | **534,978** |

실측은 적재 후 확정.

### 2.5 source 값
- 기존: `seoul_restaurant_inheoga` (531,183) → DELETE 전체
- 신규: `sosang_biz_202512` (약 371K)

### 2.6 sub_category 정책
- CSV의 `상권업종중분류명`을 그대로 sub_category로 저장 (한글 원문)
- v0.2 validate_category.py의 sub_category 화이트리스트와는 **정확히 일치하지 않음** (소상공인 명명은 한식/기타 간이 등, v0.2는 한식/분식 등 세분화 상이)
- 따라서 `validate_category(..., strict=False)` 호출: 대분류만 v0.2 enum 강제, sub_category는 pass-through

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화: places.place_id VARCHAR(36) — 상가업소번호 `MA01...` 20자. 기존 플로우 유지, UUID 아님(현 스키마 실측 source of truth, plan #10 기 해결)
- [x] #2 PG↔OS 동기화: 본 plan scope 외 (OS place_analysis 재색인은 후속 plan)
- [x] #3 append-only 4테이블: **places는 append-only 아님** (is_deleted 컬럼 있음). DELETE 합법
- [x] #4 소프트 삭제 매트릭스: places는 is_deleted 지원, 본 plan은 **hard TRUNCATE** — 531K는 외부 CSV 재수급 가능하므로 soft 불필요 (feedback_drop_data_freely.md 룰 부합)
- [x] #5 의도적 비정규화 4건: places.district만 유지, 신규 비정규화 없음
- [x] #6 6 지표: analysis 무관
- [x] #7 임베딩: 본 plan은 OS/임베딩 무관
- [x] #8 asyncpg 파라미터 바인딩: `$1`..`$11` 전용, f-string SQL 없음
- [x] #9 Optional[str]: 전 함수 시그니처에 Optional 사용, `str | None` 금지
- [x] #10-17: intent/WS 무관
- [x] #18 Phase 분리: LocalBiz ETL — Phase 라벨 명시
- [x] #19 기획 우선: 카테고리_분류표 v0.2 verbatim, validate_category() 경유

## 4. 작업 순서 (atomic steps)

1. **사전 검증**
   - 현 places row count 캡처 (기대: 531,183)
   - place_analysis row count 캡처 (기대: 0)
   - FK CASCADE 재확인 (이미 실측 완료)
2. **loader 작성** — `backend/scripts/etl/load_sosang_biz.py`
   - CSV DictReader (utf-8), 1000건 batch
   - category mapping 함수 (§2.4 표 로직)
   - validate_category(strict=False) 호출
   - asyncpg $1..$11 파라미터 바인딩
   - ST_SetSRID(ST_MakePoint(lng, lat), 4326) for geom
   - raw_data = JSONB of entire CSV row
   - `--dry-run` 옵션 (첫 5건 변환 + skip 통계만 출력, DB write 없음)
   - `--truncate` 옵션 (INSERT 전 places TRUNCATE — 안전장치)
3. **dry-run** — 변환만, DB 무변경
   - 카테고리별 적재/skip 수치 실측 확인 (§2.4 예측 vs 실측)
4. **TRUNCATE + 실 적재**
   - `python -m scripts.etl.load_sosang_biz --truncate` 1회 실행
   - 진행률 로그 5% 단위
5. **Zero-Trust 검증**
   - places 총 count
   - source='sosang_biz_202512' count (=places 총 count)
   - category distribution 실측 (10개 카테고리 모두 포함)
   - sub_category NULL count
   - geom NULL count (기대: 0)
   - district distinct (기대: 25 서울 자치구)
   - place_analysis row count (기대: 0, CASCADE 영향 확인)
6. **validate.sh** 6/6
7. **notepad/memory/boulder 갱신** (decisions, learnings, project_db_state, resume)

## 5. 검증 계획

### 5.1 자동 (loader 내부 DO assertion — plan #9 표준)
- loader는 INSERT 완료 후 동일 트랜잭션에서 assertion SQL 실행:
  - `SELECT COUNT(*) FROM places WHERE source='sosang_biz_202512'` vs loader 카운터
  - `SELECT COUNT(DISTINCT category) FROM places` ≥ 10
  - `SELECT COUNT(*) FROM places WHERE geom IS NULL` = 0
- 불일치 시 transaction ROLLBACK

### 5.2 외부 (Zero-Trust postgres MCP)
- §4 step 5 6 SQL 직접 실행

### 5.3 validate.sh
- ruff + pyright + SQL guard + docx drift + tests + ERD guard 6/6

### 5.4 데이터 정합성 수동 확인
- 강동구 암사2동 샘플 1건 CSV → DB 교차 확인 (sample row `60계치킨암사` 등)

## 6. 리뷰 (E 모드)

Metis/Momus skip. 근거:
- 사용자 δ 확정 = scope/중복 정책 승인
- DDL 0 (스키마 무변경)
- fuzzy match 없음 (단순 CSV→INSERT)
- TRUNCATE는 place_analysis=0 확인으로 안전
- 불변식 위반 가능성 0 (places는 append-only 아님)
- loader 내부 assertion + Zero-Trust 외부 검증 이중 안전망

## 7. 롤백 계획 (escape hatch)

- 실패 시: loader transaction 자동 ROLLBACK (places 무변경)
- TRUNCATE 후 INSERT 실패 시: 기존 531K 데이터는 소실. 복구 = `서울시 일반음식점 인허가 CSV` 재적재 plan 별도 실행 (이미 csv_data/음식점 카페/에 원본 보관)
- 재적재 위험 없음 확인: csv_data/음식점 카페/서울시 일반음식점 인허가 정보.csv 존재 확인됨

## 8. 완료 결과

- [x] places 총 row: **371,418** (예측 371,418 == 실측, 100% 일치)
- [x] 카테고리 분포 (실측, 10종): 쇼핑 111,632 / 음식점 98,722 / 교육 45,158 / 미용·뷰티 30,617 / 카페 21,624 / 의료 18,840 / 주점 15,538 / 관광지 11,384 / 체육시설 9,062 / 숙박 8,841
- [x] skip count: **163,560** (과학·기술 93,261 / 부동산 25,059 / 시설관리·임대 24,231 / 수리·개인 비미용 21,009)
- [x] 자치구 분포: 25/25 완비 (강남 36,683 최다 ~ 도봉 8,127 최소)
- [x] source 치환: seoul_restaurant_inheoga 0 / sosang_biz_202512 371,418
- [x] null_geom=0, place_analysis=0 (FK CASCADE 영향 없음)
- [x] 소요 시간: **48.6초** (TRUNCATE 포함, dry-run 17.5초)
- [x] validate.sh: **6/6 통과**
- [x] 내부 assertion 3건 (db_count/null_geom/distinct_cat) transaction 내부 통과
- [x] 샘플 1:1 검증 (60계치킨암사 / 강동구 / 127.12686, 37.55081)
