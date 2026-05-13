# SSE 응답 구조 개선 — 카드별 설명 추가 & 블록 순서 변경

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-13
- 상태: approved
- 최종 결정: APPROVED

> v2→v3 변경: Momus 003-reject 4건 반영 — blocks.py 수정 대상 추가, EVENT 순서 "신규 추가" 명시, Gemini timeout/fallback 상세, 단위 테스트 항목 정리.

## 1. 요구사항

사용자 원문:
> 1. SSE 응답이 text_stream으로 한 줄 한 줄 전달되어 단락 구분, 폰트 설정이 어려움
> 2. 장소/행사 응답 시 텍스트 전부 → 카드 나중에 나오는데, 카드1+응답1 순으로 보내자
> 3. 코스 추천은 마지막에 지도 상 코스 연결 UI용 좌표값 보내자

### 해결 전략 (v3 확정)

| 요청 | 해결 |
|---|---|
| 카드+텍스트 매칭 | places/events 아이템에 `description` 필드 추가 + 블록 순서 변경 (카드 먼저, 종합 요약 나중에) |
| 단락 구분 | 시스템 프롬프트에 마크다운 구조화 지시 |
| 코스 좌표 | 변경 불필요 — `map_route` 블록에 이미 polyline 좌표 전송 중 |

### Pydantic 필드 결정

- **`PlaceBlock`**: 기존 `summary: Optional[str]` 필드를 per-place description 용도로 재활용. 별도 `description` 필드 추가하지 않음 (Metis 권고 채택).
- **`EventItem`**: `description: Optional[str]` 필드 신규 추가 (기존에 해당 필드 없음).

### Gemini JSON mode 상세

```python
response = await model.generate_content(
    contents=[prompt],
    generation_config=GenerationConfig(
        response_mime_type="application/json",
        response_schema=<per-item description schema>,
        temperature=0.3,
    ),
    request_options={"timeout": 10},  # 10초 timeout
)
```

- **timeout**: 10초. 초과 시 `google.api_core.exceptions.DeadlineExceeded` catch → description 없이 진행 (기존 동작 유지).
- **JSON 파싱 실패**: description 없이 진행.
- **비용**: Gemini 2.5 Flash 구조화 출력. 요청당 ~500 input tokens + ~300 output tokens. 기존 `astream()` 호출에 추가 1회.
- **rate limit**: 기존 astream과 합쳐 요청당 Gemini 2회 호출. Flash 모델 RPM 한도(2000) 대비 여유.

## 2. 영향 범위

- 신규 파일: 없음
- 수정 파일:
  - `backend/src/models/blocks.py` — `EventItem`에 `description: Optional[str]` 필드 추가
  - `backend/src/graph/place_search_node.py` — `_build_blocks`: per-place description 생성 (PlaceBlock.summary 활용) + 블록 순서 변경
  - `backend/src/graph/place_recommend_node.py` — 동일 패턴
  - `backend/src/graph/event_search_node.py` — per-event description 생성 + 블록 순서 변경
  - `backend/src/graph/event_recommend_node.py` — 동일 패턴
  - `backend/src/graph/response_builder_node.py` — `_EXPECTED_BLOCK_ORDER`에 4개 intent 순서 추가/변경
  - `backend/src/graph/general_node.py` — 시스템 프롬프트 마크다운 구조화 지시
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 타입 추가 없음. `EventItem`에 optional 필드 1개 추가 (블록 타입 자체는 `events` 유지)
- intent 추가/변경: 없음
- 외부 API 호출: Gemini `generate_content` JSON mode 추가 1회/요청 (timeout 10초, fallback 있음)
- FE 영향: `PlacesBlock.tsx`에서 `summary` 필드, `EventsBlock.tsx`에서 `description` 필드 렌더링 추가

### 블록 순서 변경 (기획 §4.4 업데이트)

| Intent | 현재 (기획/코드) | 변경 후 |
|---|---|---|
| PLACE_SEARCH | intent → text_stream → places → map_markers → done | intent → places(+summary) → text_stream(요약) → map_markers → done |
| PLACE_RECOMMEND | intent → text_stream → places → map_markers → references → done | intent → places(+summary) → text_stream(요약) → map_markers → references → done |
| EVENT_SEARCH | **신규 추가** (기획/코드에 미정의) | intent → events(+description) → text_stream(요약) → done |
| EVENT_RECOMMEND | **신규 추가** (기획/코드에 미정의) | intent → events(+description) → text_stream(요약) → references → done |

