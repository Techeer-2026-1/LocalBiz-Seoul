# {Title}

- Phase: P1 | P2 | P3 | ETL | Infra
- 요청자: {user}
- 작성일: YYYY-MM-DD
- 상태: draft
- 최종 결정: PENDING

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

사용자 표현 그대로 + 명확화 질문 답변.

## 2. 영향 범위

- 신규 파일:
- 수정 파일:
- DB 스키마 영향 (ERD 컬럼 변경 여부):
- 응답 블록 16종 영향:
- intent 추가/변경:
- 외부 API 호출:
- FE 영향:

## 3. 19 불변식 체크리스트

- [ ] PK 이원화 준수 (places/events/place_analysis만 UUID)
- [ ] PG↔OS 동기화 (해당 시)
- [ ] append-only 4테이블 미수정 (messages/population_stats/feedback/langgraph_checkpoints)
- [ ] 소프트 삭제 매트릭스 준수
- [ ] 의도적 비정규화 4건 외 신규 비정규화 없음
- [ ] 6 지표 스키마 보존 (score_satisfaction/_accessibility/_cleanliness/_value/_atmosphere/_expertise)
- [ ] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [ ] asyncpg 파라미터 바인딩 ($1, $2)
- [ ] Optional[str] 사용 (str | None 금지)
- [ ] WS 블록 16종 한도 준수
- [ ] intent별 블록 순서 (기획 §4.5) 준수
- [ ] 공통 쿼리 전처리 경유
- [ ] 행사 검색 DB 우선 → Naver fallback
- [ ] 대화 이력 이원화 (checkpoint + messages) 보존
- [ ] 인증 매트릭스 (auth_provider) 준수
- [ ] 북마크 = 대화 위치 패러다임 준수
- [ ] 공유링크 인증 우회 범위 정확
- [ ] Phase 라벨 명시
- [ ] 기획 문서 우선 (충돌 시 plan으로 변경 요청)

## 4. 작업 순서 (Atomic step)

1.
2.
3.

## 5. 검증 계획

- validate.sh 통과
- 단위 테스트:
- 수동 시나리오:

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

PENDING (Metis/Momus 통과 시 APPROVED로 갱신)
