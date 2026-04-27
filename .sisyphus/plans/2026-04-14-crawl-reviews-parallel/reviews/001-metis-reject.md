# Review 001 — Metis
## 판정: reject
## 핵심 사유
1. sync urllib → asyncio 전환 전략 미명시 (aiohttp vs run_in_executor)
2. step 2 세분화 필요
3. 프로세스 kill 손실 복구 근거 없음
4. 속도 개선 추정 근거 부족
