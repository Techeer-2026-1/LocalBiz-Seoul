# 001-metis-reject

- 검토자: Metis
- 판정: **reject**
- 일시: 2026-04-29

## reject 사유 4건

1. **에러 코드 목록 미확정**: ErrorBlock.code에 들어갈 값 부재
2. **error 블록 DB 저장 정책 미정의**: messages에 저장할지, SSE 전송만 할지
3. **용어 불일치**: retryable vs recoverable 혼용
4. **검증 기준 부족**: ruff만으로는 에러 처리 정확성 미검증
