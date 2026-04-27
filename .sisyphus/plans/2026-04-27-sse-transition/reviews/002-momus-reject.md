# 002 — Momus 리뷰 (엄격한 검토)

- plan: `../plan.md`
- 검토자: Momus (엄격한 검토)
- 판정: **reject**
- 일시: 2026-04-27

## 요구 수정사항

### R1. 영향 범위 수정 파일 목록 보완 (MUST)
Section 2 + Step 4-2에 누락된 2파일 추가:
- `.claude/skills/localbiz-erd-guard/REFERENCE.md` (WS 참조 1건)
- `.claude/agents/fe-visual.md` (WS 참조 2건)

### R2. 불변식 #10 원문 수정 범위 명시 (MUST)
CLAUDE.md 불변식 #10의 "WS 블록"/"WS 제어 프레임" 용어를 SSE로 변경하는지 명시. 코드리뷰 체크리스트 "WS 블록 추가/제거 시"도 함께 갱신 여부 명시.

### R3. 검증 계획 grep 범위 통일 (MUST)
Section 5의 grep을 프로젝트 전체 범위로 갱신. 현재 `backend/src/`만 대상이라 `.claude/`, `CLAUDE.md`, `기획/` 잔존을 검출하지 못함.
