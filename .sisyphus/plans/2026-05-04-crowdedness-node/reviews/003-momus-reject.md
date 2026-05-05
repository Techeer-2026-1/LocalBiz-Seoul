# Momus 검토 — REJECT

- 검토자: momus
- 검토일: 2026-05-04
- 판정: REJECT

## 결정적 reject 사유

1. reviews/에 `*-metis-okay.md` / `*-metis-approved.md` 없음 — Metis 통과 전 Momus 호출 절차 위반
2. `_resolve_dong_code` SQL에서 `total_pop` 컬럼 소속 모호 (population_stats 컬럼인데 JOIN 없이 사용한 것처럼 서술)
3. `_fetch_population` district fallback 시 함수 시그니처 미정의
4. real_builder.py 수정 4군데 미명시 (add_node / _route_by_intent / conditional_edges / add_edge)
5. 기능 명세서 CSV 라인 번호 오류 — L25가 아닌 L41

## 다음 액션

plan.md 수정 → Metis 3차 `okay` → Momus 재호출 (004-momus-*.md)
