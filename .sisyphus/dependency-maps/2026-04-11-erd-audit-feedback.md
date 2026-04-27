# 의존성 맵: 2026-04-11-erd-audit-feedback

## 헤더

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-11-erd-audit-feedback |
| plan_path | `.sisyphus/plans/2026-04-11-erd-audit-feedback/plan.md` |
| atlas_version | 0.1 |
| 생성일 | 2026-04-11 |
| 작성 | Atlas (self-bootstrap, 메인 Claude 페르소나 채택) |
| 권위 | `.claude/agents/atlas.md` + `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 |
| 시범 목적 | plan #5 (`harness-atlas-only`) 첫 출력 검증용 |

### 통계

| 항목 | 값 |
|---|---|
| 총 atomic step 수 | **21** |
| `visual-engineering` | 0 (FE 작업 없음) |
| `ultrabrain` | 4 (분류표 설계, 흐름도 설계, ERD 정정 분석, 사용자 enum 결정) |
| `deep` | 1 (FK CASCADE smoke test — asyncpg + DB 결합) |
| `quick` | 10 (read-only 검증 + 메모리 갱신 + trace log) |
| `db-migration` | 6 (orphan 검증 + SQL 작성 + dry-run + apply + 컬럼 검증 + row count) |
| `langgraph-node` | 0 (LangGraph 노드 미터치) |
| (sum) | 21 ✓ |
| 그룹 개수 | **7** |
| 병렬 가능 그룹 | **3** (g1, g5, g6) |
| 사용자 검토 의존 그룹 | **1** (g6a 안의 step 14) |

### 3 객관적 검증 기준 (Atlas 자가 적용)

- [x] **(a) 카테고리 매핑 누락 0** — 21/21 step 모두 6 카테고리 중 하나에 매핑됨 ✅
- [x] **(b) depends_on cycle 0** — DAG 형태, cycle 0건 ✅
- [x] **(c) 병렬 후보 group ≥ 1** — 3개 식별 (g1, g5, g6) ✅

→ **3 기준 모두 통과. 사용자 검토 진입 가능.**

---

## Section 1. 카테고리별 step 분류

| id | description (요약) | category | sub_phase | depends_on | parallelizable_with | 비고 |
|---|---|---|---|---|---|---|
| 1 | plan #1 종료 확인 (grep + reviews/) | quick | §A | [] | [2, 3] | read-only |
| 2 | validate.sh baseline | quick | §A | [] | [1, 3] | read-only |
| 3 | trace log 생성 (`~/Desktop/anyway-erd-audit-2026-04-11.txt`) | quick | §A | [] | [1, 2] | file-write |
| 4 | place_analysis 17 row orphan 검증 (postgres MCP) | db-migration | §B | [] | [16, 17] | read-only, 다른 §과 독립 |
| 5 | 17 row place_name + analyzed_at 백업 (trace log append) | quick | §B | [4] | [] | 4의 결과 필요 |
| 6 | 마이그레이션 SQL 파일 작성 (137 lines, 10 DDL) | db-migration | §C | [4, 5] | [16, 17] | file-write |
| 7 | dry-run (`run_migration.py --dry-run`) | db-migration | §D | [6] | [] | DB 연결 X |
| 8 | apply (`run_migration.py`) ⚠️ destructive | db-migration | §D | [7] | [] | **단독 group, 트랜잭션** |
| 9 | postgres MCP 컬럼 검증 (information_schema) | db-migration | §E | [8] | [10, 11] | read-only |
| 10 | row count 회귀 (places=531183 / events=7301 / pa=0) | db-migration | §E | [8] | [9, 11] | read-only |
| 11 | FK CASCADE smoke test (asyncpg + ROLLBACK) | deep | §E | [8] | [9, 10] | Python 코드 + DB |
| 12 | `places.category` 분포 실측 (postgres MCP) | quick | §F | [] | [13, 16, 17] | read-only, §E와 데이터 의존 X |
| 13 | `places.sub_category` 매트릭스 실측 | quick | §F | [] | [12, 16, 17] | read-only |
| 14 | 사용자 enum 검토 (사용자 의존) | ultrabrain | §F | [12, 13] | [] | **사용자 검토 의존**, 비동기 |
| 15 | `기획/카테고리_분류표.md` 작성 (166 lines) | ultrabrain | §F | [14] | [] | 사용자 결정 후 |
| 16 | `기획/thread_id_흐름도.md` 작성 (200+ lines) | ultrabrain | §G | [] | [12, 13, 17] | 독립, 다른 §과 병렬 가능 |
| 17 | langgraph 4 테이블 컬럼 실측 (postgres MCP) | quick | §H | [] | [12, 13, 16] | read-only, 독립 |
| 18 | `기획/ERD_v6.1_to_v6.2_변경사항.md §4` 갱신 | ultrabrain | §H | [17] | [] | 17 결과 필요 |
| 19 | validate.sh post-plan #2 | quick | §I | [8, 15, 16, 18] | [] | 모든 변경 완료 후 |
| 20 | 메모리 갱신 (project_db_state, project_resume) | quick | §I | [19] | [] | |
| 21 | trace log 종료 + plan.md 상태 COMPLETE 마크 | quick | §I | [20] | [] | |

---

## Section 2. 그룹 + 추천 실행 순서

### Group g1: §A 사전검증 (병렬 ✅)

| id | category | description |
|---|---|---|
| 1 | quick | plan #1 종료 확인 |
| 2 | quick | validate.sh baseline |
| 3 | quick | trace log 생성 |

→ **병렬 ✅** (모두 read-only/file-write 독립). 직렬 3 step → 병렬 1 단위.

### Group g2: §B 데이터 검증 (직렬)

| id | category | description |
|---|---|---|
| 4 | db-migration | place_analysis orphan 검증 |
| 5 | quick | 17 row 백업 trace log |

→ 직렬 (5가 4에 의존). 2 step.

### Group g3: §C SQL 작성 (단독)

| id | category | description |
|---|---|---|
| 6 | db-migration | SQL 파일 137 lines 작성 |

→ 단독 1 step.

### Group g4: §D 마이그레이션 적용 (직렬, 🔴 destructive 단독)

| id | category | description |
|---|---|---|
| 7 | db-migration | dry-run |
| 8 | db-migration | **apply** ⚠️ destructive 트랜잭션 |

→ **단독 group, 절대 다른 group과 병렬 금지**. 사용자 이중 컨펌 권고. 2 step.

### Group g5: §E 검증 (병렬 ✅)

| id | category | description |
|---|---|---|
| 9 | db-migration | 컬럼 검증 (information_schema) |
| 10 | db-migration | row count |
| 11 | deep | FK CASCADE smoke test |

→ **병렬 ✅** (모두 step 8 적용 후, 상호 독립). 직렬 3 step → 병렬 1 단위.

### Group g6: §F+§G+§H 문서 작업 (3 sub group 병렬 ✅)

이 group이 plan #2의 **가장 큰 병렬화 기회**.

#### g6a: §F 카테고리 분류표 (직렬, 사용자 검토 의존)

| id | category | description |
|---|---|---|
| 12 | quick | category 분포 실측 |
| 13 | quick | sub_category 매트릭스 실측 |
| 14 | ultrabrain | **사용자 enum 검토** ⏸ 비동기 |
| 15 | ultrabrain | 분류표 작성 |

→ 직렬, 사용자 검토 의존. 4 step.

#### g6b: §G thread_id 흐름도 (단독)

| id | category | description |
|---|---|---|
| 16 | ultrabrain | thread_id 흐름도 작성 |

→ 단독 1 step. **독립** (다른 group과 데이터 의존 X).

#### g6c: §H langgraph ERD §4 (직렬)

| id | category | description |
|---|---|---|
| 17 | quick | langgraph 4 테이블 실측 |
| 18 | ultrabrain | ERD §4 갱신 |

→ 직렬 2 step. **독립**.

→ **g6a, g6b, g6c는 서로 병렬 ✅**. 가장 긴 sub group은 g6a (4 step). g6b/g6c는 g6a 진행 중 백그라운드로 처리 가능. 단 g6a step 14가 사용자 검토 의존이라 *시간 단축은 g6b/g6c가 step 14 대기 중에 진행됨*에서 발생.

### Group g7: §I 종료 (직렬)

| id | category | description |
|---|---|---|
| 19 | quick | validate.sh |
| 20 | quick | 메모리 갱신 |
| 21 | quick | trace log 종료 + plan 상태 |

→ 직렬 3 step.

### 추천 실행 순서

```
g1 (병렬 ✅, 3→1)
   ↓
