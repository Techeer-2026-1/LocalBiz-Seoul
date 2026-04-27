# OpenSearch 비정형 데이터 적재 — 클로드 코드 실행 가이드

> 이 문서를 클로드 코드에 첨부하고, 단계별로 프롬프트를 입력하세요.
> 각 단계는 독립적으로 실행 가능합니다. 순서대로 진행하세요.

---

## 사전 준비

### 환경변수 설정 (.env 파일)

```
OPENSEARCH_HOST=<EC2 퍼블릭 IP 또는 도메인>
OPENSEARCH_PORT=9200
OPENSEARCH_PASSWORD=<admin 비밀번호>
OPENAI_API_KEY=<OpenAI API 키>
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<dbname>
NAVER_CLIENT_ID=<네이버 검색 API 클라이언트 ID>
NAVER_CLIENT_SECRET=<네이버 검색 API 시크릿>
GOOGLE_PLACES_API_KEY=<Google Places API 키>
ANTHROPIC_API_KEY=<Anthropic API 키 — 이미지 캡셔닝용>
```

### 필요 패키지

```
opensearch-py openai httpx psycopg2-binary python-dotenv anthropic
```

### 참조 문서

- opensearch_data_loading_guide.md (인덱스 스키마 + 적재 코드 + 검색 함수)
- LocalBiz_Intelligence_기획서_v4.docx (전체 아키텍처 + ERD)

---

## 단계 1: OpenSearch 인덱스 생성

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 OpenSearch 인덱스 3개를 생성하는
Python 스크립트를 만들어줘.

인덱스:
1. places_vector — 장소 의미 검색 + 이미지 캡션 유사도
2. place_reviews — 리뷰 분석 요약 의미 검색
3. events_vector — 행사/축제 의미 검색

요구사항:
- .env 파일에서 환경변수 로드 (python-dotenv)
- 기존 인덱스가 있으면 삭제 후 재생성
- nori 분석기 사용 (한국어 토크나이저)
- knn_vector dimension = 1536 (text-embedding-3-small)
- 각 인덱스 생성 결과 로깅
- 연결 실패 시 에러 메시지 출력 후 종료

파일명: etl/create_indices.py
실행: python etl/create_indices.py
```

### 성공 확인

```
출력 예시:
Connected to OpenSearch at <host>:9200
Deleted existing index: places_vector
Created index: places_vector
Created index: place_reviews
Created index: events_vector
All 3 indices created successfully.
```

---

## 단계 2: PostgreSQL → places_vector 적재

### 전제 조건
- PostgreSQL places 테이블에 데이터가 있어야 함
- PostGIS가 설치되어 geom 컬럼이 존재해야 함

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 PostgreSQL places 테이블의 데이터를
OpenSearch places_vector 인덱스에 적재하는 스크립트를 만들어줘.

처리 흐름:
1. PostgreSQL places 테이블에서 전체 SELECT
   (place_id, name, category, sub_category, district, address,
    ST_Y(geom) as lat, ST_X(geom) as lng, raw_data, attributes, source)
2. 각 장소마다 page_content 생성 (템플릿 기반)
   - "{district}에 위치한 {sub_category} {category}. {name}."
   - attributes/raw_data에서 와이파이, 주차, 놀이방 등 추출
   - address 추가
   - raw_data에 blog_price_data가 있으면 평균 가격 추가
3. page_content를 OpenAI text-embedding-3-small로 배치 임베딩
   - 500건씩 배치
   - 임베딩 실패 시 해당 배치 스킵하고 계속 진행
4. OpenSearch helpers.bulk로 적재
   - place_id를 _id로 사용 (중복 방지)

요구사항:
- .env 환경변수 사용
- 진행률 로깅 (100건마다 "Processing 100/810...")
- 총 적재 건수, 실패 건수, 소요 시간 출력
- --dry-run 옵션: 임베딩/적재 없이 page_content 샘플 5개만 출력
- --limit N 옵션: 처음 N건만 처리

파일명: etl/load_places_vector.py
실행: python etl/load_places_vector.py --dry-run
실행: python etl/load_places_vector.py --limit 10
실행: python etl/load_places_vector.py
```

### 성공 확인

```
출력 예시:
Loaded 810 places from PostgreSQL
Processing 100/810...
Processing 200/810...
...
places_vector 적재 완료: 810 indexed, 0 errors, 45.2초
```

---

## 단계 3: 리뷰 배치 분석 → place_analysis 생성

