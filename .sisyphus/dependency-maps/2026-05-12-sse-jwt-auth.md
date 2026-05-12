# Dependency Map — SSE JWT Auth

## Plan

`.sisyphus/plans/2026-05-12-sse-jwt-auth/plan.md`

## Steps

| # | Step | Category | Files | Depends On |
|---|---|---|---|---|
| 1 | sse.py JWT 파싱 + _ensure_seed_user 제거 | quick | `backend/src/api/sse.py` | — |
| 2 | 기존 테스트 수정 (있는 경우) | quick | `backend/tests/test_sse.py` | 1 |
| 3 | validate.sh 검증 | quick | — | 1, 2 |

## Recommended Order

```
g1: [step 1]          — sse.py 수정
g2: [step 2]          — 테스트 반영
g3: [step 3]          — 검증
```

## Parallelizable

- g1 → g2 → g3: 순차 (의존성 체인)

## Notes

- 단일 파일 수정 (sse.py) + 테스트 반영. 병렬화 불필요.
- `_ensure_seed_user` 함수 정의도 함께 제거 (dead code).
