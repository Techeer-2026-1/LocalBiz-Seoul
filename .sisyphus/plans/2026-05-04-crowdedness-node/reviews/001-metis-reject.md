# Metis 검토 — REQUEST_CHANGES

- 검토자: metis
- 검토일: 2026-05-04
- 대상: `plan.md` (draft)
- 판정: **REQUEST_CHANGES**

## 핵심 갭

### 1. Phase 격상 처리 부재 — 불변식 #18/#19 위반 위험
기획서 §3.2 L103, `intent_router_node.py` L94 주석 모두 CROWDEDNESS를 Phase 2로 명시.
현 plan의 step 1 "PM 컨펌" 한 줄로 기획서 변경을 회피하려는 구조 → 기획서/주석이 갱신 안 된 채로 머지되면 문서와 코드 불일치.
**택1 필요**:
- (A) scope 축소: Phase 2 노드만 선행 구현, PHASE1_INTENTS/\_ROUTABLE_INTENTS 변경 없음
- (B) plan 분할: plan A = 기획서 §3.2 + 주석 갱신 + 버전 bump → plan B = 노드 구현

### 2. adm_dong_code 매핑 전략 미정의
`_extract_location`이 "홍대" → 8자리 adm_dong_code 변환을 어떻게 하는지 plan에 없음.
`query_preprocessor`는 `district`/`neighborhood` 문자열만 추출 — 코드 변환 로직 선결 필요.

### 3. 혼잡도 등급 컷오프 숫자 없음
"코드에서 결정론적으로 산출"이라 했으나 임계 비율이 plan에 미정의.

### 4. fallback 응답 계약 없음
`population_row=None` / `dong_code=None` / `MAX(base_date) IS NULL` 3케이스 응답 미정의.

## 추가 수정 사항 (mechanical)

5. step 2를 2a(헬퍼/SQL/등급 단위 테스트) + 2b(진입점/배선)으로 분할
6. §5 테스트 케이스 목록 enumerate (현재 "7케이스"만 언급, 목록 없음)
7. `_NODE_STATUS_MESSAGES["crowdedness"]` 한국어 문구를 plan §2에 명시

## 참조 위치

- 기획서 L103 — Phase 2 도메인 목록
- 기획서 L178 — 블록 순서 `intent → status → text_stream → done`
- `intent_router_node.py` L94 — Phase 2 주석
- `query_preprocessor_node.py` L30/L32 — district/neighborhood 추출 계약
- `sse.py` L97 — `_NODE_STATUS_MESSAGES`
