# 002 Momus Review — plan #7 erd-etl-blockers

- 대상: `.sisyphus/plans/2026-04-12-erd-etl-blockers/plan.md`
- 검토자: Momus (엄격한 검토)
- 일자: 2026-04-12
- 판정: **okay** (approved 보류, Mo6a 필수 수정 사유)
- agentId: `a993011897fd7e4fd`
- duration: 215.8s, tokens: 52,948
- 선행: `reviews/001-metis-okay.md` (agentId `a08acdeff1d3eb7aa`, 7건 전부 반영 확인)

## 종합

체크리스트·경로·템플릿·검증가능성 네 영역 합격. Metis 7건 반영 품질 우수. 단 §1.3 사용자 결정 표의 `99.8%` factual 오류 1건(Mo6a, Metis M3 반영 파생)이 factual 기록 정확성 차원에서 반드시 수정되어야 해 approved 보류. 해당 한 건 수정 후 approved 재진입 가능.

## Metis 7건 반영 품질

| ID | 기대 반영 | 실제 반영 | 품질 |
|---|---|---|---|
| M1 geom NULL 해설 | §2.3 DDL 주석 | 후속 plan 용도 + 본 plan NOT NULL 재확인 | ✅ |
| M2 CSV/GeoJSON 경로 | §2.1-bis + §부록1 | 절대 경로 병기 | ✅ |
| M3 CSV 날짜 실측 | §부록1 표 | min 20260201 / max 20260228 / 28일 | ✅ |
| M4 ETL 실행 규약 | §C 앞 블록 | `cd backend && ... && python -m scripts.etl.<name>` | ✅ |
| M5 이중 첫 실전 | §1.2 | 제목 + 본문 재구성 | ✅ |
| Bonus-1 TRUNCATE 한정 | §부록5 위험 3 | 초기 ETL 한정, 운영 phase 금지 | ✅ |
| Bonus-2 step 22 rename 제거 | §G step 22 | 기존 파일 갱신 단일화 | ✅ |
| 보조 step 9 $5 바인딩 | §D step 9 | ST_GeomFromText($5, 4326) + f-string 금지 | ✅ |

**파생 결함**: Metis M3 반영 과정에서 §부록1은 97.9%로 정정됐으나 §1.3은 "99.8%" 방치 → Mo6a.

## Momus 독립 지적

### Mo1 체크리스트 → PASS
19 항목 [x] 완전. "해당 없음" 항목 정당. #1/#3/#5/#8/#18 실질 검증 근거 명시.

### Mo2 파일 경로 → PASS (1 minor)
fs 교차 검증 결과 plan 인용 12 경로 전부 EXISTS 또는 신규 충돌 없음.

**Mo2a (minor)**: §2.2 `memory/…` 3 파일은 사용자 auto-memory (`~/.claude/projects/-Users-ijeong-Desktop---------/memory/`). 프로젝트 루트 `memory/`는 부재. CLAUDE.md 상단 auto-memory 블록 기준 관습이나 외부인 혼선 가능 → 각주 1줄 권장.

### Mo3 step numbering → PASS (1 minor)
1~31 연속, §A~§J 라벨 정합.

**Mo3a (minor)**: §부록4 진정 워커 매트릭스 표가 9 step만 명시 (6/9/10/13/14/17/25/26/28). §G step 19-24는 누락. 표 아래 "§G step 19-24 = 메인 Claude 직접" 1줄 권장.

### Mo4 템플릿 충실도 → PASS
TEMPLATE 7 섹션 전부 채움 + 부록 6종 확장.

### Mo5 검증 가능성 → PASS (1 minor)
§5.2 10 항목 SQL assertion + 허용 오차. §5.3 smoke 3개 concrete SQL.

**Mo5a (minor)**: §5.2 마지막 행 "skip 카운트 로그" 는 stdout 검증. 로그 포맷 미정 → step 13 hephaestus spawn prompt에 `SKIP_COUNT=<n>` 고정 포맷 스펙 추가 권장.

### Mo6 내부 일관성 → **okay 저지 (Mo6a)**

**Mo6a (BLOCKER)**: `415 / 424 = 0.9787` = **97.9%**가 정확. §1.3 "99.8%"는 오산. 사용자 결정 표에 박힌 factual 오류로 6개월 뒤 고고학 유발.

**권고 수정**: §1.3 line 40 `99.8%` → `97.9%`.

**Mo6b (cosmetic)**: §4 step 15 주석 `(284,929 × 0.979)` 산출식 엉성. 실제 근거는 `284,929 − 6,048 (9 × 24 × 28)`. 278,881 정확값. 주석 정정 권장.

### Mo7 외부 참조 → PASS
ERD docx §4.4/4.5, feedback_etl_validation_gate.md, plan #6 COMPLETE, CLAUDE.md 불변식 인용 전부 정확.

## 지적 요약

| ID | 영역 | 심각도 | 한 줄 |
|---|---|---|---|
| Mo2a | 경로 | minor | §2.2 `memory/…` 출처 각주 1줄 |
| Mo3a | step 할당 | minor | §부록4 표 아래 메인 Claude step 라인 |
| Mo5a | 검증가능성 | minor | step 13 SKIP_COUNT stdout 포맷 합의 |
| **Mo6a** | **factual** | **okay 저지** | **§1.3 "99.8%" → "97.9%"** |
| Mo6b | 일관성 | cosmetic | step 15 산출식 주석 정정 |

## 판정

**okay** — approved 보류. Mo6a 필수 수정 후 approved 재진입 가능. Mo2a/Mo3a/Mo5a/Mo6b 4건 선택 반영.
