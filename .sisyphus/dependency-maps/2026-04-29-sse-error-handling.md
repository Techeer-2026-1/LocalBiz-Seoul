# 의존성 맵: 2026-04-29-sse-error-handling

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-29-sse-error-handling |
| 생성일 | 2026-04-29 |

## step

| id | description | category | depends_on |
|---|---|---|---|
| 1 | ErrorBlock import 추가 | quick | [] |
| 2 | Gemini 스트리밍 실패 catch + error 블록 | quick | [1] |
| 3 | DB pool 실패 분기 | quick | [1] |
| 4 | 최외곽 except 개선 | quick | [1] |
| 5 | validate.sh 통과 | quick | [2,3,4] |
