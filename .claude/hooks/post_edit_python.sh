#!/bin/bash
# Phase 1 Hard-constraint: backend/**/*.py 파일이 수정될 때마다 실행
# 1) append-only 테이블 SQL 가드  2) ruff check --fix  3) ruff format  4) pyright
#
# 호출 규약 (Claude Code PostToolUse hook):
#   stdin: {"tool_name": "Edit", "tool_input": {"file_path": "...", ...}, ...}
#   exit 0: 통과 (stdout은 사용자에게 표시)
#   exit 2: 차단 (stderr가 Claude에게 전달되어 재작업 유도)

set -u

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BACKEND="$PROJECT_ROOT/backend"

# stdin에서 JSON 읽어 file_path 추출
input=$(cat)
file_path=$(printf '%s' "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

# backend 하위 .py 파일이 아니면 무시
case "$file_path" in
    "$BACKEND"/*.py|"$BACKEND"/**/*.py) ;;
    *) exit 0 ;;
esac

# 파일이 실제로 존재하지 않으면 (삭제된 경우 등) 무시
[ -f "$file_path" ] || exit 0

# ─────────────────────────────────────────────────────────
# 1. Append-only 테이블 SQL 가드
# messages, feedback, population_stats, langgraph_checkpoints 에 대한
# UPDATE / DELETE FROM 문자열 패턴 차단
# ─────────────────────────────────────────────────────────
if grep -nEi "(UPDATE[[:space:]]+(messages|feedback|population_stats|langgraph_checkpoints)[[:space:]]+SET|DELETE[[:space:]]+FROM[[:space:]]+(messages|feedback|population_stats|langgraph_checkpoints))" "$file_path" >&2; then
    cat >&2 <<'EOF'

[BLOCKED] append-only 테이블에 UPDATE/DELETE를 작성했습니다.
다음 4개 테이블은 ERD v6.1 §3 규약상 INSERT 전용입니다:
  - messages              (대화 원본, append-only 원칙)
  - feedback              (이력성, 수정 불가)
  - population_stats      (시계열 적재)
  - langgraph_checkpoints (라이브러리 자동 관리)
SQL 문장을 INSERT로 바꾸거나, 다른 테이블을 사용하세요.
EOF
    exit 2
fi

# ─────────────────────────────────────────────────────────
# 2~4. ruff / pyright (venv 활성화)
# ─────────────────────────────────────────────────────────
RUFF="$BACKEND/venv/bin/ruff"
PYRIGHT="$BACKEND/venv/bin/pyright"

# venv가 없으면 도구 검증을 건너뛰고 종료 (경고만)
if [ ! -x "$RUFF" ]; then
    echo "[warn] backend/venv/bin/ruff 없음 — 린트 스킵 (venv 활성화 후 재시도)" >&2
    exit 0
fi

# 2. ruff check --fix (자동 수정)
if ! "$RUFF" check --fix "$file_path" >&2; then
    echo "[BLOCKED] ruff check 실패. 위의 오류를 수정하세요." >&2
    exit 2
fi

# 3. ruff format
"$RUFF" format "$file_path" >&2

# 4. pyright (설치되어 있을 때만)
if [ -x "$PYRIGHT" ]; then
    if ! "$PYRIGHT" --outputjson "$file_path" > /tmp/pyright_out.json 2>/dev/null; then
        # 에러가 있으면 상세 출력
        "$PYRIGHT" "$file_path" >&2
        # error 카운트 추출
        err_count=$(python3 -c "
import json
try:
    d = json.load(open('/tmp/pyright_out.json'))
    print(d.get('summary', {}).get('errorCount', 0))
except Exception:
    print(0)
" 2>/dev/null)
        if [ "${err_count:-0}" -gt 0 ]; then
            echo "[BLOCKED] pyright 타입체크 실패 ($err_count errors)" >&2
            exit 2
        fi
    fi
fi

exit 0
