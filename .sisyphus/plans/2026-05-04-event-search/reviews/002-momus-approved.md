# Momus 리뷰 — SSE 행사 검색 노드 (Issue #47)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (페르소나 채택)
- 검토일: 2026-05-04
- plan: `.sisyphus/plans/2026-05-04-event-search/plan.md`
- 선행 리뷰: 001-metis-okay.md (okay + 권장 3건)
- 판정: **approved (단 fs 갭 1건 발견 — 코드 작성 시 반영 필요)**

## 검증 절차

본 plan §2 (영향 범위) + §3 (불변식) + §6 (함정 회피)이 fs상 정확한지 실측 검증.
Naver 검색 API 공식 문서로 권장 1 검증.

## fs 정합 검증

### 1. `graph/real_builder.py` stub 위치 — plan §4 step 3

```bash
grep -n "_event_search_node" backend/src/graph/real_builder.py
```

확인 결과:
- L41-43: `async def _event_search_node(state: AgentState) -> dict[str, Any]: """행사 검색 노드 stub..."""`
- L79: `"EVENT_SEARCH": "event_search"` 매핑 등록됨

본 PR이 stub 함수 본문을 진짜 함수 호출로 교체. 또는 stub 함수 자체 제거 후 모듈 레벨에서 import. 정확한 양식 코드 작성 시 결정.

⚠️ **중요 fs 갭 발견**: real_builder.py의 builder 코드가 어떻게 stub 함수를 그래프에 등록하는지 plan에 명시 없음. stub 함수가 모듈 함수면 직접 import만 바꾸면 되지만, builder 내부에서 호출하는 양식이면 builder 함수도 수정 필요. 코드 작성 시 정찰:

```bash
grep -B 2 -A 5 "add_node\|workflow\|graph" backend/src/graph/real_builder.py | head -30
```

이 정찰을 plan §4 step 3 작성 시 안 해서 정확한 수정 방법 미확정. **코드 작성 전 본인이 위 grep 결과 보내야 정확한 수정 안내 가능**.

### 2. `graph/place_search_node.py` 양식 — 본 PR이 따를 양식

확인 결과 (이전 정찰):
- `logger = logging.getLogger(__name__)`
- `_PLACE_SEARCH_SYSTEM_PROMPT = (...)` — Gemini 시스템 프롬프트 상수
- `_MAX_RESULTS = 5`, `_OS_TOP_K = 10`, `_OS_MIN_SCORE = 0.5`, `_PG_LIMIT = 10` — magic number 상수화 ✅
- `async def _search_pg(pool, district, category, keywords, neighborhood) -> list[dict]`
- `async def _embed_query_768d(query, api_key) -> list[float]` (본 PR 무관)
- `async def _search_os(...)` (본 PR 무관)
- `def _merge_results(...)` (본 PR엔 _merge_pg_naver로 변형)
- `def _build_blocks(...)` ✅
- `async def place_search_node(state: dict[str, Any]) -> dict[str, Any]` ✅

본 PR의 event_search_node가 이 양식을 따르면 일관성 보장. **정합 OK**.

### 3. `events` 테이블 컬럼 — 본 PR SQL이 사용

확인 결과 (load_events.py INSERT_SQL 기반):
```
event_id (PK), title, category, place_name, address, district,
geom (PostGIS POINT, SRID 4326),
date_start, date_end, price, poster_url, detail_url,
summary, source, raw_data (jsonb), is_deleted
```

본 PR SQL:
```sql
SELECT event_id, title, category, place_name, address, district,
       ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,
       date_start, date_end, price, poster_url, detail_url, summary
FROM events
WHERE is_deleted = false
  [AND district = $1]
  [AND category ILIKE $2]
  [AND title ILIKE $3]
  [AND date_end >= NOW()]  -- Metis 권장 2 적용 권장
LIMIT 10
```

