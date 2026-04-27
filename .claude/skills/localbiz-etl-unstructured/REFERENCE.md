# localbiz-etl-unstructured — REFERENCE (L2)

리뷰·가격·이미지 캡션 등 비정형 텍스트를 LLM으로 구조화·임베딩·적재하는 ETL 패턴.

## 핵심 원칙

1. **임베딩 통일**: `gemini-embedding-001` 768d. **OpenAI 임베딩 절대 금지** (19 불변식 #7).
2. **embed_utils 공용**: 새 ETL이라도 `backend/scripts/embed_utils.py`의 `embed_texts(list[str]) -> list[list[float]]`만 사용. 직접 Gemini API 호출 금지.
3. **광고 필터**: Naver Blog 결과는 `iframe`/`광고`/`체험단`/`협찬` 키워드 자동 제거 후 LLM 투입.
4. **6 지표 일관성**: LLM 응답이 항상 `score_satisfaction/_accessibility/_cleanliness/_value/_atmosphere/_expertise` 6개 키를 갖도록 JSON mode + Pydantic 검증.
5. **TTL 7일**: place_analysis는 `ttl_expires_at = analyzed_at + 7 days`. 만료 후 재분석 트리거.
6. **--naver-only 모드**: google_place_id가 NULL인 장소(대부분)를 위한 fallback. 현재 PoC 17건은 이 모드로 검증됨.

## 파이프라인 카탈로그 (현재 적재 상태 + 서비스 기능)

| 파이프라인 | 스크립트 | 서비스 기능 (intent/feature) | 소스 → 저장 | 현재 |
|---|---|---|---|---|
| 리뷰 분석 | `batch_review_analysis.py` | REVIEW_COMPARE / ANALYSIS / PLACE_RECOMMEND 사유 표시 | Naver Blog → Gemini 채점(6지표) → place_analysis | 17건 |
| 리뷰 임베딩 | `load_place_reviews.py` | (위 3개 비정형 검색의 벡터 기반) | place_analysis 요약+키워드 → 768d → OS place_reviews | 17 |
| **가격 수집** | **`collect_price_data.py`** | **COST_ESTIMATE ②단계 데이터 소스 (Phase 2)** | Naver Blog `"{name} 메뉴 가격"` → 3중 필터 → 정규식 `숫자+원` → places.raw_data.blog_price_data (min/max/avg) | 12건 |
| 장소 임베딩 | `load_places_vector.py` | PLACE_SEARCH / PLACE_RECOMMEND 의미 검색 | places page_content → 768d → OS places_vector | 100 |
| 행사 임베딩 | `load_events_vector.py` | EVENT_SEARCH 비정형 검색 | events title+summary → 768d → OS events_vector | 1,146 |
| **이미지 캡셔닝** | **`load_image_captions.py`** | **IMAGE_SEARCH 간판 없음 경로 (Phase 2)** | Google Photos → Claude Haiku 캡션(분위기/외관 3문장) → 768d → OS places_vector image_caption + image_embedding | 코드 완성, 미실행 (~$3/1K) |

이 모든 스크립트는 현재 `backend/_legacy_scripts/`에 있음 — Phase 2 이후 새 `backend/scripts/`로 재작성 예정.

## 런타임 도구와의 연계 (잊지 말 것)

비정형 ETL은 **런타임 도구의 데이터 소스를 사전 빌드**하는 것이 본질이다. 새 ETL을 만들 때는 항상 "어떤 런타임 도구가 이 데이터를 읽는가"를 명시하고, 도구 측 코드·스키마와 일치시킬 것.

### COST_ESTIMATE — 3단계 가격 추정 (Phase 2 런타임 도구)

기획서 §3.2 / 기능 명세서 5.2.1:

- **① price_level + LLM 추정** — Google Places API의 `price_level` 필드(0~4)를 받아 LLM이 카테고리·지역 맥락 반영해 ~만원 단위 추정. 런타임.
- **② places.raw_data.blog_price_data 조회** — `collect_price_data.py`가 사전 적재한 min/max/avg 직접 사용. ETL 의존.
- **③ 런타임 Naver Blog fetch fallback** — 위 둘 다 데이터 부족 시 즉석 Naver Blog 호출. 식신 API는 미확보 확정.

→ 런타임 도구는 ②를 우선 시도하므로 `collect_price_data.py` 적재 커버리지가 결정적. 현재 12건뿐이라 음식점 카테고리 전체 적재가 P2 시작 전 선결.

### IMAGE_SEARCH — 두 경로 (Phase 2 런타임 도구)

기능 명세서 2.5.1 / 2.5.2:

- **A. 간판 있음 (OCR 경로)** — easyocr로 상호명 추출 → places DB 검색 → 체인점은 PostGIS `ST_Distance`로 가장 가까운 지점. **LLM 0회 호출**. ETL 불필요 (places만 있으면 됨).
- **B. 간판 없음 (Vision 경로)** — Gemini Vision 1회로 타입+분위기 키워드 추출 → `gemini-embedding-001` 768d → **OS places_vector image_caption + image_embedding 필드와 k-NN 유사도 검색**. ETL 의존: `load_image_captions.py`.

→ B 경로가 작동하려면 image_caption 인덱스 사전 적재가 필수. 현재 미실행, 비용 ~$3/1K. 대규모 실행 시 사용자 사전 승인.

### REVIEW_COMPARE / ANALYSIS / PLACE_RECOMMEND 사유 표시

세 기능 모두 **place_analysis (PG) + OS place_reviews 임베딩**에 의존:
- `batch_review_analysis.py` → place_analysis 6 지표 채점
- `load_place_reviews.py` → place_analysis 요약+키워드 → 벡터 인덱스
- `place_analysis.ttl_expires_at` 7일 만료 후 재분석 트리거 (현재 수동, Phase 5+에서 자동 cron)

## 절차 (새 비정형 ETL 추가)

1. `localbiz-plan` 호출 → 영향 범위·LLM 비용·예상 처리 시간 명시
2. **embed_utils 사용 검증**: 새 함수가 자체 임베딩 호출하지 않는지 확인
3. **JSON mode + Pydantic**: LLM 응답을 dict로 받지 말고 Pydantic 모델로 파싱
4. 표준 인자:
   ```
   --batch              # 배치 모드 (기본)
   --naver-only         # google_place_id NULL 대응
   --category 음식점    # 카테고리 필터
   --limit 20           # 처리 개수 한도
   --dry-run            # LLM 호출 없이 입력 데이터만 출력
   --resume-from PLACE_ID
   ```
5. **Idempotent**: 같은 place_id 재실행 시 UPSERT (analyzed_at만 갱신)
6. **OS 동기화**: PG INSERT 직후 즉시 OS bulk index. 비동기 큐 사용 시 dead-letter 처리

## 비용 추적

- Gemini 2.5 Flash: 거의 무료
- Claude Haiku (이미지 캡셔닝): ~$3/1K건. 대규모 실행 시 사전 승인 필수
- Naver Blog API: 일일 25,000건 한도. 분당 throttle

## 하지 말 것

- OpenAI 임베딩 사용 (어떤 형태로도)
- 768d 외 차원 사용
- embed_utils 우회한 직접 Gemini API 호출
- TTL 무시한 재분석 (비용 폭증)
- 광고/협찬 필터 생략

## 참고 파일
- `backend/_legacy_scripts/embed_utils.py` (참고)
- `backend/_legacy_scripts/batch_review_analysis.py` (참고, --naver-only 모드 정답 패턴)
- `~/.../memory/project_db_state_2026-04-10.md`
- `기획/ERD_테이블_컬럼_사전_v6.3.md` (ERD 컬럼 권위, v6.1 docx는 기획/_legacy/)
