# LLM 시스템 프롬프트 — 매 응답 자기소개 반복 제거

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-13
- 상태: approved
- 최종 결정: APPROVED

## 1. 요구사항

모든 intent 노드의 LLM 시스템 프롬프트에 "당신은 서울 로컬 라이프 AI 챗봇 'AnyWay'입니다"가 포함되어 있어,
Gemini가 매 응답마다 "안녕하세요! 서울 로컬 라이프 AI 챗봇 AnyWay입니다..."로 시작함.

**수정**: 13개 노드의 시스템 프롬프트에 자기소개/인사 금지 지시를 추가.
프롬프트 자체의 역할 설정("당신은 ... 챗봇입니다")은 유지하되, 출력에서 자기소개를 하지 않도록 제어.

## 2. 영향 범위

- 수정 파일 (13개 노드의 시스템 프롬프트 문자열):
  - `backend/src/graph/place_search_node.py`
  - `backend/src/graph/place_recommend_node.py`
  - `backend/src/graph/event_search_node.py`
  - `backend/src/graph/event_recommend_node.py`
  - `backend/src/graph/course_plan_node.py`
  - `backend/src/graph/general_node.py`
  - `backend/src/graph/detail_inquiry_node.py`
  - `backend/src/graph/image_search_node.py`
  - `backend/src/graph/review_compare_node.py`
  - `backend/src/graph/analysis_node.py`
  - `backend/src/graph/crowdedness_node.py`
  - `backend/src/graph/booking_node.py`
  - `backend/src/graph/calendar_node.py`
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 해당 없음
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 3건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 해당 없음
- [x] Optional[str] 사용 — 해당 없음
- [x] SSE 이벤트 타입 16종 한도 준수 — 해당 없음
- [x] intent별 블록 순서 준수 — 변경 없음
- [x] 공통 쿼리 전처리 경유 — 변경 없음
- [x] 행사 검색 DB 우선 — 변경 없음
- [x] 대화 이력 이원화 보존 — 변경 없음
- [x] 인증 매트릭스 준수 — 해당 없음
- [x] 북마크 = 대화 위치 패러다임 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — P1
- [x] 기획 문서 우선 — 해당 없음 (프롬프트 튜닝)

## 4. 작업 순서 (Atomic step)

1. 13개 노드의 시스템 프롬프트 문자열 끝에 "자기소개나 인사로 시작하지 마세요. 바로 본론으로 답변하세요." 추가
2. validate.sh 검증

## 5. 검증 계획

- validate.sh 통과 (ruff/pyright — 문자열 변경만이므로 pytest는 기존 통과 유지)
- 수동: SSE 호출 → 응답이 "안녕하세요! ... AnyWay입니다"로 시작하지 않는지 확인

## 6. 최종 결정

APPROVED
