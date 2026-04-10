# localbiz-memory-dream — REFERENCE (L2)

`~/.claude/projects/-Users-ijeong-Desktop---------/memory/` 의 메모리 시스템을 수동으로 정리·압축한다.

## 절차 (4단계 — 문서 분석의 KAIROS 명세 그대로)

### 1. Orientation
- `MEMORY.md` 인덱스 읽고 모든 메모리 파일 목록화
- 각 파일의 frontmatter `type` 확인 (user/feedback/project/reference)
- 마지막 갱신일 추적 (git log 또는 파일 mtime)

### 2. Gather Signal
다음만 표적 추출:
- 사용자 명시적 정정 (예: "더 이상 그렇게 하지마")
- 핵심 결정 (예: "옵션 b로 가")
- 반복된 패턴 (3회 이상 등장한 규칙)
- 새 권위 정보 (예: 새 ERD 버전, 새 API 키)

무시:
- 일회성 작업 로그
- 시효 만료된 진행 상황 ("어제 작업 중...")
- 코드/git에서 derive 가능한 정보

### 3. Consolidation
- **상대시간 → 절대시간**: "어제" → `2026-04-09`, "다음 주" → `2026-04-17`
- **모순 해결**: 같은 주제의 메모리가 충돌하면 최신/구체적인 것이 옳음
- **삭제된 파일 참조 제거**: skeptical_protocol에 따라 실제 fs 검증
- **단일 진실 유지**: 같은 사실이 두 메모리에 중복되면 한 곳으로 합침
- **outdated 마킹**: 갱신 불가능한 옛 사실은 `# OUTDATED 2026-04-10` 주석 추가 후 별도 파일 보관

### 4. Prune & Index
- `MEMORY.md`를 200줄 이내로 재구성
- 한 줄 형식 엄수: `- [Title](file.md) — one-line hook`
- 종류별로 묶지 말고 의미별로 정렬 (사용자 → 피드백 → 프로젝트 → 레퍼런스 순서가 자연스러움)
- 새로 생긴 메모리 파일 누락 없는지 `ls memory/*.md` 와 cross-check

## 하지 말 것

- 사용자 동의 없이 메모리 파일 삭제
- 진행 중 작업의 컨텍스트를 메모리로 영속화 (그건 task list 또는 plan에 속함)
- skeptical_protocol 메모리 자체 변경 (메타 규칙, 보호 대상)
- frontmatter 형식 변경 (name/description/type 필드 필수)

## 출력 형식

작업 종료 시 사용자에게 다음 형식으로 보고:

```
=== Memory Dream 결과 ===
대상 파일: N개
변경 사항:
  - 압축: ... (X줄 → Y줄)
  - 통합: ... → ...
  - 삭제: ... (이유)
  - 절대시간 변환: K건
MEMORY.md: A줄 → B줄 (한도 200)
권장 후속:
  - ...
```

## 참고 파일
- `~/.claude/projects/.../memory/MEMORY.md` (인덱스, 200줄 한도)
- `~/.claude/projects/.../memory/skeptical_protocol.md` (메타 규칙, 보호 대상)
- 문서 분석: Phase 6 KAIROS Auto Dream 명세
