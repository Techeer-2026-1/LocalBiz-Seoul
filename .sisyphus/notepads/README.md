# .sisyphus/notepads/ — 지혜 축적 (Wisdom Accumulation)

Phase 5 워커들의 발견·판단·실패·검증 로그를 **조직적 기억**으로 누적하는 4 파일 시스템.

> 권위: `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 5 본문:
> "작업 중 특정 워커가 함정(Gotchas)에 빠지거나, 훌륭한 터미널 명령어 조합을 발견하면 아틀라스가 이를 즉각 추출한다. 추출된 지혜는 .sisyphus/notepads/ 디렉토리 하위에 구조화되어 저장된다."
>
> "추출된 노트패드의 지혜들이 이후 실행되는 다른 서브 에이전트들의 선행 지식 프롬프트(**최대 50~200줄**)로 즉각 브로드캐스팅된다."

## 4 파일 고정 (추가 금지)

| 파일 | 목적 | 주력 기록 워커 |
|---|---|---|
| `learnings.md` | 발견된 코딩 컨벤션·성공적 접근법·재사용 가능한 패턴 | sisyphus-junior (단순 패턴) / hephaestus (다중 파일 패턴) / fe-visual (FE 팁) |
| `decisions.md` | 아키텍처적 선택과 그 수학적·논리적 근거 | hephaestus (주력) / oracle (진단 기반 결정) |
| `issues.md` | 마주친 함정(Gotchas)·블로커·19 불변식 위반 의심 | oracle (주력, 진단 결과) / 모든 워커 |
| `verification.md` | Zero-Trust 검증 로그 (validate.sh / pytest / postgres MCP 실측) | hephaestus (db-migration 실측) / 메인 Claude (spawn 결과 취합) |

**새 파일 생성 금지**. 4 파일 고정 규약은 권위 문서 명시.

## 절대 원칙: Append-only

모든 notepad는 **append-only**다. 기존 내용 덮어쓰기/삭제 금지.

- ✅ 파일 맨 아래에 새 엔트리 append
- ❌ 기존 엔트리 수정
- ❌ 기존 엔트리 삭제 (오류 판명돼도 "오류로 판명됨" append로 덧붙일 것)
- ❌ 파일 재정렬·압축 (Phase 6 KAIROS Auto Dream이 담당, 수동 X)

## 엔트리 양식 (표준)

```markdown
## {YYYY-MM-DD} — {slug/제목 한 줄} (by {워커_name})

**맥락**: {어느 plan·group·step 실행 중인가}

**내용**: {핵심 발견/판단/함정/검증 결과, 50줄 이내 권장}

**근거** (선택): {파일 경로 / DB 쿼리 결과 / validate.sh 로그 일부}

**영향** (선택): {다른 워커가 이걸 알면 어떤 이득? 누구에게 broadcast 대상?}
```

### 예시 (learnings.md)

```markdown
## 2026-04-15 — asyncpg 파라미터 바인딩 ($1, $2) f-string 회귀 방지 패턴 (by hephaestus)

**맥락**: plan `erd-p1-foundation` §D step 12, places_vector ETL 재작성 중

**내용**: asyncpg 쿼리에서 f-string 유혹을 받을 때 19 불변식 #8을 기억하는 것만으로는 부족. 
`ruff-preview-E501` 룰을 pyproject.toml에 추가하니 긴 파라미터 바인딩 라인이 자동 감지되어 패턴 회귀를 물리적으로 차단한다. validate.sh 2/6 단계에서 잡힘.

**근거**: `backend/pyproject.toml:42` ruff.lint.select = ["E501", ...]

