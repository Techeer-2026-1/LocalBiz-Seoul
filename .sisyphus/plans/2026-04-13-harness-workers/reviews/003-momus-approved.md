# Momus 리뷰 #3 — plan #6 harness-workers (재검토)

- **판정**: `approved`
- 검토자: Momus (재호출, 3rd pass, agentId `af51c7ab89de4aef8`)
- 검토일: 2026-04-11
- 대상: `.sisyphus/plans/2026-04-13-harness-workers/plan.md`
- 선행: `001-metis-okay.md` ✓ + `002-momus-okay.md` ✓ (전제조건 충족)

## 수정 7건 fs 검증 표

| # | 지적 | 요구 수정 | plan.md 실제 위치 | 상태 |
|---|---|---|---|---|
| M1 | step 5 재정독 충돌 시 중단 | "재정독 결과가 본 plan 가정과 충돌 시 step 6 진입 전 작업 중단 + 사용자에게 plan 재심의 요청" | L91 말미 | ✓ 정확히 반영 |
| M2+Mo2 | schema 파일 폐기 → README 흡수 | §2에서 `boulder.schema.md` 제거, L43 README 항목에 "boulder.json schema 섹션 흡수 (별도 schema 파일 X)" / step 10 L102에 동일 명시 / step 12 L104 "schema 설명은 step 10의 README 섹션 참조" | L43, L102, L104 | ✓ 3지점 교차 일치 |
| M3+Mo4 | fe-visual positive+negative 2 case + Read 차단 불가 명시 | step 18 L122 "(a) positive: frontend/README.md Read 성공 (b) negative: backend/src/ Read 시도 → Read는 tools 필드로 차단 불가이므로 contract 본문 자발 거부에만 의존 ... 위반 시 즉시 abort + 사유 로그 명문화 필수" | L122 | ✓ 2 case + 한계 투명 |
| M5 | 부록 1 LINE#ID 근거 | L179 "원리적 불필요 — Claude Code는 단일 메인 세션 + 순차 Agent tool spawn 구조라 동시 경합 발생 불가" | L179 | ✓ 논거 보강 완료 |
| Mo1 | step 28 "필요 시" 제거 | L141 "신규 resume 행 추가 + 기존 2026-04-11 행 교체 (**필수**)" | L141 | ✓ 모호어 제거 |
| Mo3 | oracle adversarial case | step 17 L121 "(b) adversarial negative: oracle에 backend/src/main.py Edit 시도 지시 → frontmatter tools가 Edit 호출을 자동 차단하는지 확인. 차단되면 tools 필드 강제력 입증" | L121 | ✓ vacuous pass 해소 |
| Mo5 | step 19 주체 명시 | L123 "메인 Claude가 notepads/README.md 규약에 따라 4 워커 spawn 결과를 verification.md에 append" | L123 | ✓ 주체 명시 |

## 회귀 점검 (수정이 새 결함 유발했는가)

| 점검 | 결과 |
|---|---|
| §2 신규 파일 목록이 §4 step과 1:1 일치 (schema 파일 제거 후) | ✓ 11개 신규 (agents 4 + boulder.json 1 + notepads README+4) 모두 §4에 대응 step 존재 |
| step 번호 연속성 (삭제 없이 L87-L143 30 step) | ✓ 1-30 연속 |
| step 10-12 간 schema 책임 분배 중복 없음 | ✓ step 10이 schema 섹션 작성, step 12는 "참조"만 |
| 19 불변식 체크리스트 영향 | ✓ 인프라 plan 특성상 무영향, 본문 교차 일치 재확인 |
| 수정 지점 추가 경로 충돌 | ✓ `frontend/README.md` 존재 확인 불필요 (positive 케이스 자체가 "경로 존재 여부" 무관한 spawn 작동 검증) |
| step 17 oracle postgres MCP 접근 | ✓ `.mcp.json` 기존 존재, frontmatter `mcpServers: postgres` 기존 agents와 일관 |
| step 18 `Read`는 tools 필드 차단 불가 명시 — 한계 투명화 | ✓ 6개월 뒤 읽어도 contract 자발 거부 의존이 명백 |

## 총평

7건 수정 모두 plan.md 본문에 정확한 위치·문구로 반영됐고, 회귀 결함은 없다. 특히 Mo3 adversarial case 추가로 step 17 oracle 검증이 vacuous pass에서 실증 가능 테스트로 격상됐으며, Mo4의 "Read는 tools로 차단 불가"라는 Claude Code 실제 동작 한계를 plan 본문이 명시적으로 수용해 "검증할 수 없는 주장"을 남기지 않았다. M2/Mo2 schema 파일 흡수는 §2·§4 교차 정합을 3지점(L43·L102·L104)에서 재확인했고, Mo1 "필수" 명문화로 §H 종료 step의 pass/fail 판정이 객관화됐다. 6개월 뒤 누가 이 plan만 보고 코드를 짜도 워커 4종의 tools 필드·차단 기전·검증 증거가 모두 자명하다. 체크리스트 거짓말 없음, 파일 참조 정확, 검증 계획 실행 가능 — 세 영역 모두 통과. Metis okay + Momus okay 선행 확인, 본 재검토에서 결함 0건. **`approved` 부여**. 메인 Claude는 즉시 plan.md L6을 `최종 결정: APPROVED`로 갱신하고 §G Atlas 자동 호출 진입 가능.
