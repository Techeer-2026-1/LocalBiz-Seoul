# LocalBiz Intelligence — CSV 데이터 프로파일링 작업 프롬프트

## 프로젝트 배경

LocalBiz Intelligence는 **서울 로컬 라이프 AI 챗봇**이다. 사용자가 자연어로 질문하면 서울의 장소, 행사, 맛집, 카페 등에 대해 AI가 실시간으로 검색·추천·분석하여 응답한다.

### 아키텍처
- **백엔드**: FastAPI + LangGraph (GCE)
- **정형 DB**: PostgreSQL + PostGIS (Google Cloud SQL)
- **벡터 검색**: OpenSearch 2.17 (GCE, 768d, nori, k-NN)
- **프론트엔드**: Next.js + Three.js (Vercel)
- **LLM**: Gemini (메인), Claude Haiku (이미지 캡셔닝)

### 타겟 테이블 (PostgreSQL)

현재 ETL로 적재해야 하는 핵심 테이블은 다음 3개다:

#### 1. places (장소 마스터)
```sql
CREATE TABLE places (
    place_id        VARCHAR(36) PRIMARY KEY,  -- UUID, OpenSearch _id와 매칭
    name            VARCHAR(200) NOT NULL,     -- 상호명
    category        VARCHAR(50),               -- 대분류 (음식점, 카페, 공원 등)
    sub_category    VARCHAR(100),              -- 소분류 (한식, 커피전문점 등)
    address         TEXT,                      -- 주소
    district        VARCHAR(50),               -- 자치구
    lat             DOUBLE,                    -- 위도 (실제: PostGIS geom)
    lng             DOUBLE,                    -- 경도 (실제: PostGIS geom)
    phone           VARCHAR(20),               -- 전화번호
    google_place_id VARCHAR(100),              -- Google Places ID
    booking_url     TEXT,                      -- 예약 딥링크
    raw_data        JSON,                      -- 원본 CSV 전체 칼럼 보존
    source          VARCHAR(50),               -- 데이터 출처
    created_at      DATETIME,
    updated_at      DATETIME,
    is_deleted      TINYINT(1) DEFAULT 0
);
```

#### 2. events (행사/축제)
```sql
CREATE TABLE events (
    event_id    VARCHAR(36) PRIMARY KEY,  -- UUID, OpenSearch _id와 매칭
    title       VARCHAR(200) NOT NULL,     -- 행사명
    category    VARCHAR(50),               -- 분류 (축제, 공연, 전시 등)
    place_name  TEXT,                      -- 개최 장소명
    address     TEXT,                      -- 주소
    district    VARCHAR(50),               -- 자치구
    lat         DOUBLE,                    -- 위도
    lng         DOUBLE,                    -- 경도
    date_start  DATE,                      -- 시작일
    date_end    DATE,                      -- 종료일
    price       TEXT,                      -- 가격
    poster_url  TEXT,                      -- 포스터 URL
    detail_url  TEXT,                      -- 상세 URL
    summary     TEXT,                      -- 설명 (임베딩 대상)
    source      VARCHAR(50),               -- 출처
    raw_data    JSON,                      -- 원본 보존
    created_at  DATETIME,
    updated_at  DATETIME,
    is_deleted  TINYINT(1) DEFAULT 0
);
```

#### 3. population_stats (생활인구)
```sql
CREATE TABLE population_stats (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    base_date     DATE NOT NULL,
    time_slot     SMALLINT NOT NULL,        -- 시간대 (0~23)
    adm_dong_code VARCHAR(20) NOT NULL,     -- 행정동 코드
    total_pop     INT DEFAULT 0,
    raw_data      JSON,                     -- 성별/연령대별 세부
    created_at    DATETIME
);
```

---

## 너의 작업

### 목표
Google Drive에서 다운받은 CSV 폴더 전체를 프로파일링하여, ETL 칼럼 매핑과 카테고리 표준화를 설계하기 위한 기초 데이터를 확보한다.

### CSV 폴더 위치
Google Drive 폴더를 로컬에 다운받은 경로를 사용한다. 대략 다음과 같은 폴더 구조로 되어 있다:

```
csv_data/
├── 음식점 카페/
│   └── *.csv
├── 도서관/
│   └── *.csv
├── 관광지/
│   └── *.csv
├── 체육시설/
│   └── *.csv
├── 쇼핑/
│   └── *.csv
├── 공공시설/
│   └── *.csv
├── 의료 시설/
│   └── *.csv
├── 복지/
│   └── *.csv
├── 복지·보육/
│   └── *.csv
├── 교육 관련/
│   └── *.csv
├── 주차장/
│   └── *.csv
├── 지하철역 관련/
│   └── *.csv
├── 생활편의업 / 숙박/
│   └── *.csv
├── 생활인구 통계/
│   └── *.csv
├── 축제·행사/
│   └── *.csv
├── 그 외/
│   └── *.csv
└── 소상공인시장진흥공단_상가(상권)_정보(서울)(CSV)(202512)/
    └── *.csv
```

