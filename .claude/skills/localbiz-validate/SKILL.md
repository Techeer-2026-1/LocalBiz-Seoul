---
name: localbiz-validate
description: validate.sh 단일 진입점 실행. 5+1(Phase 3 후 6+1) 단계 결과를 카테고리별로 해석. 실패 시 가이드 제공, 자동 수정은 사용자 승인 필요.
phase: 2
project: localbiz-intelligence
---

# localbiz-validate (L1)

Phase 5 Zero-Trust 검증의 사전 단계.

## 발동 조건

- "validate", "검증", "체크", "통과", "PR 머지", "끝났어?"
- "확인", "ok야?", "테스트 돌려"
- 직전 작업이 backend 코드 수정을 포함했고 사용자가 종료를 시사할 때

## L2 본문

단계별 실패 가이드·하지 말 것·참고 파일은 같은 디렉터리의 `REFERENCE.md`를 Read.
