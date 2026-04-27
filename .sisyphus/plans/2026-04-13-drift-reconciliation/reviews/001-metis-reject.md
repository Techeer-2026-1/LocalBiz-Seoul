# Review 001 — Metis

> 파일명 규약: `NNN-{role}-{verdict}.md`

## 검토자

metis

## 검토 일시

2026-04-13 19:30

## 검토 대상

../plan.md (2026-04-13 작성, 상태 draft)

## 판정

reject

## 근거

### 1. 갭 (Gap)

plan은 메모리 파일 3건(resume, db_state, phase_boundaries)의 갱신을 명시하지만, `project_data_model_invariants.md`가 누락되어 있다. 이 파일의 "권위 문서 위치" 섹션이 여전히 `기획/서비스 통합 기획서 33d7a82c52e281f0a57fd84ac07c56f8.md`를 참조한다. CLAUDE.md 드리프트 #1과 동일한 경로 불일치가 메모리에도 존재하며, 이를 함께 정합하지 않으면 다음 세션에서 메모리 기반 교차검증 시 혼란이 발생한다.

또한 드리프트 테이블 항목 #7에 사실 오류가 있다. `etl-events` 디렉터리에는 이미 plan.md가 존재한다. plan step 3에서 "사후 plan.md 작성"을 실행하면 기존 감사 기록이 덮어써질 위험이 있다. 실제 orphan은 `etl-g4-tourism-supplement` 1건뿐이다.

boulder.json의 `place_analysis: "NOT EXISTS"`와 db_state 메모리 사이 의미 차이(테이블 자체 부재 vs 빈 테이블)도 정합 대상이나 plan이 다루지 않는다.

### 2. 숨은 의도

사용자의 진짜 목표는 "다음 세션 재개 시 메모리/boulder/CLAUDE.md가 실측과 100% 일치하여 skeptical protocol 교차검증이 즉시 통과되는 상태"를 만드는 것이다. plan의 방향은 정확하나 위 Gap의 누락이 이 목표를 저해한다.

### 3. AI Slop

해당 없음. 간결하고 구체적.

### 4. 오버엔지니어링

해당 없음. Infra 유지보수로서 범위 적절.

### 5. 19 불변식 위반 위험

DB/코드 미접촉이므로 위반 가능성 없음. 단 step 3에서 etl-events plan.md를 잘못 덮어쓸 경우 감사 추적 훼손.

### 6. 검증 가능성

6개 step 각각 검증 가능 산출물 있음. 단 step 3의 전제가 사실과 다르므로 실행 전 수정 필요.

## 요구 수정사항

1. **드리프트 테이블 #7 정정**: orphan은 `etl-g4-tourism-supplement` 1건만. step 3을 수정.
2. **메모리 갱신 대상에 `project_data_model_invariants.md` 추가**.
3. **(권장) boulder.json `place_analysis` 값 의미 통일**.

## 다음 액션

reject → 필수 2건 반영 후 Momus로 직행 가능.
