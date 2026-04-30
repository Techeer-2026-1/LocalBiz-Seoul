# PLACE_SEARCH 노드 구현 — SQL + Vector k-NN 하이브리드 검색

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-30
- 상태: approved
- 최종 결정: APPROVED (Metis 003-okay + Momus 004-approved, 2026-04-30)

> 핵심 검색 파이프라인. places 535K + places_vector 768d k-NN. 이 노드가 PLACE_RECOMMEND, DETAIL_INQUIRY의 기반.

## 1. 요구사항

기획서: "SQL + Vector k-NN 하이브리드 검색. Text-to-SQL(PG+PostGIS) + places_vector k-NN(OS 768d) 병합 검색."

### SSE 블록 순서 (기획서 §4.5)

```text
intent → status → text_stream → places[] → map_markers → done
```

※ `status`는 SSE 제어 이벤트(DB 미저장). `_EXPECTED_BLOCK_ORDER`에는 콘텐츠 블록만 포함:
`["intent", "text_stream", "places", "map_markers", "done"]`

### 검색 흐름

```text
1. processed_query에서 district/category/keywords 추출
2. PostgreSQL 검색: places WHERE district/category/name ILIKE + is_deleted=false
3. OpenSearch 검색: places_vector k-NN (HNSW approximate, cosinesimil, top-10)
   - 쿼리 임베딩: langchain_google_genai GoogleGenerativeAIEmbeddings 사용 (단건)
   - pre-filter: 없음 (535K 전체 대상, HNSW이므로 성능 문제 없음)
   - min_score: 0.5 (유사도 낮은 결과 제거)
4. 병합: PG 결과 + OS 결과 → place_id 기준 중복 제거 → 상위 5건
5. text_stream 블록: Gemini가 검색 결과를 자연어로 요약
6. places 블록: PlacesBlock 형태
7. map_markers 블록: 좌표 있는 결과만 MarkerItem 형태
```

### 임베딩 방식

