"""Load Seoul resident (internal) population stats 2026-02 into population_stats.

File       : backend/scripts/etl/load_population_stats.py
Plan       : .sisyphus/plans/2026-04-12-erd-etl-blockers/ (g5 step 13)
Date       : 2026-04-12
Purpose    : Parse 서울 생활인구(내국인) 2026-02월 CSV (284,928 data rows, 32 columns)
             → timestep × 행정동 시계열 → INSERT into population_stats
             (base_date, time_slot, adm_dong_code, total_pop, raw_data JSONB).

Execution  :
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_population_stats --dry-run
    python -m scripts.etl.load_population_stats

Input      : data/csv/생활인구 통계/행정동 단위 서울 생활인구(내국인)(CSV)(API)(202603)/
             행정동 단위 서울 생활인구(내국인)202603.csv
             Encoding: UTF-8 BOM (utf-8-sig). 32 columns: 기준일ID, 시간대구분,
             행정동코드, 총생활인구수, + 27 sex/age breakdown columns.

Mismatch policy:
    administrative_districts에 없는 행정동코드는 **skip** (plan 사용자 결정 —
    9건 추정, 후속 plan `admin-code-reconcile` 에서 해소). skipped count는
    stdout 마지막 라인 `SKIP_COUNT=<n>` 포맷으로 출력 (Momus Mo5a, §5.2 검증
    재현성). dry-run 모드에서도 동일하게 출력.

Append-only:
    population_stats는 불변식 #3 append-only 4테이블 중 하나.
    - UPDATE / DELETE / TRUNCATE 금지
    - updated_at / is_deleted 컬럼 없음
    - ON CONFLICT 절 없음 (clean insert 전제, 기존 row 있으면 UniqueViolation)
    - 전체 단일 트랜잭션으로 감싸 원자성 보장 (실패 시 전부 롤백)

raw_data JSONB:
    불변식 #5 화이트리스트 4건 중 하나 (*.raw_data JSONB 원천 보존).
    32 컬럼 전부를 `{header_name: raw_value_str}` dict 로 직렬화하여 저장.

Invariants:
    #3  append-only — UPDATE/DELETE/TRUNCATE 없음, 트랜잭션 원자성.
    #5  raw_data JSONB 원천 32 컬럼 전부 보존.
    #8  asyncpg 파라미터 바인딩 $1..$5 only. f-string SQL 없음.
    #9  타입 힌트는 Optional[...] 사용 (Python 3.9 호환, `str | None` 금지).

DB credentials:
    backend/scripts/run_migration.py / load_administrative_districts.py 와 동일 —
    backend/.env 의 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME.
"""

import argparse
import asyncio
import csv
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import asyncpg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# __file__ = backend/scripts/etl/load_population_stats.py
# parents[0]=etl, [1]=scripts, [2]=backend, [3]=repo_root
CSV_PATH: Path = (
    Path(__file__).resolve().parents[3]
    / "data/csv"
    / "생활인구 통계"
    / "행정동 단위 서울 생활인구(내국인)(CSV)(API)(202603)"
    / "행정동 단위 서울 생활인구(내국인)202603.csv"
)

BATCH_SIZE: int = 1000  # plan §4 step 13 명시
EXPECTED_TOTAL: int = 278881  # 5% 로깅용 대략 예상치 (valid rows after skip)
DRY_RUN_LIMIT: int = 100

# Invariant #8: parameter binding only. No f-string SQL.
INSERT_SQL = """
    INSERT INTO population_stats
        (base_date, time_slot, adm_dong_code, total_pop, raw_data)
    VALUES
        ($1, $2, $3, $4, $5::jsonb)
"""


# ---------------------------------------------------------------------------
# .env loader (mirrors backend/scripts/run_migration.py convention)
# ---------------------------------------------------------------------------


def load_env(env_path: Path) -> dict:
    """Minimal .env parser (no python-dotenv dependency)."""
    env: dict = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------------------
# Valid code set loader
# ---------------------------------------------------------------------------


async def fetch_valid_codes(conn: asyncpg.Connection) -> set:
    """Load administrative_districts.adm_dong_code into a Python set[str]."""
    rows = await conn.fetch("SELECT adm_dong_code FROM administrative_districts")
    codes = {r["adm_dong_code"] for r in rows}
    logging.info("loaded %d valid adm_dong_code from administrative_districts", len(codes))
    return codes


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def parse_row(raw: list, header: list) -> Optional[tuple]:
    """Parse one CSV row → (base_date, time_slot, adm_dong_code, total_pop, raw_json).

    Invariant #5: raw_data preserves all 32 columns verbatim (as-is strings).
    Raises ValueError on malformed rows (no row-level catch — plan data-quality gate).
    """
    raw_kijun = raw[0].strip()
    raw_time = raw[1].strip()
    raw_code = raw[2].strip()
    raw_total = raw[3].strip()

    if len(raw_kijun) != 8:
        raise ValueError("invalid 기준일ID: " + repr(raw_kijun))

    base_date = datetime.date(
        int(raw_kijun[:4]),
        int(raw_kijun[4:6]),
        int(raw_kijun[6:8]),
    )
    time_slot: int = int(raw_time)
    adm_dong_code: str = raw_code
    total_pop: int = round(float(raw_total))

    # 32 키-값 전부 보존 (빈 문자열 포함). header 길이 기준으로 안전하게 zip.
    raw_data_dict = {header[i]: raw[i] for i in range(len(header))}
    raw_json = json.dumps(raw_data_dict, ensure_ascii=False)

    return (base_date, time_slot, adm_dong_code, total_pop, raw_json)


