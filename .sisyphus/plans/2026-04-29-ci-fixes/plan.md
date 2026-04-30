# CI 실패 수정 — validate.sh 기획 CSV + security.py pyright

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: COMPLETE
- 최종 결정: APPROVED → COMPLETE (2026-04-29)

## 1. 요구사항

GitHub Actions CI에서 validate.sh 기획 무결성 체크 실패 + security.py pyright 에러 해결.

### 문제 1: 기획 CSV 파일 미커밋
- 로컬에서 노션 v1 CSV 4개를 삭제하고 v2 CSV 4개로 교체했으나, git에 커밋되지 않음
- CI 환경에서는 v1만 존재 → validate.sh의 NFD 수정이 v2 파일명을 찾지 못함
- 해결: v1 삭제 + v2 추가를 커밋

### 문제 2: security.py pyright 에러
- 한정수 PR #13에서 들어온 `security.py`에 pyright 에러 2건
  - `UTC` unknown import (Python 3.11 datetime.UTC, pyright 미인식)
  - `Mapping[str, Any]` → `dict[str, Any]` 타입 불일치 (google_id_token 반환값)
- 해결: pyright ignore + dict() 래핑

## 2. 영향 범위

- 수정 파일:
  - `backend/src/core/security.py` — pyright ignore 추가
- 커밋 대상 추가:
  - `기획/` v1 CSV 4개 삭제 + v2 CSV 4개 추가

## 3. 19 불변식 체크리스트

- [x] 전체 해당 없음 (인프라/문서 변경, 비즈니스 로직 무관)

## 4. 작업 순서

1. security.py pyright ignore 추가 (이미 완료)
2. 기획 CSV v1→v2 교체 커밋 준비
3. validate.sh 통과 확인

## 5. 검증 계획

- `./validate.sh` 로컬 통과
- CI 환경에서도 통과 확인 (push 후)

## 6. 최종 결정

PENDING
