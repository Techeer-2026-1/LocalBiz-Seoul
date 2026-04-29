# 002-momus-reject

- 검토자: Momus
- 판정: **reject**
- 일시: 2026-04-27

## 결함 3건

1. **검증 계획 불충분** — 수동 시나리오만, 재현 가능한 테스트 스크립트 경로 없음
2. **except Exception: pass → silent bypass** — JSON 파싱 실패 시 exit 0으로 통과 (pre_bash_guard.sh L20-23). SHA 검증 실패 핸들러(L88-92)는 exit 2로 차단하므로 정상. JSON 파싱 핸들러의 exit 0이 문제.
3. **CLAUDE.md hooks 수정 금지 예외 미명시** — 감사 추적용 기록 필요