### 전제 조건
- Google Places API 키 필요
- 네이버 블로그 검색 API 키 필요
- places 테이블에 google_place_id가 있는 장소 필요

### 프롬프트

```
opensearch_data_loading_guide.md와 리뷰비교_PoC_데이터소스_정리.md를 참조해서
장소별 리뷰를 수집하고 LLM으로 분석하여 place_analysis 테이블에 적재하는
배치 스크립트를 만들어줘.

처리 흐름:
1. PostgreSQL places 테이블에서 google_place_id가 있는 장소 SELECT
   - --category 옵션으로 특정 카테고리만 처리 가능 (예: --category 카페)
2. 장소마다 리뷰 수집 (병렬):
   a. Google Places Details API → reviews 필드 최대 10건
   b. 네이버 블로그 검색 API → "{상호명} {자치구} 후기" display=10
3. 전처리:
   - HTML 태그 제거 (네이버 snippet의 <b> 등)
   - 광고/협찬 키워드 필터링 ("소정의 원고료", "협찬", "제공받아" 등)
   - 중복 제거
4. LLM 분석 (Gemini 2.5 Flash, JSON mode):
   - 6개 지표 채점 (taste, service, atmosphere, value, cleanliness, accessibility) 1~5점
   - 키워드 5개 추출
   - 3줄 요약 생성
   - 응답 JSON 스키마 강제
5. PostgreSQL place_analysis 테이블에 UPSERT
   - ON CONFLICT (place_id) DO UPDATE
   - ttl_expires_at = NOW() + INTERVAL '7 days'
6. Rate limit 관리:
   - Google Places: 요청 간 0.1초 sleep
   - 네이버: 요청 간 0.1초 sleep
   - Gemini: 요청 간 0.5초 sleep

place_analysis 테이블 DDL (없으면 자동 생성):
CREATE TABLE IF NOT EXISTS place_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id UUID REFERENCES places(place_id),
    google_place_id VARCHAR(100),
    place_name VARCHAR(200),
    score_taste NUMERIC(2,1),
    score_service NUMERIC(2,1),
    score_atmosphere NUMERIC(2,1),
    score_value NUMERIC(2,1),
    score_cleanliness NUMERIC(2,1),
    score_accessibility NUMERIC(2,1),
    keywords TEXT[],
    summary TEXT,
    review_count INTEGER,
    source_breakdown JSONB,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    ttl_expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
    UNIQUE(place_id)
);

요구사항:
- .env 환경변수 사용 (GOOGLE_PLACES_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)
- Gemini API 키는 환경변수 GEMINI_API_KEY
- 진행률 로깅 (장소명 + 수집 리뷰 수 + 분석 결과 요약)
- 실패한 장소는 failed_analysis.json에 별도 저장
- --dry-run: 첫 3건만 수집하고 LLM 분석 결과 출력 (DB 적재 안 함)
- --limit N: 처음 N건만 처리
- --category CAT: 특정 카테고리만 (예: --category 카페)
- 총 분석 건수, 실패 건수, 평균 점수, 소요 시간 출력

파일명: etl/batch_review_analysis.py
실행: python etl/batch_review_analysis.py --dry-run --limit 3
실행: python etl/batch_review_analysis.py --category 카페 --limit 10
실행: python etl/batch_review_analysis.py --category 카페
```

### 성공 확인

```
출력 예시:
Target places: 334 (카페)
[1/334] 블루보틀 삼청점 — Google 8건 + Naver 7건 = 15건 → 분석 완료
  맛:3.9 서비스:4.3 분위기:3.9 가성비:2.6 청결:- 접근:2.5
  키워드: 핸드드립, 미니멀, 삼청동, 디저트, 조용한
[2/334] 스타벅스 강남R점 — Google 10건 + Naver 10건 = 20건 → 분석 완료
  맛:4.3 서비스:3.0 분위기:4.0 가성비:3.8 청결:3.0 접근:4.7
...
완료: 334건 분석, 2건 실패, 평균 맛:3.8, 소요: 94분
```

---

## 단계 4: place_analysis → place_reviews 인덱스 적재

### 전제 조건
- 단계 3이 완료되어 place_analysis 테이블에 데이터가 존재해야 함

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 PostgreSQL place_analysis 테이블의
데이터를 OpenSearch place_reviews 인덱스에 적재하는 스크립트를 만들어줘.

처리 흐름:
1. place_analysis 테이블에서 TTL 만료되지 않은 row SELECT
   - places 테이블과 LEFT JOIN하여 category, district 가져오기
