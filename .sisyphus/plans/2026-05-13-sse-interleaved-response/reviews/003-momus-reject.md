# Review: 003-momus-reject

## 검토자: momus
## 검토 일시: 2026-05-13
## 판정: reject

## 결함 4건

### 1. blocks.py 수정 대상 누락 (CRITICAL)
plan은 "기존 아이템에 optional description 필드 추가"라 하지만 `blocks.py`가 수정 파일 목록에 없음. Pydantic 모델(`PlaceBlock`, `EventItem`)에 필드 추가 없이 dict에만 넣으면 `serialize_block()` 시 strip됨. `PlaceBlock.summary`(이미 존재) 재활용 vs `description` 별도 추가 결정 필요.

### 2. EVENT_SEARCH/EVENT_RECOMMEND가 기획서·response_builder에 부재
plan의 "현재" 블록 순서 표에 이 2개 intent가 있지만, 실제로 `_EXPECTED_BLOCK_ORDER`에도 기획서 §4.4에도 없음. "변경"이 아니라 "추가"임을 명시해야 함.

### 3. Gemini generate_content 비용/throttle/timeout 미명시
추가 API 호출의 비용 추정, timeout 값(Metis 권고 5-10초), rate limit 고려, timeout 시 fallback(파싱 실패 외) 누락.

### 4. 단위 테스트 인프라 부재
"단위 테스트: response_builder 변경 확인"이라 하지만 tests/ 디렉토리에 관련 테스트 없음. 테스트 파일 신규 생성이면 "신규 파일"에 추가, 수동 검증만이면 명시.

## 요구 수정사항
1. blocks.py를 수정 대상에 추가 + PlaceBlock.summary 재활용 vs description 추가 결정
2. EVENT_SEARCH/EVENT_RECOMMEND는 "신규 추가"로 표기
3. Gemini 호출 timeout 10초 + timeout fallback 명시
4. 단위 테스트 항목 제거 또는 테스트 파일 경로 신규 파일에 추가
