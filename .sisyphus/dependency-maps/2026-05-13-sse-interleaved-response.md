# 의존성 맵: 2026-05-13-sse-interleaved-response

| 항목 | 값 |
|---|---|
| plan_slug | 2026-05-13-sse-interleaved-response |
| 총 step | 9 |
| 그룹 | 5 (병렬 2) |

## 카테고리별 step 분류

| id | description | category | depends_on | parallelizable_with |
|---|---|---|---|---|
| 1 | 기획 §4.4 블록 순서 업데이트 | quick | [] | [2, 8] |
| 2 | blocks.py EventItem description 추가 | quick | [] | [1, 8] |
| 3 | place_search_node description + 순서 변경 | deep | [1, 2] | [5] |
| 4 | place_recommend_node 동일 패턴 | deep | [3] | [6] |
| 5 | event_search_node description + 순서 변경 | deep | [1, 2] | [3] |
| 6 | event_recommend_node 동일 패턴 | deep | [5] | [4] |
| 7 | response_builder_node 순서 업데이트 | quick | [3, 4, 5, 6] | [] |
| 8 | general_node 마크다운 개선 | quick | [] | [1, 2] |
| 9 | 통합 검증 | quick | [7, 8] | [] |

## 그룹 + 실행 순서

```
g1 (병렬: 1,2,8) → g2 (병렬: 3,5) → g3 (병렬: 4,6) → g4 (직렬: 7) → g5 (직렬: 9)
```

| group | steps | parallelizable |
|---|---|---|
| g1 | 1, 2, 8 | YES |
| g2 | 3, 5 | YES |
| g3 | 4, 6 | YES |
| g4 | 7 | NO |
| g5 | 9 | NO (사용자 검토) |
