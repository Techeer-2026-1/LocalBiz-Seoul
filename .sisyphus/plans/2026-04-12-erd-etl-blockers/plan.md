# ERD ETL Blockers — administrative_districts + population_stats 적재 (ERD v6.2 §4.4/4.5)

- Phase: P1 (ETL blocker) + Infra (하네스 Phase 5 진정 워커 첫 시범)
- 요청자: 이정 (PM)
- 작성일: 2026-04-12
- 상태: **COMPLETE**
- 최종 결정: **APPROVED** (2026-04-12) → **COMPLETE** (2026-04-12)
  - g1 §A 사전검증 4/4 PASS · g2 §B SOURCE.md 확인 · g3 §C DDL (427 admin + pop table) 6/6 Zero-Trust PASS · g4 §D admin_districts ETL 427 row + 25 자치구 + ST_IsValid 전수 · g5 §E population_stats ETL 278,880 / SKIP 6,048 / 415 × 24 × 28 수학 완전 일치 · g6 §F Oracle spawn SKIP (velocity directive, 메인 Claude 직접 MCP 진단 + 9 mismatch 완전 수치화) · g7 §G notepads 4 + memory 3 갱신 · g8 §H Metis/Momus 이미 APPROVED · g9 §I Atlas dep-map 이미 존재 · g10 §J validate.sh 6/6 PASS (ruff UP015 5건 autofix + format 2파일)
