#!/bin/bash
# Phase 2-bis A2: UserPromptSubmit hook — 트리거 키워드 매칭으로
# 사용자 프롬프트에 "필수 호출 스킬" 인젝션.
#
# 호출 규약 (Claude Code UserPromptSubmit hook):
#   stdin: {"hook_event_name":"UserPromptSubmit","prompt":"...","session_id":"...","cwd":"..."}
#   stdout: 메인 컨텍스트에 시스템 메시지로 prepend됨
#   exit 0: 정상 (인젝션 적용)
#   exit 2: 차단 (사용 안 함 — 사용자 질문까지 막으면 안 됨)
#
# /force 키워드가 프롬프트에 있으면 인젝션 스킵 (사용자 명시적 우회).

set -u

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PROJECT_ROOT

input=$(cat)

python3 - "$input" <<'PY'
import sys, json

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

prompt = data.get("prompt", "") or ""
session_id = data.get("session_id", "default") or "default"
if not prompt.strip():
    sys.exit(0)

# 사용자 명시적 우회
if "/force" in prompt:
    sys.exit(0)

# 스킬별 트리거 키워드 (대소문자 무시 + 한글 그대로)
TRIGGERS = {
    "localbiz-plan": [
        "새 기능", "추가해줘", "구현해줘", "만들어줘",
        "리팩토링", "재작성", "구조 변경",
        "버그 ", "안 돌아가", "고쳐줘",
        "intent 추가", "응답 블록 추가", "노드 추가", "etl 추가",
        "/plan", "기획부터", "설계 먼저",
    ],
    "localbiz-erd-guard": [
        "테이블 추가", "컬럼 추가", "스키마 변경", "ddl",
        "alter table", "create table", "drop column", "rename",
        "score_", "place_analysis", "6 지표", "지표 변경",
        "administrative_districts", "population_stats", "bookmarks",
        "shared_links", "langgraph_checkpoints",
    ],
    "localbiz-etl-structured": [
        "정형 etl", "csv 적재", "places 적재", "events 적재",
        "행정동", "생활인구", "서울시 공공데이터", "data.seoul.go.kr",
        "tm 좌표", "행정동 폴리곤",
    ],
    "localbiz-etl-unstructured": [
        "비정형", "리뷰 분석", "리뷰 적재", "가격 수집",
        "이미지 캡셔닝", "임베딩 적재",
        "naver blog", "google reviews", "place_reviews",
        "batch_review", "load_place_reviews", "collect_price",
        "load_image_captions",
    ],
    "localbiz-langgraph-node": [
        "새 노드", "노드 추가", "ws 블록", "응답 블록",
        "real_builder", "intent_router", "agentstate",
        "chart 블록", "calendar 블록", "place 블록",
    ],
    "localbiz-memory-dream": [
        "메모리 정리", "consolidation", "memory.md 압축",
        "auto dream", "메모리 정합", "오래된 메모리",
    ],
    "localbiz-validate": [
        "validate", "검증해", "validate.sh", "pr 머지", "끝났어",
        "테스트 돌려", "통과했어", "체크해줘",
    ],
}

prompt_lc = prompt.lower()
triggered = []
for skill, keywords in TRIGGERS.items():
    for kw in keywords:
        if kw.lower() in prompt_lc:
            triggered.append(skill)
            break

if not triggered:
    sys.exit(0)

# 중복 제거 + pending 파일에 append (PreToolUse hook이 검사)
import os
triggered = sorted(set(triggered))
project_root = os.environ.get("PROJECT_ROOT", ".")
pending_path = os.path.join(project_root, ".sisyphus", "state", "pending_skills.txt")
os.makedirs(os.path.dirname(pending_path), exist_ok=True)

# 기존 pending 읽어서 같은 (session, skill) 중복 안 적기
existing = set()
if os.path.exists(pending_path):
    with open(pending_path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                existing.add((parts[0], parts[1]))

with open(pending_path, "a", encoding="utf-8") as f:
    for skill in triggered:
        if (session_id, skill) not in existing:
            f.write(f"{session_id}\t{skill}\n")

print("=" * 60)
print("[Phase 2-bis SKILL ROUTER] 트리거 감지")
print("=" * 60)
print(f"매칭된 스킬: {', '.join(triggered)}")
print("")
print("MANDATORY: 위 스킬을 Skill 도구로 호출한 뒤 작업을 시작하세요.")
print("각 스킬 디렉터리의 SKILL.md(L1) → REFERENCE.md(L2) 순서로 Read.")
print("")
print("우회가 필요하면 사용자에게 '/force' 입력을 요청하세요.")
print("Edit/Write/Bash는 해당 스킬을 호출하지 않으면 PreToolUse hook이 차단합니다.")
print("=" * 60)
sys.exit(0)
PY
