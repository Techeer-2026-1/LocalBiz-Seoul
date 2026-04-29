# Zero-Trust 검증 강제 — hook + 스크립트

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-27
- 상태: COMPLETE
- 최종 결정: APPROVED

> 배경: 대화 관리 API에서 Phase 4-5를 건너뛰고 바로 코드 작성 → CodeRabbit이 런타임 버그 3건 발견.
> 목적: APPROVED 후 Atlas dependency-map 없이 코드 편집 불가 + PR 전 Zero-Trust 검증 필수.

## 1. 요구사항

1. **Phase 4 강제**: plan APPROVED 후 dependency-map 없으면 코드 편집 차단 (이미 구현, 테스트 통과)
2. **Phase 5 강제**: `gh pr create` 시 zero-trust flag 없으면 차단
3. **zero-trust.sh**: validate.sh + 서버 import + 헬스체크 3단계 검증. 통과 시 flag에 HEAD SHA 기록.

## 2. 영향 범위

- 신규 파일:
  - `zero-trust.sh` — 프로젝트 루트. 3단계 검증 스크립트.
- 수정 파일:
  - `.claude/hooks/pre_edit_planning_mode.sh` — Phase 4 Atlas 강제 (이미 수정 완료, 테스트 통과)
  - `.claude/hooks/pre_bash_guard.sh` — `gh pr create` 시 zero-trust flag 체크 (이미 수정 완료)
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음

### CLAUDE.md "hooks 수정 금지" 규칙 예외 선언

CLAUDE.md에 `.claude/hooks/` 수정 금지 규칙이 있다. 이 plan은 hook 2개를 수정한다.
예외 사유: PM(이정) 본인이 하네스 강화를 목적으로 직접 요청. Phase 4-5 강제를 코드 수준으로 보장하기 위해
hook 로직 추가가 불가피하다. 비즈니스 로직 변경이 아닌 가드 강화이므로 "수정 금지" 규칙의 취지(가드 무력화 방지)에
부합한다.

## 3. 19 불변식 체크리스트

- [x] 전 항목 해당 없음 — 인프라(hook/script) 변경이며 비즈니스 코드 미접촉

## 4. 작업 순서 (Atomic step)

1. `zero-trust.sh` 신규 작성 (프로젝트 루트)
   - validate.sh 실행
   - 서버 import smoke test
   - 서버 실행 + 헬스체크
   - 통과 시 `.sisyphus/state/zero-trust-passed.flag`에 HEAD SHA 기록

2. `.claude/hooks/pre_bash_guard.sh` — `gh pr create` 패턴 감지 시 flag 체크 (이미 수정)

3. `.claude/hooks/pre_edit_planning_mode.sh` — APPROVED plan의 dependency-map 존재 강제 (이미 수정)

4. 과거 APPROVED plan들 COMPLETE로 일괄 변경 (이미 완료)

5. 테스트:
   - flag 없이 `gh pr create` → 차단 확인
   - flag SHA != HEAD → 차단 확인
   - flag SHA == HEAD → 통과 확인
   - dependency-map 없이 코드 편집 → 차단 확인

## 5. 검증 계획

### 문법 검증
```bash
bash -n .claude/hooks/pre_edit_planning_mode.sh && echo "OK"
bash -n .claude/hooks/pre_bash_guard.sh && echo "OK"
bash -n zero-trust.sh && echo "OK"
```

### hook 시나리오 테스트 (재현 가능한 명령)
```bash
# 테스트 1: flag 없이 gh pr create → 차단
rm -f .sisyphus/state/zero-trust-passed.flag
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create --base dev"},"session_id":"t"}' \
  | CLAUDE_PROJECT_DIR="$(pwd)" bash .claude/hooks/pre_bash_guard.sh 2>&1
# 기대: EXIT 2, "[BLOCKED by Phase 5 Zero-Trust]"

# 테스트 2: flag SHA != HEAD → 차단
echo "wrong-sha" > .sisyphus/state/zero-trust-passed.flag
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create --base dev"},"session_id":"t"}' \
  | CLAUDE_PROJECT_DIR="$(pwd)" bash .claude/hooks/pre_bash_guard.sh 2>&1
# 기대: EXIT 2, "SHA 불일치"

# 테스트 3: flag SHA == HEAD → 통과
git rev-parse HEAD > .sisyphus/state/zero-trust-passed.flag
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create --base dev"},"session_id":"t"}' \
  | CLAUDE_PROJECT_DIR="$(pwd)" bash .claude/hooks/pre_bash_guard.sh 2>&1
# 기대: EXIT 0

# 테스트 4: dependency-map 없이 코드 편집 → 차단
echo "test" > .sisyphus/state/planning_mode.flag
echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"'$(pwd)'/backend/src/api/sse.py"},"session_id":"t","cwd":"."}' \
  | CLAUDE_PROJECT_DIR="$(pwd)" bash .claude/hooks/pre_edit_planning_mode.sh 2>&1
# 기대: EXIT 2, "[BLOCKED by Phase 4 Atlas 강제]" 또는 "[BLOCKED by Phase 3]"
rm -f .sisyphus/state/planning_mode.flag
```

## 6. Metis/Momus 리뷰

- Metis: reviews/001-metis-*.md
- Momus: reviews/002-momus-*.md

## 7. 최종 결정

PENDING (Metis/Momus 통과 시 APPROVED로 갱신)
