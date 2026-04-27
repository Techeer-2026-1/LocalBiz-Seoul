# ETL G2 — 공공/문화 신규 커버리지 4 카테고리 (A scope)

- Phase: LocalBiz ETL
- 요청자: 이정 (PM) — 2026-04-13, "권장대로 다 처리해"
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드)
- 선행: plan #13 COMPLETE

## 1. 요구사항

**사용자 지시 (원문)**: "권장대로 다 처리해. 일단 데이터 적재 다 네가 만탄해서 끝내고 다 적재 끝나면 말해."

**목표**: v0.2 카테고리 중 현재 row 0인 4개 신규 커버리지 카테고리 채움 (A 안, 중복 리스크 0).

- **공원** (0 → ~2,400): 25 지구별 공원 CSV (utf-8, WGS84)
- **도서관** (0 → ~527): 25 지구별 도서관 CSV (utf-8, WGS84)
- **문화시설** (0 → ~3,361): 문화공간 1036 + 공연장 1404(TM) + 영화상영관 921(TM)
- **공공시설** (0 → ~22,661): AED 10000 + 무더위쉼터 4107 + 시설물 3606 + 지진옥외대피소 1580 + 자전거 편의시설 3368

**예상 총합**: ~28,949 row 신규 INSERT (source 다중)

## 2. 영향 범위

### 2.1 신규 파일
- `backend/scripts/etl/load_g2_public_cultural.py` (source registry 패턴, 단일 loader)

### 2.2 DB 영향
- places 371,418 → **~400K** (순 증가)
- source 신규: `seoul_park_{district}` (25) + `seoul_library_{district}` (25) + `seoul_culture_venue` + `seoul_theater_inheoga` + `seoul_cinema_inheoga` + `seoul_aed` + `seoul_cooling_shelter` + `seoul_facility` + `seoul_earthquake_shelter` + `seoul_bicycle_facility`
- DDL 0 (스키마 불변)

### 2.3 TM EPSG:5186 변환
- PostGIS 내부 `ST_Transform(ST_SetSRID(ST_MakePoint(x,y), 5186), 4326)` 사용
- 공연장/영화상영관 2 CSV만 해당

### 2.4 skip 대상 (본 plan 외)
- 교육 강좌정보 / 교육 공공서비스예약 2건: cp949 decode 실패 (errors=replace만 가능, 데이터 품질 저하 + events 성격) → issues.md 기록
- 둘레길 21건: course 데이터, places 아님
- 서울도서관 일정 / 시설대관: events 테이블 후보
- 당구장/청소년게임/영화상영업: 체육·유원지 (소상공인 중복 + scope 폭발 방지)
- 관광지 4 CSV: B/C 안, 본 plan 제외

### 2.5 특수 처리
- **공연장 CSV 첫 row 더미**: row 0 = 'mng_no'/'bplc_nm'/'xcrdnt'/'ycrdnt' 스킵 (값 기준 감지)
- **폐업 필터**: 인허가 CSV (공연장/영화상영관)는 `영업상태명 == '영업/정상'`만 적재
- **district 추출**: CSV별 전용 필드(시군구명/자치구) 우선, 없으면 도로명주소 regex `([가-힣]+구)`

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화: place_id VARCHAR(36), CSV별 고유 ID (관리번호/contentid/시설번호 등) + source prefix
- [x] #3 append-only: places 아님, INSERT 합법
- [x] #5 비정규화 4건: district는 기존 허용 범위
- [x] #8 asyncpg $1..$N 파라미터 바인딩, f-string SQL 없음
- [x] #9 Optional[...] 사용
- [x] #18 Phase 라벨: LocalBiz ETL
- [x] #19 기획 우선: validate_category(strict=False) 경유, v0.2 카테고리 enum

## 4. 작업 순서

1. source registry 설계 (13 CSV 스키마 매핑)
2. loader 작성 (WGS84 / TM 분기, district 추출 helper, 더미 row 필터)
3. `--dry-run` 실행 → source별 적재/skip 수치 확인
4. 실적재
5. Zero-Trust postgres MCP 검증 (source별 count, category distribution, null_geom=0)
6. validate.sh 6/6
7. issues.md: 교육 2 CSV decode 에러 기록

## 5. 검증 계획

### 5.1 loader 내부 assertion
- source별 inserted count 로그
- null_geom = 0
- distinct category ≥ 기존 10 (카테고리 추가됨)

### 5.2 Zero-Trust
- `SELECT source, COUNT(*) FROM places GROUP BY source`
- `SELECT category, COUNT(*) FROM places GROUP BY category`
- 각 카테고리 sample row 교차 확인

## 6. 리뷰 (E 모드)

Metis/Momus skip. 근거:
- 사용자 "권장대로 다 처리해" = A 안 승인
- DDL 0, 스키마 불변
- 중복 리스크 0 (신규 카테고리만)
- 불변식 위반 가능성 0

## 7. 완료 결과

- **places**: 371,418 → **398,166** (+26,748)
- **카테고리**: 10 → **14** (신규 공원 1,777 / 도서관 540 / 문화시설 1,776 / 공공시설 22,655)
- **source 10종**: seoul_park / seoul_library / seoul_culture_venue / seoul_theater_inheoga / seoul_cinema_inheoga / seoul_aed / seoul_cooling_shelter / seoul_facility / seoul_earthquake_shelter / seoul_bicycle_facility
- **소요**: dry-run 0.8초 + 실적재 3.4초 + TM 재적재 0.3초
- **해결된 이슈**:
  - macOS APFS NFD 파일명 vs NFC glob 패턴 (park/library 50 CSV 매칭 0 → 2,317)
  - phone VARCHAR(20) 초과 값 truncate
  - TM EPSG:5186 오가정 → 5174 (Korea 2000 Bessel 중부원점) 수정, 100km 오차 해소
- **validate.sh**: 6/6 ✅
