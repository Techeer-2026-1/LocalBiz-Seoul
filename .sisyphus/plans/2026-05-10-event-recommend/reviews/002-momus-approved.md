# Momus 리뷰 — SSE 행사 추천 노드 (Issue #46)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (페르소나 채택)
- 검토일: 2026-05-10
- plan: `.sisyphus/plans/2026-05-10-event-recommend/plan.md`
- 선행 리뷰: 001-metis-okay.md (okay + 권장 2건)
- 판정: **approved (단 fs 갭 1건 발견 — plan §2 수정 필수)**

## 검증 절차

본 plan §2 (영향 범위) + §3 (불변식) + §6 (함정 회피)을 fs 실측 검증.

## fs 정합 검증

### 1. `graph/real_builder.py` stub 등록 — plan §4 step 2

```bash
grep -n "_event_recommend_node\|event_recommend" backend/src/graph/real_builder.py
```

확인 결과 (dev base):
- L42: `async def _event_recommend_node(state: AgentState) -> dict[str, Any]: ...`
- L63: 매핑 주석 `EVENT_RECOMMEND → "event_recommend"`
- L76: `"EVENT_RECOMMEND": "event_recommend"` (라우팅 매핑)
- L106: `graph.add_node("event_recommend", _event_recommend_node)` (등록)
- L127: 조건부 라우팅 `"event_recommend": "event_recommend"`
- L142: 엣지

본 PR이 stub 함수 본문 + L106 add_node 인자만 진짜 함수로 교체. 나머지 5 위치(L63 주석/L76 매핑/L127/L142)는 그대로 유지. **정합 OK**.

### 2. `graph/intent_router_node.py` EVENT_RECOMMEND intent

확인 결과 (dev base):
- L23: `EVENT_RECOMMEND = "EVENT_RECOMMEND"` (Enum 등록)
- L45: `IntentType.EVENT_RECOMMEND` (검색 intent set)
- L63: `IntentType.EVENT_RECOMMEND` (response intent set)
- L85: Gemini 프롬프트에 `EVENT_RECOMMEND: asking for event recommendations`

본 PR이 intent_router 수정 0건. **정합 OK**.

### 3. ⚠️ `config.py` Naver Settings — plan §2 갱신 필수

```bash
grep -n "naver" backend/src/config.py
```

확인 결과 (dev base): **0건 매치**.

**fs 갭 발견**: plan §2는 "config.py 수정 0건 (NAVER_CLIENT_ID/SECRET 키 이미 존재)"이라 명시했으나, 이는 **#47 PR 브랜치 기준** 사실. dev에는 #47이 미머지라 `naver_client_id` / `naver_client_secret` 변수 **미존재**.

**해결 방안**: plan §2 수정 — "수정 파일 1개" → "수정 파일 2개" (real_builder.py + config.py). 본 PR step 0으로 config.py에 Naver Settings 추가 필요:

```python
# Naver Open API (event_search/recommend, Phase 1 fallback)
naver_client_id: str = ""
naver_client_secret: str = ""
```

→ plan §4 작업 순서에 step 1.5 (또는 step 1 앞) 삽입: "config.py에 naver_client_id/secret 추가"

### 4. `events` 테이블 컬럼 — 본 PR SQL이 사용

ERD v6.3 §2 확인:
```
1. event_id VARCHAR(36) PK NN
2. title VARCHAR(200) NN
3. category VARCHAR(50)
4. place_name TEXT
5. address TEXT
6. district VARCHAR(50)
7. geom geometry(Point,4326)
8. date_start DATE
9. date_end DATE
10. price TEXT
11. poster_url TEXT
12. detail_url TEXT
13. summary TEXT
14. source VARCHAR(50)
15. raw_data JSONB
16. created_at TIMESTAMPTZ
17. updated_at TIMESTAMPTZ NN
18. is_deleted BOOLEAN NN false
```

본 PR SQL:
```sql
SELECT event_id, title, category, place_name, address, district,
       ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,
       date_start, date_end, price, poster_url, detail_url, summary, source
FROM events
WHERE is_deleted = FALSE AND date_end >= NOW()
  [AND district = $1]
  [AND category ILIKE $2]
  [AND title ILIKE $3]
LIMIT 10
```

