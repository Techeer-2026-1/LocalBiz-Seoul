#!/bin/bash
# Phase 2-bis A3.5: PostToolUse(Skill) — Skill 도구 호출 시
# .sisyphus/state/pending_skills.txt 에서 해당 (session, skill) 라인 제거.
#
# 호출 규약:
#   stdin: {"hook_event_name":"PostToolUse","tool_name":"Skill","tool_input":{"skill":"localbiz-plan",...},"session_id":"...","cwd":"..."}
#   exit 0: 정상

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

if data.get("tool_name") != "Skill":
    sys.exit(0)

skill_name = data.get("tool_input", {}).get("skill", "") or ""
session_id = data.get("session_id", "default") or "default"
if not skill_name:
    sys.exit(0)

pending_path = os.path.join(os.environ.get("PROJECT_ROOT", "."), ".sisyphus", "state", "pending_skills.txt")
if not os.path.exists(pending_path):
    sys.exit(0)

with open(pending_path, encoding="utf-8") as f:
    lines = f.readlines()

# 정확 일치 또는 짧은 이름(예: skill="plan" → "localbiz-plan") 모두 제거
target_full = skill_name if skill_name.startswith("localbiz-") else f"localbiz-{skill_name}"
new_lines = []
removed = False
for line in lines:
    parts = line.rstrip("\n").split("\t")
    if len(parts) >= 2 and parts[0] == session_id and (parts[1] == skill_name or parts[1] == target_full):
        removed = True
        continue
    new_lines.append(line)

if removed:
    with open(pending_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

sys.exit(0)
PY
