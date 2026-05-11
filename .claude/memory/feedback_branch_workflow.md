---
name: 브랜치 워크플로
description: 이슈 먼저 → feat/#번호 브랜치 → dev PR 병합 순서 준수
type: feedback
---

이슈부터 먼저 생성 → feat/#이슈번호 브랜치에서 작업 → dev로 PR 병합.
dev 브랜치에 직접 커밋/push 금지.

**Why:** 팀 워크플로 규칙. 이슈 트래킹 + 코드 리뷰 프로세스 유지.
**How to apply:** 모든 작업 시작 시 gh issue create → git checkout -b feat/#번호 → 작업 → gh pr create --base dev