`httpx.AsyncClient`로 Gemini REST API 직접 호출 (불변식 #7):
```python
async def _embed_query_768d(query, api_key):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=body, headers={"x-goog-api-key": api_key})
    return resp.json()["embedding"]["values"]  # 768d
```

ETL 배치용 `embed_batch_async()`는 aiohttp.ClientSession 의존이라 런타임 노드에 부적합.
langchain `GoogleGenerativeAIEmbeddings`는 `outputDimensionality` 파라미터 미지원 (3072d 반환).
httpx 직접 호출로 768d 보장 + async non-blocking.

### OpenSearch k-NN 쿼리

```python
# HNSW approximate (brute-force 아닌 근사 검색, 535K에 적합)
body = {
    "size": 10,
    "query": {
        "knn": {
            "embedding": {
                "vector": query_vector,  # 768d
                "k": 10,
            }
        }
    },
    "min_score": 0.5,
}
result = await os_client.search(index="places_vector", body=body)
```

### 외부 API 비용

| API | 호출 | RPM 제한 |
|---|---|---|
| Gemini 2.5 Flash (intent) | 1회 | 15 RPM (생성 API) |
| Gemini 2.5 Flash (전처리) | 1회 | 15 RPM |
| Gemini embedding-001 (쿼리 임베딩) | 1회 | 1500 RPM (임베딩 API) |
| Gemini 2.5 Flash (요약) | 1회 | 15 RPM |
| **합계** | **4회** | 생성 3회/15 RPM + 임베딩 1회/1500 RPM |

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/place_search_node.py` — PLACE_SEARCH 노드
  - `backend/tests/test_place_search.py` — 단위 테스트
- 수정 파일:
  - `backend/src/graph/real_builder.py` — stub → 실제 import 교체
  - `backend/src/graph/response_builder_node.py` — PLACE_SEARCH 블록 순서 추가
- DB 스키마 영향: 없음 (places 테이블 + places_vector OS 인덱스 이미 존재)
- 응답 블록 16종: places, map_markers, text_stream 사용 (기존 정의, 추가 없음)
- FE 영향: places 카드 리스트 + 지도 마커 렌더링

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — places UUID(VARCHAR 36). 불변식 준수.
- [x] #2 PG↔OS 동기화 — place_id == places_vector._id 패턴 준수. SELECT만.
- [x] #3 append-only — places는 append-only 대상 아님. SELECT만 사용.
- [x] #4 소프트 삭제 — places.is_deleted=false 필터 적용.
- [x] #5 비정규화 3건 — places.district 의도적 비정규화. 신규 추가 없음.
- [x] #6 6 지표 고정 — 해당 없음 (검색, 분석 아님)
- [x] #7 임베딩 768d — GoogleGenerativeAIEmbeddings gemini-embedding-001 768d. OpenAI 금지.
- [x] #8 asyncpg 바인딩 — $1, $2 파라미터 바인딩. 동적 WHERE는 파라미터 인덱스만 f-string, 값은 바인딩.
- [x] #9 Optional[str] — str | None 미사용.
- [x] #10 SSE 16종 — places, map_markers, text_stream 사용 (기존 정의)
- [x] #11 블록 순서 — `["intent", "text_stream", "places", "map_markers", "done"]` (status는 제어 이벤트, 검증 대상 외)
- [x] #12 공통 쿼리 전처리 — processed_query에서 district/category/keywords 소비.
- [x] #13 행사 DB 우선 — 해당 없음 (장소 검색)
- [x] #14 대화 이력 이원화 — 해당 없음
- [x] #15 이중 인증 — 해당 없음
- [x] #16 북마크 — 해당 없음
- [x] #17 공유링크 — 해당 없음
- [x] #18 Phase 라벨 — P1 명시
- [x] #19 기획 문서 우선 — API/기능 명세서 준수

## 4. 작업 순서 (Atomic step)

1. `backend/src/graph/place_search_node.py` 신규
   - PG 검색: 동적 WHERE (district/category/name ILIKE). 파라미터 바인딩 ($N). is_deleted=false.
   - OS 검색: GoogleGenerativeAIEmbeddings.aembed_query() → k-NN HNSW top-10, min_score 0.5.
   - 병합: PG + OS → place_id 중복 제거 → 상위 5건.
   - text_stream 블록: Gemini 요약 (system + 검색 결과).
   - places 블록: PlacesBlock dict.
   - map_markers 블록: 좌표 있는 결과만.
   - PG/OS 둘 다 실패 → text_stream "검색 결과가 없습니다" fallback.
   - 검증: ruff + pyright 통과.

2. `backend/src/graph/real_builder.py` — stub 교체
   - `_place_search_node` → `from src.graph.place_search_node import place_search_node`
   - 검증: ruff + pyright 통과.

3. `backend/src/graph/response_builder_node.py` — 블록 순서 추가
   - `_EXPECTED_BLOCK_ORDER["PLACE_SEARCH"] = ["intent", "text_stream", "places", "done"]`
   - `_OPTIONAL_BLOCKS`에 `map_markers` 추가 (좌표 없는 결과에서 생략 가능)
   - 검증: ruff 통과.

4. `backend/tests/test_place_search.py` — 단위 테스트
   - PG + OS mock → places + map_markers 블록 반환 확인
   - PG 실패 → OS 결과만으로 동작
   - OS 실패 → PG 결과만으로 동작
   - 둘 다 실패 → text_stream "검색 결과가 없습니다"
   - 검증: pytest 통과.

5. validate.sh 전체 통과.

## 5. 검증 계획

- `pytest tests/test_place_search.py` — 4건 통과
- `./validate.sh` 전체 통과
- curl 테스트: `?query=홍대 카페` → places[] + map_markers 확인
- DB 확인: assistant 메시지에 places 블록 저장 확인

## 6. Metis/Momus 리뷰

- 001-metis-reject: embed_texts / 블록 순서 / OS 설계 → 본 수정에서 반영
- 002-momus-reject: Metis 미통과 / embed_texts / 블록 순서 / RPM → 본 수정에서 반영

## 7. 최종 결정

APPROVED (Metis 003-okay + Momus 004-approved, 2026-04-30)
