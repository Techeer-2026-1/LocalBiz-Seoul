"""Load 소상공인 상가(상권) 202512 서울 CSV into places (fresh δ replacement).

File       : backend/scripts/etl/load_sosang_biz.py
Plan       : .sisyphus/plans/2026-04-13-etl-g1-shopping-commerce/plan.md
Date       : 2026-04-12
Purpose    : 소상공인시장진흥공단 상가(상권)_서울_202512 CSV (534,978 row)를
             places 테이블에 fresh load. 기존 `seoul_restaurant_inheoga` 531K
             row는 --truncate 옵션으로 치환. 사용자 결정 δ (2026-04-12).

Execution  :
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_sosang_biz --dry-run
    python -m scripts.etl.load_sosang_biz --truncate

Category mapping (v0.2 10 대분류):
    음식/한식등       -> 음식점
    음식/비알코올     -> 카페
    음식/주점         -> 주점
    소매              -> 쇼핑
    보건의료          -> 의료
    숙박              -> 숙박
    교육              -> 교육
    수리·개인/이용·미용 -> 미용·뷰티
    예술·스포츠/스포츠 서비스 -> 체육시설
    예술·스포츠/유원지·오락,도서관·사적지 -> 관광지
    (과학·기술/부동산/시설관리·임대/수리·개인 비미용) -> SKIP

Invariants:
    #1  places.place_id VARCHAR(36) — 상가업소번호 20자 사용 (plan #13 §3)
    #3  places는 append-only 아님, DELETE 합법
    #8  asyncpg $1..$11 파라미터 바인딩, f-string SQL 금지
    #9  Optional[...] 사용 (Python 3.9 호환)
    #19 카테고리_분류표 v0.2 verbatim + validate_category() 경유
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import asyncpg

from scripts.etl.validate_category import validate_category

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# __file__ = backend/scripts/etl/load_sosang_biz.py → parents[3] = repo_root
CSV_PATH: Path = (
    Path(__file__).resolve().parents[3]
    / "data/csv"
    / "소상공인시장진흥공단_상가(상권)_정보(서울)(CSV)(202512)"
    / "소상공인시장진흥공단_상가(상권)정보_서울_202512.csv"
)

SOURCE_TAG: str = "sosang_biz_202512"
BATCH_SIZE: int = 1000
EXPECTED_ROWS: int = 534978  # profiled 2026-04-12

# Invariant #8: parameter binding only.
INSERT_SQL = """
    INSERT INTO places (
        place_id, name, category, sub_category, address, district,
        geom, phone, raw_data, source, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        ST_SetSRID(ST_MakePoint($7, $8), 4326),
        $9, $10::jsonb, $11, 0
    )
