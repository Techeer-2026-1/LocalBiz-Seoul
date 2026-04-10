# Contributing to AnyWay

> 이 문서는 *기존 팀원·신규 팀원* 모두가 자력으로 PR을 머지할 수 있게 하는 최소 핸드북.
> 셋업이 처음이면 먼저 [`README.md`](README.md) 의 6단계 onboarding 완료할 것.

---

## 0. 핵심 원칙 5개

1. **plan-driven** — 코드 짜기 전에 plan 작성. `localbiz-plan` 스킬이 자동 발동.
2. **하네스 hook 우선** — Claude Code hooks가 ruff/pyright/append-only/destructive op를 hard block. 우회 금지.
3. **기획 문서 권위** — 코드와 충돌 시 기획서가 옳음. 기획 변경은 plan으로.
4. **19 불변식** — [`CLAUDE.md`](CLAUDE.md) 의 19개 룰. 위반 = 머지 거부.
5. **destructive op 격리** — rm/mv/||/$VAR 같은 줄 금지. [상세](#hook-troubleshooting).

---

## 1. 워크플로 (issue → plan → branch → PR → merge)

### 1.1 issue 작성

[Issue templates](.github/ISSUE_TEMPLATE/) 에서 종류 선택:
- 🐛 bug — 재현 가능한 결함
- ✨ feature — 새 기능 (plan 필수)
- 🔧 chore — 리팩토링/문서/CI

### 1.2 plan 작성 (feature/non-trivial chore)

```bash
# Claude Code 세션 안에서:
# "PLACE_RECOMMEND 노드 추가해줘" 같은 트리거 키워드 → localbiz-plan 자동 발동
# 또는 명시적으로:
/plan PLACE_RECOMMEND 노드 추가
```

생성 위치: `.sisyphus/plans/{YYYY-MM-DD}-{slug}/plan.md`
검토: Metis (전술적 분석) → Momus (엄격한 검증) → APPROVED
APPROVED 라인이 plan.md 마지막에 있어야 `pre_edit_planning_mode` hook이 코드 편집을 허용.

### 1.3 branch + commit

브랜치 prefix:
- `feat/` — 새 기능
- `fix/` — 버그 fix
- `refactor/` — 리팩토링
- `docs/` — 문서
- `chore/` — 인프라/의존성
- `test/` — 테스트만

```bash
git checkout -b feat/place-recommend-node
```

커밋 메시지:
- `feat: PLACE_RECOMMEND 노드 추가 (사유 표시 포함)`
- `fix: opensearch SSL 인증 거부 처리`
- `docs: README dev-environment 링크 갱신`
- `chore: ruff 0.16 업그레이드`
- `refactor: intent_router_logic INTENT_TO_NODE 매핑 분리`

**main 직접 commit 금지** (pre-commit hook 차단).

### 1.4 PR 생성

```bash
gh pr create --title "feat: PLACE_RECOMMEND 노드 추가" --body "$(cat <<'EOF'
[plan link]
[19 불변식 체크]
[검증]
EOF
)"
```

PR template ([.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)) 가 자동 로드됨. 19 불변식 체크박스 + plan 링크 + 검증 결과 필수.

### 1.5 머지 전 체크

- [ ] CI green (`validate` workflow 통과)
- [ ] 리뷰어 1명 이상 approve
- [ ] PR template 모든 체크박스
- [ ] plan 상태가 `APPROVED`
- [ ] 충돌 해결

main 머지는 **squash merge** 권장 (커밋 history 단순화).

---

## 2. validate.sh 6단계

```bash
./validate.sh
```

| 단계 | 검사 | 실패 시 |
|---|---|---|
| 1 | venv 활성화 | `cd backend && python3.11 -m venv venv && pip install -r requirements.txt -r requirements-dev.txt` |
| 2 | ruff check | `cd backend && ruff check --fix .` (사용자 승인) |
| 3 | ruff format --check | `cd backend && ruff format .` |
| 4 | pyright basic | 메시지에 따라 코드 수정. legacy는 `_legacy_*`로 mv |
| 5 | pytest | 수집 0건이면 자동 스킵 |
| 6 (bonus) | 기획 무결성 + plan 무결성 | `기획/v5/` 같은 stale link / 6 지표 누락 / plan 필수 섹션 누락 |

CI에서도 동일한 6단계가 실행됨 (`.github/workflows/validate.yml`).

---

## 3. 하네스 hook 흐름

| 시점 | Hook | 강제력 | 우회 |
|---|---|---|---|
| 사용자 프롬프트 | `skill_router` (UserPromptSubmit) | soft 인젝션 | `/force` |
| 사용자 프롬프트 | `intent_gate` (UserPromptSubmit) | planning_mode flag 생성 | `/force` |
| Bash 직전 | `pre_bash_guard` (PreToolUse Bash) | hard block (destructive op, --no-verify, etc.) | 우회 불가, 명령 분리 |
| Edit/Write 직전 | `pre_edit_skill_check` (PreToolUse) | hard block (pending 스킬 미호출) | 해당 스킬 호출 |
| Edit/Write 직전 | `pre_edit_planning_mode` (PreToolUse) | hard block (planning_mode 활성) | plan APPROVED 또는 `/force` |
| Edit/Write 직후 | `post_edit_python` (PostToolUse) | hard block (ruff/pyright/append-only) | 코드 수정 |
| Skill 호출 직후 | `skill_invocation_log` (PostToolUse) | pending 정리 | — |

---

## 4. <a name="hook-troubleshooting"></a>Hook 차단 트러블슈팅

### 🚫 `pre_bash_guard` 차단 (destructive op)

```
[BLOCKED by pre_bash_guard]
  명령: ... && rm -rf foo
  위반 패턴: || 와 같은 줄의 rm/mv 금지
```

**원인**: `&& ... ||  rm -rf` chain이 fail 시 fallback으로 destructive op 실행됨 (2026-04-10 사고).

**해결**:
```bash
# ❌ 금지
mkdir -p foo && do_thing || rm -rf foo

# ✅ 권장 — 별도 호출
mkdir -p foo
do_thing
[ $? -ne 0 ] && rm -rf "${foo:?}"  # 별도 if 블록
```

변수 가드:
```bash
# ❌ 금지
rm -rf $TARGET/old

# ✅ 권장
rm -rf "${TARGET:?TARGET must be set}/old"
```

자세한 룰: `.claude/skills/safe-destructive-ops/REFERENCE.md`.

### 🚫 `pre_edit_skill_check` 차단

```
[BLOCKED by Phase 2-bis pre_edit_skill_check]
이 세션에서 다음 스킬이 트리거되었으나 아직 호출되지 않았습니다:
  localbiz-plan, localbiz-erd-guard
```

**해결**: 메시지에 적힌 스킬을 Skill 도구로 호출 (Claude Code 세션 안에서). 호출 후 같은 Edit 재시도.

명시적 우회: 사용자가 다음 프롬프트에 `/force` 입력.

### 🚫 `pre_edit_planning_mode` 차단

```
[BLOCKED by Phase 3 pre_edit_planning_mode]
PLANNING MODE 활성화 상태입니다.
이 모드에서는 .sisyphus/, .claude/, memory/ 외 경로의 Edit/Write/MultiEdit이 차단됩니다.
```

**해결 1**: `.sisyphus/plans/{name}/plan.md` 작성 + Metis/Momus 리뷰 → 마지막 라인 `최종 결정: APPROVED` → 다음 Edit 호출 시 자동 해제.

**해결 2**: 사용자가 `/force` 입력 (intent_gate가 flag 즉시 제거).

### 🚫 `post_edit_python` 차단 (ruff/pyright/append-only SQL)

```
[BLOCKED] append-only 테이블에 UPDATE/DELETE를 작성했습니다.
```

**해결**: 19 불변식 #3 — messages/feedback/population_stats/langgraph_checkpoints는 INSERT only. SQL을 INSERT로 바꾸거나 다른 테이블 사용.

```
[BLOCKED] ruff check 실패
[BLOCKED] pyright 타입체크 실패
```

**해결**: 위 메시지 안내대로 코드 수정. UP045(`X | None`) 발생 시 → CLAUDE.md 정책 `Optional[str]` 사용.

### 🚫 pre-commit hook fail

```bash
cd backend
pre-commit run --all-files  # 로컬 진단
# 메시지에 따라 수정 → git add -A → git commit 재시도
```

---

## 5. 자주 묻는 것

### Q. 빠른 1줄 fix인데도 plan 작성이 필요한가?

**아니오**. 1줄 fix는 plan 면제. 단:
- 19 불변식과 무관해야 함
- ERD 영향 없어야 함
- intent/응답 블록 변경 없어야 함

이런 조건 *모두* 만족하면 `localbiz-plan` 스킬이 자동 발동해도 사용자가 `/force` 로 우회 가능.

### Q. main에 직접 push 하고 싶다

**불가**. pre-commit `no-commit-to-branch` + GitHub branch protection (require PR review). 응급 hotfix도 PR 거쳐야 함.

### Q. legacy 코드를 수정해도 되나?

`backend/_legacy_src/`, `backend/_legacy_scripts/` 는 **참조 전용**. ruff/pyright 검사 제외 (`extend-exclude`). 수정 금지. 새 코드를 `backend/src/`, `backend/scripts/` 에 작성.

### Q. 새 의존성 추가는?

`backend/requirements.txt` (런타임) 또는 `backend/requirements-dev.txt` (개발 도구) 에 핀. PR 설명에 *왜 필요한지* + *대안 검토* 명시.

### Q. 1Password 자격증명 노출됨

즉시 PM(이정) DM. DB_PASSWORD/API key 즉시 회전. 노출 경로 추적 (.env 커밋? Slack? screenshot?).

---

## 6. 참고

- `README.md` — 6단계 onboarding
- `CLAUDE.md` — 19 불변식 + 절대 금지
- `docs/dev-environment.md` — DB/OS 셋업
- `기획/AGENTS.md` — 기획 문서 변경 규약
- `backend/AGENTS.md` — backend 디렉터리 가이드
- `.claude/skills/*/REFERENCE.md` — 각 스킬 상세 절차
- `.sisyphus/plans/TEMPLATE/plan.md` — plan 양식
