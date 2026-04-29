#!/bin/bash
# Zero-Trust 검증 — PR 올리기 전 필수 실행
#
# 3단계 검증:
#   1) validate.sh (ruff + pyright + pytest + 기획/plan 무결성)
#   2) 서버 실행 + import smoke test
#   3) curl 헬스체크
#
# 통과 시 .sisyphus/state/zero-trust-passed.flag에 현재 HEAD SHA 기록.
# gh pr create 시 pre_bash_guard가 이 flag의 SHA == HEAD SHA인지 확인.
#
# 사용: ./zero-trust.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FLAG="$ROOT/.sisyphus/state/zero-trust-passed.flag"

echo "=== Zero-Trust 검증 시작 ==="
echo ""

# --- 1단계: validate.sh ---
echo "==> [1/3] validate.sh (정적 검증)"
if ! bash "$ROOT/validate.sh"; then
    echo "❌ validate.sh 실패. Zero-Trust 중단." >&2
    rm -f "$FLAG"
    exit 1
fi
echo ""

# --- 2단계: 서버 import smoke test ---
echo "==> [2/3] 서버 import smoke test"
# shellcheck disable=SC1091
source "$BACKEND/venv/bin/activate"
cd "$BACKEND"
if ! python -c "from src.main import app; print('    import OK')"; then
    echo "❌ 서버 import 실패. Zero-Trust 중단." >&2
    rm -f "$FLAG"
    exit 1
fi
cd "$ROOT"
echo ""

# --- 3단계: 서버 실행 + 헬스체크 ---
echo "==> [3/3] 서버 실행 + 헬스체크"
# 기존 8000 포트 프로세스 정리
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

# 서버 백그라운드 실행
cd "$BACKEND"
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 3

# 헬스체크
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")

# 서버 종료
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true
cd "$ROOT"

if [ "$HEALTH_STATUS" = "200" ]; then
    echo "    헬스체크 OK (HTTP $HEALTH_STATUS)"
else
    echo "❌ 헬스체크 실패 (HTTP $HEALTH_STATUS). Zero-Trust 중단." >&2
    rm -f "$FLAG"
    exit 1
fi

echo ""

# --- 통과: flag 파일에 HEAD SHA 기록 ---
HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
mkdir -p "$(dirname "$FLAG")"
echo "$HEAD_SHA" > "$FLAG"

echo "✅ Zero-Trust 검증 통과"
echo "   HEAD SHA: $HEAD_SHA"
echo "   Flag: $FLAG"
echo ""
echo "이제 PR을 올릴 수 있습니다."
