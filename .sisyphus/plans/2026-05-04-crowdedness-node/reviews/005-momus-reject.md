# Momus 2차 검토 — REJECT

- 검토자: momus
- 검토일: 2026-05-04
- 판정: REJECT

## 결정적 reject 사유

### [R1] API 명세서 v2 (SSE) CSV 라인 번호 오류

plan §1 L18 인용: `기획/API 명세서 v2 (SSE) ...csv L150`
fs 실측: CROWDEDNESS row = **L152** (L150은 COST_ESTIMATE 멀티라인 빈 줄)
Metis 004 본문도 "CSV L152"로 인용 → plan §1의 "L150" 명백한 오류.

### [R2] CSV vs legacy 시퀀스 차이 노트 부재 (Metis OKAY 후속 권고 #1 미반영)

- API 명세서 v2 CSV L152: `intent → text_stream → done` (status 없음)
- 서비스 통합 기획서 v2.md L178: `intent → status → text_stream → done`
- sse.py L97 `_NODE_STATUS_MESSAGES`가 노드 진입 시 status 자동 emit → 양립 가능하나 plan에 노트 없음.
  6개월 뒤 구현자가 두 source 충돌을 발견했을 때 권위 판단 불가.

### [R3] §3 불변식 체크박스 19개 전부 `[ ]` — 자기검증 흔적 부재

TEMPLATE 그대로 복사. Momus 검토 기준: "각 항목이 plan 본문에서 어떻게 준수되는지 최소 흔적(체크 표시) 필요". 본문 근거는 충분하나 `[x]` 표시 전무.

## 요구 수정사항

1. plan §1 L18 `L150` → `L152` 정정
2. plan §1 L24 또는 §2에 노트 추가: "API 명세서 v2 CSV L152는 `intent → text_stream → done`; sse.py `_NODE_STATUS_MESSAGES` 자동 emit으로 legacy 기획서 v2 L178 `intent → status → text_stream → done`과 양립"
3. plan §3 19 불변식 항목 관련 항목 `[x]` 마킹 (본문 근거 충분, 체크만 필요)

## 다음 액션

plan.md 3건 수정 → Metis 4차 okay → Momus 3차 재호출 (006-momus-*.md)
