# 003 — Momus 리뷰 (엄격한 검토)

- plan: `../plan.md`
- 검토자: Momus (엄격한 검토)
- 판정: **reject**
- 일시: 2026-04-27

## 이전 reject(002) 3건 반영 확인

모두 정상 반영.

## 결함 1건

Step 4-1이 `.claude/hooks/` 파일을 수정하려 하지만 CLAUDE.md가 "수정 금지"로 선언. plan에 정당화 없음.

## 요구 수정: Step 4-1 삭제 또는 규칙 조정

(a) CLAUDE.md hook 규칙 범위 조정, 또는 (b) Step 4-1 삭제 + 기존 "ws 블록" 키워드 하위 호환으로 의식적 제외 명시.
