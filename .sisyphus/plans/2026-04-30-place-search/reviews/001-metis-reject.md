# 001-metis-reject

- 검토자: Metis
- 판정: **reject**
- 일시: 2026-04-30

## reject 사유 3건

1. `embed_texts()` 함수 미존재 → 실제는 `embed_batch_async(session, texts, api_key)`
2. 블록 순서 자기모순 — plan 19행(status 포함) vs 93행(status 미포함)
3. OS k-NN 쿼리 설계 미비 — 쿼리 타입/pre-filter/min_score 결정 없음
