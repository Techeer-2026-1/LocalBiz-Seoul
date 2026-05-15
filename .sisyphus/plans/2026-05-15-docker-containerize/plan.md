# Docker 컨테이너화 — Dockerfile 수정 + docker-compose api 서비스 + 배포 파이프라인 전환

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-05-15
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

현재 프로덕션 배포가 GCE VM에서 `git pull → pip install → systemctl restart` (bare VM).
기존 Dockerfile은 경로가 `COPY app/` → 실제 `src/`로 빌드 불가.
docker-compose.yml은 DB(PostgreSQL + OpenSearch) 전용.

**요구**:
- Dockerfile을 실제 프로젝트 구조에 맞게 재작성
- docker-compose.yml에 api 서비스 추가 → `docker-compose up` 한방 기동
- deploy-dev.yml CI/CD를 Docker 기반으로 전환
- 로컬 개발용 venv 세팅 (validate.sh 실행용)

## 2. 영향 범위

- 신규 파일: `backend/.dockerignore`
- 수정 파일: `backend/Dockerfile`, `backend/docker-compose.yml`, `.github/workflows/deploy-dev.yml`
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FE 영향: 없음

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 인프라 변경, DB 미접촉
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 해당 없음
- [x] Optional[str] 사용 — 해당 없음
- [x] SSE 이벤트 타입 16종 한도 준수 — 해당 없음
- [x] intent별 블록 순서 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 보존 — 해당 없음
- [x] 인증 매트릭스 준수 — 해당 없음
- [x] 북마크 = 대화 위치 패러다임 준수 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — Infra
- [x] 기획 문서 우선 — 인프라 전용, 기획 충돌 없음

## 4. 작업 순서 (Atomic step)

### Step 1: `.dockerignore` 생성
- 경로: `backend/.dockerignore`
- 내용: venv, __pycache__, .git, .github, .claude, .sisyphus, _archive, _legacy_src, tests, docs, data, monitoring, deploy, *.md, *.log, .env, .env.*, .ruff_cache, .pytest_cache, .pyright, graphify-out
- verify: 파일 존재 확인

### Step 2: `Dockerfile` 재작성
- 경로: `backend/Dockerfile`
- multi-stage 빌드 (builder → runtime)
- builder: python:3.11-slim-bookworm, libpq-dev + gcc, pip install --prefix=/install
- runtime: python:3.11-slim-bookworm, libpq5 + curl만, non-root appuser
- COPY: `src/` + `scripts/` (앱 코드 + init_db.sql)
- HEALTHCHECK: curl -f http://localhost:8000/health
- CMD: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
- verify: `docker build -t localbiz-api:test .` 성공

### Step 3: `docker-compose.yml`에 api 서비스 추가
- 기존 postgres + opensearch 서비스 유지
- api 서비스 추가:
  - build: context=., dockerfile=Dockerfile
  - ports: 8000:8000
  - env_file: .env (API 키 등)
  - environment: DB_HOST=postgres, OPENSEARCH_HOST=opensearch (compose 네트워크 오버라이드)
  - depends_on: postgres(service_healthy), opensearch(service_healthy)
  - restart: unless-stopped
- verify: `docker compose up -d` → `curl localhost:8000/health`

### Step 4: `deploy-dev.yml` Docker 전환
- 기존: SSH → git pull → pip install → systemctl restart
- 변경: SSH → git pull → docker compose build api → docker compose up -d api → health check 대기
- GCE VM에 Docker/Docker Compose V2 설치 전제 (1회성 수동 작업)
- systemd 서비스는 비활성화 (`sudo systemctl disable localbiz-api`)
- nginx 변경 없음 (127.0.0.1:8000 프록시 타겟 동일)
- verify: CI 워크플로 YAML 문법 검증

### Step 5: 로컬 venv 세팅
- `python3.11 -m venv venv && source venv/bin/activate`
- `pip install -r requirements.txt -r requirements-dev.txt`
- verify: `./validate.sh` 6단계 통과

## 5. 검증 계획

- validate.sh 통과 (Step 5 이후)
- `docker build -t localbiz-api:test .` 이미지 빌드 성공
- `docker compose config` 문법 검증
- `docker compose up -d` 전체 기동 → `curl localhost:8000/health` 응답 확인
- deploy-dev.yml YAML lint 통과

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

APPROVED (Metis okay 001 + Momus okay 002, 2026-05-15)
