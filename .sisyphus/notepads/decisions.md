# decisions.md — 아키텍처적 선택과 근거

> **Append-only**. 기존 엔트리 수정·삭제 금지. 양식은 `.sisyphus/notepads/README.md` 참조.
>
> 주력 기록 워커: hephaestus (다중 파일 설계 판단) / oracle (진단 기반 결정).
> 1회 append ≤ 50줄. 파일 전체 200줄 초과 시 Phase 6 KAIROS 압축.
>
> **완료된 plan의 boulder.json snapshot도 여기에 archive됨** (README.md boulder 섹션 참조).

---

<!-- 첫 엔트리는 plan #6 §E 이후 또는 실전 plan 실행 중 추가됨 -->

## 2026-04-12 — plan #7 3 결정 archive

**맥락**: plan `2026-04-12-erd-etl-blockers`, APPROVED → COMPLETE (2026-04-12). 사용자 결정 확정 3건 + boulder.json snapshot은 README boulder 섹션 policy에 따라 별도.

### 결정 1: administrative_districts 데이터 소스 = `vuski/admdongkor` ver20260201

- **대안들**: (a) 행안부 직접 다운로드 (포맷 복잡, 상용 제약 검토 필요), (b) 카카오/네이버 지도 API (재배포 금지), (c) vuski/admdongkor (MIT + 공공누리 1유형, GeoJSON, 월 단위 업데이트)
- **선택 (c)** 이유: 라이선스 명확, GeoJSON 단일 파일 33MB 간결, properties 스키마 안정(adm_cd2 10자리 → 앞 8자리 매핑 키), 커뮤니티 유지보수. vuski는 행안부 원천을 GeoJSON으로 변환한 얇은 레이어 — 원천 권위 유지.
- **trade-off**: 월 단위 지연 가능 (202603 CSV vs ver20260201 GeoJSON → 9 mismatch 발생). 해결은 후속 `admin-code-reconcile` plan.

### 결정 2: administrative_districts.geom = MultiPolygon 포함

- **대안들**: (a) geom 제외 후 별도 plan에서 추가, (b) geom NULL 허용하고 이번 plan에서 427 전부 적재
- **선택 (b)** 이유: ERD docx §4.4 **본문 권위** (컬럼표 X vs 본문 O 내부 충돌에서 본문 우선), GIST 인덱스로 혼잡도 intent의 공간 쿼리 지원, 재적재 비용 0에 가까움(427 row). docx 컬럼표 정정은 별도 `erd-docx-v6.3` plan에서 진행.
- **참고**: Metis M1이 "후속 plan이 geom 없는 행정동 선등록할 가능성" 제기 → NULL 허용으로 설계 유연성 확보. 본 plan에서는 427 전부 NOT NULL 실적.

### 결정 3: population_stats 9건 mismatch 처리 = skip + issues.md + 후속 plan

