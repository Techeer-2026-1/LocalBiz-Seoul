# Review: 001-metis-reject

## 검토자: metis
## 검토 일시: 2026-05-13
## 판정: reject

## 근거

### 1. 갭 — `event` 단일 블록 타입 부재

plan은 `[event + text] x N` 인터리빙을 제안하지만, `blocks.py`의 `CONTENT_BLOCK_TYPES`에 `event`(단수)가 없다. `place`(단수)는 `PlaceBlock`으로 등록되어 있으므로 장소 인터리빙은 가능하나, 행사는 `events`(복수) 하나만 존재. 선택지:
- (a) `EventBlock` 17번째 타입 추가 → 불변식 #10 위반
- (b) `events` 블록을 단건 items로 반복 전송 → 타입 유지, 의미론적 왜곡
- (c) 행사는 인터리빙하지 않음

### 2. Gemini JSON mode 구현 상세 부재

per-place 설명 JSON mode 생성의 schema, 에러 fallback, 파싱 로직이 plan에 없다.

### 3. FE 영향 미확인

개별 `place` 블록 렌더러, `text` 블록(비스트리밍) 렌더러 존재 여부 확인 필요.

### 4. response_builder 반복 블록 검증 로직

`[place, text, place, text, ...]` 반복 패턴을 `_validate_block_order`가 어떻게 처리할지 구체 로직 없음.

## 요구 수정사항

1. event 블록 타입 결정 명시 + 불변식 #10 체크리스트 업데이트
2. Gemini JSON mode 구현 상세 (schema, fallback, 파싱)
3. FE 영향 확인 또는 FE 작업 항목 추가