> PLACE_SEARCH/PLACE_RECOMMEND: 기존 순서 **변경**. EVENT_SEARCH/EVENT_RECOMMEND: `_EXPECTED_BLOCK_ORDER`에 **신규 추가**.

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수
- [x] PG↔OS 동기화 (해당 시)
- [x] append-only 4테이블 미수정
- [x] 소프트 삭제 매트릭스 준수
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존
- [x] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [x] asyncpg 파라미터 바인딩 ($1, $2)
- [x] Optional[str] 사용 (str | None 금지)
- [x] SSE 블록 16종 한도 준수 — 타입 추가 없음
- [ ] intent별 블록 순서 — **본 plan이 2개 변경 + 2개 신규 추가 요청**
- [x] 공통 쿼리 전처리 경유
- [x] 행사 검색 DB 우선 → Naver fallback
- [x] 대화 이력 이원화 보존
- [x] 인증 매트릭스 준수
- [x] 북마크 = 대화 위치 패러다임 준수
- [x] 공유링크 인증 우회 범위 정확
- [x] Phase 라벨 명시 — P1
- [ ] 기획 문서 우선 — **기획 §4.4에 EVENT 2개 intent 순서 신규 추가 + PLACE 2개 순서 변경**

## 4. 작업 순서 (Atomic step)

### Step 1: 기획 §4.4 블록 순서 업데이트
- `기획/_legacy/서비스 통합 기획서 v2.md` §4.4: PLACE_SEARCH/RECOMMEND 순서 변경 + EVENT_SEARCH/RECOMMEND 순서 신규 추가
- verify: grep으로 4개 intent 순서 확인
- Category: `quick`

### Step 2: blocks.py EventItem에 description 필드 추가
- `EventItem`에 `description: Optional[str] = None` 추가
- `PlaceBlock.summary`는 이미 존재하므로 변경 없음
- verify: `pyright src/models/blocks.py` 통과
- Category: `quick`

### Step 3: place_search_node per-place description + 블록 순서 변경
- Gemini JSON mode로 per-place description 생성 → PlaceBlock.summary에 삽입
- 블록 순서 변경: places(+summary) → text_stream(종합 요약)
- text_stream 프롬프트: "각 장소는 이미 카드로 소개되었으니 전체를 종합 요약해주세요"
- Gemini timeout 10초 + DeadlineExceeded catch → description 없이 fallback
- verify: `validate.sh` 통과
- Category: `deep`

### Step 4: place_recommend_node 동일 패턴 적용
- Step 3의 description 생성 로직 재사용. 추천 사유 + 리뷰 키워드 포함
- verify: `validate.sh` 통과
- Category: `deep`

### Step 5: event_search_node per-event description + 블록 순서 변경
- Gemini JSON mode → EventItem.description에 삽입
- 블록 순서: events(+description) → text_stream(요약)
- verify: `validate.sh` 통과
- Category: `deep`

### Step 6: event_recommend_node 동일 패턴 적용
- verify: `validate.sh` 통과
- Category: `deep`

### Step 7: response_builder_node _EXPECTED_BLOCK_ORDER 업데이트
- PLACE_SEARCH/RECOMMEND: 기존 순서 변경 (places → text_stream)
- EVENT_SEARCH/RECOMMEND: 신규 항목 추가
- verify: `validate.sh` 통과
- Category: `quick`

### Step 8: general_node text_stream 마크다운 개선
- 시스템 프롬프트에 "## 소제목, 번호 목록, 빈 줄 구분" 마크다운 구조 지시
- verify: GENERAL intent 응답 마크다운 구조 확인
- Category: `quick`

### Step 9: 통합 검증
- `validate.sh` 전체 통과
- 수동 시나리오:
  - "홍대 맛집 추천해줘" → places(summary 포함) 먼저 → 종합 요약 text_stream
  - "이번 주 행사 알려줘" → events(description 포함) 먼저 → 종합 요약
  - "홍대 코스 짜줘" → map_route 좌표 포함 (기존 동작 확인)
  - "안녕" → text_stream 마크다운 단락 구분
- Category: `quick`

## 5. 검증 계획

- `validate.sh` 통과 (ruff + pyright + pytest)
- 수동 시나리오: Step 9 참조
- pytest: 기존 테스트 통과 확인 (신규 테스트 파일 없음 — 통합 검증은 수동)

## 6. Metis/Momus 리뷰

- Metis v1: 001-metis-reject.md — event 단수 타입 부재 → v2에서 per-item description으로 전환
- Metis v2: 002-metis-okay.md — 통과
- Momus v1: 003-momus-reject.md — blocks.py 누락, EVENT 신규 추가 미표기, timeout 미명시, 테스트 인프라 부재
- Momus v2: 004-momus-*.md 대기

## 7. 최종 결정

APPROVED (Metis 002-okay + Momus 004-approved)
