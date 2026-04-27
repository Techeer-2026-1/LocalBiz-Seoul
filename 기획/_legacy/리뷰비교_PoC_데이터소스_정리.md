# 리뷰 비교 — PoC 결과 및 데이터 소스 조달 계획

작성일: 2026-03-31 | 작성: 이정

---

## 1. PoC 결과 요약

### 1.1 무엇을 검증했는가

리뷰 비정형 데이터를 LLM으로 정량화하여 레이더차트로 시각화하는 전체 파이프라인의 기술적 실현 가능성.

```
수집 → 전처리 → LLM 분석 → DB 적재 → 채팅 UI 인라인 렌더링
```

### 1.2 테스트 장소

| 장소 | Google Place ID | 카테고리 |
|------|----------------|---------|
| 스타벅스 강남R점 | ChIJobb671mhfDURrcE4SebLfyw | cafe |
| 블루보틀 삼청 카페 | ChIJhRZcnnOjfDURuMDQe5XSOa8 | cafe |

### 1.3 파이프라인 단계별 결과

| 단계 | 처리 내용 | 소요 시간 | 비고 |
|------|----------|----------|------|
| 1. 수집 | Google 5건 + Naver 10건 = 15건/장소 | ~0.5초 | Google Places Details API + 네이버 블로그 검색 API |
| 2. 전처리 | 광고/협찬 키워드 필터링, 스팸 제거, 중복 제거 | 즉시 | 정규식 기반. 테스트 시 필터링 0건 (클린 데이터) |
| 3. LLM 분석 | Gemini 2.5 Flash → 6개 지표 JSON 채점 | ~17초 | JSON mode (`responseMimeType: application/json`) |
| 4. DB 적재 | PostgreSQL `place_analysis` 테이블 UPSERT | 즉시 | TTL 7일, `ON CONFLICT` 최신 분석만 유지 |
| 5. 서빙 | 채팅 "A vs B 비교해줘" → 레이더차트 인라인 표시 | ~20초 | intent=ANALYSIS → search_agent → compare_reviews tool |

### 1.4 분석 결과 (실제 출력)

| 지표 | 스타벅스 강남R점 | 블루보틀 삼청 카페 |
|------|:---:|:---:|
| 맛 | 4.3 | 3.9 |
| 서비스 | 3.0 | 4.3 |
| 분위기 | 4.0 | 3.9 |
| 가성비 | 3.8 | 2.6 |
| 청결도 | 3.0 | -(미평가) |
| 접근성 | 4.7 | 2.5 |

### 1.5 구현된 파일

| 파일 | 역할 |
|------|------|
| `backend/scripts/batch_review_analysis.py` | 배치 수집→전처리→LLM분석→적재 스크립트 |
| `backend/scripts/init_db.sql` (추가분) | `place_analysis` 테이블 DDL |
| `backend/src/tools/compare_reviews.py` | 채팅 내 비교 도구 (LangChain @tool) |
| `backend/src/api/analysis.py` | REST API (단일 조회 + 복수 비교) |
| `seoul-chatbot-fe/components/blocks/ChartBlock.tsx` | 레이더차트 렌더링 (Recharts) |
| `seoul-chatbot-fe/components/blocks/AnalysisSourcesBlock.tsx` | 출처·기준·원본 리뷰 샘플 카드 |
| `seoul-chatbot-fe/app/poc/analysis/page.tsx` | 독립 PoC 확인 페이지 |

---

## 2. 현재 데이터 소스의 한계

### 2.1 Google Places API — 리뷰

| 항목 | 현재 상태 |
|------|----------|
| 데이터 종류 | 실제 사용자 리뷰 원문 + 별점(1~5) |
| 건수 | **최대 5건/장소** (API 제한) |
| 언어 | `language=ko` 파라미터로 한국어 우선, 외국어 리뷰 혼재 |
| 신뢰도 | **높음** — 실제 방문 기반 리뷰 |
| 한계 | 5건으로는 통계적 대표성 부족. 특히 리뷰 수 1000건 이상 장소에서 5건은 편향 가능 |

### 2.2 Naver Blog Search API — 후기

| 항목 | 현재 상태 |
|------|----------|
| 데이터 종류 | 블로그 검색 결과 **snippet** (description 필드) |
| 건수 | 최대 10건/장소 (display 파라미터) |
| 실제 내용 | 검색 키워드 주변 ~200자 발췌문. **블로그 본문 전체가 아님** |
| 신뢰도 | **낮음** — 맥락 없는 단편, 광고/협찬 혼재 |
| 한계 | snippet만으로는 분위기·서비스 등 세부 지표 판단 근거가 부족 |

### 2.3 기 수집된 CSV (비용 견적 PoC에서 수집)

