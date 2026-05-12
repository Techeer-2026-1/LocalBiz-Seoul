# Review 001 — Metis

## 판정: okay

## 근거

### 1. 갭 (Gap) — 3건 (reject 미해당, 구현 시 권고)

- **(a) proxy_set_header**: `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Real-IP` 미언급. 로깅/감사 시 클라이언트 IP 추적 불가. conf 작성 시 반드시 포함 권고.
- **(b) GCE 방화벽**: 포트 443 인바운드 허용 규칙 미명시. setup.sh 또는 전제조건으로 추가 권고.
- **(c) DNS 설정**: 도메인 A 레코드 → GCE 외부 IP 필요. ephemeral IP인 경우 static 승격 필요. 전제조건으로 명시 권고.

### 2. 숨은 의도

`deploy/nginx/` 디렉터리 신설 = 인프라 표준화 시작. 합리적이며 과도하지 않음.

### 3. AI Slop

없음. conf 1개 + setup 1개 + workflow 1줄 수정. 최소한 구성.

### 4. 오버엔지니어링

범위 적절. TLSv1.2+1.3, cipher suite, certbot 자동갱신 모두 보안 기본.

### 5. 19 불변식

인프라 전용. 체크리스트 "해당 없음" 판정 모두 정확.

### 6. 검증 가능성

4개 항목 실행 가능. 추가 권고: HTTP 301 리다이렉트 확인, `openssl s_client` 인증서 체인 검증.

## 다음 액션

Momus 검토로 진행.
