# Metis 3차 검토 — OKAY

- 검토자: metis
- 검토일: 2026-05-04
- 판정: OKAY (Momus 진행 가능)

## 결정 요약

1차/2차 지적 + Momus 1차 지적 전부 반영됨. 새로 발견한 모순 1건은 reject 사유 아님 (후속 권고).

## 해소 확인

- `_resolve_dong_code(neighborhood, district) -> Optional[str]` 시그니처 + JOIN SQL (파라미터 바인딩 $1/$2) 명시
- `_fetch_population(pool, dong_code, district, time_slot)` 시그니처 명시
- real_builder.py 4군데 각각 명시 (import / add_node / _route_by_intent / conditional_edges+edge loop)
- `_NODE_STATUS_MESSAGES` 키 이름 = 노드 이름 "crowdedness" 정합 확인
- CSV 라인 번호 L41 정정
- `monkeypatch.setattr("src.graph.crowdedness_node.datetime", FrozenDatetime)` 명시
- step 2(헬퍼 12개) / step 3(진입점 2개) / step 6(통합 1개) 검증 명령 분리
- avg_pop=0/NULL → 보통 fallback 명시
- 30일 윈도우 `base_date >= MAX(base_date) - INTERVAL '30 days'` 명시

## 후속 권고 (Momus 판단 영역)

1. API 명세서 v2 CSV L152는 `intent → text_stream → done` (status 없음) — legacy 기획서 v2 L178의 `intent → status → text_stream → done`과 미세 차이. sse.py가 노드 진입 시 status 자동 emit하므로 양립 가능하나 plan에 한 줄 노트 추가 권장.
2. §3 불변식 체크리스트 전 항목이 `[ ]` 빈 칸 — Momus가 형식 위반 여부 판정.
