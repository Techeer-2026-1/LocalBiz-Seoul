# issues.md — 함정·블로커·19 불변식 위반 의심

> **Append-only**. 기존 엔트리 수정·삭제 금지. 양식은 `.sisyphus/notepads/README.md` 참조.
>
> 주력 기록 워커: oracle (진단 결과) / 모든 워커 (발견 즉시 append).
> 1회 append ≤ 50줄. 파일 전체 200줄 초과 시 Phase 6 KAIROS 압축.

---

## 2026-04-11 — Claude Code subagent session-start 로드 제약 재확인 (by 메인 Claude)

**맥락**: plan #6 g5 §E step 15 sisyphus-junior 첫 spawn 시도 중

**내용**: `.claude/agents/{sisyphus-junior,hephaestus,oracle,fe-visual}.md` 4 파일을 g2(§B)에서 작성했으나, Agent tool `subagent_type: "sisyphus-junior"` 호출 시 "Agent type 'sisyphus-junior' not found. Available agents: ..., atlas, metis, momus" 에러 발생. 등록된 목록에 atlas/metis/momus는 있으나 신규 4종 없음.

**근거**: Agent tool 리턴 에러 원문 + plan #5 검증 2차 때 동일 원리 이미 확립됨 (`~/.claude/projects/-Users-ijeong-Desktop---------/memory/project_harness_phase_mapping.md` "🚨 결정적 검증 결과" 섹션).

**원인**: Claude Code CLI는 `.claude/agents/*.md`를 **session start 시점에만 로드**. 세션 중간에 추가된 agent .md 파일은 다음 세션 시작 시에야 등록됨. plan #5에서 이미 이 제약을 실측 확인한 바 있으며, atlas 진정 spawn 활성은 "plan #5 묶음 1-4 완료 후 Claude Code 재시작" 직후였음.

**영향**:
- plan #6 §E step 15-18 (4 워커 spawn 테스트) **일시 blocked** — Claude Code session restart 필요
- plan #6 §F Metis/Momus 리뷰는 기존 3 agent(atlas/metis/momus)만 쓰므로 재시작 없이도 진행 가능했음 (이미 완료됨)
- 재시작 후 step 15-18 4종 순차 재시도 → step 19 (verification.md 취합) → §F~§H 계속
- 재발방지: 미래 plan에서 신규 agent .md 작성 직후 즉시 사용자에게 "이번 세션에서 사용하려면 재시작 필요" 공지. plan #6, #5 양쪽에서 동일 패턴이므로 이는 **안정적 제약**으로 확정 (변동 없음).