"""

TRUNCATE_SQL = "TRUNCATE TABLE places RESTART IDENTITY CASCADE"


# ---------------------------------------------------------------------------
# Category mapping (plan §2.4)
# ---------------------------------------------------------------------------


def map_category(major: str, mid: str) -> Optional[str]:
    """Map (소상공인 대분류, 중분류) → v0.2 대분류.

    Returns None → skip this row.
    """
    if major == "음식":
        if mid == "비알코올":
            return "카페"
        if mid == "주점":
            return "주점"
        return "음식점"
    if major == "소매":
        return "쇼핑"
    if major == "보건의료":
        return "의료"
    if major == "숙박":
        return "숙박"
    if major == "교육":
        return "교육"
    if major == "수리·개인":
        if mid == "이용·미용":
            return "미용·뷰티"
        return None
    if major == "예술·스포츠":
        if mid == "스포츠 서비스":
            return "체육시설"
        if mid in ("유원지·오락", "도서관·사적지"):
            return "관광지"
        return None
    # 과학·기술, 부동산, 시설관리·임대
    return None


# ---------------------------------------------------------------------------
# Row transform
# ---------------------------------------------------------------------------


def transform_row(row: dict) -> Optional[tuple]:
    """Map one CSV dict → INSERT tuple. Returns None if row is skipped."""
    major = (row.get("상권업종대분류명") or "").strip()
    mid = (row.get("상권업종중분류명") or "").strip()

    proposed = map_category(major, mid)
    if proposed is None:
        return None

    # v0.2 enum 강제 (sub_category pass-through)
    category = validate_category(proposed_category=proposed, sub_category=None, strict=False)

    place_id = (row.get("상가업소번호") or "").strip()
    if not place_id:
        return None
    if len(place_id) > 36:
        raise ValueError("place_id overflow: " + place_id)

    name = (row.get("상호명") or "").strip()
    if not name:
        return None

    # address 우선순위: 도로명주소 → 지번주소
    address: Optional[str] = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None

    district = (row.get("시군구명") or "").strip()
    if not district:
        return None

    lng_raw = (row.get("경도") or "").strip()
    lat_raw = (row.get("위도") or "").strip()
    if not lng_raw or not lat_raw:
        return None
    try:
        lng = float(lng_raw)
        lat = float(lat_raw)
    except ValueError:
        return None
    # Seoul WGS84 bbox sanity
    if not (126.7 <= lng <= 127.3 and 37.4 <= lat <= 37.7):
        return None

    sub_category: Optional[str] = mid or None

    phone: Optional[str] = None  # 소상공인 CSV에 전화번호 없음

    # raw_data: 전체 row를 그대로 JSONB로 저장 (비정규화 #5 허용 range)
    raw_data_json = json.dumps(row, ensure_ascii=False)

    return (
        place_id,
        name,
        category,
        sub_category,
        address,
        district,
        lng,
        lat,
        phone,
        raw_data_json,
        SOURCE_TAG,
    )


# ---------------------------------------------------------------------------
# .env loader (mirrors backend/scripts/run_migration.py)
# ---------------------------------------------------------------------------


def load_env(env_path: Path) -> dict:
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
# DB insert
# ---------------------------------------------------------------------------


async def run_insert(rows_iter, env: dict, truncate: bool) -> dict:
    """Open transaction, optionally TRUNCATE, then batch-insert all rows."""
    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=60,
    )
    stats = {"inserted": 0, "skipped": 0, "by_category": {}, "by_skip_major": {}}
    t0 = time.time()
    try:
        async with conn.transaction():
            if truncate:
                pre_count = await conn.fetchval("SELECT COUNT(*) FROM places")
                logging.info("pre-truncate places row count: %d", pre_count)
                await conn.execute(TRUNCATE_SQL)
                logging.info("TRUNCATE places executed")

            batch: list = []
            for row in rows_iter:
                result = transform_row(row)
                if result is None:
                    stats["skipped"] += 1
                    major = (row.get("상권업종대분류명") or "").strip()
                    stats["by_skip_major"][major] = stats["by_skip_major"].get(major, 0) + 1
                    continue
                batch.append(result)
                cat = result[2]
                stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
                if len(batch) >= BATCH_SIZE:
                    await conn.executemany(INSERT_SQL, batch)
                    stats["inserted"] += len(batch)
                    batch = []
                    if stats["inserted"] % 50000 == 0:
                        elapsed = time.time() - t0
                        logging.info(
                            "progress: inserted=%d skipped=%d elapsed=%.1fs",
                            stats["inserted"],
                            stats["skipped"],
                            elapsed,
                        )
            if batch:
                await conn.executemany(INSERT_SQL, batch)
                stats["inserted"] += len(batch)

            # Assertions (plan #9 표준)
            db_count = await conn.fetchval(
                "SELECT COUNT(*) FROM places WHERE source=$1",
                SOURCE_TAG,
            )
            if db_count != stats["inserted"]:
                raise RuntimeError(
                    "assertion fail: db_count=" + str(db_count) + " vs inserted=" + str(stats["inserted"])
                )
            null_geom = await conn.fetchval("SELECT COUNT(*) FROM places WHERE geom IS NULL")
            if null_geom > 0:
                raise RuntimeError("assertion fail: null geom count=" + str(null_geom))
            distinct_cat = await conn.fetchval("SELECT COUNT(DISTINCT category) FROM places")
            if distinct_cat < 10:
                raise RuntimeError("assertion fail: distinct category=" + str(distinct_cat))
            logging.info(
                "assertions OK: db_count=%d null_geom=0 distinct_cat=%d",
                db_count,
                distinct_cat,
            )
    finally:
        await conn.close()
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def iter_csv(path: Path):
    """Yield dict rows from utf-8 CSV."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        yield from reader


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load 소상공인 상가(상권) 202512 into places (δ).")
    parser.add_argument("--dry-run", action="store_true", help="Transform only, no DB.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE places before INSERT (destructive).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("csv: %s", CSV_PATH)
    logging.info("dry_run=%s truncate=%s", args.dry_run, args.truncate)

    if not CSV_PATH.exists():
        raise FileNotFoundError("CSV not found: " + str(CSV_PATH))
    # size_limit for large fields (raw_data might have long strings)
    csv.field_size_limit(sys.maxsize)

    if args.dry_run:
        stats = {
            "inserted": 0,
            "skipped": 0,
            "by_category": {},
            "by_skip_major": {},
        }
        t0 = time.time()
        for row in iter_csv(CSV_PATH):
            result = transform_row(row)
            if result is None:
                stats["skipped"] += 1
                major = (row.get("상권업종대분류명") or "").strip()
                stats["by_skip_major"][major] = stats["by_skip_major"].get(major, 0) + 1
                continue
            stats["inserted"] += 1
            cat = result[2]
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        stats["elapsed_sec"] = round(time.time() - t0, 1)
        logging.info("DRY-RUN stats: %s", json.dumps(stats, ensure_ascii=False, indent=2))
        logging.info(
            "DRY-RUN: would insert %d, skip %d (total %d)",
            stats["inserted"],
            stats["skipped"],
            stats["inserted"] + stats["skipped"],
        )
        return

    repo_root = Path(__file__).resolve().parents[2]
    env = load_env(repo_root / ".env")
    if not env.get("DB_HOST"):
        raise RuntimeError("DB_HOST not in backend/.env")

    stats = await run_insert(iter_csv(CSV_PATH), env, truncate=args.truncate)
    logging.info("DONE stats: %s", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
