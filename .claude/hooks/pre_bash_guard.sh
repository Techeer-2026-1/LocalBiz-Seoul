#!/bin/bash
# Phase 1 Hard-constraint: 위험한 Bash 명령 차단
# Phase 2-bis 확장 (2026-04-10): destructive op 격리 룰 추가
#   사고 사례: `cmd1 && cmd2 && cmd3 || rm -rf X` 가 cmd1~3 중 하나라도 실패하면
#              fallback으로 rm -rf 실행 → backend_old untracked 손실
#   대책: || 와 rm/mv 같은 줄 금지. 변수는 ${VAR:?} 가드 필수.
#
# 호출 규약 (Claude Code PreToolUse hook on Bash):
#   stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}, ...}
#   exit 0: 통과
#   exit 2: 차단

set -u

input=$(cat)

python3 - "$input" <<'PY'
import sys, json, re

try:
    data = json.loads(sys.argv[1])
except Exception:
    # fail-closed: JSON 파싱 실패 시 차단 (보안상 통과시키면 안 됨)
    sys.stderr.write("[pre_bash_guard] JSON 파싱 실패 — 차단\n")
    sys.exit(2)

cmd = data.get("tool_input", {}).get("command", "") or ""
if not cmd.strip():
    sys.exit(0)

# 기존 차단 패턴 (Phase 1)
LEGACY = [
    (r'--no-verify', '--no-verify (pre-commit 우회)'),
    (r'git\s+reset\s+--hard', 'git reset --hard'),
    (r'git\s+push\s+(--force|-f(\s|$))', 'git push --force'),
    (r'docker-compose\s+down\s+-v', 'docker-compose down -v'),
    (r'rm\s+-rf?\s+/(\s|$)', 'rm -rf / (시스템 파괴)'),
    (r'\bDROP\s+TABLE\b', 'DROP TABLE'),
    (r'\bTRUNCATE\s+TABLE\b', 'TRUNCATE TABLE'),
]

# Phase 2-bis 추가 (2026-04-10 사고 재발방지)
DESTRUCTIVE_CHAIN = [
    (
        r'\|\|[^|]*\b(rm|mv)\b',
        '|| 와 같은 줄의 rm/mv 금지: && 체인 실패 시 fallback으로 destructive op 실행됨. '
        '재발방지 룰 (2026-04-10 사고). 별도 Bash 호출로 분리하세요.',
    ),
    (
        r'\b(rm|mv)\b[^|]*\|\|',
        'rm/mv 다음 || 금지: 마찬가지 위험 클래스. 별도 Bash 호출 사용.',
    ),
    (
        r'rm\s+-rf?\s+\$(?!\{[A-Za-z_][A-Za-z_0-9]*:\?)',
        'rm -rf $VAR (가드 없는 변수): $VAR가 비면 rm -rf / 와 같음. '
        '${VAR:?must be set} 가드 필수.',
    ),
    (
        r'find\s+[^|]*-delete',
        'find -delete: 필터 오타 시 광범위 삭제. find -print 으로 먼저 확인 권장. '
        '꼭 필요하면 결과를 xargs로 받아 별도 Bash 호출.',
    ),
]

# Phase 5 Zero-Trust: gh pr create 시 flag 체크
if re.search(r'gh\s+pr\s+create', cmd):
    import os
    ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.environ.get("PROJECT_ROOT", "."))
    flag_path = f"{ROOT}/.sisyphus/state/zero-trust-passed.flag"
    if not os.path.exists(flag_path):
        sys.stderr.write("\n[BLOCKED by Phase 5 Zero-Trust]\n\n")
        sys.stderr.write("  PR 생성 전에 Zero-Trust 검증이 필요합니다.\n")
        sys.stderr.write("  실행: ./zero-trust.sh\n\n")
        sys.stderr.write("  Zero-Trust 3단계:\n")
        sys.stderr.write("    1) validate.sh (정적 검증)\n")
        sys.stderr.write("    2) 서버 import smoke test\n")
        sys.stderr.write("    3) 서버 실행 + 헬스체크\n\n")
        sys.exit(2)
    else:
        # flag의 SHA가 현재 HEAD와 일치하는지 확인
        try:
            import subprocess
            head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
            flag_sha = open(flag_path).read().strip()
            if head_sha != flag_sha:
                sys.stderr.write("\n[BLOCKED by Phase 5 Zero-Trust]\n\n")
                sys.stderr.write(f"  Zero-Trust flag SHA ({flag_sha[:8]}...) != HEAD SHA ({head_sha[:8]}...)\n")
                sys.stderr.write("  검증 후 새 커밋이 추가되었습니다. ./zero-trust.sh 를 다시 실행하세요.\n\n")
                sys.exit(2)
        except Exception as e:
            sys.stderr.write(f"\n[BLOCKED by Phase 5 Zero-Trust]\n\n")
            sys.stderr.write(f"  SHA 검증 실패: {e}\n")
            sys.stderr.write("  ./zero-trust.sh 를 다시 실행하세요.\n\n")
            sys.exit(2)

violations = []
for pat, msg in LEGACY + DESTRUCTIVE_CHAIN:
    if re.search(pat, cmd, re.IGNORECASE):
        violations.append(msg)

if violations:
    sys.stderr.write("\n[BLOCKED by pre_bash_guard]\n")
    sys.stderr.write(f"  명령: {cmd[:300]}{'...' if len(cmd) > 300 else ''}\n\n")
    sys.stderr.write("  위반 패턴:\n")
    for v in violations:
        sys.stderr.write(f"    - {v}\n")
    sys.stderr.write(
        "\n  해결: 위 패턴을 별도 Bash 호출로 분리하거나, 변수 가드 ${VAR:?} 사용.\n"
        "        사용자가 명시적으로 우회 승인하면 사용자에게 직접 실행을 부탁하세요.\n"
    )
    sys.exit(2)

sys.exit(0)
PY
