# 의존성 맵: 2026-04-30-place-search

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-30-place-search |
| 생성일 | 2026-04-30 |

## step

| id | description | category | depends_on | parallelizable_with |
|---|---|---|---|---|
| 1 | place_search_node.py 신규 (PG+OS 하이브리드 검색) | deep | [] | [] |
| 2 | real_builder.py stub 교체 | quick | [1] | [3] |
| 3 | response_builder_node.py 블록 순서 추가 | quick | [] | [2] |
| 4 | test_place_search.py 단위 테스트 | quick | [1] | [] |
| 5 | validate.sh 통과 | quick | [2, 3, 4] | [] |

## 비고

- step 1이 볼륨 80%+ (PG 동적 WHERE + OS k-NN + 병합 + 블록 생성)
- step 2, 3은 병렬 가능 (서로 독립)
