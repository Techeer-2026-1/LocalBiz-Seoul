# PLACE_RECOMMEND 노드 구현 — SQL + Vector k-NN + LLM Rerank

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-05
- 상태: approved

## 1. 요구사항

API 명세서: `intent → text_stream → places[] → map_markers → references → done`

"카공하기 좋은 카페 추천해줘" 같은 비정형 조건 기반 장소 추천. PLACE_SEARCH(키워드 정확 매칭)와 달리 **의미 기반 매칭 + 추천 사유 제시**가 핵심 차별점.

기능 명세서 정의: "SQL + Vector k-NN + LLM Rerank 3단계. PostGIS ST_DWithin + Google Places 병렬 → LLM Rerank(Gemini Flash) → 상위 N건"

> **기획 변경 제안 (PM 이정 자체 승인):** 기능 명세서 v2 L5의 "Google Places 병렬"을 "OS places_vector k-NN + place_reviews k-NN"으로 변경한다. 근거: PoC 보고서 결론 — 외부 API 의존 탈피 + 자체 적재 데이터(places_vector 475K, place_reviews 7.5K) 활용이 품질·비용·속도 모두 우월. 기능 명세서 업데이트는 구현 완료 후 v2.1로 반영 예정.

PoC 보고서 + 하이브리드 파이프라인 계획서를 기반으로 현재 인프라(places 535K + places_vector 475K + place_reviews 7.5K)에 맞게 구현.

### 핵심 흐름

```
processed_query (district, category, keywords, expanded_query)
  → ① PG 정형 필터 (ST_DWithin + category + is_deleted=false)
  → ② OS places_vector k-NN (expanded_query 768d 의미 검색)
  → ③ OS place_reviews k-NN (비정형 조건 리뷰 매칭)
  → 병합 + 중복 제거
  → ④ LLM Rerank (Gemini Flash — 조건 적합도 순위 재배치)
  → 상위 5건
  → ⑤ 블록 생성: text_stream + places[] + map_markers + references
```

### PLACE_SEARCH vs PLACE_RECOMMEND 차이

| | PLACE_SEARCH | PLACE_RECOMMEND |
|---|---|---|
| 쿼리 | 단일 키워드 | 비정형 조건 (의미 매칭) |
| OS 검색 | places_vector만 | places_vector + **place_reviews** |
| 리랭킹 | 없음 (유사도 순) | **LLM Rerank** (조건 적합도) |
| 응답 | 요약 | 추천 사유 + references |

## 2. 영향 범위

- 신규 파일: `backend/src/graph/place_recommend_node.py`
- 수정 파일: `backend/src/graph/real_builder.py` (stub → 실제 import 교체)
- DB 스키마 영향: 없음 (기존 places + places_vector + place_reviews 활용)
- 응답 블록 16종 영향: 기존 블록만 사용 (text_stream, places, map_markers, references)
- intent 추가/변경: 없음 (PLACE_RECOMMEND 이미 등록됨)
- 외부 API 호출: Gemini 2.5 Flash (LLM Rerank용, 1회 ���천당 1 호출, 입력 ~2K tokens — 후보 20건 x 장소 메타 100자 + 사용자 조건. RPM 한도 초과 시 OS 유사도 순 그대로 반환하는 graceful degradation)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — places는 UUID(VARCHAR(36))
- [x] PG↔OS 동기화 — place_id == places_vector._id, place_reviews도 place_id 기준
- [x] append-only 4테이블 미수정 — SELECT만 사용
- [x] 소프트 삭제 매트릭스 준수 — is_deleted=false 필터
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존 — place_reviews._raw_scores 참조만
- [x] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [x] asyncpg 파라미터 바인딩 ($1, $2)
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 이벤트 타입 16종 한도 준수 — 기존 타입만 사용
- [x] intent별 블록 순서 (기획 §4.5) 준수 — text_stream → places → map_markers → references → done
- [x] 공통 쿼리 전처리 경유 — query_preprocessor 결과 활용
- [ ] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [ ] 대화 이력 이원화 보존 — 해당 없음 (조회만)
- [ ] 인증 매트릭스 준수 — 해당 없음
- [ ] 북마크 = 대화 위치 패러다임 — 해당 없음
- [ ] 공유링크 인증 우회 범위 — 해당 없음
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — API/기능 명세서 블록 순서 준수

## 4. 작업 순서 (Atomic step)

1. **place_recommend_node.py 신규 작성** (category: `langgraph-node`)
   - `_search_pg()`: PostGIS ST_DWithin 반경 검색 + category + is_deleted=false
   - `_search_os_places()`: places_vector k-NN (expanded_query 임베딩)
   - `_search_os_reviews()`: place_reviews k-NN (비정형 조건 임베딩) → place_id + 리뷰 snippet 추출
   - `_merge_candidates()`: 3채널 결과 병합, place_id 중복 제거. OS에서 place_id만 나온 경우 PG places에서 name/address/lat/lng 2차 조회 (`ANY($1::varchar[])` 배열 바인딩)
   - `_llm_rerank()`: Gemini Flash로 조건 적합도 순위 재배치 (상위 5건)
   - `_build_blocks()`: text_stream + places + map_markers + references 블록 생성. references 블록에는 place_reviews에서 매칭된 리뷰 snippet(출처: Naver Blog URL)을 장소별로 포함. 리뷰 데이터 없는 장소는 references에서 제외.
   - `_embed_query_768d()`: place_search_node.py와 동일 로직 복제 (Simplicity First — 공통화는 추후 리팩토링)
   - `place_recommend_node()`: LangGraph 노드 엔트리 (state → response_blocks)

2. **real_builder.py 수정** (category: `quick`)
   - `_place_recommend_node` stub 제거
   - `from src.graph.place_recommend_node import place_recommend_node` 추가
   - `graph.add_node("place_recommend", place_recommend_node)` 교체

3. **단위 테스트 작성** (category: `deep`)
   - `tests/test_place_recommend_node.py`
   - mock PG pool / OS client / Gemini LLM
   - 케이스: 정상 5건 반환, PG 0건 + OS만, 전체 0건(빈 결과), LLM rerank 실패 fallback

## 5. 검증 계획

- `validate.sh` 6단계 통과
- 단위 테스트: `pytest tests/test_place_recommend_node.py -v`
- 수동 시나리오:
  - "홍대 카공하기 좋은 카페 추천해줘" → places[] + map_markers + references 반환
  - "강남역 근처 분위기 좋은 맛집" → 반경 기반 필터 + 리랭킹 동작
  - "조용한 도서관 추천" → place_reviews k-NN이 "조용한" 의미 매칭
- smoke: `python -c "from src.graph.real_builder import build_graph; build_graph()"`

## 6. 최종 결정

APPROVED (2026-05-05, Metis okay + Momus approved)