**영향**: 모든 db-migration / deep 카테고리 워커에 broadcast. 신규 백엔드 코드 작성 전 ruff 설정 확인 필수.
```

## 크기 제한 + 브로드캐스팅

- **1회 append**: 50줄 이내 권장 (간결성)
- **파일 전체**: 200줄 초과 시 **broadcast 대상으로 지정**. 200줄 도달 시 Phase 6 KAIROS Auto Dream이 압축·관리 담당 (수동 개입 X).
- **선행 지식 프롬프트**: 다음 워커 spawn 시 메인 Claude가 관련 notepad 섹션(50-200줄 선별)을 prompt에 포함시켜 broadcast.

권위 문서 인용:
> "워커 A가 겪은 시행착오는 조직 전체의 면역력으로 전환되어, 동일한 실수의 반복을 막고 프로젝트가 진행될수록 시스템 전체가 똑똑해지는 누적 학습(Cumulative learning)을 실현한다."

## 기록 주체 (Momus Mo5 주체 명시)

- **Read-only 워커 (oracle, atlas)**: 직접 쓰지 못함. 리턴 메시지로 출력 → **메인 Claude가 받아 append**
- **Write 권한 워커 (sisyphus-junior, hephaestus, fe-visual)**: 작업 중 발견 즉시 **본인이 직접 append** (단 1회 ≤50줄)
- **메인 Claude**: 
  - Read-only 워커 리턴을 받아 해당 파일에 append
  - spawn 결과 취합 (verification.md에 워커별 완료 로그)
  - notepads 전체를 read-only로 관찰, 다음 워커 spawn prompt에 broadcast

## Read 접근

모든 워커는 본 디렉토리를 **Read**할 수 있어야 한다. spawn 전 메인 Claude가 관련 섹션을 prompt에 복사하거나, 워커가 필요 시 직접 Read한다 (Read는 tools 제약 없음, 모든 워커 허용).

---

# boulder.json 스키마 (Metis M2 / Momus Mo2 흡수)

`.sisyphus/boulder.json`은 현재 실행 중인 plan의 **허브 상태 파일**이다. 권위 문서 Phase 5:

> "이러한 상태 데이터베이스의 허브 역할을 하는 파일이 바로 .sisyphus/boulder.json이다. 이 파일은 현재 실행 중인 계획(active_plan), 기여한 세션 ID(session_ids), 시작 시간(started_at) 등을 기록하여, 예기치 않은 시스템 크래시나 로그아웃이 발생하더라도 언제든 완벽한 상태 복원(Session Resume)을 가능하게 한다."

## 필드 정의

| 필드 | 타입 | 목적 | 예시 |
|---|---|---|---|
| `active_plan` | string (plan slug) | 현재 실행 중인 plan 식별자 | `"2026-04-13-harness-workers"` |
| `active_group` | string \| null | 현재 실행 중인 Atlas 의존성 맵 group ID | `"g3"` |
| `session_ids` | object | 기여한 Claude Code 세션들 (로그 추적용) | `{"2026-04-11T10:00Z": "ses_abc"}` |
| `started_at` | string (ISO8601) | plan 최초 실행 시작 | `"2026-04-11T10:30:00Z"` |
| `last_updated` | string (ISO8601) | 마지막 상태 변경 시각 | `"2026-04-11T13:45:00Z"` |
| `status` | enum | `draft` \| `in_progress` \| `blocked` \| `complete` \| `abandoned` | `"in_progress"` |
| `workers_spawned` | array | 지금까지 spawn된 워커 목록 (중복 OK, 시간순) | `[{"agent": "oracle", "at": "...", "agentId": "abc"}]` |

## 동시성 규약

- **쓰기**: 단일 메인 Claude만 쓰기 가능 (워커는 write 금지)
- **읽기**: 모든 워커 read 허용 (spawn prompt에 current active_plan/active_group 주입 가능)
- **경합 방지**: Claude Code는 단일 메인 세션 + 순차 Agent tool spawn이라 동시 쓰기 경합 발생 불가 (plan #6 부록 1 LINE#ID 앵커 불필요 논거와 동일)

## 상태 전이

```
draft → in_progress → {complete | blocked | abandoned}
          ↑               ↓
          └──── (재개) ────┘  (blocked에서 재개 시 in_progress 복귀)
```

- `draft`: plan 작성 중 (아직 APPROVED 전)
- `in_progress`: APPROVED + Atlas 의존성 맵 생성 + g1 이상 실행 시작
- `blocked`: 사용자 재심의 필요 / 외부 의존 대기
- `complete`: plan.md 헤더 COMPLETE 마크 + validate.sh 6/6 + 메모리 갱신 완료
- `abandoned`: 사용자가 폐기 결정 (재개 X)

## 파일 생성·갱신 시점

- **생성**: plan #6 §C step 12 (최초), 이후 각 plan §C 동등 step에서 overwrite (아닌, plan 전환 시 이전 boulder.json을 notepads/decisions.md에 snapshot 기록 후 새로 작성)
- **`active_group` 갱신**: 메인 Claude가 Atlas 의존성 맵의 다음 group 진입 시
- **`workers_spawned` 갱신**: Agent tool 호출 직후 (agentId 반환 시)
- **`last_updated` 갱신**: 모든 쓰기 시 자동

## 주의

- boulder.json은 단일 **활성** plan 상태만 보관. 완료된 plan의 snapshot은 `notepads/decisions.md`에 archive.
- Git 커밋 대상: 예 (재개성 위해). 단 `session_ids`에 민감 정보 있으면 redact.
- Phase 6 KAIROS 구현 후 auto-save 훅 추가 예정 (`hooks-reactivate` plan).
