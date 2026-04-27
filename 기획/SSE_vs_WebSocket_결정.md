# LocalBiz Intelligence - AI 채팅 프로토콜 결정: SSE vs WebSocket

## TL;DR

**결정: SSE(Server-Sent Events)로 전환.** 기존 API 명세서의 WebSocket 기반 설계를 SSE 기반으로 재작성 필요.

## 배경

API 명세서 `API_명세서_424797f5eaec40c2bc66463118857814.csv`에는 채팅 관련 엔드포인트가 `/api/v1/chat/ws`로 WebSocket 기반 설계되어 있음. 12개 intent (PLACE_SEARCH, EVENT_SEARCH, PLACE_RECOMMEND, ANALYSIS, COURSE_PLAN, IMAGE_SEARCH, CALENDAR, BOOKING, REVIEW_COMPARE, COST_ESTIMATE, CROWDEDNESS, GENERAL) 모두 WebSocket으로 처리하는 구조.

검토 결과 현재 시스템 요구사항에는 SSE가 더 적합하다고 판단되어 전환 결정.

## 결정 근거

### 1. 실제 요구사항이 단방향 스트리밍 중심

LocalBiz의 핵심 기능은 "질의 → 풍부한 인사이트 스트리밍 응답"이다. 거의 모든 intent가 다음 패턴을 따름:

- **장소/행사/이미지 검색**: 쿼리 → 결과. 단방향.
- **장소 추천, 리뷰 비교, 비용 견적**: 쿼리 → 결과. 단방향.
- **단일 장소 분석(ANALYSIS)**: 쿼리 → 6지표 분석. 단방향.
- **코스 추천(COURSE_PLAN)**: 쿼리 → 코스 + 지도 경로. 단방향.

본질적으로 "검색 + 인사이트 제공" 서비스이며, 챗봇 UI를 입고 있지만 실제 통신 패턴은 OpenAI/Anthropic API와 유사한 스트리밍 응답 구조.

### 2. 양방향 기능의 실제 필요성이 낮음

명세서상 양방향 제어가 필요해 보이는 기능들을 재검토한 결과:

**Disambiguation**: 한두 intent에서만 사용 예정. 다음 방식으로 처리 가능:
- 옵션 A: "새 쿼리 자동 전송" 방식 (사용자가 선택지 클릭 시 새 SSE 스트림으로 재질의). UX상 자연스럽고 구현 가장 단순.
- 옵션 B: `pending_disambiguations` dict + `asyncio.Future` 로 같은 세션 내 이어가기. 단일 서버 구조에서 간단히 구현 가능.

**Interrupt (응답 중단)**: SSE에서는 FastAPI의 `request.is_disconnected()`로 클라이언트 disconnect를 감지해 처리. 별도 `/cancel` 엔드포인트 불필요.

```python
async def event_generator(request: Request):
    async for token in search_and_generate(query):
        if await request.is_disconnected():
            break  # 클라 연결 끊김 감지 시 파이프라인 중단
        yield f"data: {json.dumps({'content': token})}\n\n"
```

**음성 모드**: 계획 없음. WebSocket의 바이너리 지원 이점 불필요.

### 3. 단일 서버 구조

아키텍처 다이어그램 기준 GCE 인스턴스 하나에 FastAPI + LangGraph 운영. SSE의 일반적 단점으로 거론되는 "분산 환경에서의 세션 라우팅 복잡도, Redis Pub/Sub 필요"가 현재 구조에서는 적용되지 않음. 단일 프로세스 내 메모리 기반 상태 관리로 충분.

### 4. 인프라/운영 단순성

| 항목 | SSE | WebSocket |
|---|---|---|
| 로드밸런서 설정 | 기본 HTTP 그대로 | Upgrade 헤더 전달 설정 필요 |
| Sticky session | 불필요 | 필요 |
| Nginx timeout | `proxy_read_timeout` 단일 | 업그레이드 연결 별도 설정 |
| CDN 호환성 | 완전 지원 | 플랜별 제약 |
| 무중단 배포 | 쉬움 | 어려움 (재연결 폭주 가능) |
| 자동 재연결 | 브라우저 기본 제공 | 직접 구현 필요 |

