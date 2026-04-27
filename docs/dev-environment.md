# 개발 환경 셋업 — AnyWay

> 이정 (PM) 의 자리 기준으로 작성됨. 5인 팀이 동일 인프라 (Cloud SQL 1개 + GCE OpenSearch 1개) 공유.
> 1Password 항목 **`AnyWay-Dev-Shared`** 단일 자격증명.

---

## 0. 사전 요구

- macOS / Linux (Windows는 WSL2 권장, 미검증)
- Python **3.11.x** (3.12/3.13은 LangGraph 일부 비호환)
- Node.js 20+ (Claude Code + postgres MCP)
- `git`, `gh` (GitHub CLI), `brew`(macOS) 또는 `apt`(Linux)
- Cloud SQL Auth Proxy 또는 직접 IP 접속 권한 (팀 가입 후 GCP IAM 또는 1Password 안내)
- 1Password 데스크톱 앱 + Techeer 팀 vault 가입

---

## 1. 1Password 항목 명세

**vault**: Techeer 2026-1
**item**: `AnyWay-Dev-Shared`
**type**: Login (or Secure Note)

| 필드 | 설명 |
|---|---|
| `DB_HOST` | Cloud SQL public IP (예: `REDACTED_DB_HOST`) |
| `DB_PORT` | `5432` (고정) |
| `DB_NAME` | `postgres` (고정) |
| `DB_USER` | `etl` (read+write 계정) |
| `DB_PASSWORD` | **중요** — postgres MCP 와 backend 양쪽에서 사용 |
| `OPENSEARCH_HOST` | GCE 인스턴스 public IP (예: `REDACTED_OS_HOST`) |
| `OPENSEARCH_PORT` | `9200` (고정) |
| `GEMINI_LLM_API_KEY` | Google AI Studio 발급 |
| `ANTHROPIC_API_KEY` | console.anthropic.com — 이미지 캡셔닝 (Claude Haiku) |
| `GOOGLE_PLACES_API_KEY` | GCP Places API |
| `NAVER_CLIENT_ID` | developers.naver.com |
| `NAVER_CLIENT_SECRET` | 동상 |
| `SEOUL_API_KEY` | data.seoul.go.kr |
| `GCE_SSH_PRIVATE_KEY` | 첨부 파일 — OpenSearch 인스턴스 SSH 접속 |

> 항목 이름·필드 변경 시 본 문서 + `backend/.env.example` + 루트 `.env.example` 동시 갱신.

---

## 2. PostgreSQL — Cloud SQL 접속

### 옵션 A: 직접 IP 접속 (현재 default)

`backend/.env`에 `DB_HOST=<공인 IP>` 적용. 한 번 셋업하면 끝. 단, GCP Cloud SQL 의 **Authorized networks** 에 자기 공인 IP 등록 필요 (이정에게 IP 알려주면 추가).

```bash
# 자기 공인 IP 확인
curl ifconfig.me
# → 이정에게 알리면 GCP Console에서 추가
```

연결 테스트:
```bash
psql -h $DB_HOST -p 5432 -U etl -d postgres
# password 입력 후 \dt 로 테이블 목록 확인
```

### 옵션 B: Cloud SQL Auth Proxy (선택, 더 안전)

공인 IP 노출이 부담되면 Auth Proxy 사용. GCP IAM 권한 부여가 별도 필요하므로 PM 합의.

```bash
# 설치 (macOS)
brew install cloud-sql-proxy

# 실행 (별도 터미널, 백그라운드)
cloud-sql-proxy <PROJECT_ID>:<REGION>:<INSTANCE_NAME> &

# 그러면 localhost:5432 로 접속 가능
DB_HOST=127.0.0.1
```

> **현재 default는 옵션 A**. 옵션 B로 전환 시 팀 합의 후 본 문서 갱신.

---

## 3. OpenSearch — GCE 직접 접속

### 직접 IP 접속

`backend/.env`에 `OPENSEARCH_HOST=<GCE 공인 IP>`. **HTTPS + Basic Auth** 필수.

> **nori 한국어 분석기**: ✅ 설치 완료 (2026-04-13). `analysis-nori 2.17.0`. 기존 인덱스에 nori 매핑 적용은 재적재 완료 후 별도 진행 예정.

연결 테스트:
```bash
curl -sk -u admin:Localbiz2026! "https://$OPENSEARCH_HOST:9200/_cluster/health"
# {"cluster_name":"...","status":"green",...} 확인
```

> `.env` 필요 키: `OPENSEARCH_USER=admin`, `OPENSEARCH_PASS=Localbiz2026!`

> 인덱스 생성·삭제 권한 강력. 실수 방지로 본인 작업 외 인덱스 건드리지 않음. 운영 인덱스: `places_vector`, `events_vector`, `place_reviews`.

### SSH 접속 (디버깅용)

