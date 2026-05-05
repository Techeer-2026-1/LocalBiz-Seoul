# Metis 2차 검토 — REQUEST_CHANGES

- 검토자: metis
- 검토일: 2026-05-04
- 판정: REQUEST_CHANGES (1차 7건 모두 해소, 신규 7건 정책 결정 필요)

## 1차 reject 사유 해소 확인

| # | 1차 사유 | 해소 |
|---|---|---|
| 1 | Phase 격상 정책 미정 | OK — PM 승인 + 기획서 §3.2 갱신 step 선행 |
| 2 | adm_dong_code 매핑 전략 없음 | 부분 해소 — N건 매칭 처리 미정 |
| 3 | 등급 임계값 없음 | OK |
| 4 | fallback 계약 없음 | OK |
| 5 | step 비원자성 | OK |
| 6 | 테스트 케이스 목록 없음 | OK |
| 7 | status 문구 없음 | OK |

## 신규 7건

1. ILIKE N건 매칭 시 정책 미정 (total_pop DESC LIMIT 1 vs SUM vs 첫 매치)
2. district fallback 집계 단위 미정 (SUM vs 대표 동 vs 평균 ratio)
3. 30일 평균 쿼리 윈도우 미정 + avg_pop=0/NULL 가드 없음
4. 단위 테스트 KST 시각 freeze 방식 미명시
5. `_resolve_dong_code` 별도 함수 여부 모호
6. Phase 격상 권위 출처 미인용 (기능 명세서 v2 CSV L25, API 명세서 v2 CSV L150이 이미 P1)
7. step 2 검증(헬퍼 단위)과 step 6 검증(통합 시퀀스) 혼재