| 파일 | 위치 | 건수 | 내용 |
|------|------|------|------|
| `blog_review_data.csv` | `output/` | ~190KB | 50개 장소 × 네이버 블로그 후기 snippet |
| `blog_price_data.csv` | `output/` | ~25KB | 가격 언급 블로그 + 정규식 추출 가격 |
| `blog_price_data.csv` (정제) | `output_refined/` | ~8KB | 광고 제거 후 정제 가격 데이터 |

> 이 CSV들도 네이버 블로그 snippet 기반이므로 동일한 한계를 공유.

---

## 3. 데이터 소스 조달 계획

### 3.1 정적 데이터 (CSV / 배치 수집)

#### A. 장소 마스터 (places 테이블 적재용)

| # | 데이터 | 출처 | 형태 | 조달 방법 | 활용 |
|---|--------|------|------|----------|------|
| 1 | 소상공인 상권 정보 | data.go.kr | CSV/API | 공공데이터포털 다운로드 or API 호출 | 음식점·카페·헬스장·미용실 위치, 업종코드 |
| 2 | 전국일반음식점 표준데이터 | data.go.kr | CSV | 공공데이터포털 다운로드 | 음식점 인허가, 위생등급, 좌석수 |
| 3 | 전국 체력단련장 표준데이터 | data.go.kr | CSV | 공공데이터포털 다운로드 | 헬스장 인허가, 시설면적 |
| 4 | 전국미용업소 표준데이터 | data.go.kr | CSV | 공공데이터포털 다운로드 | 미용실 인허가 |
| 5 | 서울관광재단 식당운영정보 | data.go.kr | CSV | 공공데이터포털 다운로드 | 주차/와이파이/놀이방 등 속성(attributes JSONB) |
| 6 | 서울시 구별 헬스장 현황 | data.go.kr | CSV | 공공데이터포털 다운로드 | 시설면적, 좌표 |

> **ETL 경로:** CSV → `etl_places.py` → PostgreSQL `places` + OpenSearch `places_vector`

#### B. 행사/축제 (events 테이블 적재용)

| # | 데이터 | 출처 | 형태 | 조달 방법 | 활용 |
|---|--------|------|------|----------|------|
| 7 | 서울시 문화행사 정보 | data.seoul.go.kr | API | `culturalEventInfo` API 호출 | 공연·전시·축제 일정 |
| 8 | KOPIS 공연예술 | kopis.or.kr | API | KOPIS API 호출 | 유료 공연, 포스터 이미지, 판매율 |
| 9 | TourAPI 4.0 축제 | data.go.kr | API | TourAPI 호출 | 관광 축제·체험 |
| 10 | 전국문화축제 표준데이터 | data.go.kr | CSV | 공공데이터포털 다운로드 | 축제 설명 텍스트 (임베딩 가능) |
| 11 | KOPIS 예매상황판 | bigdata-culture.kr | CSV | 빅데이터 포털 다운로드 | 공연 판매율→인기순 정렬 |

#### C. 리뷰 분석 전용 (place_analysis 적재용)

| # | 데이터 | 출처 | 형태 | 조달 방법 | 활용 | 한계 |
|---|--------|------|------|----------|------|------|
| 12 | Google Places 리뷰 | Google | API | Place Details `reviews` 필드 | 별점 포함 리뷰 원문 | 최대 5건/장소 |
| 13 | 네이버 블로그 snippet | Naver | API | Blog Search API | 후기 발췌문 | 본문 아님, ~200자 |
| 14 | 네이버 블로그 본문 (검토 중) | Naver | 크롤링 | blog link URL 접근 → 본문 파싱 | 전문 리뷰 텍스트 | 크롤링 정책 확인 필요 |
| 15 | 카카오맵 리뷰 (검토 중) | Kakao | 크롤링 | - | 한국 사용자 리뷰 | API 미제공, 크롤링 필요 |

#### D. 비용 견적 전용

| # | 데이터 | 출처 | 형태 | 조달 방법 | 활용 |
|---|--------|------|------|----------|------|
| 16 | 네이버 블로그 가격 정보 | Naver | 기 수집 CSV | `output/blog_price_data.csv` | 메뉴별 가격 추출 |
| 17 | Google Places 가격대 | Google | API | Place Details `price_level` 필드 | 1~4 가격대 |

#### E. 혼잡도 분석 전용

| # | 데이터 | 출처 | 형태 | 조달 방법 | 활용 |
|---|--------|------|------|----------|------|
| 18 | 서울시 실시간 도시데이터 | data.seoul.go.kr | API | 실시간 API 호출 | 지구별 혼잡도 |
| 19 | 관광지별 연관 관광지 | data.go.kr | API/CSV | 공공데이터포털 | 코스 추천 연관 장소 |

---

### 3.2 실시간 API (런타임 호출)

사용자 요청 시 실시간으로 호출하는 API. 배치 적재 아님.

