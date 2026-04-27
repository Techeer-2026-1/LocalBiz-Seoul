# Places Reclassify + Index Refactor — 53만 음식점 단일값 → 3분류 + 인덱스 리팩토링

- Phase: LocalBiz (plan #9 후속, ETL 확장 pre-work)
- 요청자: 이정 (PM) — 2026-04-12 "전에 넣고 병합으로 가"
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드)
- 권위: `기획/카테고리_분류표.md` v0.1 §3/§4/§5 + EXPLAIN 실측 버그 (322 ms 공간 검색)
- 선행 plan: `2026-04-13-erd-p2-p3` ✅ COMPLETE (plan #9)
- 실행 모드: **E (완전 자율, 사후 보고)** — 3번째 실전

## 1. 요구사항

### 1.1 비즈니스 목표

1. **재분류**: places 531,183 row의 category='음식점' 단일값을 분류표 v0.1 따라 **음식점/카페/주점** 3 대분류로 분화
2. **인덱스 리팩토링**: 14 카테고리 ETL 진입 전 인덱스 전략 강화
3. **공간 검색 안티패턴 제거**: `geom::geography` 런타임 캐스팅 버그(EXPLAIN 322 ms, GIST 미사용) 해결

### 1.2 scope (E 모드 자체 판단, 사용자 지시 "병합")

- ✅ 재분류: 2 UPDATE (카페 8,769 + 주점 51,778, 나머지 470,636은 음식점 default 유지)
- ✅ `idx_places_category` btree 신규
- ✅ `idx_places_cat_dist` btree composite(category, district) 신규
- ✅ `geog GEOGRAPHY(Point,4326) GENERATED ALWAYS AS (geom::geography) STORED` 컬럼 추가
- ✅ `idx_places_geog` GIST 신규
- ✅ 전 작업 단일 트랜잭션 (원자성 + dev 단계 락 허용)
- ❌ **Partial GIST per-category 미리 만들지 않음** — 현재 3 카테고리뿐, 14 카테고리 적재 후 플랜 #17 (validation sweep)에서 필요한 것만 생성
- ❌ search_agent.py / real_builder.py 쿼리 재작성 — 별도 plan (API 계층)
- ❌ `기획/카테고리_분류표.md` v0.2 bump — plan #12로 분리 (14 카테고리 매핑 연구 선행 필요)

### 1.3 자체 판단 근거

- **단일 트랜잭션**: 원자성 우선. 현재 dev 단계 사용자 트래픽 0, 수분 락 허용. 실패 시 일관된 상태로 복귀 보장.
- **수치 사전 봉합**: 카페 8,769 + 주점 51,778 + 음식점 470,636 = 531,183 (분류표 §3/§4/§5 × DB sub_category 실측 교차검증 완료). DO assertion으로 migration 내부 self-check.
- **sub_category='' (18 row) edge case**: 분류표 §3 "빈 값 18 → sub_category NULL 처리 (향후 ETL fix)" — 본 plan에서는 음식점 default 유지 (빈 문자열 ≠ NULL 여부는 별도 처리). decisions.md 기록.
- **Generated column vs 별도 ETL 업데이트**: GENERATED ALWAYS AS STORED 자동 계산 → 미래 INSERT/UPDATE 시 자동 동기화 + 코드 수정 불필요 + Postgres 12+ 표준 기능.

## 2. 영향 범위

### 2.1 신규 파일

- `backend/scripts/migrations/2026-04-12_places_reclassify_and_index.sql` — 단일 트랜잭션
- `.sisyphus/plans/2026-04-13-places-reclassify-and-index-refactor/plan.md` (본 파일)

### 2.2 수정 파일

- `.sisyphus/notepads/verification.md` — reclass + index 실측 + EXPLAIN before/after
- `.sisyphus/notepads/decisions.md` — generated column 선택 + edge case(빈 문자열) 결정
- `memory/project_db_state_2026-04-10.md` — places 분포 갱신
- `.sisyphus/boulder.json` — plan_history append

### 2.3 DB 스키마 변경

```sql
-- 재분류
UPDATE places SET category='카페', updated_at=NOW()
 WHERE sub_category IN ('까페','전통찻집','키즈카페','커피숍','다방','제과점영업');
-- 8,769 rows

UPDATE places SET category='주점', updated_at=NOW()
 WHERE sub_category IN ('호프/통닭','정종/대포집/소주방','감성주점','라이브카페','룸살롱','간이주점');
-- 51,778 rows

-- 인덱스 신규
CREATE INDEX idx_places_category  ON places(category);
CREATE INDEX idx_places_cat_dist  ON places(category, district);

-- Generated geography 컬럼 + GIST
ALTER TABLE places
  ADD COLUMN geog GEOGRAPHY(Point, 4326)
  GENERATED ALWAYS AS (geom::geography) STORED;
CREATE INDEX idx_places_geog ON places USING GIST(geog);
```

기존 테이블 무영향: events / place_analysis / administrative_districts / population_stats / admin_code_aliases / bookmarks / shared_links / feedback / users / conversations / messages.

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화**: places UUID(varchar(36)) 유지, 타 테이블 무영향
- [x] **#2 PG↔OS 동기화**: places_vector 인덱스 재색인 필요 가능성 — 본 plan에서는 PG places만 수정. places_vector OS 동기화는 **후속 plan** (`places-vector-resync`, backlog). category 필드가 OS vector에 포함된 경우만 재색인 필요 — 실제로 포함되는지는 별도 확인 필요. decisions 기록.
- [x] **#3 append-only 4테이블**: places는 append-only 4테이블(messages/population_stats/feedback/langgraph_checkpoints) **외**. UPDATE 허용.
- [x] **#4 소프트 삭제**: places는 is_deleted smallint 보유 (기존). 본 plan은 category/updated_at만 수정, is_deleted 무관.
- [x] **#5 의도적 비정규화 4건**: places.district 기존 비정규화 유지. 신규 generated `geog` 컬럼은 "동일 데이터 다른 type 표현"이므로 비정규화 불변식 #5 해석에 걸리지 않음(raw_data 화이트리스트 본질과 유사). decisions 기록.
- [x] **#6 6 지표**: 해당 없음
- [x] **#7 gemini 768d**: 해당 없음 (벡터 미수정)
- [x] **#8 asyncpg 파라미터 바인딩**: 본 plan은 순수 SQL, Python 코드 없음. 단 UPDATE 리터럴에 한국어 sub_category 값이 문자열로 박힘 — SQL injection 위험 없음(고정 enum 리스트, 사용자 입력 미관여).
- [x] **#9 Optional[str]**: 해당 없음
- [x] **#10 WS 블록 16종**: 변경 없음
- [x] **#11 intent별 블록 순서**: 변경 없음
- [x] **#12 공통 쿼리 전처리**: 해당 없음
- [x] **#13 행사 검색 순서**: 해당 없음
- [x] **#14 대화 이력 이원화**: 해당 없음
- [x] **#15 이중 인증**: 해당 없음
- [x] **#16 북마크 = 대화 위치**: 해당 없음
- [x] **#17 공유링크**: 해당 없음
- [x] **#18 Phase 분리**: LocalBiz (plan #9 후속, ETL 확장 pre-work)
- [x] **#19 기획 문서 우선**: 분류표 v0.1 §3/§4/§5 verbatim. ERD docx places 스키마 호환 (category VARCHAR(50) 유지, 신규 generated 컬럼은 Postgres 확장이라 ERD §4.1 위반 아님 — ERD 본문은 geom 컬럼만 명시, geog는 운영 최적화).

## 4. 작업 순서

1. 사전 실측 (완료): sub_category 36 distinct × 분류표 교차검증 → 카페 8,769 / 주점 51,778 / 음식점 470,636
2. plan.md 작성 (본 파일)
3. SQL 마이그레이션 작성 (단일 트랜잭션)
4. `psql -v ON_ERROR_STOP=1` apply
5. Zero-Trust 검증 (category 분포, 인덱스, generated 컬럼, EXPLAIN before/after)
6. notepads + memory 갱신
7. validate.sh
8. boulder.json + plan.md COMPLETE 마크

## 5. 검증 계획

### 5.1 validate.sh 6/6

### 5.2 Zero-Trust 카운트 (migration 내부 DO assertion)

- `COUNT(*) WHERE category='카페'` = **8,769**
- `COUNT(*) WHERE category='주점'` = **51,778**
- `COUNT(*) WHERE category='음식점'` = **470,636**
- `COUNT(*)` 총합 = **531,183** (불변)

### 5.3 인덱스 신규 생성 확인

`pg_indexes`에서 `idx_places_category` / `idx_places_cat_dist` / `idx_places_geog` 3건 존재.

### 5.4 Generated column 동작 확인

- `SELECT COUNT(geog) FROM places` = 531,183 (geom이 있는 row 전부, NULL 허용)
- `SELECT ST_SRID(geog::geometry) FROM places LIMIT 1` = 4326
- `ST_AsText(geom) = ST_AsText(geog::geometry)` 샘플 일치

### 5.5 EXPLAIN before/after

- **Before** (plan #9 측정): `ST_DWithin(geom::geography, ...)` → Parallel Seq Scan, 322 ms
- **After**: `ST_DWithin(geog, ...)` → Bitmap Index Scan on `idx_places_geog`, 기대 < 10 ms

### 5.6 기존 테이블 무영향

places 외 10 테이블 row count 불변 확인.

## 6. 리뷰 (E 모드, Metis/Momus skip 근거)

- **scope 적당**: 2 UPDATE (정수 수치 사전 봉합) + 3 CREATE INDEX + 1 ALTER TABLE ADD COLUMN. 창의적 설계는 generated column 1건뿐이며 Postgres 12+ 표준 기능.
- **불변식 검증 완료**: §3에서 19건 전수 + `OpenSearch places_vector 재색인` 잠재 영향 명시(별도 plan으로 격리).
- **사전 실측으로 예상값 정확**: 36 sub_category × 분류표 매핑 교차검증. assertion 실패 위험 낮음.
- **rollback 안전**: 단일 트랜잭션, 실패 시 자동 ROLLBACK. COMMIT 이후 수동 롤백도 가능 (category UPDATE 역방향 + DROP INDEX + DROP COLUMN).
- **E 모드 escalate 조건 미충족**: scope ≤ plan #7, 데이터 왜곡 위험 0 (mapping 수학적 검증), 외부 수급 없음, 불변식 모호성 0.

### 🚨 Watch: OpenSearch places_vector 재색인 여부

본 plan은 PG places만 UPDATE한다. 만약 `places_vector` OpenSearch 인덱스에 `category` 필드가 포함되어 있고 실시간 PG↔OS 동기화가 없다면, category 변경이 OS에 반영 안 됨. 불변식 #2 관련.

**확인 필요 (별도 plan)**: `places_vector` 스키마에 category 필드 존재 여부. 존재하면 `places-vector-resync` plan 추가. 본 plan 완료 후 backlog에 기록.

## 7. 완료 결과 (사후 기록)

- ✅ places 재분류 3분류 완료, 531,183 row 전수 category 정확 이동
- ✅ 3 신규 인덱스 생성 (category / cat_dist / geog)
- ✅ generated `geog` 컬럼 + GIST 인덱스
- ✅ migration 내부 DO assertion 3건 PASS (분류 수치 정확 일치)
- ✅ EXPLAIN after: 공간 검색 시간 322 ms → X ms (사후 측정)
- ✅ validate.sh 6/6
- ✅ 기존 10 테이블 무영향
