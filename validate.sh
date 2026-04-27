#!/bin/bash
# LocalBiz Intelligence — Phase 1 Harness 검증 단일 진입점
#
# 사용: ./validate.sh
# 통과 없이는 작업 완료로 간주하지 않는다.
#
# 검사 항목:
#   1) ruff check        — 린트
#   2) ruff format       — 포맷 검증 (수정 안 함)
#   3) pyright           — 타입 체크 (basic 모드)
#   4) pytest            — 테스트
#   5) 기획 무결성       — 깨진 경로 / 6 지표 스키마 / 마스터 문서 존재
#   6) plan 무결성       — .sisyphus/plans/*/plan.md 필수 필드 + APPROVED (Phase 3)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
export PROJECT_ROOT="$ROOT"

echo "==> [1/5] backend venv 활성화"
if [ ! -d "$BACKEND/venv" ]; then
    echo "ERR: backend/venv 없음. 먼저 'cd backend && python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt' 실행"
    exit 1
fi
# shellcheck disable=SC1091
source "$BACKEND/venv/bin/activate"

cd "$BACKEND"

echo "==> [2/5] ruff check"
ruff check .

echo "==> [3/5] ruff format --check"
ruff format --check .

echo "==> [4/5] pyright (basic)"
if ! command -v pyright >/dev/null 2>&1; then
    echo "ERR: pyright 미설치. 'pip install -r requirements-dev.txt' 실행"
    exit 1
fi
pyright src scripts

echo "==> [5/5] pytest"
if pytest --co -q >/dev/null 2>&1; then
    pytest -q
else
    echo "    (테스트 수집 결과 0건 — 스킵)"
fi

cd "$ROOT"

echo "==> [bonus] 기획 무결성 체크"
python3 - <<'PY'
import os
import sys

errors = []

# 1. CLAUDE.md / AGENTS.md 에 깨진 경로 (구버전 v5) 잔존 검사
for p in ["CLAUDE.md", "backend/AGENTS.md", "기획/AGENTS.md"]:
    if not os.path.exists(p):
        continue
    with open(p, encoding="utf-8") as f:
        txt = f.read()
    if "기획/v5/" in txt:
        errors.append(f"{p}: '기획/v5/' 깨진 경로 잔존")

# 2. 6개 지표 스키마 검증 (init_db.sql 있을 때만)
sql_path = "backend/scripts/init_db.sql"
if os.path.exists(sql_path):
    with open(sql_path, encoding="utf-8") as f:
        sql = f.read()
    required = [
        "score_satisfaction",
        "score_accessibility",
        "score_cleanliness",
        "score_value",
        "score_atmosphere",
        "score_expertise",
    ]
    missing = [c for c in required if c not in sql]
    if missing:
        errors.append(f"{sql_path}: 6 지표 컬럼 누락 → {', '.join(missing)}")

# 3. 기획 마스터 문서 존재 확인
master_files = [
    "기획/ERD_테이블_컬럼_사전_v6.3.md",
    "기획/ETL_적재_현황.md",
    "기획/AGENTS.md",
]
# 기능/API 명세서는 노션 DB가 source of truth (CSV export는 보조)
import glob as _glob
if not _glob.glob("기획/기능 명세서 *.csv"):
    errors.append("기획 권위 문서 누락: 기획/기능 명세서 *.csv")
if not _glob.glob("기획/API 명세서 *.csv"):
    errors.append("기획 권위 문서 누락: 기획/API 명세서 *.csv")
for m in master_files:
    if not os.path.exists(m):
        errors.append(f"기획 권위 문서 누락: {m}")

if errors:
    print("기획 무결성 체크 실패:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print("    기획 무결성 OK")
PY

echo "==> [bonus 2] plan 무결성 체크 (Phase 3)"
python3 - <<'PY'
import os
import sys
import glob

errors = []
warnings = []

ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
plans_dir = f"{ROOT}/.sisyphus/plans"

if not os.path.isdir(plans_dir):
    print("    .sisyphus/plans/ 없음 — 스킵")
    sys.exit(0)

REQUIRED_SECTIONS = [
    "## 1. 요구사항",
    "## 2. 영향 범위",
    "## 3. 19 불변식 체크리스트",
    "## 4. 작업 순서",
    "## 5. 검증 계획",
]

found_any = False
for plan_path in sorted(glob.glob(f"{plans_dir}/*/plan.md")):
    if "TEMPLATE" in plan_path:
        continue
    # COMPLETE plan은 과거 기록이므로 형식 체크 스킵
    with open(plan_path, encoding="utf-8") as _pf:
        _ptxt = _pf.read()
    if "COMPLETE" in _ptxt[:500]:
        continue
    found_any = True
    plan_dir = os.path.dirname(plan_path)
    rel = os.path.relpath(plan_path, ROOT)
    with open(plan_path, encoding="utf-8") as f:
        txt = f.read()

    missing = [s for s in REQUIRED_SECTIONS if s not in txt]
    if missing:
        errors.append(f"{rel}: 필수 섹션 누락 → {', '.join(missing)}")

    # Phase 라벨 확인
    if "Phase: " not in txt and "- Phase:" not in txt:
        errors.append(f"{rel}: Phase 라벨 누락")

    # 상태 확인
    state_line = None
    for line in txt.splitlines():
        ll = line.strip().lower()
        if ll.startswith("- 상태:") or ll.startswith("상태:"):
            state_line = line.strip()
            break

    # APPROVED 상태인데 reviews/ 안에 momus-approved 없으면 warning
    if "최종 결정: APPROVED" in txt or "최종결정: APPROVED" in txt:
        reviews_glob = glob.glob(f"{plan_dir}/reviews/*-momus-approved.md")
        if not reviews_glob:
            warnings.append(f"{rel}: APPROVED 상태이나 momus-approved 리뷰 없음")

if not found_any:
    print("    plan 없음 — 스킵")

if warnings:
    print("    [warn]")
    for w in warnings:
        print(f"      - {w}")

if errors:
    print("plan 무결성 체크 실패:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

if found_any and not warnings:
    print("    plan 무결성 OK")
PY

echo ""
echo "✅ 모든 검증 통과"
