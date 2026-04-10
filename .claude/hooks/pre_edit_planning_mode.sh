#!/bin/bash
# Phase 3 B3: PreToolUse(Edit|Write|MultiEdit) — planning_mode.flag 존재 시
# .sisyphus/ / .claude/ 외 경로의 Edit/Write 차단 (Read-only Prometheus 원칙).
#
# 해제 조건:
#   1. /force 키워드 (intent_gate가 flag 제거) — 다음 프롬프트부터 적용
#   2. .sisyphus/plans/{name}/plan.md 의 최종 결정 라인이 'APPROVED'로 갱신됨
#      → 이 hook이 발동될 때 자체 검사하여 flag 제거
#
# 호출 규약:
#   stdin: {"hook_event_name":"PreToolUse","tool_name":"Edit"|"Write"|"MultiEdit","tool_input":{...},"session_id":"...","cwd":"..."}
#   exit 0: 통과
#   exit 2: 차단

set -u

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PROJECT_ROOT

input=$(cat)

python3 - "$input" <<'PY'
import sys, json, os, glob

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

tool = data.get("tool_name", "")
if tool not in ("Edit", "Write", "MultiEdit"):
    sys.exit(0)

ROOT = os.environ.get("PROJECT_ROOT", ".")
flag_path = f"{ROOT}/.sisyphus/state/planning_mode.flag"
if not os.path.exists(flag_path):
    sys.exit(0)

# 자체 해제: 어떤 plan.md 라도 'APPROVED'를 가지면 flag 제거
plan_files = glob.glob(f"{ROOT}/.sisyphus/plans/*/plan.md")
approved = False
for pf in plan_files:
    if "TEMPLATE" in pf:
        continue
    try:
        with open(pf, encoding="utf-8") as f:
            txt = f.read()
        if "최종 결정: APPROVED" in txt or "최종결정: APPROVED" in txt:
            approved = True
            break
    except Exception:
        pass

if approved:
    try:
        os.remove(flag_path)
    except OSError:
        pass
    sys.exit(0)

# 편집 대상 확인
file_path = data.get("tool_input", {}).get("file_path", "") or ""

ALLOW_PREFIXES = (
    f"{ROOT}/.sisyphus/",
    f"{ROOT}/.claude/",
    os.path.expanduser("~/.claude/projects/"),
)
if any(file_path.startswith(p) for p in ALLOW_PREFIXES):
    sys.exit(0)

msg = f"""
[BLOCKED by Phase 3 pre_edit_planning_mode]

PLANNING MODE 활성화 상태입니다 (.sisyphus/state/planning_mode.flag 존재).
이 모드에서는 .sisyphus/, .claude/, memory/ 외 경로의 Edit/Write/MultiEdit이 차단됩니다.

차단 대상: {file_path}

해제 방법:
  1. .sisyphus/plans/{{name}}/plan.md 작성 후 Metis/Momus 리뷰 통과 →
     마지막 줄을 '최종 결정: APPROVED'로 변경 → 다음 Edit 호출 시 자동 해제
  2. 사용자 명시적 우회: 사용자에게 '/force' 입력을 요청

문서 분석 기준: Prometheus는 Read-Only 권한만 가지며 .sisyphus/ 외 어떤 소스 코드도
변경할 수 없다 (Phase 3 원칙 §38).
"""
print(msg, file=sys.stderr)
sys.exit(2)
PY
