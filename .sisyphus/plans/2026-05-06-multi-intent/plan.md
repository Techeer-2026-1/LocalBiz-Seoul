# Multi-Intent — 중첩된 요청 대응 (복수 intent 순차 실행)

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-06
- 상태: APPROVED

## 1. 요구사항

사용자가 "홍대 카페 추천해주고 주말 전시회도 알려줘"처럼 **복수 intent가 포함된 쿼리**를 보내면,
각 intent를 순차 실행하고 `done_partial` 제어 이벤트로 구분하여 SSE 스트리밍한다.

**엔드포인트**: `GET /api/v1/chat/stream?query=홍대 카페 추천해주고 주말 전시회도 알려줘`

**SSE 이벤트 흐름** (기획서 §4.5):
```
Intent #1 (PLACE_RECOMMEND):
  intent → status → text_stream → places → map_markers → references
  → done_partial {completed_intent: "PLACE_RECOMMEND"}

Intent #2 (EVENT_SEARCH):
  intent → status → text_stream → events
  → done {status: "done"}
```

**`done_partial`**: SSE 제어 이벤트. messages.blocks에 저장하지 않음 (불변식 #10 주석 참조).
**`done`**: 모든 intent 처리 완료 시 최종 전송.

**단일 intent 쿼리**: 기존과 동일하게 동작 (done_partial 없이 done만).

**intent 최대 개수**: 3개 제한 (무한 체인 방지).

**DB 저장**: 전체 intent의 블록을 하나의 assistant 메시지로 INSERT (append-only, 불변식 #3).

### 설계 결정

### 왜 SSE 핸들러 레벨에서 루프하는가

LangGraph 그래프 내부에 multi-intent 루프를 넣으면:
- StateGraph 구조 변경 필요 (순환 엣지, 복잡도 급증)
- 기존 단일 intent 노드 전부 영향
- 테스트/디버깅 어려움

대신 **SSE 핸들러(`sse.py`)에서 intent별로 그래프를 재실행**:
- 그래프 구조 변경 없음
- 기존 노드 코드 변경 없음
- intent 분류만 SSE 핸들러에서 선행

### 그래프 재실행 시 중복 호출 문제

그래프 실행 시 `intent_router → query_preprocessor → [노드]` 순서로 실행됨.
매 intent마다 그래프를 재실행하면 intent_router/query_preprocessor가 불필요하게 재실행되는 문제.

**해결**: SSE에서 `classify_intents()` 선행 호출 → **모든 intent에 대해** `input_state`에 `intent`를 주입.
그래프 내 `intent_router_node`는 **intent가 주입되면 분류 스킵**, intent 블록만 emit.

```python
# intent_router_node — 이미 intent가 주입되면 classify 스킵
if state.get("intent"):
    return {"response_blocks": [{"type":"intent", ...}]}  # intent 블록만 emit
```

### processed_query 재사용 불가 — intent별 sub_query로 전처리

"카페 추천하고 전시회 알려줘"에서 첫 intent의 processed_query(`category="카페"`)를
두번째 intent(EVENT_SEARCH)에 재사용하면 **category 오염**. 따라서:

- `classify_intents()`가 **intent별 sub_query**도 함께 반환
- 매 intent마다 **sub_query로 query_preprocessor를 실행** (스킵하지 않음)
- query_preprocessor는 가드 없이 기존 코드 그대로 유지

```json
{"intents": [
  {"intent": "PLACE_RECOMMEND", "confidence": 0.9, "sub_query": "홍대 카페 추천해줘"},
  {"intent": "EVENT_SEARCH", "confidence": 0.85, "sub_query": "주말 전시회 알려줘"}
]}
```

### FE 영향

FE(`useWebSocket.ts`)에서 `done_partial` 이벤트 수신 시:
- `isLoading = true` 유지 (finalize 하지 않음)
- 블록 누적 계속
- `done` 수신 시 비로소 finalize

→ **FE 수정은 이 plan 범위 밖** (별도 이슈). BE는 `done_partial` 이벤트만 정상 emit하면 됨.

## 2. 영향 범위

- **수정 파일**:
  - `backend/src/graph/intent_router_node.py` — `classify_intents()` 새 함수 추가 + 노드에 intent 주입 가드
  - `backend/src/api/sse.py` — event_generator에 multi-intent 루프 추가
- **신규 파일**:
  - `backend/tests/test_multi_intent.py`
- **DB 스키마 영향**: 없음 (messages.blocks JSONB에 블록 리스트 그대로 저장)
- **응답 블록 16종 영향**: 변경 없음. `done_partial`은 SSE 제어 이벤트 (16종 밖)
- **외부 API 호출**: Gemini classify_intents 1회 + query_preprocessor intent별 실행 (최대 3회)
- **query_preprocessor_node.py**: 수정 없음 (매 intent마다 sub_query로 정상 실행)

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — 해당 없음
- [x] #2 PG↔OS 동기화 — 해당 없음
- [x] #3 append-only 4테이블 — messages INSERT만 (전체 블록 단일 메시지)
- [x] #4 소프트 삭제 — 해당 없음
- [x] #5 비정규화 — 신규 없음
- [x] #6 6지표 — 해당 없음
- [x] #7 임베딩 — 해당 없음
- [x] #8 asyncpg 바인딩 — 해당 없음 (기존 _insert_message 재사용)
- [x] #9 Optional[str] — 준수
- [x] #10 SSE 이벤트 타입 16종 — done_partial은 SSE 제어 이벤트 (16종 밖, 기획서 §4.5 명시)
- [x] #11 intent별 블록 순서 — 각 intent 실행마다 기존 순서 그대로 유지
- [x] #12 공통 쿼리 전처리 — intent별 sub_query로 실행 (경로 유지)
- [x] #13 행사 검색 순서 — 해당 없음 (노드 코드 미수정)
- [x] #14 대화 이력 이원화 — 보존
- [x] #15 인증 매트릭스 — 해당 없음
- [x] #16 북마크 — 해당 없음
- [x] #17 공유링크 — 해당 없음
- [x] #18 Phase 라벨 — P1
- [x] #19 기획 문서 우선 — API 명세서 v2 SSE 준수

## 4. 작업 순서 (Atomic step)

### g1 — classify_intents() 함수 추가 (intent_router_node.py)

기존 `classify_intent()` 유지 (하위 호환). 새 함수 `classify_intents()` 추가.

**핵심**: intent별 **sub_query**를 함께 반환하여 query_preprocessor가 각 intent에 맞는 전처리 실행 가능.

```python
_CLASSIFY_MULTI_SYSTEM_PROMPT = """
...
If the query contains multiple distinct requests, split them and return ALL matching intents.
Return JSON: {"intents": [{"intent": "...", "confidence": 0.X, "sub_query": "..."}, ...]}
- sub_query: the portion of the original query that corresponds to this intent (in Korean)
- Maximum 3 intents per query.
- If only one intent, return list with single element (sub_query = original query).
- "카페에서 전시회 가는 코스" is ONE intent (COURSE_PLAN), not two.
"""

async def classify_intents(
    query: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> list[tuple[IntentType, float, str]]:
    """복수 intent 분류. 최대 3개.

    Returns:
        [(IntentType, confidence, sub_query), ...]. 최소 1개 보장.
    """
```

- 단일 intent → `[("PLACE_SEARCH", 0.95, "홍대 카페 추천해줘")]`
- 복수 intent → `[("PLACE_RECOMMEND", 0.9, "홍대 카페 추천해줘"), ("EVENT_SEARCH", 0.85, "주말 전시회 알려줘")]`
- Phase 2 intent → GENERAL fallback (sub_query 유지)
- 빈 결과 → `[("GENERAL", 0.0, query)]` fallback
- 3개 초과 → 앞 3개만 채택

> verify: 단위 테스트 — mock Gemini 응답으로 단일/복수/3개 초과 검증

### g2 — intent_router_node 주입 가드

`intent_router_node(state)` 수정:
- `state.get("intent")`가 이미 있으면 classify 스킵, intent 블록만 emit
- 없으면 기존 `classify_intent()` 호출 (단일 intent, 하위 호환)

```python
async def intent_router_node(state: dict[str, Any]) -> dict[str, Any]:
    pre_injected = state.get("intent")
    if pre_injected:
        return {
            "response_blocks": [
                {"type": "intent", "intent": pre_injected, "confidence": 1.0}
            ]
        }
    # 기존 로직 (classify_intent 호출)...
```

> verify: `ruff check && pyright`

### g3 — sse.py multi-intent 루프 (핵심)

`event_generator()` 수정:

**변경 후** (multi-intent):
```python
from src.graph.intent_router_node import classify_intents

graph = build_graph()

# 1. 복수 intent 분류 (SSE에서 선행, Gemini 1회)
intents = await classify_intents(query, conversation_history=[])

# 2. intent별로 그래프 순차 실행
for idx, (intent, confidence, sub_query) in enumerate(intents):
    is_last = (idx == len(intents) - 1)

    # 모든 intent에 intent를 주입 → intent_router_node 스킵
    # sub_query를 query로 전달 → query_preprocessor가 intent별 전처리
    input_state = {
        "query": sub_query,
        "intent": intent.value,
        "thread_id": thread_id,
        "user_id": user_id,
        "conversation_history": [],
    }

    async for event in graph.astream(input_state):
        for node_name, node_output in event.items():
            blocks = node_output.get("response_blocks", [])
            for block in blocks:
                block_type = block.get("type", "")

                # done 블록: 중간 intent에서는 무시 + DB 저장도 안 함
                if block_type == "done":
                    if is_last:
                        assistant_blocks.append(block)
                    # 중간 intent의 done은 완전히 무시
                    continue

                # 나머지 블록: 기존 로직 (text_stream 스트리밍 등)
                ...

    # 중간 intent 완료 → done_partial emit (DB 미저장)
    if not is_last:
        yield format_sse_event("done_partial", {
            "type": "done_partial",
            "completed_intent": intent.value,
        })

# 전체 블록 단일 메시지 INSERT
await _insert_message(pool, thread_id, "assistant", assistant_blocks)
yield format_done_event(status="done")
```

**핵심 변경점**:
- **모든 intent에 intent 주입** → intent_router_node가 분류 스킵 (Gemini 중복 호출 방지)
- **sub_query를 query로 전달** → query_preprocessor가 intent에 맞는 전처리 실행 (category 오염 방지)
- **중간 intent의 done 블록**: SSE emit도 안 하고 assistant_blocks 저장도 안 함 (중복 done 방지)
- **마지막 intent의 done 블록만** assistant_blocks에 저장
- **done_partial**: SSE emit만 (DB 미저장, 기획서 §4.5 준수)

> verify: 수동 테스트 — 단일/복수 intent 쿼리 모두 정상 동작

### g4 — 단위/통합 테스트

`tests/test_multi_intent.py`:

- `test_classify_intents_single`: "홍대 카페 추천" → 1개 intent, sub_query = 원본
- `test_classify_intents_multi`: "카페 추천해주고 전시회 알려줘" → 2개 intent + sub_query 분리 (mock Gemini)
- `test_classify_intents_max_3`: 4개 이상 → 앞 3개만 채택
- `test_classify_intents_phase2_filter`: Phase 2 intent → GENERAL fallback
- `test_classify_intents_fallback`: Gemini 실패 → [("GENERAL", 0.0, query)]
- `test_intent_router_node_injected`: intent 주입 시 classify 스킵, intent 블록만 반환
- `test_intent_router_node_no_injection`: intent 미주입 시 기존 classify_intent 호출 (regression)

> verify: `pytest tests/test_multi_intent.py -v`

### g5 — 전체 검증 + regression

- 기존 단일 intent 테스트 전부 통과 확인 (intent_router_node 가드가 기존 동작에 영향 없는지)
- `pytest tests/ -v` 전체 통과

> verify: `./validate.sh`

## 5. 검증 계획

- `./validate.sh` 전체 통과
- `pytest tests/test_multi_intent.py -v` — 7개 케이스 통과
- `pytest tests/ -v` 전체 통과 (기존 단일 intent 테스트 regression 없음)
- 수동 시나리오:
  1. `query=홍대 카페 추천해주고 주말 전시회도 알려줘` → SSE에서 PLACE_RECOMMEND 블록 → done_partial → EVENT_SEARCH 블록 → done
  2. `query=홍대 카페 추천해줘` → 기존과 동일 (done_partial 없음, done만)
  3. `query=카페 추천하고 맛집 찾아주고 코스 짜줘` → 3개 intent 순차 실행
  4. DB messages.blocks에 전체 블록 단일 row 저장 확인

## 6. 리스크

- **Gemini 분류 정확도**: 복수 intent 분리 + sub_query 추출이 부정확할 수 있음. "카페에서 전시회 가는 코스" → COURSE_PLAN 1개 vs PLACE_RECOMMEND + EVENT_SEARCH 2개? → 프롬프트에 "하나의 목적이면 하나의 intent" 명시
- **응답 시간**: intent 수만큼 그래프 재실행 + query_preprocessor Gemini 호출. 3개 제한 + classify_intents는 1회만으로 방어. 최악 case: classify 1회 + preprocess 3회 + 노드별 Gemini 3회 = 7회 Gemini 호출
- **sub_query 품질**: Gemini가 sub_query를 잘못 분리하면 query_preprocessor 결과 부정확. fallback: sub_query가 빈 문자열이면 원본 query 사용

## 7. 최종 결정

APPROVED — 2026-05-06 PM 승인. 런타임 시뮬레이션 + 엣지 케이스 검증 완료. 구현 진입.
