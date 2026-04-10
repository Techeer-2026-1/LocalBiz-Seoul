# safe-destructive-ops — REFERENCE (L2)

> 2026-04-10 사고 재발방지로 도입. `pre_bash_guard.sh` hook이 동일 룰을 hard block으로 강제한다. 본 스킬은 *작성 단계의 사고 흐름*을 가이드.

## 사고 사례 (2026-04-10)

```bash
# 한 Bash 호출 안에서:
mv backend backend_old && \
mv backend_old/.git .git && \
mv backend_old/backend backend && \
shopt -s dotglob nullglob && \   # ← zsh에 shopt 없음 → fail
for f in backend_old/*; do ... done && \
... && \
ls backend_old/ && \
rmdir backend_old || rm -rf backend_old   # ← 위 chain 어디라도 fail 시 실행됨
```

zsh가 `shopt`을 인식 못 해 chain이 실패 → 최종 `||`가 fallback으로 평가되어 `rm -rf backend_old` 실행. **untracked 파일 손실** (venv, .env, .pytest_cache, .ruff_cache).

원인: **`||` + `rm -rf` 같은 줄 + chain 길이가 시야를 흐림**.

## 절대 룰 (3개)

### 룰 1. `||` 와 destructive op 같은 줄 금지

```bash
# ❌ 금지
cmd1 && cmd2 || rm -rf X
mv A B || cleanup_function

# ✅ 권장
cmd1 && cmd2
if [ $? -ne 0 ]; then
  rm -rf X  # 별도 Bash 호출로
fi
```

별도 Bash 호출로 나누고, 첫 호출의 결과를 *명시적으로 확인* 한 뒤 두 번째 호출.

### 룰 2. 변수 가드 필수

```bash
# ❌ 금지
rm -rf $TARGET/old
mv $SRC $DST

# ✅ 권장
rm -rf "${TARGET:?TARGET must be set}/old"
mv "${SRC:?}" "${DST:?}"
```

`${VAR:?msg}` 는 VAR가 unset/empty 시 에러로 즉시 종료. `$VAR` 가 의도치 않게 비면 `rm -rf /` 와 같아짐.

### 룰 3. dry-run 먼저, 확인 후 실행

```bash
# ❌ 즉시 destructive
mv old/* new/

# ✅ dry-run
ls old/        # 무엇이 옮겨질지 확인
ls new/        # 충돌 가능성 확인
mv old/* new/  # 그 다음에
```

`rm -rf` 전: `ls` 또는 `find <path> -print | head` 로 대상 확인.
`mv` 전: 양쪽 디렉터리 ls 로 충돌 확인.
`git filter-repo` 같은 history 재작성: 백업 (`cp -r .git .git.backup`) 후 실행.

## 패턴별 안전 레시피

### rm -rf 디렉터리

```bash
# 1단계: 대상 확인
TARGET="path/to/del"
[ -d "$TARGET" ] || { echo "not a dir"; exit 1; }
ls "$TARGET" | head -20

# 2단계 (별도 Bash): 삭제
rm -rf "${TARGET:?}"

# 3단계 (별도 Bash): 검증
[ ! -e "$TARGET" ] && echo "OK"
```

### mv 대량 파일

```bash
# 1단계: backup
cp -r src/ /tmp/src.backup.$(date +%s)/

# 2단계 (별도 Bash): mv (zsh dotglob 주의)
# bash로 명시적 호출
bash -c 'shopt -s dotglob; mv src/old/* dest/'

# 3단계 (별도 Bash): 확인
ls dest/
```

### git filter-repo 같은 history 재작성

```bash
# 1단계: 백업
cp -r .git ~/Desktop/git-backup-$(date +%Y-%m-%d)
git status --short  # working tree clean 확인

# 2단계 (별도 Bash): filter-repo
git filter-repo --to-subdirectory-filter <prefix> --force

# 3단계 (별도 Bash): 검증
git log --oneline | wc -l  # 커밋 수 보존
git log --oneline | head -5
```

### DB DROP/TRUNCATE

```bash
# 1단계: count
psql -c "SELECT COUNT(*) FROM target_table;"

# 2단계: backup (pg_dump)
pg_dump -t target_table > /tmp/backup.sql

# 3단계 (별도): TRUNCATE
psql -c "TRUNCATE target_table;"
```

## hook 강제력

- `.claude/hooks/pre_bash_guard.sh` 가 다음을 hard block (exit 2):
  - `\|\| ... rm/mv` 같은 줄
  - `rm -rf $UNGUARDED_VAR`
  - `find -delete`
  - 기존 룰 (rm -rf /, --no-verify, git reset --hard, git push --force, docker-compose down -v, DROP TABLE, TRUNCATE TABLE)
- 우회 불가. 사용자에게 명시적 직접 실행 부탁이 정공.

## 하지 말 것

- 한 Bash 호출에 5개 이상 명령 chain (가시성 저하)
- destructive op 직전에 인지 부하 큰 작업 (shopt, dotglob, eval)
- 백업 없이 rm/mv (백업 비용 < 복구 비용)
- 사용자에게 "알아서 우회해" 라고 떠넘기기

## 참고
- `.claude/hooks/pre_bash_guard.sh` (강제 패턴)
- 사고 사례 메모: `feedback_destructive_ops_isolation.md`
