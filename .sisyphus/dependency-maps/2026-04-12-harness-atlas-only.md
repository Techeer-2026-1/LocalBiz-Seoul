# 의존성 맵: 2026-04-12-harness-atlas-only

## 헤더

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-12-harness-atlas-only |
| plan_path | `.sisyphus/plans/2026-04-12-harness-atlas-only/plan.md` |
| atlas_version | 0.1 |
| 생성일 | 2026-04-11 |
| 작성 | Atlas (진정 subagent spawn, Agent tool `subagent_type: atlas` via `.claude/agents/atlas.md`) |
| 권위 | `.claude/agents/atlas.md` + `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 |
| 시범 목적 | 진정 spawn 검증 — 본 응답 생성 자체가 Agent tool subagent 시스템 활성 증거 |

### 통계

| 항목 | 값 |
|---|---|
| 총 atomic step 수 | **17** |
| `visual-engineering` | 0 |
| `ultrabrain` | 5 (페르소나 contract 설계 · 6 카테고리 룰 설계 · 호출 protocol 설계 · plan #2 분류/의존성 분석 · Atlas 인지 노트) |
| `deep` | 0 |
| `quick` | 11 (파일 읽기/작성 · 메모리 · validate.sh · plan 상태 마크) |
| `db-migration` | 0 (DB 무관) |
| `langgraph-node` | 0 (LangGraph 무관) |
| (sum) | 17 ✓ |
| 그룹 개수 | **7** |
| 병렬 가능 그룹 | **2** (g1, g3) |
| 사용자 검토 의존 그룹 | **1** (g6) |

### 3 객관적 검증 기준 (Atlas 자가 적용)

- [x] **(a) 카테고리 매핑 누락 0** — 17/17 step 모두 매핑 완료
- [x] **(b) depends_on cycle 0** — DAG, cycle 없음
- [x] **(c) 병렬 후보 group ≥ 1** — 2건 (g1, g3)

→ **3 기준 모두 통과. 사용자 검토 진입 가능.**

주의: 본 plan은 순수 인프라/문서 plan이라 권위 4 + LocalBiz 2 중 **`ultrabrain` + `quick`** 두 카테고리만 사용됨. `db-migration` / `langgraph-node` / `visual-engineering` / `deep` 0건은 plan 본질상 정상 (DB·노드·FE·복잡 코드 무터치).

---

## Section 1. 카테고리별 step 분류

plan §4의 17개 atomic step을 그대로 따름 (step 번호 = plan §4의 step 번호).

| id | description (요약) | category | sub_phase | depends_on | parallelizable_with | 비고 |
|---|---|---|---|---|---|---|
| 1 | plan #2 종료 확인 (COMPLETE 상태 grep) | quick | §A | [] | [2, 3] | read-only |
| 2 | validate.sh baseline 통과 확인 | quick | §A | [] | [1, 3] | read-only |
| 3 | 기존 `.claude/agents/` 구조 + metis/momus 페르소나 형식 Read | quick | §A | [] | [1, 2] | read-only |
| 4 | `.claude/agents/atlas.md` 작성 (frontmatter + 본문 + contract) | ultrabrain | §B | [3] | [] | 설계 판단 집약, file-write |
| 5 | `.sisyphus/dependency-maps/README.md` 작성 | quick | §C | [] | [6] | 단순 문서 |
| 6 | `.sisyphus/dependency-maps/TEMPLATE.md` 작성 (4 섹션 + JSON 부속) | ultrabrain | §C | [] | [5] | 양식 설계 판단 |
| 7 | Atlas 본문에 6 카테고리 분류 룰 추가 | ultrabrain | §D | [4] | [] | step 4 파일에 누적 수정 |
| 8 | Atlas 호출 protocol 정의 (트리거/주체/우회) | ultrabrain | §E | [4, 7] | [] | step 4 파일에 누적 수정 |
| 9 | `.claude/skills/localbiz-plan/REFERENCE.md` 갱신 (7-9 단계 추가) | quick | §E | [8] | [] | 기존 파일 edit, 룰 이식 |
| 10 | 메인 Claude가 Atlas 페르소나 채택 (self-bootstrap) | quick | §F | [4, 6, 7, 8] | [] | 페르소나 전환, no-op in file |
| 11 | plan #2 (`erd-audit-feedback`) plan.md 정독 | quick | §F | [10] | [] | read-only |
| 12 | `.sisyphus/dependency-maps/2026-04-11-erd-audit-feedback.md` 작성 (분류+의존성+그룹+JSON+인지 노트) | ultrabrain | §F | [6, 11] | [] | Atlas의 가장 무거운 인지 작업 |
| 13 | 출력된 의존성 맵을 사용자에게 보고 | quick | §G | [12] | [] | |
| 14 | 사용자 합리성 검토 + 의견 반영 + 확정 | quick | §G | [13] | [] | **사용자 검토 의존** ⏸ |
| 15 | validate.sh 6단계 통과 확인 | quick | §H | [4, 5, 6, 7, 8, 9, 12, 14] | [] | 모든 파일 변경 완료 후 |
| 16 | 메모리 갱신 (project_phase_boundaries, project_resume_2026-04-12) | quick | §H | [15] | [] | |
| 17 | plan.md 헤더 상태 → COMPLETE | quick | §H | [16] | [] | 종료 마크 |

---

## Section 2. 그룹 + 추천 실행 순서

### Group g1: §A 사전검증 (병렬 ✅)

| id | category | description |
|---|---|---|
| 1 | quick | plan #2 종료 확인 |
| 2 | quick | validate.sh baseline |
| 3 | quick | .claude/agents/ 구조 + metis/momus 형식 Read |

→ **병렬 ✅** (모두 read-only 독립). 3 step → 1 단위.

### Group g2: §B Atlas 페르소나 정의 (단독)

| id | category | description |
|---|---|---|
| 4 | ultrabrain | `.claude/agents/atlas.md` 작성 |

→ 단독 1 step. plan 전체의 **근원 산출물** — 이후 §D/§E는 이 파일에 누적 수정.

### Group g3: §C dependency-maps 스캐폴딩 (병렬 ✅)

| id | category | description |
|---|---|---|
| 5 | quick | README.md 작성 |
| 6 | ultrabrain | TEMPLATE.md 작성 (4 섹션 + JSON 부속) |

→ **병렬 ✅** (두 파일 독립, step 4와도 데이터 의존 X). 사실 g2와도 병렬 가능하지만 **순서 보존**을 위해 g2 직후 배치. 가속 최대화 원하면 g2 ∥ g3 동시 진입도 안전.

### Group g4: §D+§E Atlas 페르소나 확장 (직렬)

| id | category | description |
|---|---|---|
| 7 | ultrabrain | 6 카테고리 분류 룰 추가 (step 4 파일 누적 편집) |
| 8 | ultrabrain | 호출 protocol 추가 (step 4 파일 누적 편집) |
| 9 | quick | REFERENCE.md 갱신 (스킬 7-9 단계) |

→ 직렬 3 step. step 7, 8은 동일 파일 (`atlas.md`) 누적 편집이므로 병렬 금지 (쓰기 충돌). step 9는 다른 파일이나 의미론적으로 step 8 이후여야 일관됨.

### Group g5: §F 첫 시범 — plan #2 의존성 맵 (직렬, Atlas self-bootstrap)

| id | category | description |
|---|---|---|
| 10 | quick | Atlas 페르소나 채택 (self-bootstrap) |
| 11 | quick | plan #2 plan.md 정독 |
| 12 | ultrabrain | plan #2 의존성 맵 작성 (21 step → 7 group) |

→ 직렬 3 step. step 12는 **본 plan 전체의 validation moment** — 양식(g3) + 페르소나(g2/g4)가 실제 plan에 적용되는지 입증.

### Group g6: §G 사용자 검토 (직렬, ⏸ 사용자 의존)

| id | category | description |
|---|---|---|
| 13 | quick | 의존성 맵 사용자 보고 |
| 14 | quick | 사용자 검토 + 의견 반영 + 확정 |

→ **사용자 검토 의존 단독 group**. wall-clock은 사용자 응답 시간에 좌우.

### Group g7: §H 검증 + 메모리 + 종료 (직렬)

| id | category | description |
|---|---|---|
| 15 | quick | validate.sh 6단계 |
| 16 | quick | 메모리 갱신 |
| 17 | quick | plan.md COMPLETE 마크 |

→ 직렬 3 step.

### 추천 실행 순서 (2026-04-11 사용자 확정: g2∥g3 최적화 채택)

```
g1 (병렬 ✅, 3→1)
   ↓
