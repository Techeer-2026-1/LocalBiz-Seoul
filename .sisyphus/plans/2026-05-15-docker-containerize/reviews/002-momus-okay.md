# Momus 리뷰 — okay

- 검토 대상: 2026-05-15-docker-containerize/plan.md
- 검토일: 2026-05-15
- 판정: okay

## fs 검증 결과

| 항목 | 검증 방법 | 결과 |
|---|---|---|
| `.dockerignore` 경로 충돌 | Glob `**/.dockerignore` in backend/ | 충돌 없음. 파일 미존재, 신규 생성 안전 |
| `backend/Dockerfile` 존재 | Glob + Read | 존재 (`backend/backend/Dockerfile` = repo root 기준 `backend/Dockerfile`). 현재 `COPY app/` 경로 오류 확인됨 -- plan 진단 정확 |
| `backend/docker-compose.yml` 존재 | Glob + Read | 존재. postgres + opensearch 서비스만 포함, api 서비스 없음 -- plan 설명 정확 |
| `.github/workflows/deploy-dev.yml` 존재 | Glob + Read | 존재 (repo root `.github/`). 현재 bare VM 배포(`git pull` + `pip install` + `systemctl restart`) -- plan 진단 정확 |
| `validate.sh` 존재 | Glob + Read | 존재 (repo root). 6단계 검증 스크립트 확인 |
| `requirements.txt` 존재 | Glob | 존재 (`backend/backend/requirements.txt`) |
| `requirements-dev.txt` 존재 | ls 확인 | 존재 (`backend/backend/requirements-dev.txt`) |
| `src/main.py` 존재 | ls 확인 | 존재. `/health` 엔드포인트 확인 (line 115) -- HEALTHCHECK 유효 |
| `scripts/init_db.sql` 존재 | ls 확인 | 존재. docker-compose의 init volume mount 경로 정합 |
| `src/` 디렉토리 존재 | ls 확인 | 존재 (`backend/backend/src/`) -- Dockerfile COPY 대상 유효 |
| `scripts/` 디렉토리 존재 | ls 확인 | 존재 (`backend/backend/scripts/`) -- Dockerfile COPY 대상 유효 |

## 19 불변식 검증

plan의 19 불변식 체크리스트가 전부 "해당 없음"으로 표기. 실측 검증:

- Dockerfile/docker-compose/CI YAML 변경은 **애플리케이션 코드를 수정하지 않음**
- DB 스키마 접촉 없음 (init_db.sql은 기존 volume mount 유지)
- `src/models/blocks.py` 미수정, SSE 16종 영향 없음
- 임베딩 차원/쿼리 바인딩/Optional 문법 무관
- append-only 테이블 무관
- Phase 라벨 "Infra" 명시됨

판정: **19 불변식 전부 "해당 없음" 정확**. 위반 위험 제로.

## 검증 계획 평가

| 검증 항목 | 평가 |
|---|---|
| validate.sh 통과 | validate.sh 실존 확인. Step 5 후 실행 가능 |
| `docker build` 성공 | Dockerfile 재작성 후 로컬 빌드로 검증 가능. `src/main:app` 진입점 확인됨 |
| `docker compose config` | 문법 검증으로 적절. YAML 구조 오류 조기 발견 |
| `docker compose up` + health | `/health` 엔드포인트 실존 확인 (main.py:115). 다만 DB/OS 연결 없이는 health만 통과 가능 -- 이 수준이면 충분 |
| deploy-dev.yml YAML lint | CI 워크플로 문법만 검증. 실제 GCE 배포 테스트는 plan 범위 밖으로 적절 |

## Metis 조건부 권고 추적

Metis가 제기한 2건의 조건부 권고를 재확인:

1. **환경별 compose 분리 전략**: deploy-dev.yml 실측 결과 `_upsert_env`로 `.env`에 시크릿 주입 중. Docker 전환 시 `env_file: .env`로 읽으므로 기존 `_upsert_env` → `docker compose up` 순서면 동작은 하지만, `docker-compose.yml`의 `DB_HOST=postgres`(compose 내부)와 프로덕션 Cloud SQL 간 분리가 불명확. **구현 시 override 또는 환경변수 분리 필요** -- 동의.

2. **GCE `.env` 시크릿 주입 경로**: 기존 `_upsert_env` 패턴이 Docker 전환 후에도 작동하려면 `.env` 파일이 compose context 내에 있어야 함. 현재 CI가 `backend/.env`에 쓰고 compose가 같은 위치에서 읽으면 OK이나, 이를 Step 4에 명시적으로 기술해야 함 -- 동의.

## 조건부 권고

1. **[계승] Metis 권고 2건 유지**: 환경별 compose 분리 전략 + `.env` 시크릿 주입 경로를 구현 시 Step 3/Step 4에 반영할 것. reject 사유 아님.
2. **[신규] Dockerfile build context 확인**: plan Step 2에서 `COPY src/ ./src/`와 `COPY scripts/ ./scripts/`를 명시하나, Dockerfile의 위치가 `backend/backend/Dockerfile`이므로 build context가 `backend/backend/`가 되어야 함. docker-compose의 `build: context=.`이 `docker-compose.yml`과 같은 디렉토리(`backend/backend/`)를 가리키므로 정합성은 맞으나, 구현 시 `docker build .` 명령을 `backend/backend/`에서 실행해야 함을 인지할 것.
3. **[신규] `_upsert_env` → `docker compose build` 순서**: deploy-dev.yml Step 4에서 `_upsert_env` 후 `docker compose build api`인데, build 시점에는 `.env`가 불필요(runtime env)하므로 순서 자체는 문제없음. 다만 `docker compose up -d api`가 `.env`를 읽으므로 `_upsert_env`가 그 전에 실행되어야 함 -- 기존 순서 유지로 OK.

## 최종 판정

**okay** -- plan의 파일 경로 참조가 모두 실측과 일치하고, 19 불변식 "해당 없음" 판정이 정확하며, 검증 계획이 실행 가능하다. Metis 조건부 권고 2건 + Momus 신규 1건(build context)을 구현 시 반영하면 APPROVED 가능.
