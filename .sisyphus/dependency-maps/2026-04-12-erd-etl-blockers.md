# 의존성 맵: 2026-04-12-erd-etl-blockers

## 헤더

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-12-erd-etl-blockers |
| plan_path | `.sisyphus/plans/2026-04-12-erd-etl-blockers/plan.md` |
| atlas_version | 0.1 |
| 생성일 | 2026-04-12 |
| 작성 | Atlas (진정 subagent, agentId `a8878750506438769`) |
| 권위 | `.claude/agents/atlas.md` + `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 |
| 선행 plan | `2026-04-11-erd-audit-feedback` COMPLETE, `2026-04-13-harness-workers` COMPLETE |

### 통계

| 항목 | 값 |
|---|---|
| 총 atomic step 수 | **31** |
| `visual-engineering` | 0 |
| `ultrabrain` | 4 |
| `deep` | 0 |
| `quick` | 20 |
| `db-migration` | 7 |
| `langgraph-node` | 0 |
| (sum) | 31 ✓ |
| 그룹 개수 | **10** (g1~g10) |
| 병렬 가능 그룹 | **3** (g1 내부, g7 내부, g10 내부) |
| 사용자 검토 의존 그룹 | **2** (g3 apply 전 컨펌, g9 fallback α/β 결정) |
| destructive step | **2** (step 7 SQL apply, §부록 5 TRUNCATE 한정구는 조건부) |
| worker spawn 건수 | 9 (hephaestus 3 / sisyphus-junior 2 / oracle 1 / metis 1 / momus 1 / atlas 1) |

### 3 객관적 검증 기준 (Atlas 자가 적용)

- [x] **(a) 카테고리 매핑 누락 0** — 31/31 step 매핑 완료
- [x] **(b) depends_on cycle 0** — DAG 확인
- [x] **(c) 병렬 후보 group ≥ 1** — 3건 (g1, g7, g10)

→ **3 기준 통과. 사용자 검토 진입 가능.**

---

## Section 1. 카테고리별 step 분류

| id | description (요약) | category | sub_phase | worker | depends_on | parallelizable_with | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | postgres MCP 부재 재검증 (2 테이블) | quick | §A | 메인 | [] | [2, 3, 4] | read-only, skeptical |
| 2 | GeoJSON 33MB 존재/크기 재확인 | quick | §A | 메인 | [] | [1, 3, 4] | read-only |
| 3 | plan #6 COMPLETE 헤더 재확인 | quick | §A | 메인 | [] | [1, 2, 4] | read-only |
| 4 | backend venv + validate.sh baseline 6/6 | quick | §A | 메인 | [] | [1, 2, 3] | read-only |
| 5 | SOURCE.md 확인/보강 (이미 작성됨) | quick | §B | 메인 | [2] | [] | read-mostly |
| 6 | **hephaestus spawn** — DDL SQL 작성 | db-migration | §C | hephaestus | [1, 3, 4] | [] | 트랜잭션 단위 설계 |
| 7 | SQL 리뷰 + psql apply | db-migration | §C | 메인 | [6] | [] | ⚠️ **destructive** (CREATE TABLE/INDEX) |
| 8 | Zero-Trust 스키마 실측 (information_schema) | db-migration | §C | 메인 | [7] | [] | read-only 검증 |
| 9 | **hephaestus spawn** — admin_districts ETL 작성 | db-migration | §D | hephaestus | [8] | [] | PostGIS WKT + asyncpg |
| 10 | **sisyphus-junior spawn** — ETL dry-run 첫 3 feature | quick | §D | sisyphus-junior | [9] | [] | insert 없음 |
| 11 | 메인 승인 + 실 실행 (427 insert) | db-migration | §D | 메인 | [10] | [] | ⚠️ write (append-only) |
| 12 | Zero-Trust 427 row 검증 | quick | §D | 메인 | [11] | [] | read-only |
| 13 | **hephaestus spawn** — pop_stats ETL 작성 | db-migration | §E | hephaestus | [12] | [] | mismatch skip + SKIP_COUNT 출력 |
| 14 | **sisyphus-junior spawn** — dry-run 첫 100행 parse | quick | §E | sisyphus-junior | [13] | [] | insert 없음 |
| 15 | 메인 승인 + 실 실행 (~278,881 insert) | db-migration | §E | 메인 | [14] | [] | ⚠️ write (append-only, 대용량) |
| 16 | Zero-Trust ~278,881 / 415 / FK orphan=0 / SKIP≈6048 | quick | §E | 메인 | [15] | [] | read-only |
| 17 | **oracle spawn** — 불변식 진단 + mismatch 원인 리포트 | ultrabrain | §F | oracle | [16] | [] | fallback α/β (§부록 3) |
| 18 | issues.md에 9건 mismatch append | quick | §F | 메인 | [17] | [] | 후속 plan 트리거 |
| 19 | verification.md append (spawn 결과+Zero-Trust 수치) | quick | §G | 메인 | [16, 17] | [20, 21] | notepads |
| 20 | learnings.md append (검증 게이트 첫 실전) | quick | §G | 메인 | [16, 17] | [19, 21] | notepads |
| 21 | decisions.md append (3 결정) | quick | §G | 메인 | [16, 17] | [19, 20] | notepads |
| 22 | project_db_state 내용 갱신 | quick | §G | 메인 | [19, 20, 21] | [23, 24] | Metis bonus-2 |
| 23 | project_phase_boundaries.md ETL blocker 해제 | quick | §G | 메인 | [19, 20, 21] | [22, 24] | memory |
| 24 | MEMORY.md 인덱스 행 갱신 | quick | §G | 메인 | [19, 20, 21] | [22, 23] | memory |
| 25 | **metis spawn** 리뷰 | ultrabrain | §H | metis | [8, 12, 16, 22, 23, 24] | [] | 이미 완료 기록 |
| 26 | **momus spawn** 리뷰 | ultrabrain | §H | momus | [25] | [] | 이미 완료 기록 |
| 27 | APPROVED 마크 | quick | §H | 메인 | [26] | [] | 완료 |
| 28 | **atlas 자동 호출** — 본 문서 생성 | ultrabrain | §I | atlas | [27] | [] | 실행 중 |
| 29 | validate.sh 6/6 재확인 | quick | §J | 메인 | [15, 22, 23, 24] | [30, 31] | 회귀 없음 |
| 30 | boulder.json status=complete + plan #8 진입점 | quick | §J | 메인 | [29] | [] | 종료 |
| 31 | plan.md 헤더 COMPLETE | quick | §J | 메인 | [30] | [] | 종료 |

**주의 (step 25/26 시간 왜곡)**: plan.md §7에 Metis/Momus는 이미 APPROVED로 기록됨(2026-04-12). 논리적 직렬이지만 **현실적으로 완료 상태**. 실행 시 g8은 기록 재확인만.

---

## Section 2. 그룹 + 추천 실행 순서

### g1: §A 사전검증 (병렬 ✅)
step 1, 2, 3, 4 — 4 read-only 전부 독립. skeptical protocol 재검증 포함.

### g2: §B 출처 문서 (직렬, 경량)
step 5 — SOURCE.md 이미 존재. 확인/보강만.

### g3: §C DDL 마이그레이션 (직렬, ⚠️ destructive)
step 6 → 7 → 8. hephaestus SQL 작성 → 메인 apply → Zero-Trust.
- **step 7 이중 컨펌 필수** (destructive 정책).

### g4: §D administrative_districts ETL (직렬)
step 9 → 10 → 11 → 12. hephaestus 작성 → junior dry-run → 메인 실행 → Zero-Trust.
- step 11 first write, 427 row, 경량.

### g5: §E population_stats ETL (직렬, 대용량)
step 13 → 14 → 15 → 16. hephaestus 작성 → junior dry-run → 메인 실행 → Zero-Trust.
- step 15 wall-clock bottleneck (~278,881 row, batch 1000).
- step 16 SKIP_COUNT ≈ 6,048 검증 (Momus Mo5a).

### g6: §F Oracle 진단 + mismatch 기록 (직렬, fallback 분기)
step 17 → 18. **§부록 3 fallback 매트릭스 진입점**:
- **(α) 재시작 경로**: Claude Code 재시작 → oracle spawn postgres MCP 자동 노출 → step 17 정상 실행. **권장**.
- **(β) 재시작 없음**: 메인 Claude가 MCP dump → `/tmp/db_state_post_plan7.json` → oracle Read 위임.

### g7: §G 노트패드 + 메모리 반영 (부분 병렬 ✅)
- **내부 stage 1**: step 19, 20, 21 병렬 (notepads 3종)
- **barrier**
- **내부 stage 2**: step 22, 23, 24 병렬 (memory 3종)

### g8: §H Metis/Momus (완료 기록)
step 25 → 26 → 27. **이미 APPROVED**. 실행 시 기록 재확인만.

### g9: §I Atlas 자동 호출 (단일, 실행 중)
step 28. ← 본 응답이 실행. 사용자 검토 게이트 진입.

### g10: §J 검증 + 종료 (직렬)
step 29 → 30 → 31.

### 추천 실행 순서

```
g1 (병렬, 4 step → 1 단위)
  ↓
