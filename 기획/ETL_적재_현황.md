# ETL 적재 현황

> 최종 갱신: 2026-04-14 | 상세는 `서비스 통합 기획서 v2.md` §6-7 참조 (_legacy/)

---

## PostgreSQL 적재 현황

| 테이블 | 행 수 | 비고 |
|---|---:|---|
| **places** | **535,431** | 18 카테고리, 48 source, 25 자치구 |
| **events** | 7,301 | 8 source, 필드 보강 완료 |
| administrative_districts | 427 | MultiPolygon geom 4326 |
| population_stats | 278,880 | append-only, 415동 × 24시간 × 28일 |
| admin_code_aliases | 11 | 행정동 구→신 매핑 |

## 카테고리 분류 (v0.2, 18종)

| # | 카테고리 | row | 코드 |
|---|---|---:|---|
| 1 | 쇼핑 | 118,779 | shopping |
| 2 | 음식점 | 112,085 | restaurant |
| 3 | 미용·뷰티 | 57,109 | beauty |
| 4 | 의료 | 48,408 | medical |
| 5 | 교육 | 45,158 | education |
| 6 | 카페 | 41,911 | cafe |
| 7 | 공공시설 | 28,974 | public |
| 8 | 관광지 | 25,990 | tourist |
| 9 | 주점 | 17,402 | pub |
| 10 | 숙박 | 11,444 | accommodation |
| 11 | 체육시설 | 10,702 | sports |
| 12 | 주차장 | 10,568 | parking |
| 13 | 공원 | 1,908 | park |
| 14 | 문화시설 | 1,776 | cultural |
| 15 | 노래방 | 1,159 | karaoke |
| 16 | 복지시설 | 1,118 | welfare |
| 17 | 도서관 | 540 | library |
| 18 | 지하철역 | 400 | subway |

## OpenSearch 인덱스

| 인덱스 | docs | 목표 | 상태 |
|---|---:|---:|---|
| places_vector | ~475K | 535,431 | 재적재 진행 중 |
| events_vector | 7,301 | 7,301 | 완료 |
| place_reviews | ~7,572 | ~10,000 | 크롤링 진행 중 |

공통: 768d Gemini (gemini-embedding-001), nori 한국어 분석기, k-NN HNSW cosinesimil

## ETL Loader 목록

| loader | scope | row |
|---|---|---:|
| load_sosang_biz.py | 소상공인 상가(상권) 202512 | 371,418 |
| load_g2_public_cultural.py | 공원/도서관/문화시설/공공시설 | 26,748 |
| load_g3_health_daily.py | 의료/체육/주차장/공공시설 | 47,465 |
| load_g4_tourism.py | 관광지 보강 4 CSV | 14,377 |
| load_remaining_places.py | 인허가 잔여 9 source | 73,905 |
| load_events.py | events 필드 보강 재적재 | 7,301 |
| crawl_reviews.py | Naver Blog → Gemini 6지표 → OS | 진행 중 |
| load_vectors.py | PG → Gemini 768d → OS places_vector | 진행 중 |

## v2 변경사항

- ~~place_analysis~~ 테이블 **DROP** → 런타임 Gemini lazy 채점
- 임베딩: ~~OpenAI 1536d~~ → **Gemini 768d** (gemini-embedding-001)
- 좌표계: TM **EPSG:5174** (서울시 인허가 표준)
- page_content: **3-Layer** 구조 (구조적 + 카테고리 설명 + 리뷰)
