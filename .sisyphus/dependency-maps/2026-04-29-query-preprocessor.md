# 의존성 맵: 2026-04-29-query-preprocessor

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-29-query-preprocessor |
| 생성일 | 2026-04-29 |

## step

| id | description | category | depends_on |
|---|---|---|---|
| 1 | query_preprocessor_node.py 신규 | langgraph-node | [] |
| 2 | real_builder.py stub 교체 | quick | [1] |
| 3 | test_query_preprocessor.py 단위 테스트 | quick | [1] |
| 4 | validate.sh 통과 | quick | [2, 3] |