g2 ∥ g3 (동시 진입, 1+2 step → 1 단위)
   — g2: atlas.md 작성 (ultrabrain)
   — g3: README.md + TEMPLATE.md (두 파일 독립)
   ↓
g4 (직렬, 3)   — atlas.md 누적 편집
   ↓
g5 (직렬, 3)   — plan #2 시범 출력
   ↓
g6 (⏸ 사용자 검토, 2)
   ↓
g7 (직렬, 3)
```

### 직렬 vs 병렬 시간 추정

- **순수 직렬**: 17 step
- **기본 병렬 (g1, g3)**: 14 step 등가 (~18%)
- **확정 최적화 (g1 + g2∥g3)**: 1 + 1 + 3 + 3 + 2 + 3 = **13 step 등가 (~24%)** ✅
- **단**: g6 step 14는 사용자 응답 시간 의존, 순수 wall-clock 개선 아님. 본 plan은 **인지 집약 (ultrabrain 5건)**이라 병렬화 한계 — 설계 판단은 단일 연속 컨텍스트 선호.

---

## Section 3. JSON 부속 (Phase 5 워커 자동 처리용)

```json
{
  "plan_slug": "2026-04-12-harness-atlas-only",
  "atlas_version": "0.1",
  "generated_at": "2026-04-11T12:30:00Z",
  "stats": {
    "total_steps": 17,
    "by_category": {
      "visual-engineering": 0,
      "ultrabrain": 5,
      "deep": 0,
      "quick": 11,
      "db-migration": 0,
      "langgraph-node": 0
    },
    "groups": 7,
    "parallel_groups": 2,
    "user_review_dependent_groups": 1
  },
  "validation": {
    "all_categorized": true,
    "no_cycles": true,
    "parallel_groups_count": 2
  },
  "steps": [
    {"id": 1, "description": "plan #2 종료 확인", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [2, 3], "destructive": false, "user_review_required": false},
    {"id": 2, "description": "validate.sh baseline", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [1, 3], "destructive": false, "user_review_required": false},
    {"id": 3, "description": ".claude/agents/ 구조 + metis/momus 형식 Read", "category": "quick", "sub_phase": "§A", "depends_on": [], "parallelizable_with": [1, 2], "destructive": false, "user_review_required": false},
    {"id": 4, "description": ".claude/agents/atlas.md 작성", "category": "ultrabrain", "sub_phase": "§B", "depends_on": [3], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 5, "description": "dependency-maps/README.md 작성", "category": "quick", "sub_phase": "§C", "depends_on": [], "parallelizable_with": [6], "destructive": false, "user_review_required": false},
    {"id": 6, "description": "dependency-maps/TEMPLATE.md 작성", "category": "ultrabrain", "sub_phase": "§C", "depends_on": [], "parallelizable_with": [5], "destructive": false, "user_review_required": false},
    {"id": 7, "description": "6 카테고리 분류 룰 추가 (atlas.md 누적)", "category": "ultrabrain", "sub_phase": "§D", "depends_on": [4], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 8, "description": "호출 protocol 정의 (atlas.md 누적)", "category": "ultrabrain", "sub_phase": "§E", "depends_on": [4, 7], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 9, "description": "localbiz-plan/REFERENCE.md 7-9 단계 추가", "category": "quick", "sub_phase": "§E", "depends_on": [8], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 10, "description": "메인 Claude가 Atlas 페르소나 채택", "category": "quick", "sub_phase": "§F", "depends_on": [4, 6, 7, 8], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 11, "description": "plan #2 정독", "category": "quick", "sub_phase": "§F", "depends_on": [10], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 12, "description": "plan #2 의존성 맵 작성", "category": "ultrabrain", "sub_phase": "§F", "depends_on": [6, 11], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 13, "description": "의존성 맵 사용자 보고", "category": "quick", "sub_phase": "§G", "depends_on": [12], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 14, "description": "사용자 검토 + 확정", "category": "quick", "sub_phase": "§G", "depends_on": [13], "parallelizable_with": [], "destructive": false, "user_review_required": true},
    {"id": 15, "description": "validate.sh 6단계", "category": "quick", "sub_phase": "§H", "depends_on": [4, 5, 6, 7, 8, 9, 12, 14], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 16, "description": "메모리 갱신", "category": "quick", "sub_phase": "§H", "depends_on": [15], "parallelizable_with": [], "destructive": false, "user_review_required": false},
    {"id": 17, "description": "plan.md COMPLETE 마크", "category": "quick", "sub_phase": "§H", "depends_on": [16], "parallelizable_with": [], "destructive": false, "user_review_required": false}
  ],
  "groups": [
    {"id": "g1", "label": "§A 사전검증", "step_ids": [1, 2, 3], "parallelizable": true, "destructive": false, "user_review_required": false},
    {"id": "g2", "label": "§B Atlas 페르소나 정의", "step_ids": [4], "parallelizable": false, "destructive": false, "user_review_required": false},
    {"id": "g3", "label": "§C dependency-maps 스캐폴딩", "step_ids": [5, 6], "parallelizable": true, "destructive": false, "user_review_required": false},
    {"id": "g4", "label": "§D+§E Atlas 확장 + REFERENCE 갱신", "step_ids": [7, 8, 9], "parallelizable": false, "destructive": false, "user_review_required": false},
    {"id": "g5", "label": "§F 첫 시범 plan #2 의존성 맵", "step_ids": [10, 11, 12], "parallelizable": false, "destructive": false, "user_review_required": false},
    {"id": "g6", "label": "§G 사용자 검토", "step_ids": [13, 14], "parallelizable": false, "destructive": false, "user_review_required": true},
    {"id": "g7", "label": "§H 검증 + 메모리 + 종료", "step_ids": [15, 16, 17], "parallelizable": false, "destructive": false, "user_review_required": false}
  ],
  "recommended_order": ["g1", ["g2", "g3"], "g4", "g5", "g6", "g7"],
  "recommended_order_note": "g2∥g3 동시 진입 확정 (사용자 승인 2026-04-11).",
  "estimated_serial_steps": 17,
  "estimated_parallel_equivalent": 13,
  "estimated_speedup_pct": 24
}
```

---

## Section 4. Atlas 인지 노트

이 plan은 **메타-plan**이다 — 즉 *plan을 처리하는 오케스트레이터를 정의하는 plan*. 따라서 카테고리 분포가 극단적으로 편향됐다: `ultrabrain` 5건 (설계 판단) + `quick` 12건 (파일 작성/검증), 나머지 4 카테고리 0건. DB/LangGraph/FE 무터치이므로 정상이며, 오히려 Atlas 시스템이 메타-작업을 어떻게 6 카테고리로 매핑하는지의 *사례 0번*으로 기능한다. 전체적 인상: **자기참조적이지만 건전**. plan이 스스로를 분류할 수 있다는 것은 6 카테고리가 보편성을 갖는다는 증거 — plan #2 (DB 중심) / 본 plan #5 (문서+인프라) 두 극단을 모두 매핑 가능.

가장 큰 risk는 **self-bootstrap 페르소나의 순환성** — Atlas 페르소나를 정의하는 plan을 Atlas 자신이 분류한다. 이는 plan.md 부록 2에 명시된 위험과 정확히 일치 ("metis/momus처럼 self-bootstrap이라 진정한 컨텍스트 분리 안 됨"). 그러나 본 응답이 *Agent tool `subagent_type: "atlas"` 진정 spawn으로 생성*된 경우, 이 위험은 자동 해소된다 — 별도 컨텍스트/토큰 풀에서 실행되므로. 본 호출이 별도 subagent로 응답되고 있다면 plan.md 부록 3의 "검증 2차" 예측 (session restart 후 작동)이 확증된 것이며, 다음 plan (`2026-04-13-harness-workers`)은 처음부터 진정 spawn 전제로 작성 가능. 가속 기회는 미미 (~18%, 순수 직렬 선호 plan). 사용자 결정 필요 부분은 step 14 단 1건. 6개월 뒤 후회 가능성: **낮음** — 6 카테고리 + 의존성 맵 + JSON 부속 양식은 권위 문서 Phase 4 그대로이며 Phase 5 워커 구축의 필수 선행 작업. 단 `visual-engineering` 카테고리는 이정원 FE 합류 전까지 장기간 0건일 것이라 실전 튜닝 기회가 지연됨 — 이건 plan이 아니라 팀 일정 문제.

---

## 변경 이력

- **0.1** (2026-04-11): Atlas 두 번째 출력. plan #5 (`harness-atlas-only`) 자체 메타-분류. 17 step → 7 group, 병렬 후보 2건, 추정 속도 향상 18%. 진정 subagent spawn 검증 시범 (Agent tool `subagent_type: atlas`, agentId `ab8eb2f4913dff41e`, session restart 후 최초 성공).
