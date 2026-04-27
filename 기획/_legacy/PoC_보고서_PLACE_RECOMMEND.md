# LocalBiz Intelligence — PoC 보고서 (PLACE_RECOMMEND)
**작성일:** 2026-03-25
**대상 기능:** 장소 추천 (조건/취향 기반)

---

## 1. 개요

단순 키워드 검색(PLACE_SEARCH)과 달리, 사용자의 **조건·취향을 추출**해서 맞춤 장소를 추천하고 네이버 블로그 + Google Places 리뷰를 병렬로 수집해 추천 근거를 제시하는 파이프라인을 PoC로 검증했다.

**검증 완료 항목**
- PLACE_SEARCH와 분리된 전용 노드(`place_recommend_node`) 구성
- LLM을 통한 조건·카테고리·다중 검색 쿼리 자동 추출
- 다중 쿼리 병렬 검색 + place_id 기준 중복 제거 + 평점순 정렬
- Naver Blog API + Google Places Details API 병렬 리뷰 수집
- 조건 키워드 기반 리뷰 리랭킹
- 장소별 추천 이유 스트리밍 (리뷰 인용 포함)
- 네이버 블로그 참조 링크 pill UI 렌더링

---

## 2. 구현 내용

### 2-1. PLACE_SEARCH vs PLACE_RECOMMEND 분리

| | PLACE_SEARCH | PLACE_RECOMMEND |
|---|---|---|
| 사용 노드 | `place_search_node` | `place_recommend_node` |
| 검색 쿼리 | 단일 키워드 | 조건별 다중 쿼리 3개 |
| 리뷰 수집 | 없음 | Naver Blog + Google Places 병렬 |
| 응답 텍스트 | 장소 정보 요약 | 조건 매칭 추천 이유 (리뷰 인용) |

### 2-2. 플로우

```
사용자 메시지
  → LLM 조건 추출 (category, location, conditions, queries×3, limit)
  → 다중 쿼리 병렬 검색 (asyncio.gather)
      ├── 쿼리1: 카테고리 + 지역 (예: "강남 카페")
      ├── 쿼리2: 조건 일부 포함 (예: "조용한 강남 카페")
      └── 쿼리3: 다른 조건 조합 (예: "카공 분위기 강남 카페")
  → place_id 중복 제거 → 평점 높은 순 정렬 → limit개 확정
  → 장소별 리뷰 병렬 수집 (asyncio.gather)
      ├── Naver Blog: "{장소명} {카테고리}" 검색 → 장소명 필터링
      └── Google Places Details: reviews 필드 (최대 5개)
  → 리랭킹: 조건 키워드 등장 횟수로 점수 산정 → 상위 5개
  → 블록 생성: 인트로 → [카드 → 추천이유 → 링크] × N
```

### 2-3. 리뷰 수집 및 리랭킹

**Naver Blog**
- 검색어: `{장소명} {카테고리} 후기`
- 필터: 장소명 핵심 토큰(2자 이상)이 제목+본문에 포함된 글만 통과
- 최대 10개 가져와서 필터 후 상위 5개

**Google Places Details**
- `place_id`로 `reviews` 필드 직접 조회
- `language=ko`, `reviews_sort=most_relevant`
- 최대 5개, 별점 포함

**리랭킹 (`_rerank`)**
```python
def score(review):
    return sum(1 for cond in conditions if cond in review["text"])
# 조건 키워드가 많이 등장할수록 상위 노출
```

---

## 3. 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| 무관한 블로그 글 노출 (세부 여행, 청계산 등산) | 장소명 토큰 OR 조건 → 짧은 단어("레아")가 전혀 다른 글에 매칭 | AND 조건으로 강화 + 카테고리를 검색어에 포함 |
| 같은 장소(레아 카페 leah)만 반복 등장 | Google Places가 조건 무시, 평점 높은 장소를 우선 반환 | 다중 쿼리로 조건별 검색 후 중복 제거 |
| 네이버 블로그 Redis 의존성 충돌 | 기존 코드가 미사용 Redis 캐시 호출 | Redis 의존 제거, 단순 httpx 직접 호출로 교체 |

---

## 4. 개선 필요 사항

### 4-1. 구조적 한계 (PoC 범위)

**Google Places의 조건 필터링 불가**
- Text Search는 키워드 매칭 + 인기도 기반으로 결과를 반환
- "조용한 카페"를 검색해도 실제로 조용한 카페인지는 API가 판단하지 않음
- 근본 해결: 리뷰 텍스트를 벡터화해서 OpenSearch에 저장 후 의미 검색 필요

**Naver Blog 노이즈**
- 짧거나 일반적인 장소명(예: "레아")은 무관한 글에도 매칭됨
- 리뷰라기보다 블로그 포스팅 특성상 광고글·여행기·무관 글 섞임
- 근본 해결: 네이버 플레이스 리뷰 직접 수집 (ToS 이슈 검토 필요)

### 4-2. 리뷰 데이터 소스 한계 및 방향

| 소스 | 현재 상태 | 한계 |
|------|---------|------|
| Google Places 리뷰 | ✅ 사용 중 | 장소당 최대 5개, 영어 리뷰 많음 |
| Naver Blog | ✅ 사용 중 | 리뷰가 아닌 포스팅, 노이즈 높음 |
| 네이버 플레이스 리뷰 | ❌ 미사용 | ToS 문제 — 팀 결정 필요 |
| 유저 직접 작성 | ❌ 미구현 | `REVIEW_WRITE` 구현 후 점진적 축적 |

**추천 방향:** Phase 1에서 `REVIEW_WRITE` 기능 구현 → 유저 리뷰 OpenSearch 적재 → Phase 2에서 벡터 검색 기반 추천으로 교체

### 4-3. 즉시 개선 가능

- 리랭킹 로직 고도화: 단순 카운트 → TF-IDF 또는 임베딩 유사도 점수
- 영업종료 장소 필터링: `is_open == False`인 장소는 추천에서 제외
- 추천 결과 다양성: 같은 체인점 중복 제거

---

## 5. 결론

PLACE_RECOMMEND의 기본 파이프라인(조건 추출 → 다중 쿼리 → 리뷰 수집 → 리랭킹 → 스트리밍)은 동작하지만, **외부 API만으로는 조건 기반 추천의 품질에 구조적 한계**가 있다. 진짜 의미 있는 추천을 위해서는 리뷰 벡터 DB가 필수다. Phase 1 목표는 `REVIEW_WRITE`로 리뷰 데이터를 쌓기 시작하고, Phase 2에서 OpenSearch 벡터 검색으로 추천 엔진을 교체하는 것이다.
