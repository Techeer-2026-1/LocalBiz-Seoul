# CI/CD 파이프라인 + GCE 초기 배포 + CORS 설정

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-05-04
- 상태: approved
- 최종 결정: APPROVED

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

## 1. 요구사항

1. `origin/dev` 브랜치를 로컬에 pull (현재 로컬은 `feat/#34` detached 상태)
2. GitHub Actions CI/CD 구축: `dev` push → GCE(`localbiz-api`, 34.22.91.75) 자동 배포
3. GCE 초기 세팅: git clone, Python venv, .env, systemd 서비스 등록
4. FastAPI CORS 미들웨어 추가: `*.vercel.app` + `localhost:*` 허용
   - 프론트엔드 URL: `https://seoul-ai-guide-*.vercel.app`
   - Vercel 배포 URL이 매번 변경되므로 정규식 패턴 필요

## 2. 영향 범위

- 신규 파일:
  - `.github/workflows/deploy-dev.yml` — GitHub Actions 워크플로
  - (GCE) `/etc/systemd/system/localbiz-api.service` — systemd 서비스 파일
- 수정 파일:
  - `backend/src/main.py` — CORSMiddleware 추가 (3줄)
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FE 영향: CORS 허용으로 FE→BE 통신 가능해짐

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 해당 없음 (Infra)
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
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 보존 — 해당 없음
- [x] 인증 매트릭스 준수 — 해당 없음
- [x] 북마크 = 대화 위치 패러다임 준수 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — Infra
- [x] 기획 문서 우선 — 해당 없음 (인프라 변경, 기획 무관)

## 4. 작업 순서 (Atomic step)

### A. 로컬 준비
1. `git checkout dev && git pull origin dev` — dev 브랜치 최신화
2. `backend/src/main.py`에 CORSMiddleware 추가
   - `allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+"`
   - `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
   - **prod 전환 시** regex를 `https://seoul-ai-guide.*\.vercel\.app` 프로젝트 prefix로 축소 예정

### B. GCE 초기 세팅 (SSH로 `localbiz-api` 접속)
3. 시스템 패키지 설치: `python3.11, python3.11-venv, git`
4. 레포 clone: `git clone https://github.com/Techeer-2026-1/LocalBiz-Seoul.git`
5. venv 생성 + 의존성 설치: `python3.11 -m venv venv && pip install -r backend/requirements.txt`
6. `.env` 파일 생성 (사용자가 직접 값 입력 — 커밋/전송 금지)
7. systemd 서비스 등록: `localbiz-api.service` → `systemctl enable --now`
   ```ini
   [Unit]
   Description=LocalBiz API (FastAPI + uvicorn)
   After=network.target

   [Service]
   User=ijeong
   WorkingDirectory=/home/ijeong/LocalBiz-Seoul/backend
   EnvironmentFile=/home/ijeong/LocalBiz-Seoul/backend/.env
   ExecStart=/home/ijeong/LocalBiz-Seoul/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
8. 서비스 동작 확인: `curl localhost:8000/health`

### C. GitHub Actions CI/CD
9. GitHub Secrets 등록: `GCE_SSH_PRIVATE_KEY`, `GCE_HOST` (34.22.91.75), `GCE_USER` (ijeong)
10. `.github/workflows/deploy-dev.yml` 작성:
    - trigger: `push` to `dev`
    - job: SSH into GCE → `cd repo && git pull origin dev && source venv/bin/activate && pip install -r backend/requirements.txt && sudo systemctl restart localbiz-api`
11. CORS 변경 포함하여 dev에 push → 자동 배포 확인
    - **배포 실패 시 롤백**: GCE SSH 접속 → `cd ~/LocalBiz-Seoul && git log --oneline -3` 확인 → `git checkout <이전커밋>` → `sudo systemctl restart localbiz-api`

### D. 검증
12. `curl -I -H "Origin: https://test.vercel.app" http://34.22.91.75:8000/health` → CORS 헤더 확인
13. 프론트엔드에서 API 호출 테스트

## 5. 검증 계획

- validate.sh 통과 (CORS 추가 후 로컬)
- GCE health check: `curl http://34.22.91.75:8000/health` → `{"status": "healthy"}`
- CORS 검증: `curl -H "Origin: https://foo.vercel.app" -v http://34.22.91.75:8000/health` → `Access-Control-Allow-Origin` 헤더 포함
- FE→BE 실제 통신: Vercel 배포 URL에서 API 호출 성공
- CORS 단위 테스트: 별도 파일 미작성. 근거 — CORSMiddleware는 FastAPI/Starlette 프레임워크 내장이므로 프레임워크 자체 테스트에 위임. CORS 동작은 curl preflight + FE 실제 통신으로 통합 검증. GCE 방화벽은 `allow-fastapi` (tcp:8000, Apply to all) 규칙이 이미 존재하여 추가 작업 불필요.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

APPROVED (Metis okay + Momus okay → 지적사항 반영 완료)
