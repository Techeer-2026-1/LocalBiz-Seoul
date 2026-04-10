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
    "구현", "추가해", "만들어", "새 기능", "기능 추가",
    "리팩토링", "재작성", "구조 변경", "마이그레이션",
    "노드 추가", "intent 추가", "응답 블록", "ws 블록",
    "etl 추가", "스크립트 추가",
    "테이블 추가", "컬럼 추가", "스키마 변경",
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

# Socratic 인터뷰 인젝션
print("=" * 60)
print("[Phase 3 INTENT GATE] non-trivial 코딩 요청 감지")
print("=" * 60)
print(f"트리거 키워드: {', '.join(matched)}")
print("")
print("PLANNING MODE ON. 다음 절차 강제:")
print("")
print("1. 요구사항이 모호하면 코드 짜기 전에 사용자에게 질문 (Socratic):")
print("   - 영향 받는 모듈/테이블/intent/응답 블록은?")
print("   - Phase 라벨 (P1/P2/P3/ETL/Infra)?")
print("   - 19 불변식 중 위반 위험은?")
print("   - 검증 시나리오는?")
print("   - 뺀 것이 있는가? (반대 가설)")
print("")
print("2. .sisyphus/plans/{YYYY-MM-DD}-{slug}/plan.md 생성")
print("   (TEMPLATE 복사 → localbiz-plan 스킬 호출)")
print("")
print("3. Metis → Momus 서브에이전트로 검토 (Agent 도구).")
print("   reviews/NNN-{role}-{verdict}.md 영구 기록.")
print("")
print("4. 통과 시 plan.md 최종 결정을 APPROVED로 변경 → flag 자동 해제.")
print("")
print("READ-ONLY 강제: planning_mode 동안 .sisyphus/ / .claude/ 외 Edit/Write 차단.")
print("우회: 사용자에게 '/force' 입력을 요청.")
print("=" * 60)
sys.exit(0)
PY
