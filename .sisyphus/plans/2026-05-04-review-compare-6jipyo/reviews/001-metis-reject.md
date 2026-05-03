# Metis Review — 001

- 검토자: metis
- 검토 일시: 2026-05-04
- 판정: **reject**

## 치명적 결함 (블로커)

1. **PHASE1_INTENTS 누락 — 노드 호출 불가**: `intent_router_node.py` L166에서 `PHASE1_INTENTS` 체크가 `_ROUTABLE_INTENTS`보다 먼저 실행됨. g3이 `_ROUTABLE_INTENTS`에만 추가하면 REVIEW_COMPARE는 여전히 GENERAL로 떨어짐.
2. **text_stream system/prompt 키 미명시**: sse.py는 `block["system"]`/`block["prompt"]` 키를 기대함. g2 step 4에서 정확한 키 구조 누락 시 빈 토큰 스트림.
3. **PG ILIKE 모호성 무처리**: "스타벅스"는 수십 개 매장이 매칭됨. 선택 알고리즘 없으면 잘못된 비교 결과 노출.

## 주요 결함

4. **장소명 추출 우선순위 역전**: vs/VS 토큰 split이 1차여야 하는데 plan은 keywords(형용사 위주)를 우선으로 적음. "대" 토큰은 false positive 위험.
5. **OS mget doc id 패턴 불명확**: `crawl_reviews.py`의 `_id = "review_{place_id}"` 패턴 사용 여부 미명시.
6. **ChartBlock 스키마 변경 FE 합의 미확인**: `datasets → places` 변경은 16종 블록 내부 계약 변경. §4.5에 내부 스키마 미정의 → 기획서 선갱신 필요 또는 별도 plan.
7. **불변식 #5 인지 오류**: 체크리스트에 "4건"이라 적혔으나 원문은 **3건**.
8. **테스트 mock 전략 미명시**: PG pool / OS client AsyncMock 패턴 없음.
9. **데이터 가용성 근거 불명**: `ETL_적재_현황.md`는 ~500건으로 기록되어 있음 (실 DB curl 결과 7,572건과 불일치, 어느 쪽이 최신인지 명시 필요).
10. **1개 장소 입력 시 동작 미정의**: §5 수동 시나리오에서 검증하려는 동작이 §1에 정의되어 있지 않음.

## 수정 요구사항 요약

| # | 항목 | 수정 위치 |
|---|---|---|
| 1 | PHASE1_INTENTS에 REVIEW_COMPARE 추가 명시 | §4 g3 |
| 2 | text_stream 블록 system/prompt 키 명시 | §4 g2 step 4 |
| 3 | PG 모호 매칭 해결책 명시 | §4 g2 step 2 |
| 4 | 장소명 추출 우선순위 정정 | §4 g2 step 1 |
| 5 | OS mget `review_{place_id}` 패턴 명시 | §4 g2 step 3 |
| 6 | ChartBlock 변경 FE 합의 또는 §4.5 선갱신 계획 | §2, §4 g1 |
| 7 | 불변식 #5 "3건"으로 수정 | §3 |
| 8 | 테스트 mock 전략 추가 | §4 g5 |
| 9 | 데이터 가용성 근거 명시 (curl 실측 7,572건) | §1 |
| 10 | 1개 장소 입력 동작 정의 | §1 |