**broadcast 대상**: 모든 agent 추가 plan (특히 plan #7 Phase 6 KAIROS가 추가 subagent 정의 시)

---

## 2026-04-12 — Oracle postgres MCP 미노출 (session-start tool 반영 제약) (by 메인 Claude)

**맥락**: plan #6 g5 §E step 17(a) positive 테스트 중

**내용**: oracle.md frontmatter `tools: Read, Glob, Grep`에 `mcp__postgres__query`가 누락되어 있어 session restart 직전 수동 추가(Edit)했으나, oracle 진정 spawn 시 실측 결과 tool 목록에 여전히 부재. Oracle이 "MCP unavailable" 명시 보고 + Read-only contract는 준수.

**근거**: oracle spawn agentId `aa688293dd4072773` 리턴 메시지 원문 — "사용 가능 tools 확인: Read, Glob, Grep only / `mcp__postgres__query` tool: **미제공**". 페르소나 문서와 런타임 tool 목록 일치 확인됨.

**원인**: Claude Code CLI는 `.claude/agents/*.md` 파일을 **session start 시점에만 파싱**하며, 이는 (a) agent 이름 등록뿐 아니라 (b) frontmatter `tools:` 목록까지 **함께 고정**함. 2026-04-11 issues 엔트리의 session-start 제약이 agent 이름에만 국한된 게 아니라 **tool 목록에도 적용**된다는 추가 제약 확인.

**영향**:
- plan #6 step 17(a) positive postgres MCP 접근 테스트는 **PARTIAL** 판정 — spawn/contract는 ✅, MCP 접근은 ❌
- 당장 차단은 없음 — hephaestus나 메인 Claude가 postgres MCP를 직접 쓸 수 있으며, Oracle은 Read 기반 진단만으로도 19 불변식 평가 가능
- 후속 해소 plan: `2026-04-14-hooks-reactivate` 또는 신규 소규모 plan `2026-04-15-oracle-mcp-wire`에서 다룸. 해소 절차: (1) oracle.md tools 편집 (이미 완료), (2) Claude Code 재시작, (3) oracle positive 재검증, (4) 본 엔트리 resolve
- **일반화된 교훈**: 신규 agent .md에 MCP tool을 부여하려면 **파일 생성과 동시에 frontmatter에 포함**시켜야 함. 사후 편집은 반드시 session restart 필요.

**재발방지**: `.claude/skills/localbiz-plan/REFERENCE.md` §8에 "신규 agent 정의 시 필요한 MCP tool을 frontmatter 초안부터 포함" 체크리스트 추가 고려 (후속 plan).

**broadcast 대상**: 모든 agent 추가 plan, 특히 postgres/opensearch/다른 MCP를 쓰는 워커 정의 plan

---

## 2026-04-12 — 행정동 코드 mismatch 9건 (population_stats 202603 vs admin_districts ver20260201) (by 메인 Claude)

**맥락**: plan #7 (`2026-04-12-erd-etl-blockers`) g5 step 15-16, population_stats 실 적재 + Zero-Trust 검증 중

**내용**: 서울시 생활인구 CSV(202603)가 사용하는 `행정동코드` 424개 중 9개가 `administrative_districts`(GeoJSON ver20260201 기준 427개)에 부재. CSV 전체 284,928행 중 이 9 코드에 해당하는 **정확히 6,048행 (9 × 24시간 × 28일)이 skip** 되었으며, SKIP_COUNT stdout 고정 포맷으로 재현 검증됨. 나머지 415 × 24 × 28 = 278,880행 정상 insert.

**9 CSV-only (구) 코드 ↔ admin-only (신) 코드 매핑 추정**:

| 자치구 | CSV (구, 미적재) | Admin (신, 적재됨) | 해석 |
|---|---|---|---|
| 동대문구 | 11230536 | 11230515 신설동, 11230533 용두동 | 구 1코드 → 신 2코드 분할 |
| 강북구 | 11305590, 11305600, 11305606, 11305610, 11305620, 11305630 (6) | 11305595 번1동, 11305603 번2동, 11305608 번3동, 11305615 수유1동, 11305625 수유2동, 11305635 수유3동 (6) | 번동·수유동 재구획 |
| 구로구 | — | 11530800 항동 (신설) | 신설동, CSV 미조사 |
| 강남구 | 11680740 | 11680675 개포3동 | 구 1 → 신 1 재코딩 |
| 강동구 | 11740520 | 11740525 상일1동, 11740526 상일2동 | 상일동 분할 |
| **계** | **9** | **12 신설** (합계 차이 = 분할 순증) | |

**근거**: postgres MCP 직접 조회 + CSV 전체 parsing 교차검증. 415 × 24 × 28 = **278,880** (실측 일치), 9 × 24 × 28 = **6,048** (SKIP_COUNT 일치), 415 + 9 = 424 (CSV distinct 일치). 수학 완전 봉합.

**원인**: 행안부가 2025년 하반기~2026년 초 동 분할/신설을 수행했으며, admin_districts의 GeoJSON(vuski/admdongkor ver20260201, 2026-02-01 기준)은 반영되었으나 서울시 생활인구 CSV(202603, 2026-02월 조사)는 아직 구 행정동 코드로 조사·배포.

**영향**:
- 9 동(구 코드 기준) × 28일 × 24시간 = 6,048 row의 생활인구 데이터 결손. 혼잡도 intent 답변 시 해당 동 쿼리는 "데이터 없음" 리턴 필요.
- FK orphan=0 유지 (skip 정책 덕분 — ON DELETE RESTRICT 안전)
- 차단 없음 — 415동은 정상 조회 가능, 나머지 12 신설/분할 동은 "조사 전" 안내

**후속 plan 트리거**: `2026-04-13-admin-code-reconcile` (예약됨)
- 행안부 공식 행정동 코드 변경 이력 CSV 수급
- 구↔신 매핑 테이블 생성
- CSV의 9 구코드 데이터 → admin의 신코드로 재매핑 후 population_stats 재적재 (주의: append-only이므로 재적재 = 중복 row, 주의 설계 필요)
- 또는 매핑 테이블만 두고 조회 시 구→신 fallback

**재발방지**: 외부 공공데이터 수급 시 "동일 시점 다른 기관 발행 데이터는 코드 버전 불일치 가능" 체크 항목을 `feedback_etl_validation_gate.md`에 이미 암시되어 있음. 본 plan에서 사전 프로파일링 단계에서 mismatch를 발견·승인한 것은 정책 작동 증거.

**broadcast 대상**: `admin-code-reconcile` plan 작성 시 본 엔트리 필독. 추가로 다른 공공데이터 ETL plan에서도 코드 버전 교차 확인 루틴 기본 적용.

**2026-04-12 RESOLVED (partial)** — plan #8 `2026-04-13-admin-code-reconcile` COMPLETE: `admin_code_aliases` 테이블 생성 + 11 매핑 row insert (9 구 코드 → 11 신 코드). confidence=high 11건 (자체 분석, authoritative 출처 0건). population_stats 6,048 row 재적재는 **하지 않음** (1→N 분할 시 인구 배분 추정 오염 거부). 혼잡도 쿼리 시 consumer가 `JOIN admin_code_aliases ON old_code`로 구→신 해석 가능. 11530800 항동(구로구, 완전 신설)은 old_code 없으므로 본 테이블 scope 외 — 필요 시 확장 plan.


## 2026-04-12 — 교육 2 CSV cp949 decode 실패 (by 메인 Claude)

**맥락**: plan #14 G2 프로파일링 중.

**내용**: `csv_data/교육 관련/서울도서관 강좌정보.csv` + `csv_data/교육 관련/서울시 교육 공공서비스예약 정보.csv` 두 파일이 **cp949/utf-8/utf-8-sig/utf-16 모두 decode 실패**. `cp949 errors='replace'`로만 열림 (치환 문자 포함). 데이터 품질 저하 + events 성격(강좌/예약) → plan #14 scope 제외.

**근거**: 프로파일러 try/except 4 인코딩 전수 실패. 서울도서관 강좌정보 7MB, 교육 공공서비스예약 5.3MB 크기.

**원인**: 혼합 인코딩 파일로 추정. 서울시 공공데이터 포털의 일부 CSV는 라인별로 cp949/utf-8 혼재 발생 사례 있음 (공공데이터 2024년 사례).

**영향**: 본 plan에서 교육 카테고리 보강 0건. 교육 카테고리는 소상공인 45,158로 이미 충분.

**재발방지**: 교육 폴더 3 CSV 중 1건(방과후아카데미 22)만 보강 가치. 강좌/예약은 events 테이블 성격이므로 후속 events ETL plan에서 다룸.

## 2026-04-12 — TM EPSG 5186 → 5174 정정 (by 메인 Claude)

**맥락**: plan #14 G2 실적재 직후 샘플 검증.

**내용**: 서울시 인허가 CSV의 `좌표정보(X)/(Y)` 는 당연히 **EPSG:5186(GRS80 중부원점)** 이라 가정했으나 실측 결과 **EPSG:5174(Korea 2000 Bessel 중부원점)**. 공연장 샘플 "나루아트센터 소공연장" 좌표 (127.069, 36.634) 충북 청주 근처 → 100km 남쪽 오차. 4 EPSG(5186/5174/2097/5181) 병렬 변환 후 5174만 중랑구 (127.074, 37.593) 정확.

**근거**: `SELECT ST_Transform(..., 5174, 4326)` MCP 쿼리 교차검증. plan #14 §2.3 "EPSG:5186" 가정은 오류.

**원인**: 서울시 열린데이터 인허가 CSV는 **Bessel 구 측지계** 유지. 공공데이터 포털 문서에 EPSG 명시 부재. "TM" 라벨만 있음.

**영향**: plan #14 1차 적재 후 741 row (공연장 448 + 영화상영관 293) DELETE + 재적재. 해결 시간 ~3분. plan #15 이후 모든 인허가 TM source에 **EPSG:5174 표준 적용** (약국/동물병원/병원/체력단련/무도장/썰매장/요트장/수영장/공연장/영화상영관 10 source).

**재발방지**: 새 TM source 수급 시 **샘플 좌표 3건 4 EPSG 병렬 비교** 사전 검증. loader `coord` spec 입력 전 게이트.

**broadcast**: 모든 서울시 인허가 CSV ETL plan (향후 관광지/축제/교통) — TM 5174 default.

**2026-04-12 RESOLVED** — plan #14/#15 모두 5174로 통일 완료. 공연장/영화상영관/약국/동물병원/병원/체력단련/무도장/썰매/요트/수영 10 source 좌표 정상 검증.

## 2026-04-12 — macOS APFS NFD 파일명 glob 0 매칭 (by 메인 Claude)

**맥락**: plan #14 G2 dry-run 1차.

**내용**: Python `glob.glob()`에 NFC(조합형) 한글 패턴 전달 시 NFD(분해형) 파일 시스템 엔트리와 매칭 실패. plan #14 park/library 50 CSV (지구별 공원정보/도서관 폴더)가 dry-run 1차에서 0 matched.

**근거**: `unicodedata.normalize('NFC', filename) != filename` 테스트에서 False 반환 확인. APFS는 NFD로 저장.

**원인**: macOS HFS+ 이후 파일명 Unicode 정규화를 NFD로 수행. Python 소스(NFC 기본) 패턴과 불일치.

**영향**: plan #14 park 0 + library 0 → dual glob(NFC + NFD) + realpath NFC dedup 적용 후 park 1,777 + library 540 정상 로드.

**재발방지**: macOS 환경 한글 경로 glob 시 다음 이디엄 기본 사용:
```python
pattern_nfc = str(path)
pattern_nfd = unicodedata.normalize("NFD", pattern_nfc)
raw = list(glob.glob(pattern_nfc)) + list(glob.glob(pattern_nfd))
# realpath + NFC 정규화 dedup
```
plan #15 loader에서 패턴 재사용됨.

**broadcast**: 모든 macOS 개발 환경 ETL/파일 탐색 plan.

**2026-04-12 RESOLVED** — load_g2_public_cultural.py + load_g3_health_daily.py 양쪽에 적용 완료.

---

## 2026-04-27 — 회원가입 PR(#4) 셋업 중 발견 함정 3건 (by 메인 Claude, 사후 기록)

**맥락**: plan `2026-04-27-auth-signup-foundation` 코드 작성 → 로컬 검증 진행 중 발견. 본 PR과 무관하지만 다른 백엔드 작업자(정조셉/강민서) 셋업 시 동일 에러 만날 가능성 높음.

### 함정 1 — `src/db/opensearch.py` 의 `AsyncOpenSearch` import 깨짐

- 증상: `python -m uvicorn src.main:app` 시작 시 `ImportError: cannot import name 'AsyncOpenSearch' from 'opensearchpy'`
- 원인: `requirements.txt`에 `opensearch-py==2.7.1` 핀. `AsyncOpenSearch`는 3.x에서 추가된 클래스. 2.7.1엔 동기 `OpenSearch`만 존재
- 영향: 모든 백엔드 작업자가 본인 노트북에서 서버 띄우려 할 때 즉시 실패. 본 PR은 pytest로 lifespan 우회하여 검증
- 해결책 (별도 plan 권장): `requirements.txt`를 `opensearch-py==3.x`로 업그레이드 또는 `src/db/opensearch.py`를 동기 `OpenSearch`로 변경

### 함정 2 — `.env.example`의 `APP_ENV` / `SECRET_KEY`가 `Settings` 클래스에 미정의

- 증상: `Settings()` 초기화 시 `pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted [APP_ENV, SECRET_KEY]`
- 원인: `src/config.py`의 `Settings` 클래스는 `extra='forbid'` 동작 (Pydantic v2 default). `.env.example`엔 두 키가 있는데 클래스엔 정의 안 됨
- 영향: `.env.example`을 그대로 `cp .env.example .env`로 복사한 모든 신규 작업자
- 해결책 (별도 plan 권장): (1) `Settings`에 `app_env: str = "development"`, `secret_key: Optional[str] = None` 추가 또는 (2) `model_config`에 `extra='ignore'` 추가 또는 (3) `.env.example`에서 두 줄 제거

### 함정 3 — 로컬 docker `init_db.sql` 의 users 테이블이 v1 (UUID) — migrations v2와 drift

- 증상: 회원가입 코드(BIGINT PK + auth_provider 등 v2 가정)와 로컬 DB(UUID PK + email/nickname만, v1) 불일치
- 원인: `init_db.sql`은 v1 스키마. 마이그레이션 `2026-04-10_erd_p1_foundation.sql`을 적용해야 v2가 됨. 그런데 마이그레이션을 그대로 실행하면 `user_favorites`/`reviews` FK 충돌로 ROLLBACK
- 영향: 모든 신규 작업자가 docker로 로컬 셋업 시 user 관련 코드 실행 불가
- 해결책 (사후 보강): 본 PR에서 일회성 SQL로 우회 (FK 제거 → 의존 컬럼 BIGINT 변환 → users DROP+CREATE → FK 재설정). 정식 해결은 `init_db.sql`을 v2 스키마로 갱신 또는 docker-compose 시 마이그레이션 자동 적용 정책 도입 (별도 plan 권장)

**broadcast 대상**: 회원가입 PR 직후 진행될 다음 PR (로그인, 닉네임 변경 등) 작업자 + 다른 백엔드 분 (정조셉/강민서)
