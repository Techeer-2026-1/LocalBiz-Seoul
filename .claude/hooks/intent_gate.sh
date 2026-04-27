#!/bin/bash
# Phase 3 B2: UserPromptSubmit hook (skill_router 다음 단계).
# non-trivial 코딩 요청을 감지해 .sisyphus/state/planning_mode.flag 생성하고
# Socratic 인터뷰 모드를 인젝션.
#
# /force 또는 사용자가 명시적 plan을 이미 가지고 있을 때는 생성 안 함.

set -u

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PROJECT_ROOT

input=$(cat)

python3 - "$input" <<'PY'
import sys, json, os, re

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

prompt = (data.get("prompt", "") or "").strip()
if not prompt:
    sys.exit(0)

# 우회
project_root = os.environ.get("PROJECT_ROOT", ".")
if "/force" in prompt:
    # planning_mode flag 강제 해제
    flag = os.path.join(project_root, ".sisyphus", "state", "planning_mode.flag")
    if os.path.exists(flag):
        os.remove(flag)
    sys.exit(0)

# non-trivial 코딩 키워드 (게이트 트리거)
TRIGGERS = [
    "구현", "추가해", "추가하자", "만들어", "만들자", "새 기능", "기능 추가",
    "리팩토링", "재작성", "구조 변경", "마이그레이션",
    "노드 추가", "intent 추가", "응답 블록", "ws 블록",
    "etl 추가", "스크립트 추가",
    "테이블 추가", "컬럼 추가", "스키마 변경",
    "수정해", "수정하자", "변경해", "변경하자",
    "갱신해", "갱신하자", "최신화", "정리해", "정리하자",
    "바꿔", "고쳐", "생성해", "생성하자", "삭제해", "삭제하자",
    "업데이트", "검토해",
    "/plan", "기획부터", "설계 먼저",
]
prompt_lc = prompt.lower()
matched = [kw for kw in TRIGGERS if kw.lower() in prompt_lc]

if not matched:
    sys.exit(0)

# planning_mode flag 생성
state_dir = os.path.join(project_root, ".sisyphus", "state")
os.makedirs(state_dir, exist_ok=True)
flag_path = os.path.join(state_dir, "planning_mode.flag")
with open(flag_path, "w", encoding="utf-8") as f:
    f.write(f"trigger: {', '.join(matched)}\n")
    f.write(f"session_id: {data.get('session_id', 'default')}\n")

# silent: stdout 출력 없음. planning_mode.flag 파일 생성만 하고 종료.
# PreToolUse hook (pre_edit_planning_mode.sh)이 .sisyphus/.claude 외 Edit/Write를
# 차단 — 차단 메시지에 "PLANNING MODE 활성화됨, plan부터 작성하라" 안내 포함되므로
# Claude가 그때 plan 작성으로 전환하면 됨. UserPromptSubmit 단계의 인젝션은 불필요.
sys.exit(0)
PY
