---
name: safe-destructive-ops
description: rm/mv/cp -r/find -delete/git reset/dropdb 등 destructive 명령 작성 시 격리·가드·dry-run 룰 강제. 2026-04-10 사고 재발방지로 도입된 범용 스킬.
phase: 2
project: general
---

# safe-destructive-ops (L1)

destructive 셸 작업을 작성할 때 발동. 절대 한 줄에 chain하지 말고 격리·가드·dry-run.

## 발동 조건

- `rm -rf`, `rm -r`, `mv`, `cp -r`, `find -delete`
- `git reset --hard`, `git clean -fd`, `git push --force`
- `dropdb`, `DROP TABLE`, `TRUNCATE`
- `docker volume rm`, `docker-compose down -v`
- `kubectl delete` 광범위 셀렉터
- 변수 인자에 destructive op (`rm -rf $X`, `mv $A $B`)
- 다음 phrases: "정리해", "지워", "초기화", "rollback", "wipe", "purge"

## L2 본문

상세 룰·dry-run 패턴·복구 가능 작업 예시는 같은 디렉터리의 `REFERENCE.md`를 Read.
