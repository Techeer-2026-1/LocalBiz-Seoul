# localbiz-plan — REFERENCE (L2)

> SKILL.md에서 발동 후 Skill 도구가 이 파일을 Read한다. 본문은 lazy loading 대상.

LocalBiz Intelligence에서 **코드를 짜기 전에** 강제 통과해야 하는 plan 작성 절차.

## 하지 말 것

- 사용자 요청을 받자마자 코드 편집 도구를 부르는 것 (게으른 에이전트 패턴)
- 19 불변식을 무시한 plan 작성 (특히 PK 타입, append-only, 임베딩, Phase 라벨)
- 기획 문서를 임의 변경 (`기획/AGENTS.md` 참조 — plan으로 변경 사유 작성 후 PM 리뷰 필수)

## 절차

1. **요청 분류**:
   - Phase 라벨 부여 (P1/P2/P3 또는 ETL/Infra)
   - 영향 범위: backend/src, scripts, ERD, 응답 블록, 외부 API, FE
2. **plan 디렉터리 생성**: `.sisyphus/plans/{YYYY-MM-DD}-{slug}/` (Phase 3 B1 구조)
   - 파일이 아닌 디렉터리. `plan.md` + `reviews/`
3. **plan.md 본문은 `.sisyphus/plans/TEMPLATE/plan.md` 복사** 후 채움
4. **사용자에게 plan 경로 보고** + 승인 요청. 승인 전 코드 편집 금지.
5. **Metis/Momus 리뷰 진입** — Agent 도구로 metis → momus 순차 호출. reviews/NNN-{role}-{verdict}.md 생성.
6. **APPROVED 라인**이 plan.md에 들어가야 planning_mode flag 해제 (Phase 3 B3 hook)

## 표준 plan.md 구조 (TEMPLATE 참조)

```markdown
# {Title}

- Phase: P1 | P2 | P3 | ETL | Infra
- 요청자: {user}
- 작성일: YYYY-MM-DD
- 상태: draft | review | approved | done

## 1. 요구사항
사용자 표현 그대로 + 명확화 질문 답변

## 2. 영향 범위
- 신규 파일:
- 수정 파일:
- DB 스키마 영향 (ERD 컬럼 변경 여부):
- 응답 블록 16종 영향:
- intent 추가/변경:
- 외부 API 호출:

## 3. 19 불변식 체크리스트
- [ ] PK 이원화 준수
- [ ] PG↔OS 동기화 (해당 시)
- [ ] append-only 4테이블 미수정
- [ ] 소프트 삭제 매트릭스 준수
- [ ] 의도적 비정규화 4건 외 신규 비정규화 없음
- [ ] 6 지표 스키마 보존
- [ ] gemini-embedding-001 768d 사용 (OpenAI 임베딩 금지)
- [ ] asyncpg 파라미터 바인딩
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

## 5. 검증 계획
- validate.sh 통과
- 단위 테스트:
- 수동 시나리오:

## 6. 최종 결정
draft (Metis/Momus 리뷰 통과 후 APPROVED)
```

## 참고 파일
- `CLAUDE.md` — 19 불변식 압축본
- `기획/서비스 통합 기획서 ...md` — 마스터 기능 명세
- `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` — 데이터 권위
- `~/.../memory/project_data_model_invariants.md` — 불변식 체크리스트 원본
- `.sisyphus/plans/TEMPLATE/plan.md` — 표준 양식
- `.claude/agents/{metis,momus}.md` — 리뷰 서브에이전트
