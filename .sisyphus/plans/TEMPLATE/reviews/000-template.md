# Review Template

> 파일명 규약: `NNN-{role}-{verdict}.md`
> - NNN: 001부터 zero-padded
> - role: metis | momus
> - verdict: reject | okay | approved
>
> 예: `001-metis-reject.md`, `002-metis-okay.md`, `003-momus-reject.md`, `004-momus-okay.md`

## 검토자

metis | momus

## 검토 일시

YYYY-MM-DD HH:MM

## 검토 대상

../plan.md (commit hash 또는 작성일)

## 판정

reject | okay | approved

## 근거

(Metis: 갭/숨은 의도/AI Slop/오버엔지니어링)
(Momus: 체크리스트 누락/파일 참조 오류/검증 불가능 항목)

## 요구 수정사항

1.
2.

## 다음 액션

- reject: plan.md 수정 후 다음 NNN+1 리뷰 요청
- okay: 같은 검토자의 후속 라운드 또는 다른 검토자 호출
- approved: plan.md 최종 결정을 APPROVED로 갱신