### 실행 단계

#### 1단계: CSV 파일 전수 탐색
- 위 폴더 구조에서 모든 `.csv` 파일을 재귀적으로 찾는다.
- 각 파일의 인코딩을 자동 감지한다 (utf-8, cp949, euc-kr, utf-8-sig 순서로 시도).

#### 2단계: 파일별 프로파일링
각 CSV 파일에 대해 다음 정보를 추출한다:

| 항목 | 내용 |
|------|------|
| 파일명 | 파일명 + 소속 폴더 |
| 총 건수 | 행 수 |
| 파일 크기 | MB 단위 |
| 인코딩 | 감지된 인코딩 |
| 칼럼 목록 | 칼럼명 + 타입 추정 + NULL 비율 + 유니크 값 수 |
| 역할 감지 | 칼럼명에서 이름/주소/좌표/카테고리/전화번호 칼럼 자동 감지 |
| 카테고리 distinct | distinct 값이 30개 이하인 칼럼은 고유값 전체 나열 |
| 좌표 유무 | 위도/경도 칼럼 존재 여부 + NULL 비율 |
| 주소 형태 | 도로명/지번 어느 형태인지 |
| 샘플 3행 | 상위 3개 튜플 |

**칼럼명에서 역할 감지 키워드:**
- 이름: 상호, 이름, 명칭, name, 시설명, 장소명, 업소명, 사업장명
- 주소: 주소, 도로명, 지번, address, 소재지, 위치
- 좌표: 위도, 경도, lat, lng, longitude, latitude, x좌표, y좌표
- 카테고리: 업종, 분류, 카테고리, category, 유형, 종류, 업태
- 전화번호: 전화, 연락처, phone, tel

#### 3단계: 보고서 생성
프로파일링 결과를 **마크다운 파일**로 출력한다. 보고서 구조:

```
# 📊 CSV 데이터 프로파일링 보고서

## 1. 전체 요약
- 총 파일 수, 총 레코드 수
- 파일별 건수/칼럼수/크기 요약 테이블

## 2. 파일별 상세
- 폴더별로 그룹핑
- 각 파일: 칼럼 구조 테이블 + 역할 감지 결과 + 카테고리 distinct 값 + 샘플 3행

## 3. 카테고리성 칼럼 종합
- 표준 카테고리 매핑 설계를 위한 참고 자료
- 모든 파일에서 감지된 카테고리성 칼럼의 distinct 값 전체 나열

## 4. ETL 매핑 체크리스트
- 각 파일에서 places/events/population_stats 테이블로 매핑할 때 확인할 사항
```

#### 4단계: 매핑 초안 제안
프로파일링 결과를 바탕으로, 다음을 제안한다:

**카테고리 표준 매핑 초안:**
- 각 출처별 원본 카테고리 값을 우리 표준 대분류/소분류로 매핑하는 초안
- 매핑이 모호한 값은 별도 표시

**칼럼 매핑 초안:**
- 각 출처별 칼럼을 places/events/population_stats의 어떤 칼럼에 매핑할지
- 매핑 대상이 없는 칼럼은 raw_data(JSON)에 보존

---

## 중요 참고사항

1. **한국 공공데이터 CSV**이므로 인코딩이 cp949 또는 euc-kr일 가능성이 높다. utf-8이 아니면 다른 인코딩을 시도해야 한다.
2. **소상공인 상권 CSV**가 가장 큰 데이터(약 100만건+)이고 가장 중요하다. 이 파일의 "업종대분류명", "업종중분류명" 칼럼이 우리 카테고리 매핑의 핵심 기준이 된다.
3. **축제·행사 폴더**의 CSV는 events 테이블에 적재한다. 나머지는 대부분 places 테이블이다.
4. **생활인구 통계 폴더**의 CSV는 population_stats 테이블에 적재한다.
5. places 테이블의 `raw_data` 칼럼에는 원본 CSV의 전체 칼럼을 JSON으로 보존해야 한다. 공통 칼럼만 정규화된 칼럼에 매핑하고, 나머지는 raw_data에 넣는 "공통 기둥 + 유연한 주머니" 패턴이다.
6. 좌표 데이터가 있으면 실제 DB에서는 PostGIS `GEOMETRY(Point, 4326)`으로 저장하지만, 프로파일링 단계에서는 lat/lng 칼럼의 존재 여부와 NULL 비율만 확인하면 된다.

---

## 실행 방법

첨부된 `csv_profiler.py` 스크립트를 사용하거나, 직접 파이썬으로 프로파일링해도 된다.

```bash
# 스크립트 사용 시
python csv_profiler.py --input-dir ./csv_data/ --output ./profile_report.md

# 또는 직접 pandas로 프로파일링
```

프로파일링 보고서가 생성되면, 그걸 기반으로 카테고리 매핑 + 칼럼 매핑 초안을 함께 제안해달라.