| API | 용도 | 호출 시점 | 캐시 TTL |
|-----|------|----------|---------|
| Google Places Text Search | 장소 검색 | PLACE_SEARCH intent | 24h (Redis) |
| Google Places Details | 평점·영업·이미지 실시간 | 장소 카드 생성 시 | 24h |
| Google Places Reviews | 리뷰 수집 (배치) | batch_review_analysis.py | 7일 (DB TTL) |
| 네이버 블로그 Search | 후기 검색 | PLACE_RECOMMEND, 배치 분석 | 6h |
| 네이버 뉴스 Search | 행사 뉴스 | EVENT_SEARCH intent | 6h |
| 서울시 문화행사 API | 행사 검색 | EVENT_SEARCH intent | 6h |
| Google Calendar MCP | 일정 추가 | BOOKING intent | - |
| 서울시 실시간 도시데이터 | 혼잡도 | CROWDEDNESS intent | 1h |

---

## 4. 리뷰 데이터 품질 개선 방안

현재 PoC의 가장 큰 약점: **리뷰 건수 부족 + Naver snippet 품질 저하**.

### 4.1 선택지 비교

| 방안 | 리뷰 건수 | 품질 | 구현 난이도 | 리스크 |
|------|:---:|:---:|:---:|------|
| **A. 현행 유지** (Google 5건 + Naver snippet 10건) | 15건 | 중하 | 없음 | 통계적 대표성 부족 |
| **B. Google Places API (New) 전환** | 10건 | 상 | 낮음 | API 키 변경, 비용 증가 |
| **C. Naver 블로그 본문 크롤링** | 10건 | 상 | 중 | 크롤링 정책, 파싱 불안정 |
| **D. 카카오맵 리뷰 크롤링** | 20~50건 | 상 | 중 | API 미제공, 크롤링 차단 가능 |
| **E. 자체 리뷰 DB 축적** | 장기 증가 | 상 | 중 | 초기 데이터 콜드스타트 |
| **F. B + C 병행** | 20건 | 상 | 중 | 가장 현실적인 단기 개선안 |

### 4.2 권장 방안: F (Google New API + Naver 본문 크롤링)

**단계 1 — Google Places API (New) 전환**
- `places.googleapis.com/v1/places/{id}` 엔드포인트
- `reviews` 필드로 최대 10건 (기존 5건 → 2배)
- 별점 + 원문 + 작성 시점 포함
- 난이도: API URL/파라미터 변경만으로 가능

**단계 2 — Naver 블로그 본문 수집**
- Blog Search API 결과의 `link` URL 접근
- 블로그 HTML 파싱 → 본문 텍스트 추출
- `httpx` + `BeautifulSoup` 조합
- 본문에서 광고 필터링 후 LLM 분석 입력으로 사용
- 리스크: 네이버 크롤링 정책 확인 필요 (robots.txt)

**기대 효과:**
- 리뷰 건수: 15건 → 20건/장소
- Naver 데이터 품질: snippet ~200자 → 본문 1000~3000자
- LLM 채점 정확도: 맥락 있는 전문 리뷰로 지표 판단 근거 강화

---

## 5. 전체 데이터 소스 맵

```
                          ┌─────────────────────────┐
                          │   place_analysis 테이블   │
                          │  (리뷰 비교 레이더차트)    │
                          └────────┬────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
           Google Places     Naver Blog      (향후) Kakao
           Reviews API       Search API      Map 크롤링
           실 리뷰 5~10건    snippet/본문     리뷰 20~50건
           ★ 별점 포함       10건

                          ┌─────────────────────────┐
                          │     places 테이블         │
                          │  (장소 마스터 데이터)      │
                          └────────┬────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      소상공인 상권 CSV     Google Places API      TourAPI
      음식점/헬스장/미용실   실시간 평점/영업/이미지   관광지/문화시설
      data.go.kr           런타임 호출              data.go.kr

                          ┌─────────────────────────┐
                          │     events 테이블         │
                          │  (행사/축제 데이터)        │
                          └────────┬────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      서울시 문화행사 API     KOPIS API            네이버 뉴스 API
      data.seoul.go.kr      공연 + 포스터          실시간 행사 뉴스
                            kopis.or.kr

                          ┌─────────────────────────┐
                          │  population_hourly 테이블 │
                          │  (혼잡도 데이터)          │
                          └────────┬────────────────┘
                                   │
                                   ▼
                          서울시 실시간 도시데이터
                          data.seoul.go.kr
```

---

## 6. 다음 단계 (Week 3~4)

| 우선순위 | 작업 | 담당 | 비고 |
|:---:|------|------|------|
| 1 | 공공데이터 CSV 다운로드 + ETL 적재 (places 테이블) | BE | `etl_places.py` 활용 |
| 2 | Google Places API (New) 전환 | BE | 리뷰 5건 → 10건 |
| 3 | Naver 블로그 본문 크롤링 PoC | BE | robots.txt 확인 후 진행 여부 결정 |
| 4 | 배치 분석 스케줄러 구성 | BE | 신규 장소 자동 분석 (cron or APScheduler) |
| 5 | places 테이블 적재 후 배치 분석 전체 실행 | BE | google_place_id 매핑 필요 |