2. summary_text 생성: "{summary} 키워드: {keywords 콤마구분}"
3. summary_text를 OpenAI text-embedding-3-small로 배치 임베딩
4. OpenSearch place_reviews 인덱스에 Bulk 적재
   - analysis_id를 _id로 사용

요구사항:
- .env 환경변수 사용
- 진행률 로깅
- --dry-run: summary_text 샘플 5개만 출력
- 총 적재 건수, 소요 시간 출력

파일명: etl/load_place_reviews.py
실행: python etl/load_place_reviews.py --dry-run
실행: python etl/load_place_reviews.py
```

---

## 단계 5: events → events_vector 인덱스 적재

### 전제 조건
- PostgreSQL events 테이블에 데이터가 있어야 함

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 PostgreSQL events 테이블의 데이터를
OpenSearch events_vector 인덱스에 적재하는 스크립트를 만들어줘.

처리 흐름:
1. events 테이블에서 종료일이 오늘 이후인 행사만 SELECT
2. description 생성: "{title}. {summary}" (summary 없으면 "{title}. {place_name} {category}")
3. description을 OpenAI 배치 임베딩
4. OpenSearch events_vector에 Bulk 적재

요구사항:
- .env 환경변수 사용
- --dry-run 옵션
- 총 적재 건수, 소요 시간 출력

파일명: etl/load_events_vector.py
실행: python etl/load_events_vector.py --dry-run
실행: python etl/load_events_vector.py
```

---

## 단계 6: 가격 데이터 배치 수집

### 전제 조건
- 네이버 블로그 검색 API 키 필요

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 서울 장소들의 메뉴/가격 정보를
네이버 블로그 검색 API로 배치 수집하여 PostgreSQL places.raw_data JSONB에
저장하는 스크립트를 만들어줘.

처리 흐름:
1. PostgreSQL places 테이블에서 음식점/카페/헬스장/미용실 SELECT
2. 카테고리별 검색어 전략:
   - 음식점: "{상호명} 메뉴 가격"
   - 카페: "{상호명} 메뉴 가격"
   - 헬스장: "{상호명} 회원권 가격"
   - 미용실: "{상호명} 커트 가격"
   - 기타: "{상호명} 이용료"
3. 네이버 블로그 검색 API 호출 (display=5, sort=sim)
4. 응답에서 HTML 태그 제거
5. 가격 패턴 정규식 추출: "숫자+원", "숫자+만원", "₩숫자"
6. 3중 필터링:
   - 상호명이 description에 포함되어 있는지
   - 서울 자치구명이 포함되어 있는지
   - 추출된 가격이 100원 이상 100만원 이하인지
7. 필터링 통과한 가격의 min, max, avg 계산
8. PostgreSQL places.raw_data JSONB에 업데이트:
   UPDATE places SET raw_data = raw_data || '{"blog_price_data": {...}}'::jsonb
   WHERE place_id = '...'

요구사항:
- .env 환경변수 사용 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)
- Rate limit: 요청 간 0.15초 sleep
- --dry-run: 검색어만 출력
- --limit N: 처음 N건만 처리
- --category CAT: 특정 카테고리만
- 결과 통계: 총 장소 수, 가격 추출 성공 수, API 호출 수, 일일 한도 대비 사용률
- 실패한 장소 failed_prices.json에 저장

파일명: etl/collect_price_data.py
실행: python etl/collect_price_data.py --dry-run --limit 5
실행: python etl/collect_price_data.py --category 음식점 --limit 20
실행: python etl/collect_price_data.py
```

---

## 단계 7: 이미지 캡셔닝 배치 (Phase 2)

### 전제 조건
- Anthropic API 키 필요
- Google Places API 키 필요
- 단계 2가 완료되어 places_vector에 문서가 존재해야 함

### 프롬프트

```
opensearch_data_loading_guide.md를 참조해서 주요 장소 이미지를 Claude Haiku로
캡셔닝하여 OpenSearch places_vector의 image_caption + image_embedding에
부분 업데이트하는 스크립트를 만들어줘.

처리 흐름:
1. PostgreSQL places에서 google_place_id가 있는 장소 SELECT
   - 우선순위: 관광지 → 카페 → 음식점
   - LIMIT 1000
2. Google Places Details API로 photo_reference 1개 가져오기
3. Google Places Photos API로 이미지 URL 생성 (maxwidth=400)
4. 이미지 다운로드 → base64 변환
5. Claude Haiku로 캡셔닝:
   프롬프트: "이 장소 사진의 분위기, 인테리어 특징, 공간 특성을 한국어 3문장으로 설명해주세요. 객관적 묘사만."
