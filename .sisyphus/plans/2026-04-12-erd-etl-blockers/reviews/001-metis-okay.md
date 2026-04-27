# 001 Metis Review — plan #7 erd-etl-blockers

- 대상: `.sisyphus/plans/2026-04-12-erd-etl-blockers/plan.md`
- 검토자: Metis (전술적 분석)
- 일자: 2026-04-12
- 판정: **okay** (minor 5건 + bonus 2건, block 0건)
- agentId: `a08acdeff1d3eb7aa`
- duration: 140.6s, tokens: 33,232

## 종합

plan은 6 영역 모두 합리적 수준을 충족한다. 검증 게이트 증거(§부록 1), 19 불변식 체크(§3), Zero-Trust 실측 표(§5.2), 진정 워커 분담 매트릭스(§부록 4), ERD 내부 충돌 해소 근거(§부록 2), Oracle MCP α/β 대응(§부록 3)까지 필요한 모든 축이 문서화되어 있다. Momus로 넘길 준비 됨. 다만 아래 5건은 실행 전 메인 Claude가 명확히 해두면 실행 중 혼선이 준다.

## 6 영역 분석

### 1. 갭 (Gap)

- **M1 geom NULL 허용 vs Zero-Trust 기대값 충돌**: §2.3 DDL 주석에 *"NULL 허용 (9건 추정 확장 대비)"* 라고 되어 있으나 §5.2 검증 표는 `geom NOT NULL = 427, 허용 오차 0`을 요구한다. 본 plan의 427건은 GeoJSON feature 기반이라 전부 geom이 채워진다. NULL 허용을 둔 이유가 후속 plan(admin-code-reconcile)의 전제인지, 단순 방어인지 불명확.
- **M2 생활인구 CSV 파일 경로가 §2.1 신규/수정 파일 목록에 없음**: §4 step 13은 CSV를 스트리밍 읽지만 파일 경로가 plan 어디에도 명시되지 않았다. hephaestus가 스크립트 작성 시 경로를 추측하게 된다. §부록 1이 "284,929 행 / UTF-8 BOM"만 기재하고 경로는 빠졌다.
- **M3 적재 기간 가정 검증**: §5.2는 `base_date 범위 = 2026-02-01 ~ 2026-02-28`을 0 허용 오차로 못 박았다. 그러나 §부록 1은 CSV 전체 행 수(284,929)만 보고할 뿐 날짜 범위를 실측 증거로 제시하지 않았다. 검증 게이트 규약상 가정이 아니라 **실측**이어야 한다.
- **M4 ETL 스크립트 실행 커맨드 표준**: hephaestus가 3번 spawn되는데 세 스크립트의 실행 방식(`python -m backend.scripts.etl.load_...` vs `python backend/scripts/etl/...`)이 통일되지 않았다. `backend/` 는 별도 git repo이므로 PYTHONPATH·cwd 가 어디인지 step에 명시해 두면 dry-run 재현성이 높아진다.

### 2. 숨은 의도