- 권위: `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` §4.4, §4.5
- 선행 plan: `2026-04-11-erd-audit-feedback` ✅ COMPLETE (plan #2), `2026-04-13-harness-workers` ✅ COMPLETE (plan #6)
- 관련 메모리: `feedback_etl_validation_gate.md` (2026-04-12 수립, 본 plan이 첫 적용)

> 본 plan은 LocalBiz 혼잡도(CROWDEDNESS) 기능을 풀기 위한 최소 스키마 + 데이터 적재. 동시에 plan #6에서 구축한 진정 워커 4종(sisyphus-junior / hephaestus / oracle / fe-visual 중 앞 3종)의 **첫 실전 투입**이다.

## 1. 요구사항

### 1.1 비즈니스 목표

혼잡도(CROWDEDNESS) intent — "강남역 카페 / 지금 한가한 곳" 같은 질문에 시간대·행정동별 생활인구 기반 답변을 할 수 있게 만든다. ERD 권위에 따르면 2개 테이블이 필요:

1. **`administrative_districts`** (ERD §4.4) — 서울 427개 행정동 마스터. `adm_dong_code` 자연키 + 행정동 이름·자치구·PostGIS MultiPolygon `geom`.
2. **`population_stats`** (ERD §4.5) — 시간대·행정동별 생활인구 시계열. append-only.

### 1.2 하네스 목표 (이중 인프라 첫 실전)

본 plan은 **두 인프라의 첫 실전 투입**이다. 이 이중 의의는 Auto Dream(Phase 6)이 plan #7을 학습 재료로 정확히 집을 수 있도록 명시적으로 분리한다 (Metis M5).

1. **plan #6 진정 subagent 인프라의 첫 LocalBiz 투입**. 자기 자신을 처리하는 메타-plan이었던 plan #6과 달리, 본 plan은 **LocalBiz 실제 비즈니스 작업**을 워커들이 분담 실행한다:
   - **hephaestus** — DB 마이그레이션 SQL + 복합 ETL 로직 (카테고리 `db-migration`)
   - **sisyphus-junior** — 단순 CSV 파싱·검증 유틸 / validate.sh 확인 (카테고리 `quick`)
   - **oracle** — 적재 전후 DB 실측 진단 (카테고리 `ultrabrain`, postgres MCP 필요 — 아래 §부록 3 참조)

2. **`feedback_etl_validation_gate.md` 정책의 첫 준수 사례**. 2026-04-12 수립된 "외부 수급 데이터는 DB write 전 반드시 프로파일링 + 사용자 승인" 규약이 본 plan에서 처음 실행된다. plan.md 작성 **이전**에 수급 + 프로파일링 + 검증 게이트가 완료되었고, 게이트 증거가 §부록 1에 수치화되어 있다.

### 1.3 사용자 결정 (2026-04-12 확정, 검증 게이트 완료)

| 결정 | 선택 |
|---|---|
| 원본 데이터 소스 | `vuski/admdongkor` **ver20260201** (2026-02-01 기준, 공공누리 1유형) |
| administrative_districts geom 포함 | **O** — 이번 plan에서 MultiPolygon까지 적재 |
| population_stats 코드 mismatch 9건 처리 | **지금 적재 + 후속 plan** — 415/424 코드 (**97.9%**)만 insert, 9건 코드의 약 6천행은 issues.md 기록만 하고 후속 plan에서 행안부 공식 코드이력으로 재처리 |
| geom 컬럼 ERD docx 내부 충돌 (본문 O vs 컬럼표 X) | **본문이 권위** — DDL에 geom 포함. 별도 plan에서 ERD docx v6.3 bump로 컬럼 표 정정 (본 plan §부록 2 참조) |
| 검증 게이트 정책 | 적재 전 프로파일링 완료, 사용자 승인 완료 (2026-04-12) |

### 1.4 범위 외 (별도 plan)

- 행안부 행정동 코드 변경 이력 수급 + 9건 재처리 → `2026-04-13-admin-code-reconcile` (예약)
- ERD docx v6.3 bump (컬럼 표에 geom 명시) → `2026-04-14-erd-docx-v6.3` (예약, 경량 문서 작업)
- CROWDEDNESS intent LangGraph 노드 구현 → `2026-04-15-intent-crowdedness` (예약, P2)
- `bookmarks`/`shared_links`/`feedback` 테이블 → `2026-04-13-erd-p2-p3` (기존 예약)
- 생활인구 관내이동 CSV (`서울시 관내이동 생활인구 (행정동별).csv`, CP949) → 별도 plan

## 2. 영향 범위

### 2.1 신규 파일

- `backend/scripts/migrations/2026-04-12_erd_etl_blockers.sql` — DDL 단일 트랜잭션 (2 CREATE TABLE + 인덱스 + FK)
- `backend/scripts/etl/load_administrative_districts.py` — GeoJSON 파싱 + 427 feature INSERT (geom MultiPolygon 포함)
- `backend/scripts/etl/load_population_stats.py` — CSV 스트리밍 파싱 + 1000건 batch insert + mismatch 9건 skip 로그
- `backend/scripts/etl/__init__.py` — 패키지 마커 (빈 파일)
- `data_external/행정구역_geojson/HangJeongDong_ver20260201.geojson` — **이미 존재** (검증 게이트에서 수급 완료, 33 MB)
- `data_external/행정구역_geojson/SOURCE.md` — 출처·라이선스·수급일 명시 (**이미 작성 완료** 2026-04-12)

### 2.1-bis 사용 파일 (입력, 수정 없음, Metis M2)

- `csv_data/생활인구 통계/행정동 단위 서울 생활인구(내국인)(CSV)(API)(202603)/행정동 단위 서울 생활인구(내국인)202603.csv` — population_stats 원본, 284,929 행, UTF-8 BOM, 32 컬럼. **Read-only**.
- `data_external/행정구역_geojson/HangJeongDong_ver20260201.geojson` — administrative_districts 원본, 33 MB, 전국 3,558 features 중 서울 427. **Read-only**.

### 2.2 수정 파일

> **경로 주석 (Momus Mo2a)**: 아래 `memory/…` 경로는 CLAUDE.md 상단 auto-memory 블록 기준이며, 실제 위치는 사용자 auto-memory 디렉토리(`~/.claude/projects/-Users-ijeong-Desktop---------/memory/`)다. 프로젝트 루트의 `memory/` 디렉토리는 존재하지 않는다.

- `memory/project_db_state_2026-04-10.md` → 날짜 rename + 427+population 적재 반영
- `memory/project_phase_boundaries.md` → "ETL blocker 해제" 마크
- `.sisyphus/notepads/issues.md` → 9건 mismatch 엔트리 append (후속 plan 트리거)
- `.sisyphus/notepads/verification.md` → 워커 spawn 결과 취합
- `.sisyphus/notepads/learnings.md` → 검증 게이트 첫 실전 사용 learning 1건
- `.sisyphus/notepads/decisions.md` → 3 결정 기록 (데이터 소스 / geom 포함 / mismatch 처리)
- `.sisyphus/boulder.json` → active_plan 교체 + workers_spawned 누적
- `CLAUDE.md` → 변경 없음 (ETL 불변식 #3 append-only 재확인만)

### 2.3 DB 스키마 영향

**2 테이블 신규 생성** (현재 둘 다 부재, 2026-04-12 postgres MCP 실측 확인):

```sql
-- administrative_districts (ERD §4.4, 본문 권위)
CREATE TABLE administrative_districts (
  adm_dong_code   VARCHAR(20) PRIMARY KEY,                 -- 자연키 (불변식 #1)
  adm_dong_name   VARCHAR(50) NOT NULL,
  district        VARCHAR(50) NOT NULL,
  geom            geometry(MultiPolygon, 4326),            -- ERD 본문 권위, NULL 허용 — 후속 plan admin-code-reconcile이 행안부 코드만 있는 행정동 row를 geom 없이 선등록할 가능성 대비 (Metis M1). 본 plan에서는 427건 전부 geom NOT NULL 로 적재됨 (§5.2 검증 표).
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_adm_districts_geom ON administrative_districts USING GIST(geom);
CREATE INDEX idx_adm_districts_district ON administrative_districts(district);

-- population_stats (ERD §4.5, append-only 불변식 #3)
CREATE TABLE population_stats (
  id              BIGSERIAL PRIMARY KEY,                   -- BIGINT AI (불변식 #1)
  base_date       DATE NOT NULL,
  time_slot       SMALLINT NOT NULL CHECK (time_slot BETWEEN 0 AND 23),
  adm_dong_code   VARCHAR(20) NOT NULL
                  REFERENCES administrative_districts(adm_dong_code) ON DELETE RESTRICT,
  total_pop       INTEGER NOT NULL DEFAULT 0,
  raw_data        JSONB,                                   -- 의도적 비정규화 #5 화이트리스트
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- updated_at / is_deleted 없음 (불변식 #3 append-only)
);
CREATE INDEX idx_pop_stats_adm_time ON population_stats(adm_dong_code, base_date, time_slot);
CREATE INDEX idx_pop_stats_base_date ON population_stats(base_date);
```

**기존 테이블 무수정**: places / events / place_analysis / users / conversations / messages 모두 영향 없음.

### 2.4 기타 영향

- **응답 블록 16종**: 변경 없음 (CROWDEDNESS intent는 별도 plan). 단 `chart` 블록이 혼잡도 시각화에 사용될 예정.
- **intent 추가/변경**: 없음. CROWDEDNESS intent 등록은 별도 plan.
- **외부 API 호출**: 없음 (모든 데이터 로컬 파일).
- **FE 영향**: 없음.
- **postgres MCP wire (Oracle)**: 본 plan의 oracle spawn 시도는 plan #6 issues.md의 known gap. 해결책은 §부록 3.

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화**: administrative_districts = 자연키(adm_dong_code) / population_stats = BIGINT AI(id) ✅
- [x] **#2 PG↔OS 동기화**: 해당 없음 (두 테이블 모두 OpenSearch 인덱싱 대상 아님)
- [x] **#3 append-only 4테이블**: population_stats는 append-only — updated_at · is_deleted **없음** ✅
- [x] **#4 소프트 삭제**: administrative_districts는 마스터 테이블 → is_deleted 없음 (ERD §4.4 비고 명시, ON DELETE RESTRICT로 보호). population_stats는 append-only.
- [x] **#5 의도적 비정규화 4건**: population_stats.raw_data (JSONB) 화이트리스트에 이미 포함. 기존 places.district / events.* / place_analysis.place_name 무영향.
- [x] **#6 6 지표**: 해당 없음 (본 plan 무관)
- [x] **#7 gemini-embedding-001 768d**: 해당 없음 (벡터 미사용)
- [x] **#8 asyncpg 파라미터 바인딩**: ETL 스크립트에 `$1, $2` 사용 강제, f-string SQL 금지
- [x] **#9 Optional[str]**: ETL 스크립트 `Optional[int]` 사용, `str | None` 금지
- [x] **#10 WS 블록 16종**: 변경 없음
- [x] **#11 intent별 블록 순서**: 변경 없음
- [x] **#12 공통 쿼리 전처리**: 해당 없음 (Intent Router 무관)
- [x] **#13 행사 검색 DB 우선**: 해당 없음
- [x] **#14 대화 이력 이원화**: 해당 없음
- [x] **#15 이중 인증**: 해당 없음
- [x] **#16 북마크 = 대화 위치**: 해당 없음
- [x] **#17 공유링크 인증**: 해당 없음
- [x] **#18 Phase 라벨**: **P1 (ETL blocker) + Infra (하네스 Phase 5 첫 실전)**
- [x] **#19 기획 문서 우선**: ERD §4.4 본문 권위 (MultiPolygon geom 포함) 따름. docx 내부 충돌은 §부록 2에서 resolve.

## 4. 작업 순서 (Atomic step)

> 사용자 결정: **그래뉼래리티 B (Phase별 묶기)** default 유지. plan #6에서 C(group별 확인) 실행해 문제 0건 — 본 plan도 C 가능하나 B로 시작 후 진행 중 문제 0건이면 C 전환 없이 완주.

### §A 사전검증 (read-only, g1)

1. `postgres MCP`으로 현재 테이블 목록 재확인 (`administrative_districts`, `population_stats` 부재 재검증 — skeptical protocol)
2. `data_external/행정구역_geojson/HangJeongDong_ver20260201.geojson` 존재 + 크기(33 MB) 재확인
3. plan #6 COMPLETE 상태 재확인 (`.sisyphus/plans/2026-04-13-harness-workers/plan.md` 헤더)
4. `backend/venv` 활성 + `validate.sh` baseline 6/6 통과 확인

### §B 출처·라이선스 문서화 (g2)

5. `data_external/행정구역_geojson/SOURCE.md` 작성 — 출처 URL, 라이선스 (MIT repo / 공공누리 1유형 원천), 수급일 2026-04-12, 버전 ver20260201, 커맨드 재현 명령

> **ETL 실행 규약 (Metis M4)**: 본 plan의 모든 ETL·마이그레이션 스크립트는 다음 표준 진입점으로 실행한다:
> ```bash
> cd backend && source venv/bin/activate && python -m scripts.etl.<name>
> ```
> `cwd = backend/`, PYTHONPATH 자동(`python -m`), 가상환경 필수. SQL 마이그레이션은 `psql -h REDACTED_DB_HOST -U etl -d postgres -f scripts/migrations/<file>.sql` (DB_PASSWORD는 `~/.zshrc`에서 환경변수로). hephaestus spawn prompt에 본 규약 명시 필수.

### §C DDL 마이그레이션 (g3 — hephaestus 위임)

6. **hephaestus spawn** — `backend/scripts/migrations/2026-04-12_erd_etl_blockers.sql` 작성. 단일 트랜잭션(BEGIN/COMMIT), 2 CREATE TABLE + 2 INDEX(administrative_districts) + 2 INDEX(population_stats) + FK RESTRICT + rollback comment. 불변식 #1/#3/#5 체크 주석 포함.
7. 메인 Claude가 SQL 리뷰 (hyper-focused contract 준수 확인) → psql로 단일 실행 + 에러 시 rollback
8. **Zero-Trust 검증**: postgres MCP로 `information_schema.tables`·`information_schema.columns`·`pg_indexes` 실측 → 스키마 정확 일치 확인

### §D ETL 스크립트 — administrative_districts (g4 — hephaestus 위임)

9. **hephaestus spawn** — `backend/scripts/etl/load_administrative_districts.py` 작성. GeoJSON 파싱 → 서울 427 filter (`sidonm == '서울특별시'`) → 각 feature에서:
   - `adm_dong_code` = `properties.adm_cd2[:8]`
   - `adm_dong_name` = `properties.adm_nm.split()[-1]` (마지막 토큰)
   - `district` = `properties.sggnm`
   - `geom` = GeoJSON geometry → WKT 문자열 (shapely `shape(...).wkt` 또는 수동) → asyncpg 파라미터 바인딩 `$5`로 전달 → SQL은 `INSERT ... VALUES ($1, $2, $3, $4, ST_GeomFromText($5, 4326), ...)` 형태. **f-string으로 WKT를 쿼리에 박는 것 절대 금지** (불변식 #8)
   - 배치 insert (100건 batch, asyncpg)
   - ON CONFLICT 없음 (clean insert 전제, 이미 §A에서 부재 확인)
10. sisyphus-junior spawn — 스크립트 dry-run (`--dry-run` 플래그) + 첫 3 feature 샘플 출력, 실제 insert는 수행 안 함
11. 메인 Claude 승인 후 실제 실행 → 427 row insert 확인
12. **Zero-Trust 검증**: `SELECT COUNT(*) FROM administrative_districts` = 427 + `SELECT COUNT(*) WHERE geom IS NOT NULL` = 427 + `SELECT DISTINCT district ORDER BY district` = 25개 자치구 + `SELECT ST_IsValid(geom) FROM ... LIMIT 10` 모두 true

### §E ETL 스크립트 — population_stats (g5 — hephaestus 위임)

13. **hephaestus spawn** — `backend/scripts/etl/load_population_stats.py` 작성:
    - CSV 스트리밍 read (`csv.reader` + `utf-8-sig`)
    - 각 행: `기준일ID`(YYYYMMDD) → DATE / `시간대구분`(00~23 str) → SMALLINT / `행정동코드` → VARCHAR(20) / `총생활인구수` → INTEGER(반올림) / 나머지 29 컬럼 → raw_data JSONB
    - **mismatch 9건 skip**: 사전 빌드한 `valid_codes: set[str]` (415건, administrative_districts에서 SELECT로 로드)에 없으면 skip + `skipped_count` 집계
    - 1000건 batch `executemany` insert
    - 진행률 5% 단위 로깅
    - **종료 직전 stdout 마지막 라인에 `SKIP_COUNT=<n>` 고정 포맷 출력** (Momus Mo5a, §5.2 검증 재현성)
14. sisyphus-junior spawn — 스크립트 dry-run (첫 100행만 읽고 parsing 결과 검증, insert 안 함)
15. 메인 Claude 승인 후 실제 실행 → **약 278,881행 insert 예상 (284,929 − 6,048 skip, 9 코드 × 24 시간대 × 28 일)** (Momus Mo6b)
16. **Zero-Trust 검증**:
    - `SELECT COUNT(*) FROM population_stats` ≈ 278,881 (±1% 허용)
    - `SELECT COUNT(DISTINCT adm_dong_code) FROM population_stats` = 415
    - `SELECT MIN(base_date), MAX(base_date)` = (2026-02-01, 2026-02-28)
    - `SELECT COUNT(*) FROM population_stats WHERE raw_data IS NULL` = 0
    - FK 무결성: `SELECT COUNT(*) FROM population_stats p LEFT JOIN administrative_districts a USING(adm_dong_code) WHERE a.adm_dong_code IS NULL` = 0
    - skip 카운트 ≈ 6,048 (9 × 24 × 28) 로그 확인

### §F Oracle 진단 + mismatch 기록 (g6 — oracle 위임)

17. **oracle spawn** — 적재 후 DB 상태 진단. 과업: (a) 19 불변식 관련 테이블 컬럼 현황 스캔 (Read 기반 information_schema 사전 dump 파일), (b) 9건 mismatch 원인 추정 + 후속 plan 제안 리포트 작성. postgres MCP는 현재 미노출 — §부록 3 대응 방식으로 진행.
    - **fallback**: oracle이 postgres MCP 미제공을 보고하면, 메인 Claude가 postgres MCP로 information_schema를 dump → `/tmp/db_state_post_plan7.json` 파일로 저장 → oracle에 해당 파일 Read 위임
18. mismatch 9건을 `.sisyphus/notepads/issues.md`에 append (후속 plan `2026-04-13-admin-code-reconcile` 트리거)

### §G 노트패드 + 메모리 반영 (g7)

19. `.sisyphus/notepads/verification.md` append — 워커 spawn 결과 + Zero-Trust 실측 수치 + CSV 수집 게이트 정상 작동 기록
20. `.sisyphus/notepads/learnings.md` append — 검증 게이트 첫 실전 사용 learning: "외부 수급 데이터는 샘플 코드 매핑 검증이 스키마 검증보다 선행되어야 함" + 기타 발견
21. `.sisyphus/notepads/decisions.md` append — 3 결정 기록 (데이터 소스 / geom 포함 / mismatch skip+후속)
22. `memory/project_db_state_2026-04-10.md` **기존 파일 내용만 갱신** (Metis bonus-2, destructive rename 회피). 파일명은 역사적 slug로 유지하되 frontmatter `description` 필드를 2026-04-12 기준으로 교체 + 본문 테이블에 administrative_districts 427행 / population_stats 약 278,881행 / 9건 mismatch 메타 행 추가. `MEMORY.md` 인덱스의 해당 행 설명도 2026-04-12 기준으로 업데이트.
23. `memory/project_phase_boundaries.md` → "ETL blocker 해제 (administrative_districts + population_stats)" 마크
24. `memory/MEMORY.md` 인덱스 — 해당 행 업데이트

### §H Metis/Momus 리뷰 (g8)

25. Metis subagent 호출 → `reviews/001-metis-{verdict}.md`
26. Momus subagent 호출 → `reviews/002-momus-{verdict}.md`
27. 리뷰 통과 시 §7 APPROVED 마크

### §I Atlas 의존성 맵 자동 작성 (g9)

28. APPROVED 직후 atlas 진정 spawn 자동 호출 → `.sisyphus/dependency-maps/2026-04-12-erd-etl-blockers.md` 생성

### §J 검증 + 종료 (g10)

29. `validate.sh` 6단계 통과 확인 (마이그레이션 추가로 인한 회귀 없음)
30. `boulder.json` status → `complete`, plan #8 진입점 기록
31. plan.md 헤더 상태 → COMPLETE

## 5. 검증 계획

### 5.1 validate.sh 6/6 통과

기본 조건. 새 Python 스크립트 2개는 ruff + pyright 통과해야 함.

### 5.2 Zero-Trust DB 실측 (postgres MCP 또는 psql 직접)

| 항목 | 기대값 | 허용 오차 |
|---|---|---|
| `administrative_districts` row count | 427 | 0 |
| `administrative_districts` DISTINCT district | 25 | 0 |
| `administrative_districts` geom NOT NULL | 427 | 0 |
| `administrative_districts` ST_IsValid 샘플 10건 | all true | 0 |
| `population_stats` row count | ~278,881 | ±1% |
| `population_stats` DISTINCT adm_dong_code | 415 | 0 |
| `population_stats` base_date 범위 | 2026-02-01 ~ 2026-02-28 | 0 |
| `population_stats` raw_data NULL 개수 | 0 | 0 |
| FK 무결성 orphan | 0 | 0 |
| skip 카운트 로그 | ~6,048 | ±100 |

### 5.3 Smoke 시나리오 (수동)

```sql
-- 시나리오 A: 행정동 이름으로 인구 조회
SELECT a.adm_dong_name, a.district, SUM(p.total_pop) as pop_sum
FROM administrative_districts a
JOIN population_stats p USING(adm_dong_code)
WHERE a.district = '강남구' AND p.time_slot = 18 AND p.base_date = '2026-02-15'
GROUP BY a.adm_dong_name, a.district
ORDER BY pop_sum DESC LIMIT 5;

-- 시나리오 B: 장소 좌표 → 행정동 (ST_Contains)
SELECT p.name, a.adm_dong_name
FROM places p
JOIN administrative_districts a
  ON ST_Contains(a.geom, ST_Transform(p.geom, 4326))
WHERE p.name LIKE '%스타벅스%' LIMIT 5;

-- 시나리오 C: FK RESTRICT 작동
DELETE FROM administrative_districts WHERE adm_dong_code = '11110515';
-- 기대: ERROR -- violates foreign key constraint (만약 해당 코드에 population 데이터 있으면)
```

### 5.4 단위 테스트

본 plan은 **ETL + 마이그레이션**이라 단위 테스트 대신 **적재 후 DB 쿼리 assertion**으로 검증. pytest 신규 케이스는 생성하지 않음 (기존 프로젝트에 ETL 유닛 테스트 패턴 없음 + 데이터베이스 상태 변경이라 integration 성격).

### 5.5 검증 게이트 재확인

적재 **직전** oracle 또는 메인 Claude가 postgres MCP로 현재 상태를 한 번 더 실측 → 예상 beforestate와 일치 확인 후 `psql` 실행. 불일치 시 즉시 abort + 사용자 보고.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석, 갭·AI Slop·오버엔지니어링): `reviews/001-metis-*.md` (대기)
- Momus (엄격한 검토, 체크리스트·파일 경로·검증 가능성): `reviews/002-momus-*.md` (대기)

## 7. 최종 결정

**APPROVED** (2026-04-12)

- Metis 1차: `okay` (M1-M5 + bonus 2건) → `reviews/001-metis-okay.md` (agentId `a08acdeff1d3eb7aa`)
- Momus 1차: `okay` (Mo6a factual + Mo2a/Mo3a/Mo5a/Mo6b minor 4건) → `reviews/002-momus-okay.md` (agentId `a993011897fd7e4fd`)
- 메인 Claude 반영: 7+5 = 총 12건 전부 반영
- Momus 재리뷰: `approved` → `reviews/003-momus-approved.md` (agentId `a20fa97422f1214eb`)
- 다음: Atlas 진정 spawn → `.sisyphus/dependency-maps/2026-04-12-erd-etl-blockers.md` 생성 → 사용자 최종 승인 → 실행 진입 (옵션 α 재시작 여부 사용자 확인 필요)

---

## 부록 1. 수집 게이트 증거 (프로파일링 요약)

**2026-04-12 완료**. 자세한 출력은 세션 대화 기록 참조.

| 항목 | 값 |
|---|---|
| GeoJSON 소스 | `vuski/admdongkor` ver20260201 (2026-02-01 기준) |
| 파일 크기 | 33 MB |
| 전국 features | 3,558 |
| 서울 features | 427 (ERD 권위 "서울 427개"와 정확 일치) |
| Geometry type | MultiPolygon, WGS84 (EPSG:4326) |
| 생활인구 CSV 경로 | `csv_data/생활인구 통계/행정동 단위 서울 생활인구(내국인)(CSV)(API)(202603)/행정동 단위 서울 생활인구(내국인)202603.csv` |
| 생활인구 CSV 크기 | 284,929 행 |
| 생활인구 CSV 인코딩 | UTF-8 BOM |
| 생활인구 CSV 유니크 코드 | 424 |
| 생활인구 CSV 날짜 범위 (실측, Metis M3) | **min 20260201 / max 20260228 / 28일** |
| GeoJSON 경로 | `data_external/행정구역_geojson/HangJeongDong_ver20260201.geojson` |
| 매핑 키 | **CSV `행정동코드` ↔ GeoJSON `adm_cd2[:8]`** (앞 8자리) |
| 매핑 정합률 | **415/424 = 97.9%** |
| CSV-only 코드 (적재 skip) | 9건 — 강동 1 / 성북 6 / 강남 1 / 송파 1 |
| GeoJSON-only 코드 | 12건 (administrative_districts에는 들어가지만 인구 없음 — OK) |
| 라이선스 | MIT (repo) + 공공누리 제1유형 (원천 행정안전부) |
| 사용자 승인 | 2026-04-12 완료 ("가로 가자") |

## 부록 2. ERD docx 내부 충돌 해소 (불변식 #19)

**충돌**: ERD v6.1 `§4.4 행정동` 본문 — *"실제 운영 DB에서는 PostGIS MultiPolygon geom 칼럼이 포함되어 ST_Contains 공간 쿼리로 장소→행정동 매핑에 사용된다"*. 컬럼 표(Table 5) — adm_dong_code / adm_dong_name / district / created_at / updated_at **5개만**, geom 없음.

**해소 방침**:
- 본문은 "실제 운영 DB" 요구사항을 명확히 진술 → **본문이 권위**
- 컬럼 표는 v5 이전 레거시 또는 타이핑 누락으로 판단
- 본 plan은 **본문 권위 따름**: DDL에 `geom geometry(MultiPolygon, 4326)` 포함
- 후속: **`2026-04-14-erd-docx-v6.3` 경량 plan**으로 docx 컬럼 표에 geom 행 추가 (문서 작업, DDL 무관)

**Phase 라벨**: 본 plan은 P1 (ETL blocker) + Infra. ERD docx 수정은 별도 plan.

## 부록 3. Oracle postgres MCP 미노출 대응

**배경**: plan #6 §E step 17(a)에서 oracle subagent가 `mcp__postgres__query` tool 미노출로 postgres 실측 실패. 원인은 Claude Code의 session-start-only frontmatter 로드 (issues.md 2026-04-12 엔트리).

**oracle.md 현재 상태**: frontmatter에 `mcp__postgres__query` 이미 추가됨 (2026-04-12). 단 현 세션은 반영 전 상태로 로드됨.

**본 plan 대응 옵션**:
- **(α)** 본 plan 실행 전 Claude Code 재시작 → oracle spawn 시 postgres MCP 자동 노출 → §F step 17 정상 실행. **권장** (plan #6에서 재시작이 이미 검증된 프로토콜).
- **(β)** 재시작 없이 진행 → oracle은 Read-only 진단만 수행 → postgres MCP 실측은 **메인 Claude**가 직접 대행 → 결과를 `/tmp/db_state_post_plan7.json`으로 덤프 → oracle에 Read 위임.

**최종 선택**: Atlas 의존성 맵 작성(§I step 28) 직후, 사용자에게 (α)/(β) 확인 후 실행 진입. 재시작이 짧고 안전하므로 (α) 기본값.

## 부록 4. 진정 워커 분담 매트릭스 (plan #6 첫 실전)

| step | 카테고리 | 담당 | 이유 |
|---|---|---|---|
| 6 | db-migration | **hephaestus** | 복합 로직 + 트랜잭션 + FK 설계 |
| 9 | db-migration | **hephaestus** | PostGIS geometry 인코딩 + 배치 insert |
| 10 | quick | **sisyphus-junior** | dry-run 유틸 |
| 13 | db-migration | **hephaestus** | CSV 스트리밍 + mismatch 필터 + batch |
| 14 | quick | **sisyphus-junior** | dry-run 유틸 |
| 17 | ultrabrain | **oracle** | 19 불변식 진단 (postgres MCP 관점) |
| 25 | — | **metis** | 전술적 분석 |
| 26 | — | **momus** | 엄격한 검토 |
| 28 | — | **atlas** | 의존성 맵 |

**메인 Claude 직접 수행 step** (Momus Mo3a): **step 1-5** (§A 사전검증 + §B SOURCE.md), **step 7-8** (SQL 리뷰 + psql 실행 + Zero-Trust), **step 11-12** (승인 + administrative_districts 실행 + 검증), **step 15-16** (승인 + population_stats 실행 + 검증), **step 18** (issues.md append), **step 19-24** (§G 노트패드·메모리 반영 전체), **step 27** (APPROVED 마크), **step 29-31** (§J 종료). 총 subagent spawn 9건 외 모든 step.

**병렬 가능성**: g3(§C DDL)은 g4/g5(§D/§E ETL) 선행 차단. g4와 g5는 **원칙적으로 병렬 가능**이나 배치 DB 쓰기가 서로 다른 테이블이라도 **단일 Claude Code 세션이 순차 spawn**이 안전 (plan #6 §E에서 확립). Atlas 의존성 맵이 최종 확정.

**총 예상 spawn**: hephaestus 3 + sisyphus-junior 2 + oracle 1 + metis 1 + momus 1 + atlas 1 = **9 spawn**. plan #6(6 spawn)의 1.5배로 진정 워커 시스템의 실전 부하 첫 측정.

## 부록 5. 위험 + 완화

| 위험 | 완화 |
|---|---|
| GeoJSON MultiPolygon 파싱 라이브러리 버전 호환 | asyncpg가 PostGIS geometry 바이너리 직접 지원 안 할 경우 `ST_GeomFromText(WKT, 4326)` fallback (표준 패턴) |
| 33 MB 파일 메모리 로드 | 전체 로드 수용 가능 (venv 메모리 충분). 스트리밍 필요 시 `ijson` 도입 (현재 불필요 판단) |
| 적재 중간 실패 → partial state | 각 테이블 단위 트랜잭션 + 실패 시 `TRUNCATE` 재실행 가능. **한정구 (Metis bonus-1)**: TRUNCATE는 **본 plan 초기 ETL 적재 단계에 한정** 허용. 운영 phase 이후 population_stats에 대한 TRUNCATE/DELETE/UPDATE는 불변식 #3 위반이며 금지. hephaestus spawn prompt와 스크립트 주석에 이 한정구 명시 필수. |
| 9건 mismatch가 실제로는 10건 이상 (측정 누락) | 스크립트가 skip 시 코드별 집계 로그 출력, 예상 9건과 불일치하면 즉시 abort |
| 재시작 후 세션 상태 상실 | boulder.json + resume 메모리로 복원, plan #6 패턴 재사용 |
| ERD docx v6.3 bump 지연 → 코드·문서 불일치 | 본 plan §부록 2에서 명시 + 후속 plan slug 예약 → tracking 가능 |
| plan #6 인프라 실전 부하 | 9 spawn이 하루 토큰 예산 내 수용 가능 (plan #6이 6 spawn 검증됨) |

## 부록 6. 후속 plan 트리거

본 plan COMPLETE 후 자동 진입 가능 plan (우선순위 순):

1. **`2026-04-13-admin-code-reconcile`** (9건 mismatch 정식 해소) — 행안부 코드 변경 이력 수급 + 6천행 재처리
2. **`2026-04-14-erd-docx-v6.3`** (ERD docx 컬럼 표 geom 행 추가) — 경량 문서 작업
3. **`2026-04-15-intent-crowdedness`** (LangGraph CROWDEDNESS 노드 구현) — P2 기능
4. **`2026-04-13-harness-phase6-kairos-cicd`** (하네스 Phase 6) — 이번 plan의 learnings가 Auto Dream 첫 재료
