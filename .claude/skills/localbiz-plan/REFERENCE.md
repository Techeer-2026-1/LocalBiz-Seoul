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
7. **Phase 4 — Atlas 의존성 맵 자동 작성** (`harness-atlas-only` plan #5 이후 활성):
   - APPROVED 직후 메인 Claude가 **Atlas 페르소나** (`.claude/agents/atlas.md`) 채택
   - plan.md + reviews 정독 → 6 카테고리 분류 + 의존성 그래프 + 병렬 그룹 식별
   - 출력: `.sisyphus/dependency-maps/{plan-slug}.md` (Markdown 표 + JSON 부속)
   - 사용자 검토 → 의견 반영 → 실행 진입 (옵션 B/C 그래뉼래리티)
   - **우회**: 사용자가 "Atlas 생략" 명시하면 직접 step 진입
8. **Phase 5 — 워커 위임** (plan `2026-04-13-harness-workers` COMPLETE 후 활성):
   1. **group 순회**: Atlas 의존성 맵의 `recommended_order` 따라 g1 → g9 순회. 각 group 내부는 `parallelizable: true`면 Agent tool 병렬 spawn(단 컨텍스트 토큰 압력 고려), false면 직렬.
   2. **step → 워커 매칭**: 각 step의 `category` 필드로 아래 6 카테고리 매칭표 조회해서 워커 결정.
   3. **Hyper-focused spawn prompt** 양식:
      ```
      task: <단 1개 atomic step 설명>
      allowed_files: <3-10 절대 경로 리스트>
      forbidden: 그 외 모든 파일
      verification: <validate.sh 또는 특정 smoke 명령>
      notepads_broadcast: <.sisyphus/notepads/ 관련 섹션 50-200줄 inline>
      plan_slug: <active_plan>
      group_id: <active_group>
      ```
   4. **Agent tool 호출**: `subagent_type: "sisyphus-junior" | "hephaestus" | "oracle" | "fe-visual"`
      - `run_in_background: true` (병렬 group 한정)
      - `isolation: "worktree"` (destructive 작업 또는 대규모 리팩토링 한정)
   5. **Zero-Trust 검증** (메인 Claude가 워커 리턴 받은 직후):
      - `validate.sh` 6단계 실행 (필수)
      - postgres MCP `information_schema` 실측 (db-migration 카테고리 한정)
      - `python -c "from backend.src.agents.real_builder import build_graph; build_graph()"` smoke (langgraph-node 카테고리 한정)
      - Next.js `npm run build` (visual-engineering 카테고리 한정)
      - **1 경고라도 있으면 reject + 워커 재호출** (권위 문서 "무한 재작업 랠리")
   6. **notepads append**: 검증 결과를 `.sisyphus/notepads/verification.md`에 기록. 워커가 발견한 패턴은 `learnings.md`, 판단 근거는 `decisions.md`, 함정은 `issues.md`.
   7. **boulder.json 갱신**: `active_group` 전환 시 `last_updated` + `workers_spawned` append.
   8. **다음 group 진입 전**: 그래뉼래리티 C 정책 시 사용자 확인. B 정책 시 Phase 단위로 묶어 실행.
9. **Phase 6 — KAIROS Auto Dream** (`harness-phase6-kairos-cicd` plan 이후 활성):
   - plan + dependency map + 실행 결과 + 메모리를 종합하여 패턴 추출
   - 메모리 정합 + 카테고리 룰 자체 개선 (메타-학습)

## 카테고리 → 워커 매칭 표 (Phase 5 활성 후)

Atlas 의존성 맵의 `category` 필드를 아래 표로 워커 결정. 6 카테고리 × 4 워커 (+ 메인 Claude).

| 카테고리 | 1차 담당 | 2차/협력 | 비고 |
|---|---|---|---|
| **`visual-engineering`** | `fe-visual` | — | 이정원 FE 합류 후 실전. backend/ 경로 Read 자발 거부. |
| **`ultrabrain`** (설계 판단) | 메인 Claude | `oracle` (진단 기반) | 아키텍처 선택, 복잡 분석. oracle은 Read-only 진단만. |
| **`deep`** (단순) | `sisyphus-junior` | — | 3-5 파일 이내 로직. 범위 초과 시 hephaestus escalate. |
| **`deep`** (복잡) | `hephaestus` | — | 3-10 파일 복잡 로직, 리팩토링, 테스트 자율 작성. |
| **`quick`** | `sisyphus-junior` | — | 1줄 fix, 오타, 단순 수정, validate.sh 실행. |
| **`db-migration`** | `hephaestus` (SQL 작성·apply) | `oracle` (사전 실측·영향 평가) | 교차 검증: hephaestus가 SQL 작성, oracle이 19 불변식 평가 → hephaestus가 apply → oracle이 information_schema 실측 재확인 |
| **`langgraph-node`** | `hephaestus` | `oracle` (16 블록/§4.5 충돌 평가) | real_builder.py / intent_router / AgentState 변경 hephaestus 전담. oracle은 기획 §4.5 정합만 평가. |

### 특수 라우팅 규칙

1. **destructive step** (DELETE/DROP/ALTER/TRUNCATE): 항상 **사용자 이중 컨펌 + `hephaestus` + `isolation: worktree`**. `sisyphus-junior`는 destructive 절대 금지.
2. **19 불변식 위반 의심**: 어느 워커든 발견 시 즉시 abort → `oracle` 진단 우선 → 진단 결과 기반 재spawn
3. **기획 문서 수정 필요**: 어느 워커든 abort → 메인 Claude가 사용자 재심의 요청 (plan 재작성)
4. **범위 초과 발견**: `sisyphus-junior` → `hephaestus` escalate. `hephaestus` → 메인 Claude에 별도 plan 제안.
5. **외부 의존성 추가**: 모든 워커 금지 → 사용자 승인 + 별도 plan
6. **사용자 검토 의존 step**: 워커 spawn 불가. 메인 Claude가 사용자에게 직접 질의.

### Agent tool 호출 예시

```python
# 단일 spawn (직렬)
Agent(
  description="places 카테고리 정규화",
  subagent_type="hephaestus",
  prompt=<Hyper-focused 양식>
)

# 병렬 spawn (Atlas 의존성 맵 g5 같은 병렬 group)
# 단일 메시지에 Agent tool call 4개를 parallel로 발행 — 컨텍스트 압력 고려
# or run_in_background: true로 순차 시작 후 나중에 완료 알림

# 격리 실행 (destructive)
Agent(
  description="places 53만 row 재분류 (worktree 격리)",
  subagent_type="hephaestus",
  isolation="worktree",
  prompt=<Hyper-focused + dry-run 명시>
)
```

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
- [ ] SSE 이벤트 타입 16종 한도 준수
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
- `기획/ERD_테이블_컬럼_사전_v6.3.md` — 데이터 권위
- `~/.../memory/project_data_model_invariants.md` — 불변식 체크리스트 원본
- `.sisyphus/plans/TEMPLATE/plan.md` — 표준 양식
- `.claude/agents/{metis,momus}.md` — 리뷰 서브에이전트