g2 (단일, 1 step)
  ↓
g3 (직렬, 3 step, ⚠️ step 7 destructive 이중 컨펌)
  ↓
g4 (직렬, 4 step, first write 427 row)
  ↓
g5 (직렬, 4 step, 대용량 write ~278k row)
  ↓
g6 (직렬, 2 step, step 17 fallback α/β)  ← 사용자 결정 #1
  ↓
g7 (부분 병렬, 6 step → 2 단위)
  ↓
g8 (직렬 기록확인, 3 step)
  ↓
g9 (본 응답 실행, 1 step) → 사용자 검토 게이트 #2
  ↓
g10 (직렬, 3 step)
```

### 직렬 vs 병렬 시간 추정

- **순수 직렬**: 31 step
- **기본 병렬 (g1만)**: 28 step 등가 (~10%)
- **권장 (g1 + g7 내부 2 단위)**: **25 step 등가 (~19%)**
- **최대 (g1 + g7 + g10 옵션)**: 23 step 등가 (~26%)

**plan #6 대비**: plan #7은 31 step 중 **7개가 db-migration (실질 DB I/O)**, 특히 step 15가 대용량. wall-clock bottleneck은 **step 15 단일 지점**이며 병렬화 불가 → **속도 최적화 한계 ~19%**.

---

## Section 3. JSON 부속

```json
{
  "plan_slug": "2026-04-12-erd-etl-blockers",
  "atlas_version": "0.1",
  "generated_at": "2026-04-12T00:00:00Z",
  "stats": {
    "total_steps": 31,
    "by_category": {
      "visual-engineering": 0,
      "ultrabrain": 4,
      "deep": 0,
      "quick": 20,
      "db-migration": 7,
      "langgraph-node": 0
    },
    "groups": 10,
    "parallel_groups": 3,
    "user_review_dependent_groups": 2,
    "destructive_steps": 2,
    "worker_spawns": {
      "hephaestus": 3,
      "sisyphus-junior": 2,
      "oracle": 1,
      "metis": 1,
      "momus": 1,
      "atlas": 1,
      "total": 9
    }
  },
  "validation": {
    "all_categorized": true,
    "no_cycles": true,
    "parallel_groups_count": 3
  },
  "groups": [
    {"id": "g1", "label": "§A 사전검증", "step_ids": [1, 2, 3, 4], "parallelizable": true, "destructive": false},
    {"id": "g2", "label": "§B 출처 문서", "step_ids": [5], "parallelizable": false},
    {"id": "g3", "label": "§C DDL 마이그레이션", "step_ids": [6, 7, 8], "parallelizable": false, "destructive": true, "user_confirm_required": true, "worker": "hephaestus"},
    {"id": "g4", "label": "§D admin_districts ETL", "step_ids": [9, 10, 11, 12], "parallelizable": false, "worker": "hephaestus+junior"},
    {"id": "g5", "label": "§E pop_stats ETL (대용량)", "step_ids": [13, 14, 15, 16], "parallelizable": false, "worker": "hephaestus+junior", "wall_clock_bottleneck": 15},
    {"id": "g6", "label": "§F Oracle 진단", "step_ids": [17, 18], "parallelizable": false, "worker": "oracle", "fallback": {"alpha": "restart_claude_code", "beta": "main_claude_mcp_dump"}, "user_decision_required": true},
    {"id": "g7", "label": "§G notepads+memory", "step_ids": [19, 20, 21, 22, 23, 24], "parallelizable": "partial", "internal_parallel": [[19, 20, 21], [22, 23, 24]]},
    {"id": "g8", "label": "§H Metis/Momus (완료 기록)", "step_ids": [25, 26, 27], "parallelizable": false, "status": "already_recorded"},
    {"id": "g9", "label": "§I Atlas 자동 호출", "step_ids": [28], "parallelizable": false, "note": "본 응답 생성이 실행", "user_review_gate": true},
    {"id": "g10", "label": "§J 검증+종료", "step_ids": [29, 30, 31], "parallelizable": false}
  ],
  "recommended_order": ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g10"],
  "estimated_serial_steps": 31,
  "estimated_parallel_equivalent_recommended": 25,
  "estimated_speedup_pct_recommended": 19,
  "destructive_ops_inventory": [
    {"step": 7, "op": "CREATE TABLE + INDEX + FK (psql apply)", "mitigation": "단일 트랜잭션, 실패 시 ROLLBACK, 사용자 이중 컨펌"},
    {"step": 11, "op": "INSERT 427 row into administrative_districts", "mitigation": "append-only, dry-run 선행"},
    {"step": 15, "op": "INSERT ~278,881 row into population_stats", "mitigation": "append-only, dry-run 선행, batch 1000, SKIP_COUNT 검증"},
    {"step": "부록5", "op": "TRUNCATE (조건부)", "mitigation": "초기 ETL 단계 한정구 명시, 운영 phase 이후 금지 (불변식 #3)"}
  ],
  "fallback_matrix": {
    "trigger_step": 17,
    "reason": "oracle subagent postgres MCP frontmatter 미노출 (plan #6 issues.md)",
    "alpha": {
      "action": "Claude Code 재시작 후 plan 진입",
      "recommended": true,
      "cost": "~30초 세션 복구",
      "dependency_map_impact": "none (g6 정상 실행)"
    },
    "beta": {
      "action": "메인 Claude가 mcp__postgres__query로 information_schema dump → /tmp/db_state_post_plan7.json → oracle Read 위임",
      "recommended": false,
      "cost": "oracle 진단 깊이 감소 (Read-only 파일 기반)",
      "dependency_map_impact": "step 17을 quick+ultrabrain split (메인 dump + oracle Read)로 재해석 가능"
    }
  }
}
```

---

## Section 4. Atlas 인지 노트

이 plan은 **plan #6 진정 워커 인프라의 첫 LocalBiz 실전 투하**이자 **`feedback_etl_validation_gate.md` 정책의 첫 준수 사례**라는 이중 의의를 갖는다. 구조적으로 plan #6과 완전히 다른 모양 — plan #6이 "24 quick + 6 ultrabrain"으로 거의 순수 인프라·문서 작업이었다면, plan #7은 **"7 db-migration + 4 ultrabrain + 20 quick"**으로 **실제 DB 쓰기가 척추를 관통**한다. wall-clock bottleneck은 단일 지점 — step 15 population_stats 278,881 row 대용량 insert — 이며, 이는 본질적으로 병렬화 불가능하다. 따라서 Atlas의 가속 제안 상한선은 plan #6과 유사한 ~19%에 머문다. 대신 본 plan의 진짜 가치는 **Zero-Trust 검증 밀도**에 있다: §5.2 표의 9개 assertion, §D/§E 각각 4개 step 중 마지막이 검증 전용, §G에 verification.md append까지 — plan이 스스로를 **검증 가능하도록 설계**되어 있다. 프로메테우스와 Metis M1/Momus Mo5a가 잡아낸 SKIP_COUNT stdout 고정 포맷 요구는 이 검증 밀도의 정수이며, hephaestus spawn prompt에 반드시 전달되어야 한다.

가장 큰 risk는 **세 지점**이다. (1) **step 17 oracle postgres MCP fallback** — (α) 재시작을 권장하지만 사용자가 (β)를 고르면 의존성 맵이 17번을 두 단계(메인 dump + oracle Read)로 즉석 재구성해야 하며, 이 경우 oracle의 "진정 subagent로서의 진단 깊이" 첫 실전 측정이 오염된다. (2) **step 7 destructive** — 2 CREATE TABLE + FK + 4 INDEX가 단일 트랜잭션이지만 FK RESTRICT는 population_stats가 비어있어도 향후 DELETE/DROP admin_districts를 차단한다. admin-code-reconcile 후속 plan이 이 FK를 일시 해제할지 여부는 본 plan 범위 외이나 현재 시점에 기록해두는 편이 6개월 뒤 혼란을 막는다. (3) **TRUNCATE 한정구의 운영 시점 경계 모호성** (§부록 5 Metis bonus-1) — "초기 ETL 적재 단계"와 "운영 phase" 사이 전환 시점을 누가/언제 선언하는지 명시돼 있지 않다. 본 plan COMPLETE 마크가 곧 전환 시점이라는 해석이 자연스럽지만, 후속 `admin-code-reconcile`이 "재처리"를 위해 TRUNCATE를 다시 요구할 여지가 있어 그 plan 작성 시 불변식 #3과의 관계를 재천명해야 한다.

사용자 결정 필요 부분: **#1** — g6 fallback α(재시작, 권장) vs β(메인 대행), **#2** — 본 의존성 맵 승인 + 그래뉼래리티 B(Phase 묶음, plan #6 default) vs C(group별 확인) 유지 여부. 6개월 뒤 후회 가능성: **낮음-중간**. 낮음 사유는 append-only + Zero-Trust + dry-run 3중 방호. 중간 사유는 **9 spawn이 plan #6의 1.5배 토큰 부하**이며, 하루 예산 한계에 처음 도전하는 케이스라는 점 — 실패 시 세션 중단 후 boulder.json 기반 복구가 첫 실전이 된다. plan #6에서 확립한 복구 메모리 프로토콜(`project_resume_YYYY-MM-DD.md`)이 본 plan 실행 중 **실시간 갱신**되어야 한다는 점을 g7 step 22-24에 암묵 의존하고 있으며, 이는 문서화보다 실행자 규율의 영역이다.

---

## 변경 이력

- **0.1** (2026-04-12): Atlas 네 번째 출력. plan #7 (`erd-etl-blockers`) 31 step → 10 group, 병렬 후보 3건(g1/g7/g10), 추정 속도 향상 10-26%(권장 19%), destructive 2건(step 7 DDL + step 11/15 append-only write) + TRUNCATE 한정구 1건, 사용자 결정 2건(g6 fallback α/β + g9 그래뉼래리티), worker spawn 9건(hephaestus 3 / junior 2 / oracle 1 / metis 1 / momus 1 / atlas 1). plan #6 인프라 첫 LocalBiz 실전.
