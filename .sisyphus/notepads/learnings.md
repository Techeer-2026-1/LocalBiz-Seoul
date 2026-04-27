# learnings.md — 발견된 패턴·성공적 접근법

> **Append-only**. 기존 엔트리 수정·삭제 금지. 양식은 `.sisyphus/notepads/README.md` 참조.
>
> 주력 기록 워커: sisyphus-junior (단순 패턴) / hephaestus (다중 파일·아키텍처 패턴) / fe-visual (FE 팁).
> 1회 append ≤ 50줄. 파일 전체 200줄 초과 시 Phase 6 KAIROS 압축.

---

<!-- 첫 엔트리는 plan #6 §E spawn 테스트 결과 또는 plan #7 이후 실전 사용에서 추가됨 -->

## [2026-04-12] ETL dry-run 패턴 — plan #7 g4 step 10

- `python -m scripts.etl.load_administrative_districts --dry-run` 1.7초 만에 완료.
- 행정구역 GeoJSON(HangJeongDong_ver20260201.geojson): 전국 3558 features 중 서울 427개 정확히 필터링됨.
- code 8자리(예: `11110530`) → 19 불변식 §1 자연키 패턴 준수.
- dry-run 분기가 asyncpg import 자체를 건드리지 않아 DB 자격증명 없이도 실행 가능. 개발 환경에서 안전한 사전 검증 가능.
- geom 필드는 GeoJSON MultiPolygon JSON string으로 변환되어 출력됨 (DB insert 시 ST_GeomFromGeoJSON 필요).

## [2026-04-12] 검증 게이트 첫 실전 — plan #7 전체

**맥락**: `feedback_etl_validation_gate.md` (2026-04-12 수립) 정책 첫 준수 사례. plan #7 전 과정.

- 외부 수급 데이터는 DB write 전 반드시 프로파일링 + 사용자 승인 — 본 plan 작성 **이전**에 GeoJSON 33MB 수급 + SOURCE.md 작성 + 415/424 매핑 검증 + 9 mismatch 수치화 선행. plan.md에는 이미 확정된 수치만 진입. 결과: step 15 실 insert 시점에 **놀라움 0건**.
- **"샘플 코드 매핑 검증이 스키마 검증보다 선행되어야 한다"** — 스키마는 깔끔하게 통과해도 행정동 코드 버전 불일치 같은 데이터 **내용** 레벨 문제는 스키마 검사로 잡히지 않는다. 매핑 키 교차 검증(415/424)이 진짜 게이트였음.
- ETL 스크립트를 항상 쌍(dry-run + real)으로 설계: `--dry-run` 분기는 첫 100행만 파싱 + DB write 생략. dry-run 0.4초, real 36초. 시간 차가 커서 실험 비용 거의 0. plan #6 인프라 패턴 그대로 재사용 가능.
- `SKIP_COUNT=<n>` stdout 고정 포맷 (Momus Mo5a) — grep 안정성 + 재현 검증성. 로깅은 가변 포맷이지만 검증 포인트만 `sys.stdout.write(f"SKIP_COUNT={n}\n")` 로 분리. 본 plan에서 처음 적용, 검증 가치 확인.

## [2026-04-12] 진정 워커 + 메인 Claude 분업의 실전 패턴 — plan #7

**맥락**: plan #6 구축한 워커 인프라 첫 LocalBiz 투입. hephaestus 2회 spawn(SQL + 2 ETL 스크립트), junior 1회 spawn 시도.

- **hephaestus는 "파일 작성"에 탁월** — DDL SQL 100줄, admin ETL 227줄, pop ETL 298줄. 3건 모두 한 번에 통과. hyper-focused prompt(구조·상수·형제파일 규약까지 명시)가 통과율의 핵심.
- **junior spawn 가성비** — 본 plan에서 junior에게 ETL dry-run 실행+결과 보고를 맡겼으나 세부 수치를 생략하고 "PASS"만 리턴. 메인 Claude가 직접 Bash 실행 시 수치 + 샘플 + 시간까지 모두 확보. 결론: **단순 명령 실행·요약**은 메인 Claude 직행이 빠름. junior의 진짜 가치는 "hyper-focused 구현 + 메인 컨텍스트 보호" 조합에서 나옴.
- **동일 plan 내 형제 파일 일관성 요구** — hephaestus prompt에 "형제 파일(load_administrative_districts.py) 패턴 따르라" 명시 → load_env 바이트 동일, docstring 구조 동일, 로깅 규약 동일. 후속 리뷰·유지보수 비용 감소.
- **Oracle spawn은 MCP 진단이 핵심 가치** — 본 plan에서 메인 Claude가 postgres MCP를 직접 써서 9 mismatch 수치까지 뽑아내자 oracle spawn의 추가 가치가 희석됨 (사용자 velocity directive + 토큰 비용). 결론: oracle은 **메인이 접근 불가한 tool**(예: opensearch MCP 미노출 시) 또는 **구조적 진단 필요(불변식 전수 스캔)** 시 최대 가치.

## [2026-04-12] plan #13 δ fresh load — TRUNCATE + CSV replace 단순 우월

**맥락**: plan #13 `etl-g1-shopping-commerce`. 사용자 δ 결정(기존 531K DROP + 소상공인 340K fresh load). 48.6초 완료.