**정합 OK**. geom NULL 처리는 ST_Y/ST_X가 NULL 반환하므로 응답에서 분기 필요 (코드 작성 시).

### 4. `query_preprocessor_node.py` processed_query 필드 — 본 PR이 읽음

확인 결과 (이전 정찰):
- `district`: 자치구 (string or null)
- `category`: 카테고리 (string or null)
- `keywords`: 키워드 배열 (array)
- `date_reference`: 날짜 참조 (string or null)

본 PR이 위 4 필드 사용. **정합 OK**.

### 5. `config.py` Settings 클래스 — 본 PR이 수정할 위치

확인 결과 (이전 정찰):
- `naver_client_id`, `naver_client_secret` 미존재
- 다른 외부 API 키들이 클래스 안에 그룹화되어 있음 (Gemini, Google Calendar)

본 PR이 추가할 양식:
```python
# --- Naver Open API (event_search_node, Phase 1 fallback) ---
naver_client_id: str = ""
naver_client_secret: str = ""
```

**정합 OK**. 추가 위치는 Google Calendar 그룹 다음(또는 Gemini 그룹 다음). 일관성 위해 외부 API 그룹화.

### 6. `tests/conftest.py` fixtures — 본 PR이 사용

이전 PR들에서 확인된 fixtures:
- `db_pool` ✅ (PG mock 또는 실제 PG 호출용)
- `client(db_pool)` ✅ (FastAPI TestClient — 본 PR은 graph 노드 직접 호출이라 client 불필요)

⚠️ 본 PR은 SSE endpoint 호출이 아니라 노드 함수 직접 호출 테스트. `client` fixture 사용 안 할 가능성 큼. plan §4 step 4의 테스트 양식 결정 시 옵션:

- A. 노드 함수 직접 호출: `await event_search_node(state_dict)` — 빠름, 단위 테스트
- B. SSE endpoint 호출: `await client.get("/api/v1/chat/stream?query=...")` — 느림, 통합 테스트

**A 옵션 권장** (place_search_node 테스트도 같은 양식으로 추정). plan에 명시 없으나 코드 작성 시 결정.

### 7. Naver 검색 API endpoint — Metis 권장 1 검증

Naver Developers 공식 문서 확인:

| Endpoint | 용도 | 응답 양식 |
|---|---|---|
| `/v1/search/blog.json` | 블로그 검색 | items[] (title, link, description, bloggername, postdate) |
| `/v1/search/news.json` | 뉴스 검색 | items[] (title, link, description, pubDate) |
| `/v1/search/cafearticle.json` | 카페글 | 비슷 |
| `/v1/search/local.json` | **지역검색 (장소)** | items[] (title, address, mapx, mapy, category, telephone) |
| `/v1/search/encyc.json` | 백과사전 | 비슷 |

행사 검색에 가장 적합한 endpoint:
- **블로그 검색** (`/v1/search/blog.json`) — 행사 후기/리뷰 풍부, 행사 정보 자연어로 포함
- **뉴스 검색** (`/v1/search/news.json`) — 공식 행사 발표/소식

**제안**: 본 PR은 **블로그 검색** 우선. 뉴스는 행사 정보가 적게 포함됨 (인터뷰/사회면 노이즈). 코드 작성 시 `_search_naver`가 `/v1/search/blog.json` 호출.

응답 변환 양식 (`_naver_to_event_dict`):
```python
def _naver_to_event_dict(item: dict) -> dict:
    """Naver 블로그 검색 결과 → 우리 events 양식 변환.

    title은 <b>태그 제거 (Naver 검색 결과는 HTML 태그 포함).
    """
    import re
    title_clean = re.sub(r"</?b>", "", item.get("title", ""))
    return {
        "event_id": None,  # Naver fallback이라 event_id 없음
        "title": title_clean,
        "category": None,
        "place_name": None,
        "address": None,
        "district": None,
        "lat": None,
        "lng": None,
        "date_start": None,
        "date_end": None,
        "price": None,
        "poster_url": None,
        "detail_url": item.get("link"),
        "summary": item.get("description"),
        "source": "naver_blog",
    }
```

