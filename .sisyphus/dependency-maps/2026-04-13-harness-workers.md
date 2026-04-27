# 의존성 맵: 2026-04-13-harness-workers

## 헤더

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-13-harness-workers |
| plan_path | `.sisyphus/plans/2026-04-13-harness-workers/plan.md` |
| atlas_version | 0.1 |
| 생성일 | 2026-04-11 |
| 작성 | Atlas (진정 subagent spawn, agentId `a5c44282d8cf89da3`) |
| 권위 | `.claude/agents/atlas.md` + `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 5 |
| 선행 plan | `2026-04-12-harness-atlas-only` ✅ COMPLETE |

### 통계

| 항목 | 값 |
|---|---|
| 총 atomic step 수 | **30** |
| `visual-engineering` | 0 |
| `ultrabrain` | 6 |
| `deep` | 0 |
| `quick` | 24 |
| `db-migration` | 0 |
| `langgraph-node` | 0 |
| (sum) | 30 ✓ |
| 그룹 개수 | **10** (g5.5 포함) |
| 병렬 가능 그룹 | **4** (g1, g2, g5, g9-internal) |
| 사용자 검토 의존 그룹 | **1** (g8) |
| destructive step | 0 |

### 3 객관적 검증 기준 (Atlas 자가 적용)

- [x] **(a) 카테고리 매핑 누락 0** — 30/30 step 매핑 완료
- [x] **(b) depends_on cycle 0** — DAG
- [x] **(c) 병렬 후보 group ≥ 1** — 4건

→ **3 기준 통과. 사용자 검토 진입 가능.**

---

## Section 1. 카테고리별 step 분류

| id | description (요약) | category | sub_phase | depends_on | parallelizable_with | 비고 |
|---|---|---|---|---|---|---|
| 1 | plan #5 COMPLETE 확인 | quick | §A | [] | [2, 3, 4, 5] | read-only |
| 2 | 기존 `.claude/agents/` 3종 frontmatter Read | quick | §A | [] | [1, 3, 4, 5] | read-only |
| 3 | `.sisyphus/` 구조 확인 | quick | §A | [] | [1, 2, 4, 5] | read-only |
| 4 | validate.sh baseline 6/6 | quick | §A | [] | [1, 2, 3, 5] | read-only |
| 5 | 권위 docx Phase 5 재정독 (M1 가드) | quick | §A | [] | [1, 2, 3, 4] | **가정 충돌 시 작업 중단 게이트** |
| 6 | sisyphus-junior.md 작성 | ultrabrain | §B | [2, 5] | [7, 8, 9] | 독립 파일 |
| 7 | hephaestus.md 작성 | ultrabrain | §B | [2, 5] | [6, 8, 9] | 독립 파일 |
| 8 | oracle.md 작성 (postgres MCP) | ultrabrain | §B | [2, 5] | [6, 7, 9] | 독립 파일 |
| 9 | fe-visual.md 작성 (정의만) | ultrabrain | §B | [2, 5] | [6, 7, 8] | backend/ Read 거부 규약 필수 |
| 10 | notepads/README.md (boulder schema 흡수) | ultrabrain | §C | [3, 5] | [] | 근원 설계 문서 |
| 11 | notepads 4 파일 초기화 | quick | §C | [3] | [] | 논리적 순서 보존 |
| 12 | boulder.json 초기 상태 | quick | §C | [10] | [] | schema 참조는 README |
| 13 | REFERENCE.md §8 Phase 5 매뉴얼 확장 | quick | §D | [6, 7, 8, 9, 10, 11, 12] | [] | 기존 파일 edit |
| 14 | 카테고리 → 워커 매칭 표 | ultrabrain | §D | [13] | [] | 동일 파일 누적 |
| 15 | sisyphus-junior spawn 테스트 | quick | §E | [6, 13, 14] | [16, 17, 18] | |
| 16 | hephaestus spawn 테스트 | quick | §E | [7, 13, 14] | [15, 17, 18] | |
| 17 | oracle spawn 테스트 (positive + adversarial) | quick | §E | [8, 13, 14] | [15, 16, 18] | Momus Mo3 |
| 18 | fe-visual spawn 테스트 (positive + negative) | quick | §E | [9, 13, 14] | [15, 16, 17] | Metis M3 / Momus Mo4 |
| 19 | verification.md에 4 spawn 결과 append | quick | §E | [11, 15, 16, 17, 18] | [] | Momus Mo5 주체 명시 |
| 20 | Metis 호출 | quick | §F | [19] | [] | 직렬 |
| 21 | Momus 호출 | quick | §F | [20] | [] | 직렬 |
| 22 | APPROVED 마크 | quick | §F | [21] | [] | |
| 23 | atlas 자동 호출 → dependency-maps 생성 | ultrabrain | §G | [22] | [] | **본 응답 자체가 실행** |
| 24 | 사용자 검토 → 그래뉼래리티 확정 | quick | §G | [23] | [] | **사용자 검토 의존** ⏸ |
| 25 | validate.sh 6단계 | quick | §H | [6..14, 24] | [] | 전체 파일 변경 후 |
| 26 | harness_phase_mapping.md ✅ | quick | §H | [25] | [27, 28] | |
| 27 | phase_boundaries.md ✅ | quick | §H | [25] | [26, 28] | |
| 28 | MEMORY.md 인덱스 갱신 | quick | §H | [25] | [26, 27] | Momus Mo1 |
| 29 | project_resume_2026-04-13.md 작성 | quick | §H | [26, 27, 28] | [] | |
| 30 | plan.md COMPLETE 마크 | quick | §H | [29] | [] | 종료 |

---

## Section 2. 그룹 + 추천 실행 순서

### Group g1: §A 사전검증 (병렬 ✅, M1 게이트 포함)
step 1, 2, 3, 4, 5 — 5 step → 1 단위. **step 5 게이트**: 가정 충돌 시 §B 진입 전 작업 중단.

### Group g2: §B 워커 4종 페르소나 정의 (병렬 가능, 사용자 선택)
step 6, 7, 8, 9 — 4 독립 ultrabrain. 병렬(속도) vs 순차(컨텍스트 일관성) 사용자 선택.

### Group g3: §C 지혜 축적 인프라 (직렬)
step 10 → 11 → 12. README가 schema source of truth, boulder.json은 README 의존.

### Group g4: §D 호출 매뉴얼 + 매칭표 (직렬, 동일 파일 누적)
step 13 → 14. REFERENCE.md 누적 편집.

### Group g5: §E 진정 spawn 검증 4종 (병렬 가능, 사용자 선택)
step 15, 16, 17, 18 — 4 독립. 병렬 시 컨텍스트 토큰 압력 급증 고려.

### Group g5.5: §E 검증 수렴 (직렬)
step 19. verification.md append.

### Group g6: §F Metis/Momus 리뷰 (직렬 필수)
step 20 → 21 → 22. **진정 spawn 내포, 병렬 절대 금지**.

### Group g7: §G Atlas 자동 호출 (본 응답 실행 중)
step 23. ← 이 문서 생성 자체가 실행.

### Group g8: §G 사용자 검토 (⏸ 사용자 의존)
step 24.

### Group g9: §H 검증 + 메모리 + 종료 (부분 병렬)
step 25 → [26 ∥ 27 ∥ 28] → 29 → 30. 내부 3 step 병렬 권장.

### 추천 실행 순서

```
g1 (병렬 ✅, 5→1, M1 게이트)
   ↓