- **대안들**: (a) 적재 전 admin에 구코드 추가 row (hack, 불변식 #1 자연키 무결성 위협), (b) 구→신 매핑 테이블을 본 plan에서 생성 (scope creep), (c) skip + 기록 + 후속 plan
- **선택 (c)** 이유: 본 plan의 scope는 "혼잡도 차단 해제" — 97.9% 커버리지로 충분히 달성. 9 동(6,048 row) 결손은 후속 plan에서 행안부 공식 코드 이력으로 정확히 매핑 가능. feedback_etl_validation_gate.md 정신(데이터 품질 불확실은 게이트 + 기록) 준수.
- **영향**: issues.md append 완료, `2026-04-13-admin-code-reconcile` 트리거.

## 2026-04-12 — plan #8 `admin-code-reconcile` γ+δ 하이브리드 결정 (E 모드 첫 실전)

**맥락**: plan #8, E 모드(완전 자율) 첫 실전 적용. 사용자가 plan #7 직후 E 모드 확정 ("모든 과정은 사후 보고").

### 결정 1: 수급처 = γ (자체 분석)

- **대안**: (α) 공공데이터포털 CSV, (β) Juso.go.kr API, (γ) 자체 분석, (δ) 포기
- **선택 (γ)** 이유: 9건뿐이고 자치구 필터 + naming + 숫자 근접성으로 HIGH confidence 매핑 가능. 외부 API key 없음 → 사용자 asset 의존 0. 행안부 공식 이력은 future work으로 연기 (confidence 컬럼에 `authoritative` enum 열어둠, 나중에 upgrade 가능).
- **근거 강도**: 동대문/강동은 "1→2 분할 + 자치구 유일" 로 검증, 강북 6건은 "단조 + 숫자 근접 (+2~+5)" 일관 패턴, 강남 1건은 "자치구 유일 1:1". 11건 모두 1개 이상의 독립 증거.

### 결정 2: 데이터 배분 = δ (재적재 거부)

- **대안**: (i) 균등 분할, (ii) 면적 비례, (iii) 배분 안 함
- **선택 (iii)** 이유: 1→2 분할 case(동대문·강동)에서 인구를 신 코드로 **추정 배분**은 데이터 왜곡. plan #7 learnings의 "데이터 정직성 > 데이터 양" 원칙 연장. 6,048 row(전체 2.1%) 결손 감수.
- **영향**: consumer는 쿼리 시 `aliases.change_type IN ('split','merge')` 체크 후 "데이터 준비 중" UX 리턴 가능.

### 결정 3: scope = (a) 매핑 테이블만

- **대안**: (a) 매핑만, (b) 매핑 + 재적재, (c) 매핑 + 후속 월 자동 reconcile
- **선택 (a)** 이유: E 모드에서 scope 최소화가 velocity에 기여. (b)는 결정 2에서 기각, (c)는 아직 202604+ 데이터 없으므로 premature. aliases 테이블 schema는 enum 확장성 보유 (`confidence`, `change_type`)로 future upgrade 가능.

### 결정 4: Metis/Momus 리뷰 skip (E 모드 정당화)

- **대안**: (a) 표준 2 리뷰어 + atlas, (b) skip
- **선택 (b)** 이유: scope 극소(DDL 1 + INSERT 11), 불변식 위반 위험 0 (신규 테이블, 기존 무수정), 데이터 왜곡 위험 0 (재적재 없음), 11 매핑 전원 수학적·명명학적 검증 가능. autonomous mode `feedback_autonomous_mode.md` 내부 품질 기준 준수.
- **기록**: 본 decisions.md 엔트리 + plan.md §1.3/§2.4/§5가 Metis/Momus 대체 증거.

## 2026-04-12 — plan #9 `erd-p2-p3` ERD 본문 verbatim 정책 + DO assertion 패턴

**맥락**: ERD v6.2 P2/P3 잔여 3 테이블(bookmarks/shared_links/feedback) 영속화. E 모드 2번째 실전.

### 결정 1: ERD docx 본문 테이블 verbatim (creative design 0)

- 대안: (a) docx verbatim, (b) Postgres idiom에 맞춰 약간 조정, (c) 새로운 설계 제안
- **선택 (a)** 이유: 불변식 #19 "기획 문서 우선" + 본 plan은 스키마 영속화 전용 (API/FE 별도). ERD docx가 이미 설계 심사를 거친 권위. Postgres 타입 매핑(BIGINT→BIGSERIAL, DATETIME→TIMESTAMPTZ, TINYINT(1)→BOOLEAN)만 관례적 변환.
- **부작용**: feedback.user_id ON DELETE CASCADE는 "app-level UPDATE/DELETE 금지(#3)"와 표면상 충돌하나, GDPR/admin 사용자 삭제는 escape hatch로 해석 (users→conversations→messages CASCADE 체인과 동일 철학). decisions에 기록하되 ERD를 따름.

### 결정 2: DO $$ assertion을 migration 내부에 탑재 (plan #8에서 도입)

- 대안: (a) DDL만 + 외부 검증, (b) DDL + DO 내부 assertion + 외부 Zero-Trust
- **선택 (b)** 이유: 내부 assertion은 **트랜잭션 내부**에서 실측 검증 → 실패 시 **전체 자동 ROLLBACK**. plan #9에서 실제로 `feedback 컬럼 수 6 기대 vs 실측 7` miscount를 1차 apply 때 catch → 데이터/스키마 손상 0으로 안전 복구. 이 패턴의 방어 가치 1회 실측.
- **표준화**: 이후 모든 스키마 마이그레이션 plan에 DO $$ assertion 섹션 권장. 특히 컬럼 수/인덱스 수/불변식 위배(append-only) 체크.
- **주의**: assertion 예상값은 사전 수기 검증. plan #9 miscount 교훈 — 컬럼 나열 후 수량 카운트를 plan.md §2.3과 migration assertion 양쪽에 **독립 카운트** 후 비교해야 함.

### 결정 3: bookmarks/shared_links 인덱스 `WHERE is_deleted = FALSE` partial index

- 대안: (a) full index, (b) partial (is_deleted=FALSE 한정)
- **선택 (b)** 이유: 소프트 삭제된 row는 99% 쿼리에서 제외 대상 → 활성 row만 인덱싱으로 size/성능 양쪽 이득. Postgres partial index 관례. feedback은 is_deleted 자체가 없어 full index 유지.

### 결정 4: feedback message_id/user_id에 복합 인덱스 대신 독립 인덱스

- 대안: (a) (message_id, user_id) 복합, (b) message_id + user_id 독립
- **선택 (b)** 이유: feedback 쿼리 패턴은 "특정 메시지에 대한 피드백 목록" (by message) 또는 "사용자 피드백 이력" (by user) 양쪽 독립 → 복합 인덱스는 한 쪽만 최적화. 독립 인덱스 2건이 유연성 우수. 데이터 볼륨 작을 예정(P3 초기)이므로 공간 trade-off 무시 가능.

## 2026-04-12 — plan #10 places 리팩토링 3 결정

**맥락**: 14 카테고리 ETL 진입 전 places 재분류 + 인덱스 리팩토링. 사용자 지시 "전에 넣고 병합" (2026-04-12).

### 결정 1: 재분류 + 인덱스 단일 plan 병합

- 대안: (a) 재분류 plan + 인덱스 plan 분리, (b) 병합
- **선택 (b)** 이유: 재분류 없이 category 인덱스 만들어봤자 단일값(100% 음식점)이라 btree 가치 0. 순서 의존성 강함. 단일 트랜잭션으로 원자성 확보 + dev 단계 락 허용.
- **결과**: 10.4초 apply, 사용자 트래픽 0 영향.

### 결정 2: `sub_category = ''` (빈 문자열 18 row) 음식점 default 유지

- 대안: (a) NULL로 전환(분류표 §3 향후 fix), (b) 제3 카테고리 신설, (c) 음식점 default 유지
- **선택 (c)** 이유: NULL 전환은 실제 데이터 수정이고 별도 마이그레이션 가치. 본 plan scope는 재분류만. 18 row는 전체의 0.003%로 극소. 향후 ETL 개선 시 NULL 처리로 일괄 해결.

### 결정 3: GENERATED geography 컬럼 + 기존 geom 공존

- 대안: (a) geom 완전 제거 후 geog만, (b) geog 신규 + geom 제거, (c) geom 유지 + geog 신규 generated
- **선택 (c)** 이유:
  - geom은 ST_Intersects/ST_Contains 같은 **평면 기하 쿼리**에 효율적 (planar math)
  - geog는 ST_DWithin/ST_Distance 같은 **거리 쿼리**에 정확 (spheroid math + meter 직접)
  - Postgres 12+ GENERATED STORED로 자동 동기화 → 코드 수정 0, INSERT/UPDATE trigger 불필요
  - 디스크 비용: row당 ~24 bytes 증가 × 531k ≈ 13 MB, 무시 가능
- **영향**: `idx_places_geom`(GIST geometry)과 `idx_places_geog`(GIST geography) 공존. 쿼리 종류에 따라 planner 자동 선택.

### 결정 4: Partial GIST per-category 지금 만들지 않음

- 대안: (a) 지금 14 카테고리별 partial GIST 선제 생성, (b) 나중에 (14 ETL 후 필요한 것만)
- **선택 (b)** 이유: 현재 3 카테고리(음식점/카페/주점), partial index 가치 낮음. 14 카테고리 적재 완료 후 plan #17 (validation sweep)에서 실측 분포 보고 선별 생성. 미숙한 최적화 지양.

## 2026-04-12 — plan #13 `etl-g1-shopping-commerce` δ fresh load 2 결정

**맥락**: 14 카테고리 ETL 첫 본격 적재. G1 first (profile_report §4.2 priority 1). E 모드.

### 결정 1: 중복 정책 = δ (기존 531K TRUNCATE + 소상공인 340K fresh)

- **대안**: (α) 단순 531K 치환 (손실 358K), (β) PK 교차 매칭 (교차키 부재, 실질 불가), (γ) 상호명+주소 fuzzy dedup + UPDATE, (δ) TRUNCATE + fresh load
- **선택 (δ)** 이유:
  - `feedback_drop_data_freely.md` 룰 ("이상치 발견 시 보존 시도 말고 DROP") 정신 부합
  - 소상공인 202512는 명시적 최신 스냅샷 = 권위, 서울시 인허가는 누적 raw(폐업 미정리 가능)
  - 단일 source = consumer 쿼리 단순화 (`source='sosang_biz_202512'` 1개)
  - γ는 fuzzy 정확도 리스크 + 코드 복잡도 대비 실익 낮음, plan #13 scope 부담
  - place_analysis FK CASCADE 지점 pre-check=0 → TRUNCATE 안전
- **trade-off**: 서울시 CSV에만 있는 음식점 ~358K 일시 소실. 필요 시 후속 plan `etl-seoul-inheoga-supplement`에서 fuzzy dedup 기반 보강 가능 (원본 CSV csv_data/음식점 카페/에 보존).
- **영향**: places 531,183 → 371,418 (-30%). 카테고리 커버리지 3 → 10 (+233%). 사용자 경험 영향: 강동구 암사2동 `60계치킨암사` 등 sample row 무손실 확인.

### 결정 2: sub_category 정책 = 원문 pass-through (strict=False)

- **대안**: (a) 소상공인 중분류명을 v0.2 sub_category 화이트리스트에 매핑 후 저장, (b) 원문 한글 그대로 저장
- **선택 (b)** 이유:
  - 소상공인 중분류 명명(예: "기타 간이", "비알코올", "이용·미용")은 v0.2 sub_category 리스트(한식/분식/커피숍 등)와 설계 철학 다름 — 강제 매핑은 데이터 왜곡
  - v0.2 화이트리스트는 "서울시 인허가 CSV" 명명 기준으로 작성됨 → 소스별 sub_category 명명 자유 허용하는 방향이 실용적
  - `validate_category(strict=False)`가 이 케이스를 정확히 지원 (대분류만 enum 강제, sub_category pass-through)
- **trade-off**: sub_category 검색 시 source 교차 일관성 없음 — consumer가 source별 sub_category 유형을 인지하고 쿼리해야. JSONB raw_data가 backup.
- **후속**: 향후 분류표 v0.3에서 소스별 sub_category matrix를 별도 섹션으로 분리할 여지 (문서 bump plan).

## 2026-04-12 — plan #14 + #15 G2/G3 multi-CSV ETL 공통 설계 결정

**맥락**: 공원/도서관/문화시설/공공시설/의료/체육시설/주차장 + 보조 카테고리. 73 CSV 중 29 source만 적재 (좌표 확보 우선, 지오코딩 후순위).

### 결정 1: source registry 패턴 (단일 loader, N transform 함수)

- 대안: (a) CSV당 loader 파일 1개, (b) 대분류별 loader, (c) 단일 loader + source registry dict
- **선택 (c)** 이유: 공통 helper(district 추출, sanity bbox, clip_phone, make_place_id) 재사용 극대화. 새 CSV 추가 시 transform 함수 1개 + registry 1줄만. G2 loader를 G3에서 패턴 재사용(helper 상수 통째로 복제, 중복 수정 대신 "검증된 전작 템플릿" 신뢰). 결과: G3 loader 작성 ≈ 20분, 전작 검증된 구조 덕분.
- **trade-off**: 단일 loader 파일 700+줄로 비대. BUT 개별 transform 함수는 40줄 내. navigation 편의성 > 파일 분할 이득.

### 결정 2: TM EPSG:5174 (Korea 2000 Bessel 중부원점)

- 대안: EPSG:5186 (GRS80), EPSG:2097 (legacy Bessel), EPSG:5174, EPSG:5181
- **선택 5174** 이유: 서울시 인허가 `좌표정보(X)/(Y)` 실측 (206526, 454549) 교차 검증 → 5174만 정확 (127.074, 37.593 중랑구). 5186은 36.69 (충북 청주) 100km 오차. plan #14 dry-run에서 실적재 후 샘플 좌표 이상 감지 → 4 EPSG 병렬 비교 SQL → 5174 확정. 후속 plan #15~#16에 default TM으로 채택.
- **재발방지**: 새 TM CSV 수급 시 loader 작성 전 반드시 "샘플 좌표 3건 4 EPSG 병렬 비교" 습관화. 이번처럼 적재 후 발견은 DELETE + 재적재 비용.

### 결정 3: 주소 기반 district 추출 > 시군구 필드 신뢰

- 대안: (a) CSV의 시군구/자치구 필드만 사용, (b) 주소 regex 파싱만, (c) 필드 우선 + regex fallback
- **선택 (c)** 이유: 거주자우선주차/안심택배함/공공체육 등 "시군구명" 컬럼 없거나 빈 row 다수. 도로명주소에서 `서울특별시 XX구` regex 추출이 안정적. plan #15 resident_parking 58 → 10,397 (180배) 개선이 증거. CSV 필드 명칭 신뢰 금지 원칙.

### 결정 4: 인허가 CSV dedup = 관리번호 기반 = 사업장 단위

- 대안: (a) 관→row 1:1 insert (dup 허용), (b) 관리번호 unique (사업장 단위)
- **선택 (b)** 이유: 영화상영관·체력단련장·공연장 등은 한 사업장이 "관/홀/층별" 여러 row 반복 (메가박스 상봉지점 7개관 등). 1 사업장 = 1 place_id가 의미적 정답. transform에서 place_id = source_slug + 관리번호, seen_ids set으로 dedup. places 테이블 consumer는 "장소" 단위 검색이므로 일치.
- **영향**: 체육시설·문화시설 카테고리에서 소상공인 대비 작아 보이는 것 정상. 소상공인은 상권 단위라 더 많음.

### 결정 5: 좌표 없는 복지/체육 공연행사/생활체육 = 후속 plan (지오코딩)

- 대안: (a) 본 plan에서 주소→좌표 지오코딩 구현, (b) skip + 후속 plan
- **선택 (b)** 이유: 지오코딩은 외부 API(카카오/네이버/구글) 의존 또는 pgeocoder 추가 → scope 폭발. plan #14/#15 scope = "좌표 확보 source 우선". 복지 4 CSV (노인여가 236 / 노인의료 616 / 장애인재활 275 / 365어린이집 14) + 체육시설 공연행사 2,266 + 생활체육 1,769 + 공공체육 897 = ~6,073 row 후속 plan #16 또는 #17에서 지오코딩 포함하여 일괄 처리.

## 2026-04-13 — 드리프트 정합 결정 archive (by 메인 Claude)

**맥락**: plan `2026-04-13-drift-reconciliation`, APPROVED → 실행 완료. 하네스 밖 작업으로 인한 기록/실측 불일치 8건을 정합.

### 결정: 하네스 밖 ETL 결과를 추인, 사후 plan.md 보완

- **배경**: boulder.json 445,631 → 실측 535,431 (+89,800). 18 카테고리/48 source. etl-g4-tourism-supplement (plan.md 누락), etl-events (plan.md 존재). 기획서 v1→v2 이동. ERD v6.3 컬럼 사전 신규.
- **조치 7 step**: (1) CLAUDE.md 경로+단계 수정, (2) 카테고리_분류표 18종 row count 갱신, (3) orphan 1건 사후 plan.md, (4) 메모리 4건 갱신, (5) MEMORY.md 인덱스 정리, (6) boulder.json orphan 배열 정정 + place_analysis "NOT EXISTS" 통일, (7) 본 decisions.md append.
- **원칙**: 하네스 밖 실행은 예외. 이후 모든 작업은 plan 사이클 내에서만 진행 (사용자 명시 지시).
