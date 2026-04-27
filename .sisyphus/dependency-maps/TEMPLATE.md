# 의존성 맵: {plan-slug}

## 헤더

| 항목 | 값 |
|---|---|
| plan_slug | {plan-slug} |
| plan_path | `.sisyphus/plans/{plan-slug}/plan.md` |
| atlas_version | 0.1 |
| 생성일 | YYYY-MM-DD |
| 작성 | Atlas (self-bootstrap, 메인 Claude 페르소나 채택) |
| 권위 | `.claude/agents/atlas.md` + `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 |

### 통계

| 항목 | 값 |
|---|---|
| 총 atomic step 수 | N |
| `visual-engineering` | n1 |
| `ultrabrain` | n2 |
| `deep` | n3 |
| `quick` | n4 |
| `db-migration` | n5 |
| `langgraph-node` | n6 |
| (sum) | N (검증) |
| 그룹 개수 | G |
| 병렬 가능 그룹 | Gp |
| 사용자 검토 의존 그룹 | Gu |

### 3 객관적 검증 기준 (Atlas 자가 적용)

- [x] **(a) 카테고리 매핑 누락 0** — 모든 atomic step이 6 카테고리 중 하나에 매핑
- [x] **(b) depends_on cycle 0** — DAG 형태, cycle 없음
- [x] **(c) 병렬 후보 group ≥ 1** — 최소 1개 이상의 병렬 가능 group 식별

(3건 모두 ✅이어야 사용자에게 보고. 하나라도 ❌면 plan 작성자에게 sub-step 분리 요청.)

---

## Section 1. 카테고리별 step 분류

| id | description (요약) | category | sub_phase | depends_on | parallelizable_with | 비고 |
|---|---|---|---|---|---|---|
| 1 | step description | category | §A | [] | [] | |
| 2 | ... | category | §A | [1] | [] | |
| ... | | | | | | |
| N | ... | | | | | |

**범례**:
- `category`: 6 카테고리 중 하나
- `sub_phase`: plan §A/§B/§C/... (Atlas는 plan §의 그래뉼래리티를 그대로 따름)
- `depends_on`: 이 step이 시작하기 전에 완료돼야 할 step ID 목록
- `parallelizable_with`: 같은 시점에 안전하게 병렬 실행 가능한 step ID 목록 (depends_on 동일하거나 독립적)
- `비고`: 사용자 검토 의존 / destructive / 트랜잭션 단위 등 특이사항

---

## Section 2. 그룹 + 추천 실행 순서

### Group g1: §A 사전검증 (병렬 가능)

| id | category | description |
|---|---|---|
| 1 | quick | ... |
| 2 | quick | ... |

→ 병렬: ✅ (모두 read-only baseline)

### Group g2: §B SQL 작성 (직렬, 트랜잭션 단위)

| id | category | description |
|---|---|---|
| 3 | db-migration | SQL 파일 작성 |
| 4 | db-migration | dry-run |
| 5 | db-migration | apply ⚠️ destructive |

→ 병렬: ❌ (트랜잭션 직렬, destructive)

### Group g3: §C 검증 (병렬 가능)

| id | category | description |
|---|---|---|
| 6 | quick | postgres MCP 컬럼 검증 |
| 7 | quick | row count |
| 8 | deep | FK CASCADE smoke test |

→ 병렬: ✅ (모두 read-only)

(...)

### Group gN: §I 종료 (직렬)

| id | category | description |
|---|---|---|
| N-1 | quick | validate.sh |
| N | quick | 메모리 갱신 |

→ 병렬: ❌ (의존성 직렬)

### 추천 실행 순서

```
g1 (병렬 ✅) → g2 (직렬, destructive) → g3 (병렬 ✅) → ... → gN (직렬)
```

병렬 그룹 수: **Gp**개. 절약 가능 step 수: 약 X개 (직렬 대비 ~X% 단축 추정).

---

## Section 3. JSON 부속 (Phase 5 워커 자동 처리용)

```json
{
  "plan_slug": "{plan-slug}",
  "atlas_version": "0.1",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "stats": {
    "total_steps": N,
    "by_category": {
      "visual-engineering": n1,
      "ultrabrain": n2,
      "deep": n3,
      "quick": n4,
      "db-migration": n5,
      "langgraph-node": n6
    },
    "groups": G,
    "parallel_groups": Gp
  },
  "validation": {
    "all_categorized": true,
    "no_cycles": true,
    "parallel_groups_count": Gp
  },
  "steps": [
    {
      "id": 1,
      "description": "step 1 description",
      "category": "quick",
      "sub_phase": "§A",
      "depends_on": [],
      "parallelizable_with": [2],
      "destructive": false,
      "user_review_required": false
    }
  ],
  "groups": [
    {
      "id": "g1",
      "label": "§A 사전검증",
      "step_ids": [1, 2],
      "parallelizable": true,
      "destructive": false,
      "user_review_required": false
    }
  ],
  "recommended_order": ["g1", "g2", "g3", "gN"]
}
```

---

## Section 4. Atlas 인지 노트

(자유 서술 1-2 문단 — 권위 문서: "지휘관의 마인드셋, 조화로운 앙상블")

이 plan은 [전체적 인상]. 가장 무거운 카테고리는 [...]이며, 가장 큰 risk는 [...]. 가속 기회: [...]. 사용자 결정 필요 부분: [...]. 6개월 뒤 후회 가능성: [낮음/중간/높음] — [이유].

---

## 변경 이력

- **0.1** (YYYY-MM-DD): Atlas 첫 출력. plan {plan-slug} 처리.
