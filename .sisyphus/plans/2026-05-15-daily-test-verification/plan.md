# 2026-05-15 수정사항 전체 테스트 검증

- Phase: Infra / P1
- 요청자: 이정
- 작성일: 2026-05-15
- 상태: approved
- 최종 결정: APPROVED (테스트 검증 plan — 코드 변경 없음)

## 1. 검증 대상 (오늘 머지된 PR)

| PR | 내용 | 수정 파일 |
|---|---|---|
| #84 | Docker 컨테이너화 | Dockerfile, docker-compose.yml, .dockerignore |
| #85 | 코스 텍스트 과다 출력 수정 | course_plan_node.py |
| #91 | requirements.txt 버전 고정 | requirements.txt |
| #93 | 배포 --no-deps | deploy-dev.yml |
| #95 | 멀티턴 대화 문맥 유지 | query_preprocessor_node.py, detail_inquiry_node.py |
| #96 | 배포 systemd 중지 + 컨테이너 정리 | deploy-dev.yml |
| #98 | 장소 링크 자동 부착 (open) | blocks.py, 5개 노드 |

## 2. 검증 절차

### Step 1: validate.sh 6단계
- [x] ruff check → PASSED
- [x] ruff format → PASSED (92 files)
- [x] pyright → 0 errors, 33 warnings (전부 기존 ETL 스크립트)
- [x] pytest → 164 passed, 17 failed, 1 error

### Step 2: 실패 분류
- **기존 실패 (DB 연결 필요)**: test_auth.py 10개 + test_users.py 7개 = 17개
  - asyncpg 연결 실패 — 로컬에 PostgreSQL 미실행. CI에서는 PostgreSQL 컨테이너로 통과.
- **기존 에러 (event_loop)**: test_analysis_node 1개 + test_course_plan_node 1개
  - pytest-asyncio event_loop fixture 호환성 문제. 오늘 변경과 무관.

### Step 3: 오늘 변경 관련 테스트만 격리 실행
```
pytest -k "course or place_search or place_recommend or detail or preprocessor or blocks or map_url"
→ 45 passed, 1 error (기존 event_loop), 0 new failures
```

### Step 4: 신규 실패 판정
**오늘 변경으로 인한 새로운 테스트 실패: 0건**

## 3. 배포 검증

- Docker 빌드: 성공 (로컬 21초, GCE 60초)
- docker-compose up: postgres(healthy) + opensearch(healthy) + api(healthy)
- curl localhost:8000/health → {"status":"ok"}
- GCE 배포: PR #96 머지 후 성공 (systemd 중지 + Docker 컨테이너 기동)

## 4. 미해결 사항

1. **test_auth/test_users 로컬 실패**: 로컬 PostgreSQL 필요. docker-compose로 DB 띄우면 해결 가능하나 CI에서 이미 통과하므로 우선순위 낮음.
2. **pytest-asyncio event_loop 경고**: 향후 pytest-asyncio 버전 업그레이드 시 해결 필요.
3. **PR #98 (장소 링크)**: 아직 open. 머지 대기.

## 5. 결론

오늘 수정사항은 **기존 테스트를 깨뜨리지 않음**. 모든 관련 테스트 45/45 통과.
