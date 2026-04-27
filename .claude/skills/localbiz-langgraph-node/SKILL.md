---
name: localbiz-langgraph-node
description: LangGraph 새 노드·intent·응답 블록 추가 시 등록 6단계 강제. real_builder + intent_router + Pydantic + 16 블록 한도 + 기획 §4.5 동기화.
phase: 2
project: localbiz-intelligence
---

# localbiz-langgraph-node (L1)

LangGraph 그래프 확장 절차적 가드.

## 발동 조건

- "새 노드", "노드 추가", "PLACE_RECOMMEND 같은 intent", "intent 추가"
- "응답 블록 추가", "SSE 이벤트", "WS 블록", "chart/calendar/place 블록"
- "real_builder", "intent_router", "AgentState"
- 12+1 intent (PLACE_SEARCH, PLACE_RECOMMEND, EVENT_SEARCH, COURSE_PLAN, ANALYSIS, DETAIL_INQUIRY, COST_ESTIMATE, CROWDEDNESS, BOOKING, REVIEW_COMPARE, IMAGE_SEARCH, FAVORITE, GENERAL) 변경

## L2 본문

체크리스트·intent별 블록 순서표·text_stream 패턴은 같은 디렉터리의 `REFERENCE.md`를 Read.
