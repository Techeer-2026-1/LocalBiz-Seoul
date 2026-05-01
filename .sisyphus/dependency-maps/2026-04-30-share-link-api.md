# 의존성 맵: 2026-04-30-share-link-api

| 항목 | 값 |
|---|---|
| plan_slug | 2026-04-30-share-link-api |
| 생성일 | 2026-04-30 |

## step

| id | description | category | depends_on |
|---|---|---|---|
| 1 | models/share.py Pydantic 모델 | quick | [] |
| 2 | api/share.py 라우터 3개 | deep | [1] |
| 3 | main.py 라우터 등록 | quick | [2] |
| 4 | tests/test_share.py 단위 테스트 | quick | [2] |
| 5 | validate.sh 통과 | quick | [3, 4] |
