---
name: localbiz-plan
description: 새 기능·리팩토링·버그픽스 요청 시 즉시 코딩하지 말고 .sisyphus/plans/에 plan 작성. 19 불변식 + Phase 라벨 + Metis/Momus 리뷰.
phase: 2
project: localbiz-intelligence
---

# localbiz-plan (L1)

코드를 짜기 전에 plan을 강제하는 게이트.

## 발동 조건

- "새 기능", "추가해줘", "구현해줘", "만들어줘"
- "리팩토링", "재작성", "구조 변경"
- "버그", "안 돌아가", "고쳐줘" (1줄 fix는 예외)
- intent 추가, 응답 블록 추가, 노드 추가, ETL 추가
- 사용자가 "/plan", "기획부터", "설계 먼저" 같은 명시 호출

## L2 본문

상세 절차·체크리스트·plan 양식은 같은 디렉터리의 `REFERENCE.md`를 Read.