6. 캡션 텍스트를 OpenAI 임베딩
7. OpenSearch places_vector에 부분 업데이트 (_op_type: update):
   - image_caption: 캡션 텍스트
   - image_embedding: 캡션 임베딩 벡터

요구사항:
- .env 환경변수 사용 (ANTHROPIC_API_KEY, GOOGLE_PLACES_API_KEY)
- 이미지 다운로드 실패 / 캡셔닝 실패 시 스킵하고 계속 진행
- Rate limit: Google API 0.1초, Claude 0.3초 sleep
- --dry-run: 첫 3건만 캡셔닝하고 결과 출력 (OS 업데이트 안 함)
- --limit N: 처음 N건만 처리
- 진행률 로깅, 총 캡셔닝 건수, 실패 건수, 비용 추정, 소요 시간

파일명: etl/load_image_captions.py
실행: python etl/load_image_captions.py --dry-run --limit 3
실행: python etl/load_image_captions.py --limit 50
실행: python etl/load_image_captions.py
```

---

## 단계 8: 검색 테스트

### 프롬프트

```
opensearch_data_loading_guide.md의 검색 함수(섹션 7)를 참조해서
OpenSearch에 적재된 데이터를 테스트하는 스크립트를 만들어줘.

테스트 시나리오:
1. 장소 검색: "카공하기 좋은 카페" (category=카페, district=강남구) → Top 5
2. 장소 검색: "데이트 분위기 레스토랑" (category=음식점) → Top 5
3. 리뷰 검색: "서비스가 친절한 곳" → Top 5
4. 행사 검색: "아이와 갈 만한 체험" → Top 5
5. 이미지 캡션 검색: "모던한 인테리어 자연광 카페" → Top 5 (image_caption 존재하는 것만)

각 테스트마다:
- 검색 쿼리
- 결과 건수
- Top 3 결과의 name, score, page_content(또는 summary_text) 앞 100자
- 응답 시간 (ms)

파일명: etl/test_search.py
실행: python etl/test_search.py
```

---

## 실행 순서 요약

```
# 0. 환경 세팅
pip install opensearch-py openai httpx psycopg2-binary python-dotenv anthropic
cp .env.example .env  # 환경변수 채우기

# 1. 인덱스 생성
python etl/create_indices.py

# 2. places → places_vector (장소 설명 임베딩)
python etl/load_places_vector.py --dry-run
python etl/load_places_vector.py

# 3. 리뷰 배치 분석 → place_analysis (카페 우선)
python etl/batch_review_analysis.py --category 카페 --dry-run --limit 3
python etl/batch_review_analysis.py --category 카페

# 4. place_analysis → place_reviews (리뷰 요약 임베딩)
python etl/load_place_reviews.py

# 5. events → events_vector (행사 설명 임베딩)
python etl/load_events_vector.py

# 6. 가격 데이터 배치 수집 (블로그 API)
python etl/collect_price_data.py --category 음식점 --limit 20
python etl/collect_price_data.py

# 7. 이미지 캡셔닝 (Phase 2, 선택)
python etl/load_image_captions.py --dry-run --limit 3
python etl/load_image_captions.py --limit 50

# 8. 검색 테스트
python etl/test_search.py
```

---

## 트러블슈팅

### OpenSearch 연결 안 됨
- EC2 보안그룹에서 9200 포트 인바운드 허용 확인
- OpenSearch 프로세스 실행 중인지 확인: `curl -k https://localhost:9200`
- SSL 인증서 문제면 `verify_certs=False` 확인

### nori 분석기 오류
- `analysis-nori` 플러그인 설치: `sudo bin/opensearch-plugin install analysis-nori`
- 설치 후 OpenSearch 재시작 필요

### 임베딩 실패
- OpenAI API 키 확인
- 빈 문자열이 입력에 포함되면 에러 발생 → 빈 문자열 필터링 필수
- Rate limit 초과 시 60초 대기 후 재시도

### Bulk 적재 에러
- `_id` 중복 시 덮어씀 (정상)
- 벡터 차원 불일치 시 에러 → 반드시 1536 확인
- 메모리 부족 시 batch_size 줄이기 (500 → 200)

### place_analysis 테이블 없음
- 단계 3의 DDL을 직접 실행하거나, 스크립트에서 자동 생성하도록 구현

### Google Places API 한도 초과
- 월 $200 무료 크레딧 확인
- 캐싱으로 중복 호출 방지 (같은 place_id 재호출 스킵)