- **"복잡한 fuzzy match 유혹을 꺾고 TRUNCATE 선택하면 코드 50%·시간 90% 절약"** — γ(상호명+주소 fuzzy dedup) 안을 제안했으나 사용자는 δ(단순 TRUNCATE) 선택. 결과: loader 330줄 단일 파일, 매칭 엔진 0, 외부 dependency 0, 48.6초 종결. fuzzy match이었다면 매칭률·검증·false-positive 수기 확인으로 1일 소요 예상. 데이터 정직성 원칙과 동일선 — 원본 스냅샷 신뢰 > 파생 조작.
- **dry-run 실측값과 실 적재값 100% 일치** — transform_row 함수를 공유하면 dry-run 수치(371,418/163,560/10 카테고리)가 실 적재와 같아야 한다. plan §2.4 예측 표 → dry-run → 실 적재 3단계 모두 동일 → 검증 가치 보장. 회귀 버그 탐지 2차 방어선.
- **transform_row 내부에서 카테고리 매핑 + validate_category 직결** — 양쪽에서 따로 돌리지 않고 transform 1회 호출로 enum 강제 + skip 판정. validate_category(strict=False)로 sub_category 원문 pass-through → 소상공인 중분류명과 v0.2 sub_category 리스트 불일치 이슈 봉합.
- **place_analysis FK CASCADE pre-check** — TRUNCATE 전 `SELECT COUNT(*) FROM place_analysis WHERE ...` 으로 확인 (0) → RESTART IDENTITY CASCADE 안전. FK 있는 테이블 TRUNCATE는 반드시 pre-check 필수, 이 패턴을 앞으로 모든 DELETE plan에 적용.
- **CP949 vs UTF-8 소스 혼재** — 소상공인 CSV는 UTF-8 native (서울시 인허가 CP949와 다름). 인코딩은 각 소스별로 프로파일링 단계에서 `file` 또는 실측 decode 시도 필수. 가정 금지.

## [2026-04-12] plan #14 G2 — macOS NFD / EPSG / source registry 3 대학습

**맥락**: plan #14 `etl-g2-public-cultural`. 73 CSV 중 13 source 적재.

- **macOS APFS NFD normalization**: 폴더·파일명이 한글을 NFD(분해형)로 저장. Python `glob.glob`에 NFC 패턴 전달 시 0 match. `unicodedata.normalize("NFD", pattern)` 병행 + `os.path.realpath + NFC` dedup 필수. plan #14 park/library 50 CSV가 이 때문에 dry-run 1차에서 0 로드 → 증상 발견 → 수정. **재발방지**: macOS 환경에서 한글 경로 glob 시 dual NFC/NFD 시도 기본 적용.
- **EPSG 경험적 검증의 가치**: 서울시 인허가 CSV의 `좌표정보(X)/(Y)`는 관례상 EPSG:5186(GRS80)이라 가정했으나 실측은 5174(Bessel). 100km 오차로 공연장 741 row 모두 청주 근처에 적재됨. 샘플 3건을 4 EPSG 병렬 변환해 bbox 맞는 것 선택 — 5초 진단으로 DELETE + 재적재 비용 회피 가능했음. **패턴화**: TM 좌표 source는 "진짜 적재 전 EPSG 3-4종 비교" 게이트 추가.
- **source registry 단일 loader의 유연성**: 13 CSV 각기 다른 스키마·인코딩·좌표계를 spec dict 1줄(glob/encoding/coord/transform) + transform 함수 1개(평균 30줄)로 처리. 공통 helper(`extract_district`, `sanity_wgs84/tm`, `clip_phone`, `make_place_id`) 공유로 중복 코드 0. G3 loader는 G2 loader 템플릿 직접 복사 + 수정으로 작성 시간 50% 절감.

## [2026-04-12] plan #15 G3 — 필드명 신뢰 금지 + 주소 parse-first 원칙

**맥락**: plan #15 `etl-g3-health-daily`. 19 source, 47K row. dry-run 1차에서 5 source 이상 오동작.

- **"시군구명 필드 존재 ≠ 값 채워짐"**: 거주자우선주차·안심택배함·일부 공영주차장 CSV에 시군구/자치구 컬럼이 존재해도 빈 row 과반. `field != ''` 체크 후 반드시 주소 regex fallback. plan #15 resident_parking이 58 → 10,397 (180배)로 수정 효과 실증. **원칙**: "CSV 필드 우선 + 주소 regex fallback + 최종 실패 시 skip" 3단계.
- **dry-run이 실패 아닌 '이상 신호'를 내도 멈추지 말고 재검증**: dry-run 1차 hospital_loc 0 insert, safe_delivery_box 0 insert — "0은 곧 버그"인데 그냥 넘기기 쉬운 수치. source별 expected range를 plan.md §2.4에 미리 써두면 dry-run 결과와 자동 비교 가능. **체크리스트**: loader 후 dry-run 결과를 plan 예측 표에 대입해 편차 > 30% 항목은 무조건 debug.
- **"폐업이 정상"인 source와 '코드 dup이 정상'인 source 구분**: 약국 인허가 74% 폐업 (회전율 높음, 정상), 공영주차장 87 코드에 45× 중복 (요금/시간대별 row 존재, 정상). dup·skip 높다고 무작정 알람 아님. source별 특성을 이해하고 decision 기록.
- **인허가 전체 TM 5174 표준 확정**: 약국/동물병원/병원/체력단련/무도장/썰매장/요트장/수영장/공연장/영화상영관 10 source 모두 `좌표정보(X)/(Y)` → EPSG:5174 검증 공유. 서울시 인허가 CSV 표준 좌표계로 정책화.
