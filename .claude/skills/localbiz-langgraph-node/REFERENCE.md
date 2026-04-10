# localbiz-langgraph-node — REFERENCE (L2)

LangGraph 그래프 확장 작업의 절차적 가드. 빠뜨리기 쉬운 등록 단계 6개를 강제.

## 절대 차단

- 16 응답 블록 외 신규 블록 도입 (기획 §4.5 변경 = plan 필요)
- intent별 블록 순서 변경 (기획 §4.5 권위)
- intent를 12+1 외로 추가 (기획 §3.1 갱신 필요)
- text_stream 블록을 LangGraph 노드 외부에서 발행

## 새 노드 등록 절차 (체크리스트)

```
[ ] 1. src/graph/{intent_lowercase}_node.py 생성
       - async def {name}_node(state: AgentState) -> dict 시그니처
       - response_blocks list 반환 (operator.add로 자동 누적)
[ ] 2. src/graph/real_builder.py 에 노드 등록
       - graph.add_node("{name}", {name}_node)
       - graph.add_edge("{name}", "response_composer")
[ ] 3. src/graph/intent_router_logic.py 의 INTENT_TO_NODE 매핑 추가
[ ] 4. src/graph/intent_router_node.py 의 Gemini 프롬프트에 intent 추가 (기존 12+1)
[ ] 5. 응답 블록 신규 시:
       - src/models/blocks.py 에 Pydantic 모델
       - 기획서 §4.5 표 동기화 (PM 합의 필수)
       - 프론트엔드 렌더러도 갱신 (FE 팀 통보)
[ ] 6. tests/test_{name}_node.py 단위 테스트
       - mock LLM 응답
       - response_blocks 순서·타입 검증
[ ] 7. validate.sh 통과 확인
```

## intent별 블록 순서 (기획 §4.5 권위 — 변경 금지)

| intent | 블록 순서 |
|---|---|
| GENERAL | intent → text_stream → done |
| PLACE_SEARCH | intent → status → text_stream → places[] → map_markers → done |
| PLACE_RECOMMEND | intent → status → text_stream → places[] → map_markers → references → done |
| EVENT_SEARCH | intent → status → text_stream → events[] → done |
| COURSE_PLAN | intent → status → text_stream → course → map_route → done |
| BOOKING | intent → text_stream(딥링크) → done |
| CALENDAR | intent → text_stream → calendar → done |
| ANALYSIS (P2) | intent → status → text_stream → analysis_sources → done |
| REVIEW_COMPARE (P2) | intent → status → text_stream → chart → analysis_sources → done |
| COST_ESTIMATE (P2) | intent → status → text_stream → done |
| CROWDEDNESS (P2) | intent → status → text_stream → done |
| IMAGE_SEARCH (P2) | intent → status → text_stream → place \| places[] \| disambiguation → done |
| Multi-Intent (P2) | (intent → status → text_stream → … → done_partial) × N → done |

## text_stream 블록 패턴
```python
state["response_blocks"].append({
    "type": "text_stream",
    "system": "당신은 ...",
    "prompt": f"질문: {query}",
})
# websocket.py가 Gemini astream()으로 토큰 단위 전송
```

## 참고 파일
- `backend/AGENTS.md` (현재 비어있음, 신규 작성 시 이 표 따를 것)
- `backend/_legacy_src/graph/real_builder.py` (참고만)
- `기획/API 명세서 ...all.csv` (intent별 응답 블록 권위)
- `기획/서비스 통합 기획서 ...md` §4.5