g2 (병렬 or 순차, 4→1 or 4)    ← 사용자 선택
   ↓
g3 (직렬, 3)
   ↓
g4 (직렬, 2)
   ↓
g5 (병렬 or 순차, 4→1 or 4)    ← 사용자 선택
   ↓
g5.5 (직렬, 1)
   ↓
g6 (직렬, 3, 진정 spawn)
   ↓
g7 (1, 본 응답 실행)
   ↓
g8 (⏸ 사용자 검토, 1)
   ↓
g9 (부분 병렬, 6→4)
```

### 직렬 vs 병렬 시간 추정

- **순수 직렬**: 30 step
- **기본 병렬 (g1만)**: 26 step 등가 (~13%)
- **중간 권장 (g1 + g9 내부)**: 24 step 등가 (~20%) ← **권장**
- **최대 병렬 (g1 + g2 + g5 + g9 내부)**: 18 step 등가 (~40%)

30 step 중 24개가 quick이라 각 step 자체가 가볍다. 순수 wall-clock 단축보다 **컨텍스트 창 관리**가 더 중요.

---

## Section 3. JSON 부속

```json
{
  "plan_slug": "2026-04-13-harness-workers",
  "atlas_version": "0.1",
  "generated_at": "2026-04-11T13:00:00Z",
  "stats": {
    "total_steps": 30,
    "by_category": {
      "visual-engineering": 0,
      "ultrabrain": 6,
      "deep": 0,
      "quick": 24,
      "db-migration": 0,
      "langgraph-node": 0
    },
    "groups": 10,
    "parallel_groups": 4,
    "user_review_dependent_groups": 1,
    "destructive_steps": 0
  },
  "validation": {
    "all_categorized": true,
    "no_cycles": true,
    "parallel_groups_count": 4
  },
  "groups": [
    {"id": "g1", "label": "§A 사전검증 (M1 게이트)", "step_ids": [1, 2, 3, 4, 5], "parallelizable": true},
    {"id": "g2", "label": "§B 워커 4종 페르소나", "step_ids": [6, 7, 8, 9], "parallelizable": true, "user_choice": "parallel_or_serial"},
    {"id": "g3", "label": "§C 지혜 축적 인프라", "step_ids": [10, 11, 12], "parallelizable": false},
    {"id": "g4", "label": "§D 호출 매뉴얼", "step_ids": [13, 14], "parallelizable": false},
    {"id": "g5", "label": "§E 진정 spawn 검증 4종", "step_ids": [15, 16, 17, 18], "parallelizable": true, "user_choice": "parallel_or_serial"},
    {"id": "g5.5", "label": "§E 검증 수렴", "step_ids": [19], "parallelizable": false},
    {"id": "g6", "label": "§F Metis/Momus (직렬 필수)", "step_ids": [20, 21, 22], "parallelizable": false},
    {"id": "g7", "label": "§G Atlas 자동 호출", "step_ids": [23], "parallelizable": false, "note": "본 응답 생성 자체가 실행"},
    {"id": "g8", "label": "§G 사용자 검토", "step_ids": [24], "parallelizable": false, "user_review_required": true},
    {"id": "g9", "label": "§H 검증+메모리+종료", "step_ids": [25, 26, 27, 28, 29, 30], "parallelizable": "partial", "internal_parallel": [[26, 27, 28]]}
  ],
  "recommended_order": ["g1", "g2", "g3", "g4", "g5", "g5.5", "g6", "g7", "g8", "g9"],
  "estimated_serial_steps": 30,
  "estimated_parallel_equivalent_minimum": 26,
  "estimated_parallel_equivalent_maximum": 18,
  "estimated_speedup_pct_recommended": 20
}
```

---

## Section 4. Atlas 인지 노트

이 plan은 **하네스 Phase 5의 근간**이다 — plan #5가 "오케스트레이터를 정의"했다면 plan #6은 "오케스트레이터가 지휘할 실제 병렬 워커"를 정의한다. 전체적 인상: **구조가 극도로 대칭적이고 건전**. 30 step 중 destructive 0건, DB 무터치, 19 불변식 자동 통과, 병렬 후보 4 group — 인프라 plan의 교과서. 가장 무거운 인지 작업은 g2(워커 4종 contract 설계)와 g3 step 10(notepads README + boulder schema 흡수)에 집중되며, 나머지 24개 quick은 대부분 루틴이다. 가속 기회 최대치는 ~40%이나 현실적으로는 ~20% 권장 — g2/g5는 토큰 압력과 일관성 때문에 순차가 안전하다. 특히 g5의 4 진정 spawn을 동시에 띄우면 메인 컨텍스트가 4개의 subagent 리턴을 동시에 흡수해야 하는데, 이는 plan #5에서 확립한 "No-Code 컨텍스트 보호" 원리에 역행할 수 있다.

가장 큰 risk는 **§E 진정 spawn의 vacuous pass 함정** — Momus Mo3/Mo4가 이미 적시했듯, positive-only 테스트는 "워커가 spawn됐다"만 증명할 뿐 "contract가 강제된다"는 증명이 아니다. plan이 adversarial negative를 명시적으로 포함한 것(oracle Edit 시도, fe-visual backend/ Read 시도)은 훌륭하나, **step 18의 fe-visual `Read` 차단은 tools 필드로는 불가능**하고 오직 contract 본문 자발 거부에만 의존한다 — 이는 LLM의 지시 준수에 걸린 신뢰 점프이며, 실패 시 plan #6 완료 후에도 fe-visual이 실질적 접근 격리 없이 운영된다는 뜻이다. 사용자가 §E 결과를 검토할 때 반드시 이 한 건을 별도 주목해야 하며, 실패 시 `.claude/hooks/`에서 path-based guard를 추가하는 후속 plan(hooks-reactivate)이 강제된다. 사용자 결정 필요 부분: (1) g2 병렬 여부, (2) g5 병렬 여부, (3) step 18 negative 실패 시 대응 방침. 6개월 뒤 후회 가능성: **낮음**. 본 plan이 성공하면 plan #7 KAIROS Auto Dream이 즉시 착수 가능해지고, plan #2 ERD-ETL-blockers를 "진정 병렬 워커"로 처음 시연하는 실전 무대가 열린다.

---

## 변경 이력

- **0.1** (2026-04-11): Atlas 세 번째 출력. plan #6 (`harness-workers`) 30 step → 10 group, 병렬 후보 4건, 추정 속도 향상 13-40% (권장 20%), destructive 0건, 사용자 검토 의존 1건. 진정 subagent spawn 자동 호출 (plan §G step 23 실행, agentId `a5c44282d8cf89da3`).