plan은 요구사항 1.1(ETL blocker 해제) + 1.2(plan #6 워커 실전 투입) 두 축을 명시적으로 분리하고, 각 step에 카테고리 라벨까지 매핑(§부록 4)하여 숨은 의도가 표면화되어 있다. 하나 지적:

- **M5 "검증 게이트 첫 실전"이 숨어 있음**: 본 plan이 `feedback_etl_validation_gate.md` 정책의 **첫 준수 사례**라는 점이 §1.3 단 한 줄과 §부록 1로 분산되어 있다. §1.2에 "하네스 목표" 항목이 있듯이 "검증 게이트 첫 실전"을 §1.2 또는 §1.3에서 나란히 병기하면, 후일 Auto Dream이 "plan #7 = 두 인프라의 첫 실전"이라는 이중 의의를 학습 재료로 정확히 집는다.

### 3. AI Slop

- 부록 6종은 모두 실질적 근거 문서. 장식적 요소 없음.
- 단, **§부록 5 위험 3 "TRUNCATE가 append-only 원칙 위반 아님"** 서술은 불변식 해석 논쟁을 초대할 수 있는 표현. 불변식 #3은 런타임 UPDATE/DELETE 금지이고, 초기 ETL 적재 실패 시 TRUNCATE는 운영 규약상 허용되지만 plan 본문이 사후적 판례가 되어 향후 "TRUNCATE 언제나 OK"로 확장 해석될 위험. Momus 영역과 겹치니 한 줄 플래그만 남긴다.

### 4. 오버엔지니어링

- §2.3 DDL의 `ON DELETE RESTRICT`는 불변식 #4(마스터 소프트 삭제 대신 명시적 보호)와 정합하므로 합당.
- `idx_pop_stats_adm_time` + `idx_pop_stats_base_date` 두 인덱스는 CROWDEDNESS intent 쿼리 패턴 두 가지를 커버 + 날짜 범위 조회용. 오버 아님.
- **미래 플래그 없음**, **추측성 추상화 없음**. Step granularity B를 정직히 따른다.

### 5. 19 불변식 위반 위험

- **#3 append-only**: DDL은 준수. 단 §부록 5 위험 3의 TRUNCATE 언급이 플래그. 스크립트 내부에 `DELETE FROM population_stats` 같은 재실행 대비 코드가 슬그머니 들어갈 여지. hephaestus spawn 시 "DELETE 금지, 재실행 필요 시 TRUNCATE만" 명문화 필요.
- **#8 asyncpg 파라미터 바인딩**: §3 체크만 있고 `ST_GeomFromText($1, 4326)` 같은 실제 패턴 예시가 step 9에 없다. PostGIS WKT 삽입 시 f-string으로 WKT 문자열을 쿼리에 박을 유혹이 크다.
- **#1 PK 이원화**: 준수.
- **#5 비정규화 화이트리스트**: `*.raw_data` 포괄 규정에 population_stats.raw_data 포함. 안전.

### 6. 검증 가능성

- Step 5-8, 12, 16은 모두 SQL assertion이 실측 수치로 표현되어 검증 가능.
- Step 22의 `project_db_state_2026-04-10.md → 2026-04-12.md rename` 분기(rename = destructive)는 실행 시 혼선 요소. **"기존 파일 업데이트 + MEMORY.md 인덱스의 날짜 슬러그 수정"** 하나로 통일하는 게 깔끔 (rename은 destructive ops isolation 룰과도 마찰).

## 지적 요약

| ID | 영역 | 한 줄 |
|---|---|---|
| M1 | 갭 | geom NULL 허용 vs Zero-Trust 기대값 일치성 설명 |
| M2 | 갭 | 생활인구 CSV 파일 경로가 §2.1/§부록 1에 누락 |
| M3 | 갭 | CSV 날짜 범위가 검증 게이트 증거에 실측 형태로 기록 안 됨 |
| M4 | 갭 | ETL 스크립트 실행 cwd/모듈 경로 표준 부재 |
| M5 | 숨은 의도 | "검증 게이트 첫 실전" 이중 의의를 §1.2/1.3에 병기 권장 |
| Bonus-1 | Slop/해석 | §부록 5 TRUNCATE 서술을 "본 plan ETL 실패 시 한정" 한정구 추가 |
| Bonus-2 | 검증가능성 | Step 22 rename 분기를 "업데이트만"으로 단일화, destructive 회피 |

## 권고 수정 (block 없음, Momus 이전 반영 선택)

1. **M1**: §2.3 DDL 주석을 *"NULL 허용 — 후속 plan admin-code-reconcile에서 행안부 코드만 있는 행정동 row를 geom 없이 선등록 가능성 대비"* 또는 *"NOT NULL로 변경"* 중 하나로 확정.
2. **M2**: §2.1에 CSV 절대 경로 1줄 추가. §부록 1에 같은 경로 병기.
3. **M3**: §부록 1에 "CSV min/max 기준일ID = 20260201/20260228 (실측)" 한 줄.
4. **M4**: §4 §C 바로 앞에 "모든 ETL 스크립트 실행: `cd backend && source venv/bin/activate && python -m scripts.etl.<name>`" 규약 한 줄.
5. **M5**: §1.2 또는 §1.3 상단 한 문장 추가. (선택)
6. **Bonus**: step 22의 rename 분기를 "업데이트만" 하나로 확정. §부록 5 위험 3의 TRUNCATE 표현을 "본 plan ETL 실패 시 한정, 운영 phase 이후 금지" 한정구 추가.

## Momus 대상 영역 (Metis 미침범)

- 체크리스트 형식 엄격성 (19 항목 체크 X/O 표기 일관성)
- 파일 경로 절대/상대 일관성
- 템플릿 양식 충실도
- 실행 step numbering 연속성

## 판정

**okay** — M1~M5 + bonus 반영은 선택. Momus로 진행 가능. plan #6 인프라 + 검증 게이트 정책의 첫 실전이라는 이중 부하에도 불구하고 갭 누락은 경미한 명시성 부족뿐이며 19 불변식 위반 씨앗도 명시적으로 플래그되어 있다. 6개월 뒤 회고 시 "왜 이걸 여기 넣었지?"라고 후회할 구조적 결정은 발견되지 않았다.