### 5. 디버깅/테스트 편의

- **SSE**: `curl -N http://...` 한 줄로 테스트. 브라우저 DevTools Network 탭에서 스트림 내용 그대로 확인.
- **WebSocket**: `websocat` 같은 별도 도구 필요. DevTools에서 프레임 단위 확인.

팀 전체의 개발 속도와 자립적 디버깅 역량 측면에서 SSE가 유리.

### 6. 장애 복구 (모바일 환경)

- **SSE**: 브라우저가 `Last-Event-ID` 헤더 기반 자동 재연결. 네트워크 전환(Wi-Fi ↔ LTE) 자동 처리.
- **WebSocket**: 모든 재연결 로직 직접 구현. 모바일 네트워크 전환 수동 처리.

### 7. LLM 생태계 정렬

OpenAI, Anthropic, Google Gemini 등 주요 LLM API가 전부 SSE 기반 스트리밍. 현재 외부 API로 Gemini, Claude를 사용하는 구조에서 통신 프로토콜 일관성 확보.

### 8. 개발 진입 전 타이밍

아직 본격 구현 시작 전이라 변경 비용이 최소. 개발 진입 후 프로토콜 전환 시 FE/BE 양쪽 코드, 인증 흐름, 테스트 코드 전면 재작성 필요 (통상 1~2주 소요). 지금 전환 시 문서 수정 반나절 수준.

## 트레이드오프

SSE 전환으로 얻는 것과 포기하는 것을 명확히 인지:

### 얻는 것
- 인프라/코드 단순성
- 디버깅 용이성
- 모바일 환경 자동 재연결
- LLM API 생태계와의 일관성
- 단일 서버 기준 리소스 효율 (idle 연결 유지 비용 없음)

### 포기하는 것
- 양방향 실시간 제어의 자연스러움 (disambiguation 시 우회 필요)
- 음성/바이너리 데이터 지원 (현재 계획 없음)
- 작은 메시지 고빈도 교환 효율 (해당 사항 없음)

## 구현 가이드

### 엔드포인트 구조

```
GET  /api/v1/chat/stream?thread_id=xxx&query=yyy  # SSE 스트림 시작
POST /api/v1/chat/disambiguation/reply             # disambiguation 답변 (옵션 B 선택 시)
```

Cancel은 별도 엔드포인트 불필요 - 클라이언트가 `EventSource.close()` 또는 `AbortController.abort()` 호출 시 서버가 `is_disconnected()`로 감지.

### 이벤트 타입

기존 명세서의 이벤트 타입 그대로 재활용:
- `intent`, `status`, `text_stream`
- `place`, `places`, `events`, `course`, `map_markers`, `map_route`
- `chart`, `calendar`, `references`, `analysis_sources`
- `disambiguation`, `done`, `error`

### SSE 메시지 포맷

```
event: status
data: {"content": "의도를 파악하고 있어요..."}

event: text_stream
data: {"content": "강남역 근처에는"}

event: places
data: {"items": [...]}

event: done
data: {}

```

빈 줄 두 개(`\n\n`)가 이벤트 구분자. `event:` 필드로 타입 분기 가능.

### 인증

브라우저 기본 `EventSource`는 `Authorization` 헤더 커스터마이징 불가. 대응 방안:

1. **쿠키 기반 인증**: Refresh Token을 HttpOnly 쿠키로 관리하는 현재 설계와 호환. Access Token도 쿠키로 전송하거나,
2. **fetch 스트리밍 라이브러리**: `@microsoft/fetch-event-source` 사용 시 커스텀 헤더 가능. JWT Bearer 인증 유지 가능.

JMT 프로젝트의 JWT 설계(Access Token 30분 클라 메모리, Refresh Token HttpOnly 쿠키)와 일관성을 위해 **옵션 2 권장**.

### FastAPI 구현 스켈레톤

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()
pending_disambiguations: dict[str, asyncio.Future] = {}