**정합 OK**. 모든 컬럼 ERD 명세와 일치. is_deleted=FALSE + date_end>=NOW() 두 필터 모두 적용 (#47 학습 누적).

### 5. `query_preprocessor_node` processed_query 필드

이전 #47 검증에서 확인:
- district / category / keywords / date_reference

본 PR도 같은 4 필드 사용. **정합 OK**.

### 6. `place_recommend_node.py` 형제 노드 양식 — 차용 가능성

PLACE_RECOMMEND 머지본(L29-33):
```python
_RECOMMEND_SYSTEM_PROMPT = (
    "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다. "
    "사용자의 조건에 맞는 장소를 추천하고 추천 이유를 친절하게 설명해주세요. "
    "각 장소별로 왜 추천하는지 구체적인 근거(리뷰 키워드, 분위기, 특징)를 포함하세요."
)
```

본 PR `_EVENT_RECOMMEND_SYSTEM_PROMPT` 양식 차용:
```python
_EVENT_RECOMMEND_SYSTEM_PROMPT = (
    "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다. "
    "사용자의 조건에 맞는 행사를 추천하고 추천 이유를 친절하게 설명해주세요. "
    "각 행사별로 왜 추천하는지 구체적인 근거(카테고리 적합성, 일정·위치, 특징)를 포함하세요."
)
```

**정합 OK**. 형제 노드 일관성 보장.

### 7. `tests/conftest.py` fixtures

이전 검증 (place_search/event_search):
- 단위 테스트는 노드 함수 직접 호출 양식 (mock pool, monkeypatch _search_naver)
- SSE endpoint integration 테스트는 본 PR 범위 외

**A 옵션 권장** (직접 호출, 빠름). plan §4 step 4 양식 정공.

### 8. Naver 검색 API endpoint — #47 학습 차용

```text
| Endpoint | 용도 |
|---|---|
| /v1/search/blog.json | 블로그 검색 — 행사 후기 풍부 (#47이 채택) |
```

본 PR도 `/v1/search/blog.json` 사용. `_naver_to_event_dict` 양식은 #47 머지본과 동일하면 됨 (HTML 태그 제거 + link → detail_url 매핑). **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `_event_recommend_node` stub | `graph/real_builder.py` L42 | ✅ | OK |
| EVENT_RECOMMEND intent | `graph/intent_router_node.py` L23/45/63/85 | ✅ | OK (수정 0건) |
| events 테이블 18 컬럼 | ERD v6.3 §2 | ✅ | OK |
| processed_query 필드 | `graph/query_preprocessor_node.py` | ✅ | OK |
| **config.py Settings** | `src/config.py` | ⚠️ | **갭 — naver_* 미존재. 본 PR 추가 필요** |
| place_recommend 양식 | 머지본 | ✅ | OK (차용) |
| Naver API endpoint | 공식 + #47 학습 | ✅ | OK |
| httpx | requirements.txt | ✅ | OK |

**전반적 정합. 단 1건 fs 갭 — config.py에 Naver Settings 추가 필수.**

## fs 갭 1건 — plan §2/§4 수정 필수

**갭**: plan §2 "수정 파일 1개" → 실제로는 2개 (real_builder.py + **config.py**).

**해결**: plan §2 갱신 + §4 작업 순서에 step 0 추가:

```
0. config.py 수정 — Settings에 Naver 변수 2개 추가
   - naver_client_id: str = ""
   - naver_client_secret: str = ""
   - 다른 외부 API 그룹(Google Calendar 등) 옆 일관성 위치
```

이 step은 #47이 dev에 머지되는 시점에 **컨플릭트 발생** (양쪽이 Settings에 동일 변수 추가). 머지 시 양쪽 다 살리는 양식으로 해결 (한쪽만 적용 + 다른 쪽 라인 제거).

## 함정 사후 검증

본 plan §6 함정 회피 7건이 fs와 정합:

- ✅ EVENT_SEARCH 코드 중복 → 시스템 프롬프트 차별화로 의도 분리
- ✅ #47 미머지 상태 — 본 fs 갭 발견 (config.py)으로 검증됨
- ✅ 추천 사유 LLM 단순화 — Phase 2 ML 분리 명시
- ✅ references 항상 포함 — Metis 권장 2와 매핑
- ✅ _MIN_PG_RESULTS = 3 — EVENT_SEARCH 동일 임계값 (학습 누적)
- ✅ Naver timeout 5초
- ✅ PostGIS geom NULL — ST_Y/ST_X NULL 반환 처리

## 판정

**approved** — plan §2/§4를 fs 갭 1건 반영하여 갱신하면 코드 작성 진입 가능. EVENT_SEARCH(#47) + PLACE_RECOMMEND(#54)의 학습 누적이 명확히 plan §6에 반영됨.

**plan APPROVED 권장** (단 fs 갭 1건 plan 수정 선행).

## broadcast 권장

본 PR은 EVENT_SEARCH(#47) + PLACE_RECOMMEND(#54) 학습을 모두 흡수한 형제 노드 — 향후 EVENT_DETAIL/COURSE_PLAN 같은 노드 plan 작성자가 본 plan §6 함정 회피 + Momus의 fs 갭 패턴(미머지 의존성 PR로 인한 Settings 부재)을 표준 검증 항목으로 채택 권장.
