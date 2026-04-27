"""Load Seoul administrative dong boundaries into administrative_districts.

File       : backend/scripts/etl/load_administrative_districts.py
Plan       : .sisyphus/plans/2026-04-12-erd-etl-blockers/ (g4 step 9)
Date       : 2026-04-12
Purpose    : Parse HangJeongDong_ver20260201.geojson → filter Seoul 427 features
             → INSERT into administrative_districts(adm_dong_code PK, adm_dong_name,
             district, geom geometry(MultiPolygon,4326)).

Execution  :
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_administrative_districts --dry-run
    python -m scripts.etl.load_administrative_districts

Geometry handling:
    plan.md §4 step 9 원문 — "WKT 또는 수동" 허용. 본 스크립트는 shapely를 설치하지
    않고 PostGIS 표준 함수 ST_GeomFromGeoJSON($4)로 geometry를 주입하는 "수동"
    경로를 채택한다. backend/venv에 shapely 미설치이며, ST_GeomFromGeoJSON은
    places/events 적재에서 이미 사용 중인 표준 PostGIS 함수다. 신규 dependency
    도입 없음.

DB credentials:
    backend/scripts/run_migration.py의 기존 관례(load_env → backend/.env의
    DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME 5변수)를 그대로 따른다.

Invariants:
    #1  administrative_districts는 자연키(adm_dong_code) 테이블 — UUID/BIGINT 아님.
    #8  모든 SQL은 asyncpg 파라미터 바인딩($1..$4). f-string SQL 없음.
    #9  타입 힌트는 Optional[...] 사용 (Python 3.9 호환, `str | None` 금지).

ON CONFLICT 없음 — plan §4 step 9 "clean insert 전제". 기존 row가 있으면
UniqueViolationError로 실패하며 트랜잭션이 롤백된다.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import asyncpg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# repo_root/data_external/행정구역_geojson/HangJeongDong_ver20260201.geojson
# __file__ = backend/scripts/etl/load_administrative_districts.py
# parents[0]=etl, [1]=scripts, [2]=backend, [3]=repo_root
GEOJSON_PATH: Path = (
    Path(__file__).resolve().parents[3] / "data" / "external" / "행정구역_geojson" / "HangJeongDong_ver20260201.geojson"
)

SEOUL_SIDONM: str = "서울특별시"
BATCH_SIZE: int = 100

# Invariant #8: parameter binding only. No f-string SQL.
INSERT_SQL = """
    INSERT INTO administrative_districts
        (adm_dong_code, adm_dong_name, district, geom)
    VALUES
        ($1, $2, $3, ST_GeomFromGeoJSON($4))
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
# GeoJSON parsing
# ---------------------------------------------------------------------------


def load_features(path: str) -> list:
    """Read GeoJSON and return list of features where sidonm == '서울특별시'."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    all_features = payload.get("features", [])
    seoul = [feat for feat in all_features if (feat.get("properties") or {}).get("sidonm") == SEOUL_SIDONM]
    logging.info("loaded %d total features, %d Seoul features", len(all_features), len(seoul))
    return seoul


def transform(feature: dict) -> tuple:
    """Map one GeoJSON feature → (adm_dong_code, adm_dong_name, district, geom_json)."""
    props = feature.get("properties") or {}
    adm_cd2: Optional[str] = props.get("adm_cd2")
    if not adm_cd2 or len(adm_cd2) < 8:
        raise ValueError("invalid adm_cd2: " + repr(adm_cd2))
    adm_dong_code = adm_cd2[:8]

    adm_nm: Optional[str] = props.get("adm_nm")
    if not adm_nm:
        raise ValueError("missing adm_nm for adm_cd2=" + repr(adm_cd2))
    adm_dong_name = adm_nm.split()[-1]

    district: Optional[str] = props.get("sggnm")
    if not district:
        raise ValueError("missing sggnm for adm_cd2=" + repr(adm_cd2))

    geometry = feature.get("geometry")
    if geometry is None:
        raise ValueError("missing geometry for adm_cd2=" + repr(adm_cd2))
    geom_json = json.dumps(geometry)

    return (adm_dong_code, adm_dong_name, district, geom_json)


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------


async def insert_batch(conn: asyncpg.Connection, rows: list) -> None:
    """Insert a batch of rows using executemany (parameter binding, invariant #8)."""
    await conn.executemany(INSERT_SQL, rows)


async def run_insert(rows: list, env: dict) -> None:
    """Connect, open transaction, batch-insert all rows, close."""
    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=30,
    )
    try:
        async with conn.transaction():
            total = len(rows)
            batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            for i in range(0, total, BATCH_SIZE):
                chunk = rows[i : i + BATCH_SIZE]
                await insert_batch(conn, chunk)
                logging.info(
                    "batch %d/%d inserted (%d)",
                    (i // BATCH_SIZE) + 1,
                    batches,
                    len(chunk),
                )
        logging.info("DONE: inserted %d", total)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


async def main() -> None:
    """Async entrypoint — parse args, transform, dry-run or insert."""
    parser = argparse.ArgumentParser(description="Load Seoul 427 administrative dongs into administrative_districts.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + transform only; print first 3 rows and exit without DB write.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("convention: backend/.env + DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME")
    logging.info("input: %s", GEOJSON_PATH)
    logging.info("dry_run: %s", args.dry_run)

    if not GEOJSON_PATH.exists():
        raise FileNotFoundError("GeoJSON not found: " + str(GEOJSON_PATH))

    features = load_features(str(GEOJSON_PATH))
    rows = [transform(feat) for feat in features]
    logging.info("transformed %d features", len(rows))

    if args.dry_run:
        logging.info("first 3 transformed rows (dry-run):")
        for idx, row in enumerate(rows[:3]):
            code, name, district, geom_json = row
            preview = geom_json[:80] + ("..." if len(geom_json) > 80 else "")
            logging.info(
                "  [%d] code=%s name=%s district=%s geom=%s",
                idx,
                code,
                name,
                district,
                preview,
            )
        logging.info("INSERT 스킵 (dry-run)")
        logging.info("DRY-RUN: would insert %d", len(rows))
        return

    repo_root = Path(__file__).resolve().parents[2]
    env = load_env(repo_root / ".env")
    if not env.get("DB_HOST"):
        raise RuntimeError("DB_HOST not in backend/.env")

    await run_insert(rows, env)


if __name__ == "__main__":
    asyncio.run(main())
