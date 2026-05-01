# 001-metis-reject

- 검토자: Metis
- 판정: **reject**
- 일시: 2026-04-29

## reject 사유 3건

1. **partial 필드 누락**: 요구사항에 `{status: "cancelled", partial: true}` 명시했으나 DoneBlock에 partial 필드 없음. 구현에도 없음.
2. **"파이프라인 중단" 의미 불명확**: break는 iterator 소비 중단일 뿐, Gemini API 호출의 실제 취소 여부 불확실.
3. **작업 순서 미분해 + 검증 계획 부족**: disconnect 시나리오 테스트 없음.

## 수정 요구

- partial 필드를 구현에 반영하거나 요구사항에서 제거
- "중단"을 best-effort(iterator 소비 중단)로 명시
- 작업 순서를 atomic step으로 분해