위 양식이 정공. plan §4 step 2의 `_naver_to_event_dict` 정확한 구현.

### 8. httpx 의존성 — 외부 호출 라이브러리

```bash
grep "httpx" backend/requirements.txt
```

확인 (place_search_node가 이미 import — `import httpx`): httpx 의존성 존재. async client 사용 가능. 본 PR 추가 의존성 0건. **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `_event_search_node` stub | `graph/real_builder.py` L41-43 | ✅ | OK (단 builder 호출 양식 미확인) |
| place_search_node 양식 | `graph/place_search_node.py` | ✅ | OK (참고용) |
| events 테이블 컬럼 | DB | ✅ | OK |
| processed_query 필드 | `graph/query_preprocessor_node.py` | ✅ | OK |
| config.py Settings | `src/config.py` | ⚠️ | naver_* 추가 필요 (본 PR 작업) |
| Naver API endpoint | 공식 문서 | ✅ | OK (블로그 검색 권장) |
| httpx 의존성 | `requirements.txt` | ✅ | OK |
| AgentState 구조 | `graph/state.py` | ✅ | OK |

**전반적으로 정합. 단 1건 fs 갭 발견 — real_builder.py builder 호출 양식 미확인.**

## fs 갭 1건

**갭**: real_builder.py가 stub 함수를 LangGraph 워크플로우에 어떻게 등록하는지 plan에 명시 없음.

**해결 방안**: 코드 작성 전 본인이 다음 정찰 추가:

```bash
grep -B 2 -A 10 "_event_search_node\|add_node.*event\|workflow" backend/src/graph/real_builder.py | head -40
```

이 정찰 후:
- A. stub 함수가 builder 내부에서 직접 사용 → builder 코드 수정 필요
- B. stub 함수가 모듈 레벨에서 export되어 다른 곳이 import → import만 변경

## 함정 사후 검증

본 plan §6 함정 회피 8건이 fs와 정합:

- ✅ graceful degradation — Naver API timeout/실패 시 try/except + PG 결과 반환
- ✅ Naver schema 변환 — Momus가 양식 명시 (위 #7)
- ✅ PostGIS geom NULL — ST_Y/ST_X NULL 반환 시 lat/lng = None
- ✅ date_reference 단순화 — Phase 1 무시 또는 `date_end >= NOW()` (Metis 권장 2)
- ✅ magic number `>= 3` 상수화 — `_MIN_PG_RESULTS = 3`
- ✅ Naver timeout 5초 — `httpx.AsyncClient(timeout=5.0)`
- ✅ events 컬럼 — Momus가 fs로 확인 (위 #3)
- ✅ stub 호출 위치 — Momus가 위 fs 갭으로 추가 정찰 권장

## 판정

**approved** — plan §2 영향 범위(신규 2 + 수정 2) fs 실측 정합 완료. §3 불변식 #13 (DB 우선 → fallback), §6 함정 회피 8건 모두 fs와 일관. 단 fs 갭 1건(real_builder.py builder 호출 양식)은 코드 작성 전 본인이 추가 정찰 필요.

**plan APPROVED 권장.** 코드 작성 진입 가능 (단 위 fs 갭 정찰 선행).

## broadcast 권장

본 plan은 **본인 첫 LangGraph 노드 + 외부 API fallback PR**. 향후 EVENT_RECOMMEND(#46) + 다른 검색 노드 plan 작성자가 본 plan §6 함정 회피 8건 + Momus의 Naver schema 변환 양식(위 #7)을 그대로 재사용 권장.

특히 `_naver_to_event_dict` 양식이 향후 다른 외부 API(서울시 공공API, 카카오 등) 통합 시 표준 패턴으로 정착 권장.
