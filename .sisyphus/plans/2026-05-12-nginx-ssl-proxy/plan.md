# Nginx SSL Reverse Proxy — GCE HTTPS 종료

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-05-12
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done

## 1. 요구사항

프론트엔드(Vercel, HTTPS)에서 백엔드(GCE, HTTP:8000)로 요청 시 HTTPS 거부 발생.
GCE 앞단에 Nginx를 리버스 프록시로 두어 SSL을 종료(terminate)하고, 내부적으로 uvicorn(HTTP:8000)으로 프록시.

- HTTPS(443) → Nginx → HTTP(127.0.0.1:8000) uvicorn
- HTTP(80) → 301 HTTPS 리다이렉트
- SSE 스트리밍(`/api/v1/chat/stream`)은 `proxy_buffering off` 필수
- Let's Encrypt(certbot)로 무료 SSL 인증서 자동 발급/갱신
- 도메인은 `DOMAIN_PLACEHOLDER`로 작성 — 실제 도메인 확보 후 sed 치환

## 2. 영향 범위

- 신규 파일:
  - `deploy/nginx/anyway-api.conf` — Nginx site 설정 (SSL + reverse proxy + SSE)
  - `deploy/nginx/setup.sh` — GCE 1회성 셋업 스크립트 (nginx + certbot 설치, 인증서 발급, 서비스 활성화)
- 수정 파일:
  - `.github/workflows/deploy-dev.yml` — 배포 시 nginx reload 추가 (conf 변경 반영)
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FastAPI 코드 변경: 없음 (CORS는 이미 `*.vercel.app` HTTPS 허용)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 해당 없음 (인프라)
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 해당 없음
- [x] Optional[str] 사용 — 해당 없음
- [x] SSE 이벤트 타입 16종 한도 준수 — 해당 없음
- [x] intent별 블록 순서 준수 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 — 해당 없음
- [x] 대화 이력 이원화 보존 — 해당 없음
- [x] 인증 매트릭스 준수 — 해당 없음
- [x] 북마크 = 대화 위치 패러다임 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — Infra
- [x] 기획 문서 우선 — 해당 없음 (인프라 구성)

## 4. 작업 순서 (Atomic step)

1. `deploy/nginx/anyway-api.conf` 작성
   - HTTP(80) → HTTPS(301) 리다이렉트 + certbot ACME 챌린지 location
   - HTTPS(443) → proxy_pass http://127.0.0.1:8000
   - `/api/v1/chat/stream` location: proxy_buffering off, proxy_cache off, read_timeout 300s
   - SSL 프로토콜: TLSv1.2 + TLSv1.3, 안전한 cipher suite
2. `deploy/nginx/setup.sh` 작성
   - nginx + certbot 설치 (apt)
   - certbot 인증서 발급 (--webroot 또는 --standalone)
   - anyway-api.conf 심볼릭 링크 → /etc/nginx/sites-enabled/
   - default site 비활성화
   - nginx 시작 + 자동 갱신 cron 확인
3. `.github/workflows/deploy-dev.yml` 수정
   - 배포 스크립트에 `sudo nginx -t && sudo systemctl reload nginx` 추가

## 5. 검증 계획

- `nginx -t` — 설정 문법 검증 (setup.sh 내에서 실행)
- `curl -I https://DOMAIN` — SSL 핸드셰이크 + 200 확인
- `curl -N https://DOMAIN/api/v1/chat/stream?...` — SSE 스트리밍 정상 수신 확인
- 프론트엔드(Vercel)에서 HTTPS 요청 → 응답 수신 확인

## 6. 최종 결정

APPROVED
