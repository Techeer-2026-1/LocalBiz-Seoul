# Momus 리뷰 — plan #6 harness-workers

- **판정**: `okay` (approved 직전 단계 — plan 본문 minor 수정 후 재평가 또는 사용자 판단)
- 검토자: Momus (진정 subagent, agentId `ad809851ff738a71b`, 22 tool uses)
- 검토일: 2026-04-11
- 대상: `.sisyphus/plans/2026-04-13-harness-workers/plan.md`
- 선행: `001-metis-okay.md` (존재 확인 ✓ 전제조건 충족)

## fs 검증 표

| 항목 | 경로 | 상태 | 판정 |
|---|---|---|---|
| 기존 agents 3종 | `.claude/agents/{atlas,metis,momus}.md` | 존재 | ✓ |
| 신규 agents 4종 | `.claude/agents/{sisyphus-junior,hephaestus,oracle,fe-visual}.md` | 부재 | ✓ 신규로 정확 |
| 선행 plan COMPLETE | `.sisyphus/plans/2026-04-12-harness-atlas-only/plan.md` | ✅ COMPLETE 확인 | ✓ |
| dependency-maps 기존 | `.sisyphus/dependency-maps/` | 기존 (4 파일) | ✓ |
| notepads 디렉토리 | `.sisyphus/notepads/` | `.gitkeep`만 존재 | ✓ (신규 4+README 작성 가능) |
| boulder.json | `.sisyphus/boulder.json` | 부재 | ✓ 신규로 정확 |
| REFERENCE.md §8 | `.claude/skills/localbiz-plan/REFERENCE.md:30` | "Phase 5 — 워커 위임" placeholder 존재 | ✓ |
| memory 2 파일 | `project_harness_phase_mapping.md`, `project_phase_boundaries.md` | 존재 | ✓ |
| validate.sh | 루트 | 존재 | ✓ |

## 발견 사항

### 1. [minor/모호어] step 28 "인덱스 갱신 (필요 시)" 객관 판정 불가

**문제**: §H step 28 `memory/MEMORY.md` "인덱스 갱신 (필요 시)" — "필요 시"가 주관이라 §5 검증에서 pass/fail 판정 불가. Momus 관점에서 step은 조건부가 아니라 "조건 판정 + 실행/스킵 결정"으로 명문화돼야 함.

**권고**: "plan #6 COMPLETE 시 신규 `project_resume_2026-04-13.md`가 생성되므로 MEMORY.md 인덱스에 해당 행 추가 **필수**"로 조건 제거.

### 2. [minor/파일 중복] `.sisyphus/boulder.schema.md` 신규 파일이 §2 영향범위 목록 누락

**문제**: step 12가 "별도 `.sisyphus/boulder.schema.md`로 schema 설명"을 언급하지만 §2 신규 파일 목록에 이 파일이 없다. 체크리스트 완전성 위반.

**권고**: §2 신규 파일 목록에 `.sisyphus/boulder.schema.md` 추가 **또는** Metis #2 권고 수용해 `notepads/README.md` 내부 섹션으로 흡수(파일 감축). 어느 쪽이든 §2와 §4 step 12가 일치해야 함.

### 3. [minor/검증 불가능] §5 "Hyper-focused contract 준수 확인" vacuous pass

**문제**: §5의 "워커가 범위 벗어나지 않음" 검증은 negative evidence를 요구하는데, spawn 테스트가 read-only 작업이면 애초에 이탈 시도 자체가 발생하지 않아 검증이 공허(vacuous pass)하다.

**권고**: §E에 adversarial test 1건 추가 — 예: oracle에게 "이 파일을 수정하라" 지시해서 tools 필드가 실제로 `Edit` 거부하는지 확인. 또는 §5에서 "vacuous pass 수용, 실제 차단 검증은 plan #7 실사용에 위임" 명시.

### 4. [minor/중복+보강] Metis #3 (fe-visual spawn 테스트) Momus 관점 재확인

**문제**: step 18 "backend/ 경로 접근 시도 시 disallowedTools 또는 contract 거부" — `disallowedTools: Bash`만 설정인데 "backend 경로 Read 거부"는 tools 필드로 차단되지 않는다 (`Read`는 허용). contract 본문 자발 거부에만 의존 → 검증 불가능한 상태.

**권고**: step 18 검증 기준을 "contract 본문에 'backend/ 경로 금지' 명시 → 워커가 자발 거부 로그 남김" + "FE 허용 경로 Read는 성공"으로 positive/negative 2 case 명시.

### 5. [minor/갭] step 15-18 spawn 테스트 결과를 verification.md에 쓰는 주체 불명

**문제**: step 19 "4 워커 spawn 결과를 `.sisyphus/notepads/verification.md`에 첫 기록" — 누가 쓰는가? 메인 Claude? 워커 본인?

**권고**: step 19 "메인 Claude가 notepads/README.md 규약에 따라 verification.md에 append"로 주체 명시.

### 6. [observation/양호] 19 불변식 체크리스트 적정성

**확인**: plan은 DB/intent/블록/임베딩/auth 모두 무터치라고 선언 → §2 "DB 스키마 영향: 없음" / "응답 블록 16종 영향: 없음" / "intent 추가/변경: 없음" / "외부 API 호출: 없음" 명시됨. §3 체크박스가 형식적이지 않고 본문과 교차 일치 확인됨. Momus 관점 통과.

## 총평

plan은 Metis okay 판정대로 scope 경계와 권위 문서 대응이 투명하며, 19 불변식은 인프라 plan 특성상 본문과 교차 일치하여 체크리스트 거짓말 없음을 확인했다. fs 검증 표 9항 모두 통과 — 신규 파일 4 agents + notepads + boulder.json이 실제로 부재하고, 수정 대상 REFERENCE.md §8은 "Phase 5 — 워커 위임" placeholder로 line 30에 실존한다. 그러나 (a) `boulder.schema.md`가 §2에 미등재된 체크리스트 누락, (b) step 28 "필요 시" 같은 모호어, (c) spawn 검증이 vacuous pass 가능한 구조, (d) fe-visual Read 차단이 tools 필드 미지원이라는 4개 minor 결함이 남아있다. 차단 사유는 아니지만 **approved 부여하기에는 조기**다. Metis 지적 6건과 본 리뷰 5건(1·3·4는 새 발견) 중 최소 발견 사항 2(§2 목록 정합)와 4(fe-visual 검증 기준)만이라도 plan.md 본문 수정 후 `003-momus-approved.md`로 재평가하는 것을 권장한다. 사용자가 "minor는 실행 중 보정" 원칙으로 즉시 APPROVED를 원하면 이의 없음 — 다만 Momus 서명은 `okay`까지다.
