"""Load events CSV from data/csv/축제·행사/ into events table.

File   : backend/scripts/etl/load_events.py
Plan   : .sisyphus/plans/2026-04-13-etl-events/plan.md
Date   : 2026-04-13
Scope  : 3 source registries (문화행사 정보, 공공서비스예약, 구별 문화축제)

Sources (20 files, ~4,752 rows):
    서울시문화행사:      서울시 문화행사 정보.csv (cp949, WGS84)  ~3950 rows
    서울시공공서비스예약: 서울시 문화행사 공공서비스예약 정보.csv (cp949, WGS84)  ~655 rows
    서울시문화축제:      서울특별시_*_문화축제_*.csv (utf-8, WGS84)  ~147 rows

Execution:
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_events --dry-run
    python -m scripts.etl.load_events

Strategy:
    DELETE existing rows for these 3 sources, then re-insert with full field
    population (category, place_name, price, poster_url, detail_url, summary).
    The original load left many fields NULL; this script corrects that.

Invariants:
    #1 event_id UUID — deterministic UUID5 from (source, title, date_start)
    #3 events is NOT append-only — DELETE + re-insert is fine
    #5 events.{district, place_name, address} intentional denormalization
    #8 asyncpg $1..$N binding
    #9 Optional[...] (Python 3.9)
"""

import argparse
import asyncio
import csv
import glob
import json
import logging
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import asyncpg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
CSV_ROOT: Path = REPO_ROOT / "data/csv"
BATCH_SIZE: int = 500

# UUID5 namespace for deterministic event IDs
EVENT_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# WGS84 Seoul bbox
LNG_MIN, LNG_MAX = 126.7, 127.3
LAT_MIN, LAT_MAX = 37.4, 37.7

DISTRICT_RE = re.compile(r"서울특별시\s+([가-힣]+구)")
DISTRICT_RE_SHORT = re.compile(r"([가-힣]+구)")
SEOUL_GU_SET = {
    "강남구",
    "강동구",
    "강북구",
    "강서구",
    "관악구",
    "광진구",
    "구로구",
    "금천구",
    "노원구",
    "도봉구",
    "동대문구",
    "동작구",
    "마포구",
    "서대문구",
    "서초구",
    "성동구",
    "성북구",
    "송파구",
    "양천구",
    "영등포구",
    "용산구",
    "은평구",
    "종로구",
    "중구",
    "중랑구",
}

INSERT_SQL = """
    INSERT INTO events (
        event_id, title, category, place_name, address, district,
        geom, date_start, date_end, price, poster_url, detail_url,
        summary, source, raw_data, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        CASE WHEN $7::float8 IS NOT NULL AND $8::float8 IS NOT NULL
             THEN ST_SetSRID(ST_MakePoint($7, $8), 4326)
             ELSE NULL END,
        $9, $10, $11, $12, $13,
        $14, $15, $16::jsonb, false
    )
    ON CONFLICT DO NOTHING
"""

DELETE_SQL = "DELETE FROM events WHERE source = $1"

