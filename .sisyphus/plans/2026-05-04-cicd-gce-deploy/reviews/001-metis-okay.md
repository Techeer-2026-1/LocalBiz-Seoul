# Review: 001-metis-okay

## 검토자

metis

## 검토 일시

2026-05-04

## 검토 대상

../plan.md (2026-05-04 draft)

## 판정

okay

## 근거

### 1. 갭 (Gap)

**CORS regex 범위가 과도하다.** `https://.*\.vercel\.app`은 모든 Vercel 배포 URL을 허용한다. `allow_credentials=True`와 결합 시 제3자 Vercel 앱에서 credential 포함 요청이 가능하다. dev 단계라 즉시 차단 사유는 아니지만 prod 전환 시 축소 필요.

**GCE 방화벽/TLS 언급이 없다.** port 8000 외부 개방에 대한 명시 없음. HTTP 평문 노출 인지 여부 불명확. dev 단계에서 TLS 미요구하나 로드맵 한 줄 권장.

**systemd 서비스 파일 내용이 명세되지 않았다.** `ExecStart`의 uvicorn 명령, `--workers` 수 등 골격 필요.

### 2. 숨은 의도

"FE Vercel 배포 → BE GCE 연동을 최소 비용으로 성사"가 실질 목표. SSH 기반 pull-deploy는 팀 규모(5명)와 dev 단계에 합치.

### 3. AI Slop

해당 없음.

### 4. 오버엔지니어링

해당 없음. Phase Infra로 적절히 라벨링.

### 5. 19 불변식 위반 위험

없음. 유일한 코드 변경은 `main.py`에 CORSMiddleware 3줄 추가.

### 6. 검증 가능성

작업 순서(A-D)가 atomic step으로 잘 분리. 누락: **배포 실패 시 롤백 절차 없음.**

## 권장 수정사항 (reject 사유 아님)

1. CORS regex를 `seoul-ai-guide` prefix로 축소하거나 "prod 전환 시 축소 예정" 명기
2. GCE 방화벽 규칙이 이미 열려 있다면 그 사실 명기
3. systemd 서비스 파일의 `ExecStart` 골격 명시
4. CORS origin을 `config.py` 환경변수로 관리하는 방안 검토
5. 배포 실패 시 롤백 절차 1줄 추가

## 다음 액션

okay: Momus 검토로 진행 가능.