g2 (직렬, 2)
   ↓
g3 (단독, 1)
   ↓
g4 (직렬, destructive, 2) ⚠️ 이중 컨펌
   ↓
g5 (병렬 ✅, 3→1)
   ↓
g6 (3 sub group 병렬 ✅) — g6a/g6b/g6c 동시 진입
   • g6a: 4 step (직렬, 사용자 검토 의존)
   • g6b: 1 step (독립)
   • g6c: 2 step (직렬)
   • 가장 긴 sub group = g6a (4 step)
   ↓
g7 (직렬, 3)
```

### 직렬 vs 병렬 시간 추정

- **순수 직렬**: 21 step
- **병렬 적용**: 1 (g1) + 2 (g2) + 1 (g3) + 2 (g4) + 1 (g5) + 4 (g6 가장 긴 g6a) + 3 (g7) = **14 step 등가**
- **절약**: ~33% (21 → 14)
- **단**: g6a step 14가 사용자 검토 의존이라 wall-clock은 사용자 응답 시간에 좌우. g6b/g6c가 step 14 대기 동안 백그라운드 진행 시 가장 큰 효과.

---

## Section 3. JSON 부속 (Phase 5 워커 자동 처리용)

```json
{
  "plan_slug": "2026-04-11-erd-audit-feedback",
  "atlas_version": "0.1",
  "generated_at": "2026-04-11T11:50:00Z",
  "stats": {
    "total_steps": 21,
    "by_category": {
      "visual-engineering": 0,
      "ultrabrain": 4,
      "deep": 1,
      "quick": 10,
      "db-migration": 6,
      "langgraph-node": 0
    },
    "groups": 7,
    "parallel_groups": 3,
    "user_review_dependent_groups": 1
  },
  "validation": {
    "all_categorized": true,
    "no_cycles": true,
    "parallel_groups_count": 3
  },
  "steps": [
    {"id": 1, "description": "plan #1 종료 확인", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [2, 3], "destructive": false, "user_review_required": false},
    {"id": 2, "description": "validate.sh baseline", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [1, 3], "destructive": false, "user_review_required": false},
    {"id": 3, "description": "trace log 생성", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [1, 2], "destructive": false, "user_review_required": false},
    {"id": 4, "description": "orphan 검증", "category": "db-migration", "sub_phase": "§B", "depends_on": [], "parallelizable_with": [16, 17], "destructive": false, "user_review_required": false},
    {"id": 5, "description": "17 row 백업", "category": "quick", "sub_phase": "§B", "depends_on": [4], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 6, "description": "SQL 파일 작성", "category": "db-migration", "sub_phase": "§C", "depends_on": [4, 5], "parallelizable_with": [16, 17], "destructive": false, "user_review_required": false},
    {"id": 7, "description": "dry-run", "category": "db-migration", "sub_phase": "§D", "depends_on": [6], "parallelizable_with": [], "destructive": false, "user_review_required": true},
    {"id": 8, "description": "apply (destructive)", "category": "db-migration", "sub_phase": "§D", "depends_on": [7], "parallelizable_with": [], "destructive": true, "user_review_required": true},
    {"id": 9, "description": "컬럼 검증", "category": "db-migration", "sub_phase": "§E", "depends_on": [8], "parallelizable_with": [10, 11], "destructive": false, "user_review_required": false},
    {"id": 10, "description": "row count", "category": "db-migration", "sub_phase": "§E", "depends_on": [8], "parallelizable_with": [9, 11], "destructive": false, "user_review_required": false},
    {"id": 11, "description": "FK CASCADE smoke test", "category": "deep", "sub_phase": "§E", "depends_on": [8], "parallelizable_with": [9, 10], "destructive": false, "user_review_required": false},
    {"id": 12, "description": "places.category 분포", "category": "quick", "sub_phase": "§F", "depends_on": [], "parallelizable_with": [13, 16, 17], "destructive": false, "user_review_required": false},
    {"id": 13, "description": "sub_category 매트릭스", "category": "quick", "sub_phase": "§F", "depends_on": [], "parallelizable_with": [12, 16, 17], "destructive": false, "user_review_required": false},
    {"id": 14, "description": "사용자 enum 검토", "category": "ultrabrain", "sub_phase": "§F", "depends_on": [12, 13], "parallelizable_with": [], "destructive": false, "user_review_required": true},
    {"id": 15, "description": "분류표 작성", "category": "ultrabrain", "sub_phase": "§F", "depends_on": [14], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 16, "description": "thread_id 흐름도 작성", "category": "ultrabrain", "sub_phase": "§G", "depends_on": [], "parallelizable_with": [12, 13, 17], "destructive": false, "user_review_required": false},
    {"id": 17, "description": "langgraph 4 테이블 실측", "category": "quick", "sub_phase": "§H", "depends_on": [], "parallelizable_with": [12, 13, 16], "destructive": false, "user_review_required": false},
    {"id": 18, "description": "ERD §4 갱신", "category": "ultrabrain", "sub_phase": "§H", "depends_on": [17], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 19, "description": "validate.sh", "category": "quick", "sub_phase": "§I", "depends_on": [8, 15, 16, 18], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 20, "description": "메모리 갱신", "category": "quick", "sub_phase": "§I", "depends_on": [19], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 21, "description": "trace log 종료 + plan 마크", "category": "quick", "sub_phase": "§I", "depends_on": [20], "parallelizable_with": [], "destructive": false, "user_review_required": false}
  ],
  "groups": [
    {"id": "g1", "label": "§A 사전검증", "step_ids": [1, 2, 3], "parallelizable": true, "destructive": false, "user_review_required": false},
    {"id": "g2", "label": "§B 데이터 검증", "step_ids": [4, 5], "parallelizable": false, "destructive": false, "user_review_required": false},
    {"id": "g3", "label": "§C SQL 작성", "step_ids": [6], "parallelizable": false, "destructive": false, "user_review_required": false},
    {"id": "g4", "label": "§D 마이그레이션 적용", "step_ids": [7, 8], "parallelizable": false, "destructive": true, "user_review_required": true},
    {"id": "g5", "label": "§E 검증", "step_ids": [9, 10, 11], "parallelizable": true, "destructive": false, "user_review_required": false},
    {"id": "g6a", "label": "§F 카테고리 분류표", "step_ids": [12, 13, 14, 15], "parallelizable": false, "destructive": false, "user_review_required": true, "parent_group": "g6"},
    {"id": "g6b", "label": "§G thread_id 흐름도", "step_ids": [16], "parallelizable": false, "destructive": false, "user_review_required": false, "parent_group": "g6"},
    {"id": "g6c", "label": "§H langgraph ERD §4", "step_ids": [17, 18], "parallelizable": false, "destructive": false, "user_review_required": false, "parent_group": "g6"},
    {"id": "g6", "label": "§F+§G+§H 문서 작업", "sub_groups": ["g6a", "g6b", "g6c"], "sub_groups_parallelizable": true, "destructive": false, "user_review_required": true},
    {"id": "g7", "label": "§I 종료", "step_ids": [19, 20, 21], "parallelizable": false, "destructive": false, "user_review_required": false}
  ],
  "recommended_order": ["g1", "g2", "g3", "g4", "g5", "g6", "g7"],
  "estimated_serial_steps": 21,
  "estimated_parallel_equivalent": 14,
  "estimated_speedup_pct": 33
}
```

---

## Section 4. Atlas 인지 노트

이 plan은 본질적으로 **DB 정합 작업 (db-migration 6 step) + 문서 작업 (ultrabrain 4 step) + 검증/메모리 (quick 10 step)** 의 균형 있는 묶음이다. langgraph-node와 visual-engineering 카테고리는 0건 — Phase 1 skeleton 단계이고 FE는 미구현이므로 정상.

가장 큰 risk는 단연 **g4 §D apply (step 8)** — 단일 트랜잭션 안의 10 DDL이 한 번에 commit되며, place_analysis 17 row DELETE + ALTER + DROP COLUMN + RENAME + ADD CONSTRAINT가 묶여 있다. 사용자 정책 (`feedback_drop_data_freely`) 덕에 17 row 보존 안전망은 불필요하지만, ALTER USING `place_id::text` 변환 실패 가능성은 사전 dry-run + 트랜잭션 ROLLBACK으로 완화된다.

가장 큰 **가속 기회**는 **g6 (§F+§G+§H)** 묶음. g6a 안의 step 14 (사용자 enum 검토)가 사용자 응답을 비동기 대기하는 동안, **g6b (thread_id 흐름도) + g6c (langgraph 4 테이블 실측 + ERD §4 갱신)이 백그라운드로 진행 가능**. Phase 5 워커가 구축되면 이 3 sub group을 동시 spawn하여 wall-clock 30%+ 단축 기대. 현재 (Phase 5 부재) 메인 Claude 단일 스레드라 직렬 처리됐지만 의존성은 명확히 분리됨.

사용자 결정 필요 부분은 **step 14 (카테고리 enum)** 단 1건. 나머지는 모두 plan 작성 시점에 결정된 사용자 정책 (옵션 A DROP, 옵션 B 그래뉼래리티, ERD v6.2 권위)을 따른다. 실제 이번 plan 실행 (2026-04-11)에서도 step 14에서만 실시간 사용자 검토가 발생했고, 나머지는 자동 진행으로 처리됨 — Atlas의 분류가 실제 흐름과 일치 ✅.

6개월 뒤 후회 가능성: **낮음**. 본 plan은 ERD v6.2 권위 그대로 따랐고, 19 불변식 #5/#6 회복 + #1 PK 통일 + FK CASCADE 신설로 정합 회복 작업. 후속 plan들 (etl-blockers, p2-p3 등)이 본 plan의 결과 위에 자연스럽게 쌓인다. 단 *place_analysis 17 row 재생성은 별도 plan*으로 예약되어 있으므로, 그 사이에는 place_analysis 빈 테이블 상태 — 분석 기능 일시 부재 (PoC 단계라 OK).

---

## 변경 이력

- **0.1** (2026-04-11): Atlas 첫 출력. plan #2 처리. 21 step → 7 group, 병렬 후보 3건, 추정 속도 향상 33%. plan #5 (`harness-atlas-only`) 시범 산출물.