@app.get("/api/v1/chat/stream")
async def chat_stream(request: Request, thread_id: str, query: str):
    async def event_generator():
        # Intent 파악
        yield f"event: status\ndata: {json.dumps({'content': '의도 파악 중...'})}\n\n"
        intent = await analyze_intent(query)

        yield f"event: intent\ndata: {json.dumps({'type': intent.type})}\n\n"

        # Disambiguation 필요 시 (옵션 B)
        if intent.is_ambiguous:
            yield f"event: disambiguation\ndata: {json.dumps({'options': intent.options})}\n\n"
            future = asyncio.Future()
            pending_disambiguations[thread_id] = future
            try:
                choice = await asyncio.wait_for(future, timeout=60)
            except asyncio.TimeoutError:
                yield f"event: error\ndata: {json.dumps({'reason': 'disambiguation_timeout'})}\n\n"
                return
            finally:
                pending_disambiguations.pop(thread_id, None)
        else:
            choice = None

        # 본 처리 (토큰 스트리밍)
        async for event in process_intent(intent, choice):
            if await request.is_disconnected():
                return  # 클라 끊기면 자동 중단
            yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"

        yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/v1/chat/disambiguation/reply")
async def disambiguation_reply(thread_id: str, choice: int):
    future = pending_disambiguations.get(thread_id)
    if not future or future.done():
        raise HTTPException(404, "No pending disambiguation")
    future.set_result(choice)
    return {"ok": True}
```

### 프론트엔드 구현 스켈레톤

```javascript
import { fetchEventSource } from '@microsoft/fetch-event-source';

const ctrl = new AbortController();

await fetchEventSource('/api/v1/chat/stream?thread_id=xxx&query=yyy', {
  headers: { 'Authorization': `Bearer ${accessToken}` },
  signal: ctrl.signal,
  onmessage(ev) {
    const data = JSON.parse(ev.data);
    switch (ev.event) {
      case 'status': updateStatus(data.content); break;
      case 'text_stream': appendToken(data.content); break;
      case 'places': renderPlaces(data.items); break;
      case 'disambiguation': showDisambiguation(data.options); break;
      case 'done': finalize(); break;
      case 'error': handleError(data); break;
    }
  },
  onerror(err) {
    // fetch-event-source가 자동 재연결 처리
  }
});

// 중단 시
ctrl.abort();  // 서버의 is_disconnected()가 감지
```

## 변경 필요 문서

| 문서 | 변경 내용 | 예상 작업량 |
|---|---|---|
| API 명세서 CSV | WS 엔드포인트 20여 개 → SSE 엔드포인트로 재작성 (Method, URL, Request/Response 형식) | 2-3시간 |
| 기능 명세서 CSV | 통신 방식 관련 표현 수정 | 1시간 이내 |
| 아키텍처 다이어그램 | FastAPI 내부 통신 설명 부분 수정 | 30분 |
| Jira JMT 태스크 | WebSocket 관련 태스크 디스크립션 수정 | 1시간 |
| ERD | 변경 없음 | - |

총 예상 작업량: **반나절**

## 재검토 트리거

다음 조건 중 하나라도 충족되면 WebSocket 재검토:

- 음성 모드 기능 기획 확정
- 동시 접속자 수천 명 이상 규모 확장 + 작은 메시지 고빈도 교환 패턴 등장
- 실시간 협업 기능 (여러 사용자 동시 세션 공유) 추가
- LangGraph 파이프라인이 3단계 이상 양방향 상호작용 요구하는 복잡한 intent 추가

---

## 요약

**"프로토콜은 가장 단순한 걸 써라"** 원칙에서, 현재 요구사항에 대해 가장 단순한 선택은 SSE. 양방향 제어가 필요한 지점은 제한적이며, 필요한 경우 SSE + 보조 엔드포인트로 충분히 해결 가능. WebSocket의 강점(양방향 코드 단순성, 바이너리, 고빈도 교환)은 현재 요구사항에 비해 오버엔지니어링.

**개발 진입 전인 지금이 전환 최적 타이밍.**
