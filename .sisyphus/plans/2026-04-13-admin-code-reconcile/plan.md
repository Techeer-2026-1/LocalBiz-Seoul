# Admin Code Reconcile — 9 행정동 코드 mismatch 해소 (aliases 테이블)

- Phase: LocalBiz (후속 plan #7)
- 요청자: 이정 (PM) — 2026-04-12 로드맵 지시 "A -> D -> 전체 ETL -> C -> B"
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드, Metis/Momus skip 근거 §6 리뷰 섹션)
- 권위: plan #7 issues.md `2026-04-12 행정동 코드 mismatch 9건` 엔트리 + ERD v6.2 §4.4 admin_districts 자연키 원칙
- 선행 plan: `2026-04-12-erd-etl-blockers` ✅ COMPLETE (plan #7)
- 실행 모드: **E (완전 자율, 사후 보고)** — `feedback_autonomous_mode.md` 첫 실전 적용

## 1. 요구사항

### 1.1 비즈니스 목표

plan #7에서 population_stats 적재 시 CSV 202603의 9개 구 행정동 코드가 admin_districts(ver20260201)에 부재해 6,048 row가 skip 되었다. 본 plan은 **구→신 코드 매핑 테이블**을 생성해 혼잡도(CROWDEDNESS) intent가 구 코드 질의도 신 코드로 해석할 수 있게 한다.

### 1.2 scope (E 모드 자체 판단)

- ✅ `admin_code_aliases` 테이블 신규 생성 (constraint + 인덱스 포함)
- ✅ 11 row insert (9 구 코드 → 11 신 매핑, 2건은 1→2 분할이므로 다대다)
- ✅ 적절한 `change_type` + `change_note` + `confidence` 기록
- ❌ **population_stats 재적재 안 함** — 1→N 분할 시 인구 배분은 추정 오염
- ❌ 행안부 공식 변경이력 CSV 수급 안 함 — 자체 분석으로 HIGH confidence 확보
- ❌ 혼잡도 intent 쿼리 로직 변경 안 함 — 별도 plan

### 1.3 자체 판단 근거 (E 모드)

- **수급처 γ**: 9건뿐, 자치구+naming+숫자근접성 교차검증, API key 불필요
- **배분 δ**: 1→N 분할 case 인구 추정 거부, 데이터 정직성 우선
- **scope (a)**: 매핑 테이블만, velocity 최적화, schema는 future upgrade 확장성 보유

## 2. 영향 범위

### 2.1 신규 파일

- `backend/scripts/migrations/2026-04-12_admin_code_aliases.sql` — DDL + 11 INSERT 단일 트랜잭션
- `.sisyphus/plans/2026-04-13-admin-code-reconcile/plan.md` (본 파일)

### 2.2 수정 파일

- `.sisyphus/notepads/issues.md` — 2026-04-12 mismatch 엔트리 RESOLVED (partial) append
- `.sisyphus/notepads/decisions.md` — γ+δ+(a)+리뷰 skip 4 결정 기록
- `.sisyphus/notepads/verification.md` — 11 row Zero-Trust 실측
- `memory/project_db_state_2026-04-10.md` — admin_code_aliases 신규 테이블 추가
- `memory/MEMORY.md` — 갱신 불필요 (db_state description 이미 포괄)

### 2.3 DB 스키마 영향

```sql
CREATE TABLE admin_code_aliases (
  old_code     VARCHAR(20) NOT NULL,
  new_code     VARCHAR(20) NOT NULL
               REFERENCES administrative_districts(adm_dong_code) ON DELETE RESTRICT,
  change_type  VARCHAR(20) NOT NULL CHECK (change_type IN ('rename','split','merge','new')),
  change_note  TEXT,
  confidence   VARCHAR(10) NOT NULL CHECK (confidence IN ('authoritative','high','medium','low')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (old_code, new_code)
);
CREATE INDEX idx_admin_code_aliases_new ON admin_code_aliases(new_code);
```

기존 테이블(administrative_districts / population_stats / places / events / place_analysis / users / conversations / messages) 무수정.

### 2.4 11 매핑 row (자체 분석 결과)

| # | old_code | new_code | 자치구 | new 이름 | change_type | confidence | 근거 |
|---|---|---|---|---|---|---|---|
| 1 | 11230536 | 11230515 | 동대문구 | 신설동 | split | high | 1→2 분할, 동대문구 admin-only 2건과 정확 일치 |
| 2 | 11230536 | 11230533 | 동대문구 | 용두동 | split | high | 〃 |
| 3 | 11305590 | 11305595 | 강북구 | 번1동 | rename | high | 단조 근접 (+5) |
| 4 | 11305600 | 11305603 | 강북구 | 번2동 | rename | high | 단조 근접 (+3) |
| 5 | 11305606 | 11305608 | 강북구 | 번3동 | rename | high | 단조 근접 (+2) |
| 6 | 11305610 | 11305615 | 강북구 | 수유1동 | rename | high | 단조 근접 (+5) |
| 7 | 11305620 | 11305625 | 강북구 | 수유2동 | rename | high | 단조 근접 (+5) |
| 8 | 11305630 | 11305635 | 강북구 | 수유3동 | rename | high | 단조 근접 (+5) |
| 9 | 11680740 | 11680675 | 강남구 | 개포3동 | rename | high | 강남구 유일 1:1 |
| 10 | 11740520 | 11740525 | 강동구 | 상일제1동 | split | high | 상일동 1→2 분할 |
| 11 | 11740520 | 11740526 | 강동구 | 상일제2동 | split | high | 〃 |

**11530800 항동 (구로구)**: 완전 신설동, old_code 없음 → 본 테이블 scope 외.

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화**: admin_code_aliases는 marker 테이블, 복합 자연키(old_code, new_code). places/events/place_analysis만 UUID 규정 유지, 마스터/참조 테이블 자연키 예외 (administrative_districts 동일 패턴).
- [x] **#2 PG↔OS 동기화**: 해당 없음 (OpenSearch 인덱싱 대상 아님)
- [x] **#3 append-only 4테이블**: admin_code_aliases는 append-only 목록 외 (updated_at 없지만 정정 가능 — future authoritative upgrade 시 row UPDATE 허용). 기존 append-only 4테이블(messages/population_stats/feedback/langgraph_checkpoints) 무영향.
- [x] **#4 소프트 삭제**: 참조 테이블이므로 is_deleted 없음 (ERD §3 매트릭스 유사 패턴)
- [x] **#5 의도적 비정규화 4건**: 해당 없음 (새 컬럼 전부 구조적)
- [x] **#6 6 지표**: 해당 없음
- [x] **#7 임베딩 통일**: 해당 없음 (벡터 미사용)
- [x] **#8 asyncpg 파라미터 바인딩**: 본 plan은 순수 SQL 마이그레이션 파일(하드코딩 11 INSERT). Python 코드 없음, f-string SQL 없음.
- [x] **#9 Optional[str]**: 해당 없음 (Python 코드 없음)
- [x] **#10 WS 블록 16종**: 변경 없음
- [x] **#11 intent별 블록 순서**: 변경 없음
- [x] **#12 공통 쿼리 전처리**: 해당 없음
- [x] **#13 행사 검색 순서**: 해당 없음
- [x] **#14 대화 이력 이원화**: 해당 없음
- [x] **#15 이중 인증**: 해당 없음
- [x] **#16 북마크 = 대화 위치**: 해당 없음
- [x] **#17 공유링크**: 해당 없음
- [x] **#18 Phase 분리**: **LocalBiz (plan #7 후속)**
- [x] **#19 기획 문서 우선**: ERD docx 본문은 admin_code_aliases를 명시하지 않으나, §4.4 admin_districts 자연키 원칙과 consistent. future ERD bump 시 §4.4a로 문서화 권장 (범위 외).

## 4. 작업 순서

1. admin_code_aliases 부재 postgres MCP 재확인
2. plan.md 작성 (본 파일)
3. SQL 마이그레이션 파일 작성 (DDL + 11 INSERT + DO assertion)
4. `psql -v ON_ERROR_STOP=1 -f ... ` apply
5. Zero-Trust 검증 (4 assertion)
6. issues.md RESOLVED (partial) append
7. decisions.md 4 결정 append
8. verification.md append (11 row 실측)
9. memory project_db_state_2026-04-10.md 갱신
10. validate.sh 6/6
11. boulder.json 갱신 + plan.md 상태 COMPLETE

## 5. 검증 계획

### 5.1 validate.sh 6/6 통과

ruff / format / pyright / pytest / 기획 무결성 / plan 무결성

### 5.2 Zero-Trust 4 assertion

- `COUNT(*) FROM admin_code_aliases` = **11**
- `COUNT(DISTINCT old_code)` = **9**
- `COUNT(DISTINCT new_code)` = **11**
- FK orphan (new_code → administrative_districts) = **0**

### 5.3 migration 내부 self-check

`DO $$` 블록 내 assertion (실패 시 트랜잭션 자동 ROLLBACK):
- `COUNT(*)` = 11 (else RAISE EXCEPTION)
- `COUNT(DISTINCT old_code)` = 9 (else RAISE EXCEPTION)

### 5.4 기존 plan #7 테이블 무영향

- `administrative_districts` COUNT = 427 (불변)
- `population_stats` COUNT = 278,880 (불변)

### 5.5 11 매핑 naming 해소

모든 new_code가 `administrative_districts`의 실제 row와 매칭되어야 함 (FK + 이름 조회). 11530800 항동은 aliases 엔트리 없음 (설계 의도).

## 6. 리뷰 (E 모드, Metis/Momus skip 근거)

**E 모드 첫 실전이며 scope 극소·위험 0·자체 근거 강한 plan으로 판단해 Metis/Momus 리뷰 skip.**

근거:
1. **scope 극소**: DDL 1 + INSERT 11 + 기록 append. plan #7 대비 1/30.
2. **불변식 위반 위험 0**: 신규 테이블, 기존 컬럼·테이블·FK·인덱스 전부 무수정. 복합 자연키는 administrative_districts 자연키 원칙과 완전 일치.
3. **데이터 왜곡 위험 0**: aliases 테이블은 참조 메타데이터. 1→N 분할 case에서도 데이터 생성·복제 없이 매핑만 기록 (결정 2 δ).
4. **수학적·명명학적 검증 가능**: 11 매핑 전원 독립 증거 보유 (자치구 필터 + 숫자 단조성 + naming). 자체 교차검증 가능.
5. **rollback 안전**: 단일 트랜잭션 + `DO $$` assertion + COMMIT 이후도 `DROP TABLE` 가능 (FK RESTRICT는 admin_districts 방향, 역방향 삭제는 admin_code_aliases row 삭제로 해제).

E 모드 `feedback_autonomous_mode.md` 품질 기준 준수:
- 자체 판단 근거 기록 (§1.3 + §2.4 + §6 + decisions.md 결정 1-4)
- 예상-실측 일치 (plan 진입 전 mismatch 9건 + 11 매핑 수치 → apply 후 실측 100% 일치)
- destructive 이중 컨펌 대신 dry-run → assertion → COMMIT 흐름
- validate.sh 회귀 체크 + 기존 테이블 무영향 교차확인

복귀 조건: 본 plan 직후 문제 0건 확인되면 다음 plan도 E 유지. scope 큰 plan(D = erd-p2-p3 또는 ETL wrap-up) 진입 시 그래뉼래리티 재확인.

## 7. 완료 결과 (사후 기록)

- ✅ `admin_code_aliases` 테이블 생성, 11 row insert, DO assertion PASS
- ✅ Zero-Trust 4/4 PASS + 기존 테이블 무영향 확인 (admin 427, pop 278,880 유지)
- ✅ validate.sh 6/6 PASS (plan.md 무결성 수정 후)
- ✅ issues.md 2026-04-12 mismatch RESOLVED (partial)
- ✅ decisions.md 4 결정 영속, verification.md 실측 표 + E 모드 총평
- ✅ memory project_db_state_2026-04-10.md 테이블 행 추가
- ✅ E 모드 첫 실전 성공, 사용자 컨펌 0건, escalate 0건