```bash
# 1Password에서 GCE_SSH_PRIVATE_KEY 다운로드
chmod 600 ~/.ssh/anyway-gce
# config 추가
cat >> ~/.ssh/config <<EOF
Host anyway-os
  HostName <GCE_PUBLIC_IP>
  User <팀 user>
  IdentityFile ~/.ssh/anyway-gce
EOF

ssh anyway-os
# OpenSearch 로그: sudo journalctl -u opensearch -f
```

---

## 4. postgres MCP (Claude Code)

`.mcp.json` 이 `${DB_PASSWORD}` env var 를 읽으므로 **shell environment 에 export** 되어 있어야 함.

### 설치 / 셋업

```bash
# DB_PASSWORD를 ~/.zshrc (또는 ~/.bashrc) 에 export
echo 'export DB_PASSWORD="<1Password 값>"' >> ~/.zshrc
source ~/.zshrc

# 검증
echo $DB_PASSWORD  # 값이 출력되어야 함

# Claude Code 실행 (반드시 위 export 가 적용된 셸에서)
cd ~/Desktop/AnyWay  # 프로젝트 루트
claude
```

### 트러블슈팅: MCP 연결 안 됨

| 증상 | 원인 | 해결 |
|---|---|---|
| `password authentication failed` | DB_PASSWORD env var 미주입 | shell 재시작, Claude Code 완전 종료 후 재실행 (이미 떠 있는 프로세스에는 export 후에도 미주입) |
| `connection refused` | Cloud SQL Authorized networks 누락 | 자기 IP를 PM 에게 전달 |
| `host unknown` | DB_HOST 오타 | 1Password 값 재확인 |
| MCP 서버 자체 미연결 | Node.js 미설치 또는 npx 실패 | `node --version` 확인 (20+), 재설치 |

> postgres MCP는 `default_transaction_read_only=on` 으로 강제됨. 쓰기는 `backend/scripts/run_migration.py` 로만 가능.

---

## 5. Claude Code 설치 + 첫 실행

```bash
# macOS / Linux (Anthropic 공식 설치 스크립트)
curl -fsSL https://claude.com/install.sh | bash

# 설치 확인
claude --version

# 프로젝트 루트에서 실행 (반드시!)
cd ~/Desktop/AnyWay
claude
```

> 처음 실행 시 OAuth 로그인. 팀 organization 가입 필요시 PM에게 문의.

---

## 6. 검증 (셋업 완료 확인)

```bash
cd ~/Desktop/AnyWay

# 1. validate.sh 6단계 통과
./validate.sh

# 2. backend health
cd backend && source venv/bin/activate
python -c "from src.main import app; print('app import OK')"

# 3. DB 연결
psql -h $DB_HOST -U etl -d postgres -c "SELECT current_database(), current_user;"

# 4. OS 연결
curl -s http://$OPENSEARCH_HOST:9200/_cluster/health | python3 -m json.tool

# 5. Claude Code MCP 연결
cd ~/Desktop/AnyWay
claude
# 세션 진입 후: "places 테이블 컬럼 조회해줘"
# → localbiz-erd-guard 발동 + postgres MCP 응답 = 통과
```

---

## 트러블슈팅 인덱스

- **`./validate.sh` 가 ruff 못 찾음** → `pip install -r requirements-dev.txt`
- **Claude Code hook 차단** → [`CONTRIBUTING.md` § Hook 트러블슈팅](../CONTRIBUTING.md#hook-troubleshooting)
- **Cloud SQL 연결 거부** → 자기 IP를 GCP Authorized networks 에 추가 (PM 통해)
- **OpenSearch 인증 실패** → SSL 비활성화 모드 (현재 default). `verify_certs=False, use_ssl=False` 확인
- **`UP045` ruff 에러** → ruff 0.15.x 미만. `pip install ruff==0.15.9` 로 업그레이드
- **pre-commit hook fail** → `cd backend && pre-commit run --all-files` 로 로컬 진단 후 수정

---

## 현재 DB 상태 (2026-04-13)

| 항목 | 수치 |
|---|---|
| places | 535,431 (18 카테고리, 48 source) |
| events | 7,301 (8 source) |
| administrative_districts | 427 |
| population_stats | 278,880 |
| OS places_vector | 재적재 진행 중 (~535K 목표) |
| OS events_vector | 7,301 (완료) |
| OS place_reviews | 진행 중 |

> **v2 변경**: `place_analysis` 테이블 DROP — 런타임 Gemini lazy 채점으로 전환.

## 변경 이력

| 일자 | 변경 | 작성 |
|---|---|---|
| 2026-04-13 | OS HTTPS+Basic Auth, nori 대기, DB 현황 갱신, place_analysis DROP 반영 | 이정 |
| 2026-04-10 | 초안 — 1Password 단일 자격증명 + 직접 IP 접속 default | 이정 |
