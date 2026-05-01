# 의존성 맵: 2026-04-27-sse-end-to-end

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-27-sse-end-to-end |
| plan_path | `.sisyphus/plans/2026-04-27-sse-end-to-end/plan.md` |
| 생성일 | 2026-04-28 |

## 카테고리별 step 분류

| id | description | category | depends_on | parallelizable_with |
|---|---|---|---|---|
| 1 | `general_node.py` 신규 — Gemini 호출, text_stream 블록 | langgraph-node | [] | [2, 3] |
| 2 | `response_builder_node.py` 신규 — done 블록 + 블록순서 검증 | langgraph-node | [] | [1, 3] |
| 3 | `intent_router_node.py` 수정 — Gemini JSON mode 13 intent 분류 | langgraph-node | [] | [1, 2] |
| 4 | `real_builder.py` — stub → actual import 3건 교체 | quick | [1, 2, 3] | [] |
| 5 | `sse.py` — astream() 연동 + seed user + conversations + messages INSERT | deep | [4] | [] |
| 6 | validate.sh + curl 관통 테스트 | quick | [5] | [] |

## 그룹 + 실행 순서

```text
g1 (병렬: step 1,2,3 — 노드 구현 3종)
  ↓
g2 (step 4 — real_builder.py import 교체)
  ↓
g3 (step 5 — sse.py 관통 연동)
  ↓
g4 (step 6 — 검증)
```

## 비고

- g1 3개 노드는 서로 import 없음 → 완전 병렬
- step 5 (sse.py)가 plan 볼륨의 ~40-50% (seed user, conversations, messages x2, astream loop, disconnect)
- checkpointer=None (불변식 #14 P1 예외)
