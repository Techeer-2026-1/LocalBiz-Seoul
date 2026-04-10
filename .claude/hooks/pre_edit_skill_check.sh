#!/bin/bash
# Phase 2-bis A3: PreToolUse(Edit|Write|MultiEdit) — pending_skills.txt 에
# 현재 session 의 미호출 스킬이 남아있으면 차단.
#
# 호출 규약 (Claude Code PreToolUse hook):
#   stdin: {"hook_event_name":"PreToolUse","tool_name":"Edit"|"Write"|"MultiEdit","tool_input":{...},"session_id":"...","cwd":"..."}
#   exit 0: 통과
#   exit 2: 차단 (stderr가 Claude에 전달되어 재작업 유도)
#
# /force 우회는 skill_router 단계에서 처리됨 (pending에 안 들어감).

set -u

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PROJECT_ROOT

input=$(cat)

python3 - "$input" <<'PY'
import sys, json, os

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

tool = data.get("tool_name", "")
if tool not in ("Edit", "Write", "MultiEdit"):
    sys.exit(0)

session_id = data.get("session_id", "default") or "default"

# 편집 대상 경로 추출
file_path = data.get("tool_input", {}).get("file_path", "") or ""

# .sisyphus/ / .claude/ / 메모리 디렉터리 편집은 항상 허용 (하네스 자체 운영)
project_root = os.environ.get("PROJECT_ROOT", ".")
ALLOW_PREFIXES = (
    os.path.join(project_root, ".sisyphus") + os.sep,
    os.path.join(project_root, ".claude") + os.sep,
    os.path.expanduser("~/.claude/projects/"),
)
if any(file_path.startswith(p) for p in ALLOW_PREFIXES):
    sys.exit(0)

pending_path = os.path.join(project_root, ".sisyphus", "state", "pending_skills.txt")
if not os.path.exists(pending_path):
    sys.exit(0)

with open(pending_path, encoding="utf-8") as f:
    lines = f.readlines()

pending = []
for line in lines:
    parts = line.rstrip("\n").split("\t")
    if len(parts) >= 2 and parts[0] == session_id:
        pending.append(parts[1])

if not pending:
    sys.exit(0)

msg = f"""
[BLOCKED by Phase 2-bis pre_edit_skill_check]

이 세션에서 다음 스킬이 트리거되었으나 아직 호출되지 않았습니다:
  {', '.join(pending)}

각 스킬을 Skill 도구로 호출한 뒤 다시 시도하세요.
호출 순서: SKILL.md(L1) 발동 → REFERENCE.md(L2) Read → 작업.

사용자 명시적 우회: 사용자에게 '/force' 입력을 요청한 뒤 다음 프롬프트부터 효력 발생.
"""
print(msg, file=sys.stderr)
sys.exit(2)
PY
