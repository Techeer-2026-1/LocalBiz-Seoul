# Metis 리뷰 — plan #6 harness-workers

- 판정: **okay**
- 검토자: Metis (진정 subagent, agentId `a4c5c7bd40c84d7e1`)
- 검토일: 2026-04-11
- 대상: `.sisyphus/plans/2026-04-13-harness-workers/plan.md`

## 발견 사항

### 1. [minor/갭] §A step 5 재정독 피드백 루프 부재

**문제**: §A step 5 "권위 docx Phase 5 재정독"이 step 6-9 워커 contract 작성 이전에 있지만, 재정독 결과가 contract에 어떻게 반영되는지 피드백 루프가 없다. 재정독에서 새 사실이 드러나면 step 6-9를 어떻게 조정할지 미정.

**권고**: step 5에 "재정독 결과가 본 plan 가정과 충돌 시 작업 중단 + plan 재심의" 조건 1줄 추가.

### 2. [minor/AI Slop] `boulder.schema.md` 별도 파일 과대 대응

**문제**: step 12가 JSON5 주석 불가 문제를 별도 파일(`boulder.schema.md`)로 우회하는데 과한 대응이다. JSON schema 파일 내 `"_comment"` 필드 또는 README 한 섹션으로 충분.

**권고**: `.sisyphus/notepads/README.md`에 "boulder.json schema" 섹션을 끼워 파일 1개 감축. 또는 `.sisyphus/` 최상위에 `boulder.README.md` 1개 배치.

### 3. [minor/실행가능성] §E step 18 fe-visual spawn 테스트 케이스 부족

**문제**: "정의만"인 fe-visual의 spawn 테스트가 의미 있는 이유는 disallowedTools/tools 필드의 실제 차단 작동 확인이다. 다만 step 18은 "backend 경로 차단 확인"만 명시하고 **성공 케이스**(FE 경로 가짜 작업)가 없다.

**권고**: "빈 FE 경로에서 Read/Write 시도 성공 + backend 경로 Read 거부" 2 case 병기.

### 4. [minor/오버엔지니어링] §H 6 step 압축 가능

**문제**: 30 step은 plan #5 17의 1.76배. §H 종료 6 step은 실제로 memory 갱신 3개 + validate.sh + resume 작성 + 헤더 마크로 묶어서 3 step으로 압축 가능. atomic 원칙을 엄격히 적용한 결과이므로 reject 사유는 아님.

**권고**: 선택적 병합 (reject 사유 X).

### 5. [minor/갭] 부록 1 LINE#ID 앵커 보류 근거 부재

**문제**: 부록 1 대응표가 "LINE#ID 해시 앵커 편집"을 "Claude Code Edit 도구 한계"로 보류하는데, 권위 문서의 해당 원리가 **왜** 필요했는지(동시 편집 충돌 방지) plan 본문이 다루지 않는다. 현 Claude Code 환경이 단일 세션이라 불필요하다는 **논거**가 없으면 6개월 뒤 후회 가능.

**권고**: 부록 1 해당 행 "갭" 열에 "Claude Code 단일 세션 특성상 동시 편집 없음 → 불필요"로 이유 보강.

### 6. [minor/숨은 의도 부합] — 칭찬

**관찰**: 사용자가 "이대로 가자"고 한 신호는 긍정적으로 반영됨. Oracle 재정의/이종 모델/FE 검증을 모두 미래 plan으로 격리하여 scope creep 방지. 본 plan은 "빠른 실행 + 명확한 차단선"이라는 숨은 의도와 일치한다. 발견 사항이라기보다 칭찬.

## 총평

plan은 권위 문서 Phase 5의 핵심(워커 4종 + notepads + boulder.json + Hyper-focused + Zero-Trust 수동 버전)을 모두 덮고 있으며, 자동화 hook·KAIROS·모델 혼용은 명시적으로 범위 외로 격리해 scope creep을 차단했다. 19 불변식은 인프라 plan 특성상 모두 자동 통과하고, 갭은 Oracle 역할 미정독과 LINE#ID 앵커 보류 2건인데 둘 다 사용자 승인된 가정으로 투명하게 기록됐다. 발견 사항은 모두 minor이며 차단 사유 없다. Momus 체크리스트 형식 검증으로 넘겨도 된다.
