# Metis 리뷰 — okay

- 검토 대상: 2026-05-15-docker-containerize/plan.md
- 검토일: 2026-05-15
- 판정: okay

## 근거

### 갭 (Gap)

plan은 기존 Dockerfile의 `COPY app/` 경로 오류를 정확히 식별하고 `src/` + `scripts/`로 교정한다. 다만 한 가지 갭이 있다: 현재 `deploy-dev.yml`은 `_upsert_env`로 Google Calendar 시크릿 3종을 `.env`에 주입하는데, Docker 전환 후 이 시크릿 주입 메커니즘이 어떻게 유지되는지 plan에 명시되지 않았다. `env_file: .env`로 마운트한다고 했지만, GCE VM에서 `.env` 파일을 누가/언제 관리하는지 (CI가 계속 upsert하는지, 수동 관리인지) 명확히 해야 한다. 또한 `docker-compose.yml`에서 postgres 포트가 `5434:5432`인데, 프로덕션 Cloud SQL과의 관계(로컬 전용 vs 프로덕션 대체)에 대한 언급이 없다 -- api 서비스가 `DB_HOST=postgres`로 compose 내 postgres를 바라보는데, 실제 프로덕션은 Cloud SQL이므로 환경별 분리 전략이 필요하다.

### 숨은 의도

plan의 표면 목적은 "Docker 컨테이너화"이지만, 실질적 동기는 (1) 깨진 Dockerfile 수정, (2) bare VM 배포의 환경 재현성 문제 해결, (3) `docker-compose up` 원커맨드 개발환경 구축이다. 숨은 의도 자체는 합리적이며 프로젝트에 유익하다. Step 5(로컬 venv 세팅)를 포함한 것은 Docker 전환 후에도 validate.sh가 venv 기반으로 돌아야 하기 때문으로, 이중 환경 유지 의도가 읽힌다 -- 이것 역시 타당하다.

### AI Slop

multi-stage 빌드 패턴, non-root appuser, HEALTHCHECK, `service_healthy` depends_on 등은 Docker 베스트 프랙티스로서 정당하다. 불필요한 복잡성(Kubernetes manifest, Helm chart, 멀티 아키텍처 빌드 등)은 포함되지 않았다. `.dockerignore` 목록도 실제 프로젝트 디렉토리 구조와 일치한다. AI가 흔히 추가하는 불필요한 레이어(Redis, Celery, nginx reverse proxy 컨테이너 등)가 없다. 깨끗하다.

### 오버엔지니어링

multi-stage 빌드는 이미지 크기 최적화를 위해 합리적이나, 현재 규모(단일 GCE VM, 단일 서비스)에서 `--workers 2`가 적절한지는 별도 벤치마크가 필요하다. 그 외에는 최소한의 변경만 포함하고 있어 오버엔지니어링 징후가 없다. nginx 변경 없음, systemd 비활성화만(제거 아님) 등 보수적 접근이 좋다.

### 19 불변식 위반 위험

plan의 19 불변식 체크리스트가 전부 "해당 없음"으로 표기되어 있으며, 이는 정확하다. Dockerfile/docker-compose/CI 파이프라인 변경은 애플리케이션 코드, DB 스키마, SSE 이벤트, 임베딩 차원 등 어떤 불변식에도 영향을 주지 않는다. 유일한 간접 위험은 Docker 환경에서 환경변수 누락 시 런타임 장애인데, 이는 불변식 위반이 아니라 운영 이슈이다. `CLAUDE.md`의 "절대 금지" 목록 중 `docker-compose down -v`가 있는데, plan에서 이를 사용하지 않으므로 문제없다.

### 검증 가능성

5단계 검증 계획이 명확하다: (1) validate.sh 통과, (2) docker build 성공, (3) docker compose config 문법 검증, (4) docker compose up + health check, (5) YAML lint. 각 Step에도 개별 verify가 있다. 다만 Step 4의 `deploy-dev.yml` 검증이 "YAML 문법 검증"에 그치는데, 실제로 GCE VM에서 Docker가 설치되어 있는지, docker compose 명령이 동작하는지는 수동 검증이 필요하다. 이는 plan 범위 밖(1회성 인프라 작업)이므로 plan에 "전제조건: GCE VM에 Docker 설치 완료" 정도만 명시하면 충분하다 -- 이미 Step 4에 언급되어 있다.

## 조건부 권고

1. **환경별 compose 분리 전략 명시**: `docker-compose.yml`의 postgres/opensearch는 로컬 개발 전용이고, 프로덕션 api 서비스는 Cloud SQL + GCE OpenSearch를 바라봐야 한다. `docker-compose.override.yml` 또는 환경변수 오버라이드로 분리하는 방안을 Step 3에 1줄 추가 권고.
2. **GCE `.env` 시크릿 주입 경로 명시**: 기존 `_upsert_env` 패턴을 Docker 전환 후에도 유지할 것인지, `.env` 파일을 사전 배치할 것인지 Step 4에 명시 권고.
3. 위 2건은 reject 사유가 아닌 구현 시 보완 사항이다.
