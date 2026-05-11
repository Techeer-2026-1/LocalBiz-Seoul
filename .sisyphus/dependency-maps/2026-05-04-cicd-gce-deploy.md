# 의존성 맵: cicd-gce-deploy

| 항목 | 값 |
|---|---|
| plan_slug | cicd-gce-deploy |
| plan_path | `.sisyphus/plans/2026-05-04-cicd-gce-deploy/plan.md` |
| 생성일 | 2026-05-04 |

## 실행 순서

```
g1 → g2 (병렬: 2+3+9) → g3 (직렬: 4→5+6) → g4 (직렬: 7→8) → g5 (10) → g6 (11) → g7 (병렬: 12+13)
```

## Step 분류

| id | description | category | group | depends_on | 비고 |
|---|---|---|---|---|---|
| 1 | git checkout dev && git pull | quick | g1 | [] | |
| 2 | main.py CORS 추가 + validate.sh | deep | g2 | [1] | 로컬 작업 |
| 3 | GCE 시스템 패키지 설치 | quick | g2 | [] | GCE SSH |
| 9 | GitHub Secrets 등록 | quick | g2 | [] | GitHub UI, 사용자 입력 |
| 4 | GCE 레포 clone | quick | g3 | [3] | |
| 5 | GCE venv + pip install | quick | g3 | [4] | |
| 6 | GCE .env 생성 | quick | g3 | [4] | 사용자 직접 입력 |
| 7 | systemd 서비스 등록 | quick | g4 | [5, 6] | |
| 8 | curl health check | quick | g4 | [7] | |
| 10 | deploy-dev.yml 작성 | deep | g5 | [2, 9] | |
| 11 | dev push → 자동 배포 확인 | quick | g6 | [8, 10] | |
| 12 | CORS curl 검증 | quick | g7 | [11] | |
| 13 | FE API 호출 테스트 | quick | g7 | [11] | |

## Group 상세

| group | steps | parallelizable | 사용자 개입 |
|---|---|---|---|
| g1 | 1 | no | no |
| g2 | 2, 3, 9 | **yes** (3환경 독립) | yes (step 9) |
| g3 | 4, 5, 6 | partial (5+6) | yes (step 6) |
| g4 | 7, 8 | no | no |
| g5 | 10 | no | no |
| g6 | 11 | no | no |
| g7 | 12, 13 | **yes** | no |