# ---------------------------------------------------------------------------
# Main ETL
# ---------------------------------------------------------------------------


async def load_population_stats(dry_run: bool) -> tuple:
    """Core ETL — returns (inserted_count, skipped_count)."""
    repo_root = Path(__file__).resolve().parents[2]
    env = load_env(repo_root / ".env")
    if not env.get("DB_HOST"):
        raise RuntimeError("DB_HOST not in backend/.env")

    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=30,
    )

    inserted_count: int = 0
    skipped_count: int = 0

    try:
        valid_codes = await fetch_valid_codes(conn)

        if dry_run:
            # dry-run: first 100 rows, no INSERT, print first 3 parsed
            parsed_preview: list = []
            with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                logging.info("header columns: %d", len(header))
                read_count: int = 0
                for row in reader:
                    if read_count >= DRY_RUN_LIMIT:
                        break
                    read_count += 1
                    code = row[2].strip()
                    if code not in valid_codes:
                        skipped_count += 1
                        continue
                    parsed = parse_row(row, header)
                    if parsed is not None:
                        inserted_count += 1
                        if len(parsed_preview) < 3:
                            parsed_preview.append(parsed)

            logging.info("first 3 parsed rows (dry-run):")
            for idx, row in enumerate(parsed_preview):
                base_date, time_slot, adm_dong_code, total_pop, raw_json = row
                preview = raw_json[:80] + ("..." if len(raw_json) > 80 else "")
                logging.info(
                    "  [%d] base_date=%s time_slot=%d adm_dong_code=%s total_pop=%d raw=%s",
                    idx,
                    base_date,
                    time_slot,
                    adm_dong_code,
                    total_pop,
                    preview,
                )
            logging.info(
                "DRY-RUN: would insert %d, skipped %d (first %d rows)",
                inserted_count,
                skipped_count,
                DRY_RUN_LIMIT,
            )
            return (inserted_count, skipped_count)

        # Real insert — single transaction (append-only atomicity).
        batch: list = []
        next_log_threshold: int = max(1, EXPECTED_TOTAL // 20)  # 5% 단위
        async with conn.transaction():
            with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                logging.info("header columns: %d", len(header))
                for row in reader:
                    code = row[2].strip()
                    if code not in valid_codes:
                        skipped_count += 1
                        continue
                    batch.append(parse_row(row, header))
                    if len(batch) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL, batch)
                        inserted_count += len(batch)
                        batch.clear()
                        if inserted_count >= next_log_threshold:
                            pct = (inserted_count * 100) // EXPECTED_TOTAL
                            logging.info(
                                "progress: inserted %d / ~%d (%d%%), skipped %d",
                                inserted_count,
                                EXPECTED_TOTAL,
                                pct,
                                skipped_count,
                            )
                            next_log_threshold += max(1, EXPECTED_TOTAL // 20)
                # flush 잔여
                if batch:
                    await conn.executemany(INSERT_SQL, batch)
                    inserted_count += len(batch)
                    batch.clear()

        logging.info("DONE: inserted %d, skipped %d", inserted_count, skipped_count)
        return (inserted_count, skipped_count)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


async def main() -> None:
    """Async entrypoint — parse args and run ETL."""
    parser = argparse.ArgumentParser(
        description="Load Seoul 2026-02 resident population stats into population_stats.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse first 100 rows only; print first 3 and exit without DB write.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("convention: backend/.env + DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME")
    logging.info("input: %s", CSV_PATH)
    logging.info("dry_run: %s", args.dry_run)

    if not CSV_PATH.exists():
        raise FileNotFoundError("CSV not found: " + str(CSV_PATH))

    _inserted, skipped_count = await load_population_stats(args.dry_run)

    # Momus Mo5a — stdout 마지막 라인 고정 포맷 (grep 안정성, logging 아님).
    # 본 스크립트에서 f-string 사용은 이 한 줄만 허용 (SQL 아닌 stdout 포맷).
    sys.stdout.write(f"SKIP_COUNT={skipped_count}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
