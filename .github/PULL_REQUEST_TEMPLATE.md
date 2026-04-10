## 요약

<!-- 이 PR이 무엇을·왜 하는지 1~3줄 -->

## 연결된 plan / issue

<!-- 모든 feat/refactor/non-trivial fix는 .sisyphus/plans/ plan slug 또는 issue 번호 필수 -->
- plan: `.sisyphus/plans/YYYY-MM-DD-slug/plan.md` (필수, 또는 N/A 사유)
- closes #

## 변경 사항

<!-- 어떤 파일·모듈·기능이 어떻게 바뀌었는지 핵심만 -->
-

## Phase 라벨

- [ ] P1 (핵심 대화/검색/코스/예약)
- [ ] P2 (분석/북마크/공유/이미지)
- [ ] P3 (피드백)
- [ ] ETL
- [ ] Infra (하네스/CI/문서)

## 19 데이터 모델 불변식 체크리스트

<!-- 본 PR이 backend/src 또는 ERD를 건드리면 모두 체크. 인프라/문서 PR은 "해당 없음" 표시 가능 -->

- [ ] PK 이원화 준수 (places/events/place_analysis만 UUID, 나머지 BIGINT, administrative_districts는 자연키)
- [ ] PG↔OS 동기화 (해당 시)
- [ ] append-only 4테이블 미수정 (messages, population_stats, feedback, langgraph_checkpoints)
- [ ] 소프트 삭제 매트릭스 준수 (ERD §3)
- [ ] 의도적 비정규화 4건 외 신규 비정규화 없음
- [ ] 6 지표 스키마 보존 (`score_satisfaction/_accessibility/_cleanliness/_value/_atmosphere/_expertise`)
- [ ] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [ ] asyncpg 파라미터 바인딩 (`$1`, `$2`) — f-string SQL 금지
- [ ] `Optional[str]` 사용 (`str | None` 금지)
- [ ] WS 블록 16종 한도 준수
- [ ] intent별 블록 순서 (기획서 §4.5) 준수
- [ ] 공통 쿼리 전처리 경유
- [ ] 행사 검색 DB 우선 → Naver fallback
- [ ] 대화 이력 이원화 (checkpoint + messages) 보존
- [ ] 인증 매트릭스 (auth_provider) 준수
- [ ] 북마크 = 대화 위치 패러다임 준수
- [ ] 공유링크 인증 우회 범위 정확
- [ ] Phase 라벨 명시 (위 체크박스)
- [ ] 기획 문서 우선 (충돌 시 plan으로 변경 요청)

## 검증

- [ ] `./validate.sh` 6단계 통과 (CI에서 자동 실행되지만 로컬도 통과 필요)
- [ ] 신규 코드에 단위 테스트 (테스트 파일 경로:                          )
- [ ] 수동 시나리오 통과 (어떤 시나리오:                          )
- [ ] hook 차단 없음 (`pre_edit_*`, `pre_bash_guard`, `post_edit_python`)

## 추가 메모

<!-- 리뷰어가 알아야 할 가정·트레이드오프·후속 작업 -->
