#!/bin/bash
# Phase 3 B3 + Phase 4 Atlas 강제: PreToolUse(Edit|Write|MultiEdit)
#
# planning_mode.flag 존재 시:
#   1. 가장 최신 APPROVED plan 탐색
#   2. APPROVED plan 없으면 → 차단 (plan 작성 필요)
#   3. APPROVED plan 있으면 → 대응 dependency-map 존재 확인
#   4. dependency-map 없으면 → 차단 (Atlas 호출 필요)
#   5. 둘 다 있으면 → flag 제거 + 통과
#
# .sisyphus/, .claude/, memory/ 경로는 항상 허용 (plan/map 작성 자체를 허용)

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

# 편집 대상이 .sisyphus/ 또는 .claude/ 이면 항상 허용
file_path = data.get("tool_input", {}).get("file_path", "") or ""
ALLOW_PREFIXES = (
    f"{ROOT}/.sisyphus/",
    f"{ROOT}/.claude/",
    os.path.expanduser("~/.claude/projects/"),
)
if any(file_path.startswith(p) for p in ALLOW_PREFIXES):
    sys.exit(0)

# 가장 최신 APPROVED plan 탐색 (디렉토리명 날짜순 정렬)
plan_files = sorted(glob.glob(f"{ROOT}/.sisyphus/plans/*/plan.md"), reverse=True)
latest_approved = None
for pf in plan_files:
    if "TEMPLATE" in pf:
        continue
    try:
        with open(pf, encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        continue
    # COMPLETE plan은 과거 완료 기록이므로 건너뜀
    if "COMPLETE" in txt[:500]:
        continue
    if "최종 결정: APPROVED" in txt or "최종결정: APPROVED" in txt:
        latest_approved = pf
        break

if latest_approved is None:
    # APPROVED plan 없음 → plan 작성 필요
    msg = f"""
[BLOCKED by Phase 3 pre_edit_planning_mode]

PLANNING MODE 활성화 상태입니다.
APPROVED된 plan이 없습니다. plan을 작성하고 Metis/Momus 리뷰를 통과하세요.

차단 대상: {file_path}
해제: .sisyphus/plans/{{name}}/plan.md → '최종 결정: APPROVED'
우회: '/force' 입력
"""
    print(msg, file=sys.stderr)
    sys.exit(2)

# APPROVED plan 있음 → dependency-map 존재 확인
plan_dir = os.path.basename(os.path.dirname(latest_approved))
dep_map_path = f"{ROOT}/.sisyphus/dependency-maps/{plan_dir}.md"

if not os.path.exists(dep_map_path):
    msg = f"""
[BLOCKED by Phase 4 Atlas 강제]

Plan APPROVED 확인됨: {latest_approved}
그러나 대응하는 dependency-map이 없습니다: {dep_map_path}

APPROVED 후 바로 코드 작성은 금지됩니다.
Atlas 에이전트를 호출하여 dependency-map을 생성한 뒤 코드를 작성하세요.

호출 방법: Agent 도구로 subagent_type="atlas" 호출
생성 위치: .sisyphus/dependency-maps/{plan_dir}.md
"""
    print(msg, file=sys.stderr)
    sys.exit(2)

# 둘 다 있음 → planning_mode flag 제거 + 통과
try:
    os.remove(flag_path)
except OSError:
    pass
sys.exit(0)
PY
