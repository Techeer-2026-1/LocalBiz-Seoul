# Momus Review — 002

- 검토자: momus
- 검토 일시: 2026-05-04
- 판정: **reject**

## 1차 차단 — 절차 위반
Metis okay 없이 Momus가 호출됨. v2는 `001-metis-reject.md`만 존재.

## 치명적 결함

1. **Phase 라벨 모순 (불변식 #18/#19 위반)**
   - plan 헤더 `Phase: P2` vs g3 "Phase 1 active 영역으로 이동"
   - `기획/API 명세서 v2 (SSE)...csv` L155: REVIEW_COMPARE = **Phase 1**
   - 코드 enum L29 주석 "Phase 2"는 구버전. 기획서 최신 명세가 Phase 1. 불변식 #19 적용 → **Phase: P1**로 통일 필요

2. **기획서 §4.5 "미정의" 주장 오류 (불변식 #19 위반)**
   - `기획/API 명세서 v2 (SSE)...csv` L157: `chart: { chart_type: "radar", places: [{ name, scores: {6지표} }] }` **이미 정의됨**
   - plan §2의 "BE 단독 결정 가능" 정당화 무효. "기획서 v2 SSE L157 준수"로 수정 필요

3. **TextStreamBlock Pydantic vs raw dict 결정 미명시**
   - `TextStreamBlock`은 `delta` 필드만 가짐. `sse.py`는 dict에서 `system`/`prompt` 키를 직접 읽음
   - Pydantic 인스턴스 사용 시 system/prompt silently drop → 빈 스트림. **raw dict로 반환할 것을 명시** 필요

## 주요 결함

4. **disambiguation candidates 미정의**: `DisambiguationBlock.candidates` 채우기 전략 없음
5. **동명 매칭 OS 재조회 중복**: step 2 결정 규칙이 step 3 mget과 2회 OS 조회 초래
6. **단위 테스트 누락**: 동명 다중 매칭 + OS mget 부분 누락 + asyncpg $1 바인딩 인자 검증 없음

## 경미 결함

7. **ETL_적재_현황.md 갱신 작업 항목 없음**: L46 ~500 → ~7,572 (불변식 #19)

## 요구 수정사항 (8개)

| # | 항목 | 위치 |
|---|---|---|
| 1 | Phase: P2 → P1 | 헤더 |
| 2 | "기획서 미정의" → "L157 준수" | §2, §4 g1 |
| 3 | text_stream raw dict 명시 | §4 g2 step 4 |
| 4 | disambiguation candidates 전략 명시 | §1 또는 §4 g2 step 5 |
| 5 | PG 동명 매칭 + OS 조회 순서 정리 | §4 g2 step 2-3 |
| 6 | 테스트 케이스 3개 추가 | §4 g5 |
| 7 | ETL_적재_현황.md 갱신 작업 추가 | §4 |
| 8 | IntentType 주석 Phase 2 → Phase 1 수정 | §4 g3 |