MANAGED_SOURCES = ["서울시문화행사", "서울시공공서비스예약", "서울시문화축제"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_district(*candidates: Optional[str]) -> Optional[str]:
    """여러 주소·구명 후보 중 첫 번째 서울 자치구 반환."""
    for c in candidates:
        if not c:
            continue
        c = c.strip()
        if c in SEOUL_GU_SET:
            return c
        m = DISTRICT_RE.search(c)
        if m and m.group(1) in SEOUL_GU_SET:
            return m.group(1)
        m = DISTRICT_RE_SHORT.search(c)
        if m and m.group(1) in SEOUL_GU_SET:
            return m.group(1)
    return None


def district_from_filename(path: str) -> Optional[str]:
    """서울특별시_강남구_* → '강남구' 추출."""
    base = os.path.basename(path)
    m = re.search(r"서울특별시_([가-힣]+구)_", base)
    if m and m.group(1) in SEOUL_GU_SET:
        return m.group(1)
    return None


def parse_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sanity_wgs84(lng: Optional[float], lat: Optional[float]) -> bool:
    if lng is None or lat is None:
        return False
    return LNG_MIN <= lng <= LNG_MAX and LAT_MIN <= lat <= LAT_MAX


def parse_date(s: Optional[str]) -> Optional[date]:
    """날짜 문자열 파싱. 다양한 형식 대응."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # '2026-08-13~2026-08-16' → 첫 번째 날짜만 (start용)
    if "~" in s:
        s = s.split("~")[0].strip()
    # '2026-08-13 00:00:00.0' → date 부분만
    if " " in s:
        s = s.split(" ")[0].strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_date_end(s: Optional[str]) -> Optional[date]:
    """날짜 범위에서 종료일 파싱."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    if "~" in s:
        s = s.split("~")[1].strip()
    if " " in s:
        s = s.split(" ")[0].strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def make_event_id(source: str, title: str, date_start_str: str) -> str:
    """Deterministic UUID5 from source+title+date_start."""
    key = source + "|" + title.strip() + "|" + (date_start_str or "")
    return str(uuid.uuid5(EVENT_NS, key))


def clip_text(s: Optional[str], max_len: int) -> Optional[str]:
    """Truncate to max_len."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    return s[:max_len]


# ---------------------------------------------------------------------------
# Transform functions: (row, ctx) → Optional[tuple]
# ---------------------------------------------------------------------------


def t_munhwa_haengsa(row: dict, ctx: dict) -> Optional[tuple]:
    """서울시 문화행사 정보.csv — cp949, 3950 rows."""
    title = (row.get("공연/행사명") or "").strip()
    if not title:
        return None
    title = clip_text(title, 200)
    if title is None:
        return None

    category = (row.get("분류") or "").strip() or None
    district_raw = (row.get("자치구") or "").strip()
    place_raw = (row.get("장소") or "").strip() or None
    org = (row.get("기관명") or "").strip() or None
    place_name = place_raw or org

    district = extract_district(district_raw, place_raw)
    if not district and district_raw in SEOUL_GU_SET:
        district = district_raw

    # 날짜: "2026-08-13~2026-08-16" or separate start/end columns
    date_raw = (row.get("날짜") or "").strip()
    date_start_str = (row.get("시작일") or "").strip()
    date_end_str = (row.get("종료일") or "").strip()

    if date_raw and "~" in date_raw:
        ds = parse_date(date_raw)
        de = parse_date_end(date_raw)
    else:
        ds = parse_date(date_start_str or date_raw)
        de = parse_date(date_end_str)

    price = (row.get("이용요금") or "").strip() or None
    poster_url = (row.get("대표이미지") or "").strip() or None
    detail_url = (row.get("홈페이지?주소") or row.get("홈페이지\x00주소") or "").strip() or None

    # detail_url fallback: 문화행사 detail URL
    culture_url = (row.get("문화포털상세URL") or "").strip()
    if not detail_url and culture_url:
        detail_url = culture_url

    summary_parts = []
    for field in ["프로그램소개", "기타내용"]:
        val = (row.get(field) or "").strip()
        if val:
            summary_parts.append(val)
    summary = "; ".join(summary_parts) if summary_parts else None

    # coords: 위도(Y좌표), 경도(X좌표)
    lat = parse_float(row.get("위도(Y좌표)"))
    lng = parse_float(row.get("경도(X좌표)"))
    if not sanity_wgs84(lng, lat):
        lng, lat = None, None

    event_id = make_event_id(ctx["source_tag"], title, date_raw or date_start_str)
    raw = json.dumps(row, ensure_ascii=False)

    return (
        event_id,
        title,
        category,
        place_name,
        place_raw,
        district,
        lng,
        lat,
        ds,
        de,
        price,
        poster_url,
        detail_url,
        summary,
        ctx["source_tag"],
        raw,
    )


def t_gonggong_reservation(row: dict, ctx: dict) -> Optional[tuple]:
    """서울시 문화행사 공공서비스예약 정보.csv — cp949, 655 rows."""
    title = (row.get("서비스명") or "").strip()
    if not title:
        return None
    title = clip_text(title, 200)
    if title is None:
        return None

    category = (row.get("소분류명") or row.get("대분류명") or "").strip() or None
    place_name = (row.get("장소명") or "").strip() or None
    district_raw = (row.get("지역명") or "").strip()
    district = extract_district(district_raw, place_name)
    if not district and district_raw in SEOUL_GU_SET:
        district = district_raw

    address = place_name  # 공공서비스예약 CSV는 별도 주소 없이 장소명에 포함

    # 날짜
    date_start_str = (row.get("서비스개시시작일시") or "").strip()
    date_end_str = (row.get("서비스개시종료일시") or "").strip()
    ds = parse_date(date_start_str)
    de = parse_date(date_end_str)

    price = (row.get("결제방법") or "").strip() or None
    poster_url = (row.get("이미지경로") or "").strip() or None
    detail_url = (row.get("바로가기URL") or "").strip() or None
    summary = (row.get("상세내용") or "").strip() or None

    # coords
    lng = parse_float(row.get("장소X좌표"))
    lat = parse_float(row.get("장소Y좌표"))
    if not sanity_wgs84(lng, lat):
        lng, lat = None, None

    svc_id = (row.get("서비스ID") or "").strip()
    event_id = make_event_id(ctx["source_tag"], title, svc_id or date_start_str)
    raw = json.dumps(row, ensure_ascii=False)

    return (
        event_id,
        title,
        category,
        place_name,
        address,
        district,
        lng,
        lat,
        ds,
        de,
        price,
        poster_url,
        detail_url,
        summary,
        ctx["source_tag"],
        raw,
    )


def t_munhwa_chukje(row: dict, ctx: dict) -> Optional[tuple]:
    """서울특별시_*_문화축제_*.csv — utf-8, WGS84, ~147 rows total."""
    # BOM handling
    title = (row.get("\ufeff축제명") or row.get("축제명") or "").strip()
    if not title:
        return None
    title = clip_text(title, 200)
    if title is None:
        return None

    category = "축제"
    place_name = (row.get("개최장소") or "").strip() or None
    address = (row.get("소재지도로명주소") or "").strip() or (row.get("소재지지번주소") or "").strip() or None
    district = district_from_filename(ctx["filepath"]) or extract_district(address)

    date_start_str = (row.get("축제시작일자") or "").strip()
    date_end_str = (row.get("축제종료일자") or "").strip()
    ds = parse_date(date_start_str)
    de = parse_date(date_end_str)

    summary = (row.get("축제내용") or "").strip() or None
    detail_url = (row.get("홈페이지주소") or "").strip() or None

    lat = parse_float(row.get("위도"))
    lng = parse_float(row.get("경도"))
    if not sanity_wgs84(lng, lat):
        lng, lat = None, None

    event_id = make_event_id(ctx["source_tag"], title, date_start_str)
    raw = json.dumps(row, ensure_ascii=False)

    return (
        event_id,
        title,
        category,
        place_name,
        address,
        district,
        lng,
        lat,
        ds,
        de,
        None,
        None,
        detail_url,
        summary,
        ctx["source_tag"],
        raw,
    )


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCES: list = [
    {
        "name": "munhwa_haengsa",
        "glob": "축제·행사/서울시 문화행사 정보.csv",
        "encoding": "cp949",
        "source_tag": "서울시문화행사",
        "transform": t_munhwa_haengsa,
    },
    {
        "name": "gonggong_reservation",
        "glob": "축제·행사/서울시 문화행사 공공서비스예약 정보.csv",
        "encoding": "cp949",
        "source_tag": "서울시공공서비스예약",
        "transform": t_gonggong_reservation,
    },
    {
        "name": "munhwa_chukje",
        "glob": "축제·행사/서울특별시_*_문화축제_*.csv",
        "encoding": "utf-8",
        "source_tag": "서울시문화축제",
        "transform": t_munhwa_chukje,
    },
]


# ---------------------------------------------------------------------------
# File iteration (NFC/NFD dual-glob for macOS APFS)
# ---------------------------------------------------------------------------


def iter_source_rows(spec: dict):
    """spec.glob에 매칭되는 모든 파일의 row를 yield (row, ctx, spec).

    macOS APFS는 파일명을 NFD로 저장하므로 NFC/NFD 양쪽 패턴을 시도한다.
    """
    pattern_nfc = str(CSV_ROOT / spec["glob"])
    pattern_nfd = unicodedata.normalize("NFD", pattern_nfc)
    raw_matches = list(glob.glob(pattern_nfc)) + list(glob.glob(pattern_nfd))
    # realpath + NFC 정규화로 중복 제거
    seen_paths: set = set()
    files: list = []
    for p in raw_matches:
        key = unicodedata.normalize("NFC", os.path.realpath(p))
        if key in seen_paths:
            continue
        seen_paths.add(key)
        files.append(p)
    files.sort()
    if not files:
        logging.warning("no files for source=%s glob=%s", spec["name"], pattern_nfc)
        return
    for fp in files:
        try:
            with open(fp, encoding=spec["encoding"], errors="replace") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    ctx = {
                        "source_tag": spec["source_tag"],
                        "filepath": fp,
                        "row_idx": idx,
                    }
                    yield row, ctx, spec
        except Exception as e:
            logging.error("failed to read %s: %s", fp, e)
            continue


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


async def run(env: Optional[dict], dry_run: bool) -> dict:
    """Iterate all source registries, DELETE existing, then INSERT."""
    csv.field_size_limit(sys.maxsize)
    conn: Optional[asyncpg.Connection] = None
    if not dry_run:
        conn = await asyncpg.connect(
            host=env["DB_HOST"],
            port=int(env["DB_PORT"]),
            user=env["DB_USER"],
            password=env["DB_PASSWORD"],
            database=env["DB_NAME"],
            timeout=60,
        )

    stats: dict = {
        "by_source": {},
        "total_inserted": 0,
        "total_skipped": 0,
        "total_deleted": 0,
    }
    t0 = time.time()

    try:
        tx = None
        if conn is not None:
            # Count before
            before = await conn.fetchval("SELECT COUNT(*) FROM events")
            stats["count_before"] = before

            tx = conn.transaction()
            await tx.start()

            # Delete managed sources
            for src in MANAGED_SOURCES:
                deleted = await conn.execute(DELETE_SQL, src)
                cnt = int(deleted.split(" ")[-1])
                stats["total_deleted"] += cnt
                logging.info("deleted %d rows for source=%s", cnt, src)

        seen_ids: set = set()
        for spec in SOURCES:
            src_name = spec["name"]
            stats["by_source"][src_name] = {"inserted": 0, "skipped": 0, "dup": 0}
            batch: list = []

            for row, ctx, _spec in iter_source_rows(spec):
                result = spec["transform"](row, ctx)
                if result is None:
                    stats["by_source"][src_name]["skipped"] += 1
                    stats["total_skipped"] += 1
                    continue

                eid = result[0]
                if eid in seen_ids:
                    stats["by_source"][src_name]["dup"] += 1
                    stats["total_skipped"] += 1
                    continue
                seen_ids.add(eid)

                if conn is not None:
                    batch.append(result)
                    if len(batch) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL, batch)
                        stats["by_source"][src_name]["inserted"] += len(batch)
                        stats["total_inserted"] += len(batch)
                        batch = []
                else:
                    stats["by_source"][src_name]["inserted"] += 1
                    stats["total_inserted"] += 1

            # flush
            if conn is not None and batch:
                await conn.executemany(INSERT_SQL, batch)
                stats["by_source"][src_name]["inserted"] += len(batch)
                stats["total_inserted"] += len(batch)

            logging.info(
                "source %-25s inserted=%-6d skipped=%-6d dup=%d",
                src_name,
                stats["by_source"][src_name]["inserted"],
                stats["by_source"][src_name]["skipped"],
                stats["by_source"][src_name]["dup"],
            )

        if conn is not None:
            await tx.commit()
            after = await conn.fetchval("SELECT COUNT(*) FROM events")
            stats["count_after"] = after
            logging.info("committed. before=%d after=%d", before, after)

    except Exception:
        if conn is not None and tx is not None:
            try:
                await tx.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            await conn.close()

    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


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


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load events from data/csv/축제·행사/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="", help="comma-separated source names to run (empty=all)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("CSV_ROOT=%s dry_run=%s", CSV_ROOT, args.dry_run)

    global SOURCES
    if args.only:
        only_set = {s.strip() for s in args.only.split(",") if s.strip()}
        SOURCES = [s for s in SOURCES if s["name"] in only_set]
        logging.info("filtered SOURCES to: %s", [s["name"] for s in SOURCES])

    if args.dry_run:
        stats = await run(env=None, dry_run=True)
    else:
        env = load_env(REPO_ROOT / ".env")
        if not env.get("DB_HOST"):
            env = load_env(REPO_ROOT / "backend" / ".env")
        if not env.get("DB_HOST"):
            raise RuntimeError("DB_HOST not found in .env")
        stats = await run(env=env, dry_run=False)

    logging.info("STATS:\n%s", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
