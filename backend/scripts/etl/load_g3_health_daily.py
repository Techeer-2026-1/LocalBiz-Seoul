"""Load G3 (건강·일상) multi-CSV into places.

File   : backend/scripts/etl/load_g3_health_daily.py
Plan   : .sisyphus/plans/2026-04-13-etl-g3-health-daily/plan.md
Date   : 2026-04-12
Scope  : 19 source (의료 6 + 체육시설 5 + 주차장 3 + 공공시설 5 + 공원 1), ~77K row

Source notes:
    TM 인허가 CSV (약국/동물병원/병원/체력단련장/무도장/썰매장/요트장/수영장):
        `좌표정보(X)/(Y)` = EPSG:5174 (Korea 2000 중부원점 Bessel). plan #14 검증.
    WGS84 직접:
        병의원/응급실: `병원경도/병원위도`
        거주자우선: `거주자우선주차구획위도/경도`
        한강주차: `위치정보(위도)/(경도)`
        공중화장실: `x 좌표/y 좌표`
        공원음수대: `X좌표(LNG)/Y좌표(LAT)` (X=LNG, Y=LAT)
        안심택배함: `WGS X 좌표/Y 좌표`
        기타 표준: `위도/경도`

Execution:
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_g3_health_daily --dry-run
    python -m scripts.etl.load_g3_health_daily

Invariants: #1, #3, #8, #9, #19.
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
from pathlib import Path
from typing import Optional

import asyncpg

from scripts.etl.validate_category import validate_category

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
CSV_ROOT: Path = REPO_ROOT / "data/csv"
BATCH_SIZE: int = 1000

LNG_MIN, LNG_MAX = 126.7, 127.3
LAT_MIN, LAT_MAX = 37.4, 37.7
TM_X_MIN, TM_X_MAX = 180000.0, 220000.0
TM_Y_MIN, TM_Y_MAX = 435000.0, 475000.0

INSERT_SQL_WGS = """
    INSERT INTO places (
        place_id, name, category, sub_category, address, district,
        geom, phone, raw_data, source, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        ST_SetSRID(ST_MakePoint($7, $8), 4326),
        $9, $10::jsonb, $11, 0
    )
"""

INSERT_SQL_TM = """
    INSERT INTO places (
        place_id, name, category, sub_category, address, district,
        geom, phone, raw_data, source, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        ST_Transform(ST_SetSRID(ST_MakePoint($7, $8), 5174), 4326),
        $9, $10::jsonb, $11, 0
    )
"""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_district(*candidates: Optional[str]) -> Optional[str]:
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


def sanity_tm(x: Optional[float], y: Optional[float]) -> bool:
    if x is None or y is None:
        return False
    return TM_X_MIN <= x <= TM_X_MAX and TM_Y_MIN <= y <= TM_Y_MAX


def clip_phone(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    return s[:20]


def make_place_id(source_slug: str, natural_id: str, max_len: int = 36) -> Optional[str]:
    natural_id = natural_id.strip()
    if not natural_id:
        return None
    candidate = source_slug + "_" + natural_id
    if len(candidate) <= max_len:
        return candidate
    return candidate[:max_len]


# ---------------------------------------------------------------------------
# Common transform for 인허가 TM CSVs (6 sources: 약국/동물병원/병원/체력단련/무도장/썰매장/요트장/수영장)
# ---------------------------------------------------------------------------


def _t_inheoga_tm(row: dict, ctx: dict, category: str, sub_default: Optional[str]) -> Optional[tuple]:
    manage = (row.get("관리번호") or "").strip()
    if manage == "mng_no" or not manage:
        return None
    status = (row.get("영업상태명") or "").strip()
    if status and status != "영업/정상":
        return None
    name = (row.get("사업장명") or "").strip()
    if not name:
        return None
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    x = parse_float(row.get("좌표정보(X)"))
    y = parse_float(row.get("좌표정보(Y)"))
    if not sanity_tm(x, y):
        return None
    phone = clip_phone(row.get("전화번호"))
    sub_raw = (row.get("업태구분명") or "").strip() or (row.get("문화체육업종명") or "").strip() or sub_default
    place_id = make_place_id(ctx["source_slug"], manage)
    if place_id is None:
        return None
    cat = validate_category(category, sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub_raw, address, district, x, y, phone, raw, ctx["source_tag"])


def t_pharmacy(row, ctx):
    return _t_inheoga_tm(row, ctx, "의료", "약국")


def t_animal_hospital(row, ctx):
    return _t_inheoga_tm(row, ctx, "의료", "동물병원")


def t_general_hospital_inheoga(row, ctx):
    return _t_inheoga_tm(row, ctx, "의료", "병원")


def t_gym(row, ctx):
    return _t_inheoga_tm(row, ctx, "체육시설", "체력단련장")


def t_dance_hall(row, ctx):
    return _t_inheoga_tm(row, ctx, "체육시설", "무도장")


def t_sledding(row, ctx):
    return _t_inheoga_tm(row, ctx, "체육시설", "썰매장")


def t_yacht(row, ctx):
    return _t_inheoga_tm(row, ctx, "체육시설", "요트장")


def t_swimming(row, ctx):
    return _t_inheoga_tm(row, ctx, "체육시설", "수영장")


# ---------------------------------------------------------------------------
# Source-specific transforms
# ---------------------------------------------------------------------------


def t_hospital_loc(row, ctx):
    """서울시 병의원 위치 정보 (WGS84, 병원경도/병원위도, 기관명/주소/병원분류명)."""
    name = (row.get("기관명") or "").strip()
    if not name:
        return None
    address = (row.get("주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("병원경도"))
    lat = parse_float(row.get("병원위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("병원분류명") or "").strip() or "병의원"
    phone = clip_phone(row.get("대표전화1"))
    natural = (row.get("기관ID") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("의료", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_emergency(row, ctx):
    """서울시 응급실 (WGS84, 병원경도/병원위도, same schema as 병의원)."""
    name = (row.get("기관명") or "").strip()
    if not name:
        return None
    address = (row.get("주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("병원경도"))
    lat = parse_float(row.get("병원위도"))
    if not sanity_wgs84(lng, lat):
        return None
    phone = clip_phone(row.get("대표전화1") or row.get("응급실전화"))
    natural = (row.get("기관ID") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("의료", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "응급실", address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_dementia(row, ctx):
    """서울시 치매안심센터."""
    name = (row.get("치매센터명") or "").strip()
    if not name:
        return None
    address = (row.get("소재지도로명주소") or "").strip() or (row.get("소재지지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("치매센터유형") or "").strip() or "치매안심센터"
    phone = clip_phone(row.get("전화번호"))
    natural = name  # 치매센터명 unique
    place_id = make_place_id(ctx["source_slug"], natural + "_" + str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("의료", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_public_parking(row, ctx):
    """서울시 공영주차장 (위도/경도 직접, 빈 값 row 다수 예상)."""
    name = (row.get("주차장명") or "").strip()
    if not name:
        return None
    address = (row.get("주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("주차장 종류") or "").strip() or "공영"
    phone = clip_phone(row.get("운영시간 전화번호") or row.get("전화번호"))
    natural = (row.get("주차장코드") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("주차장", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_resident_parking(row, ctx):
    """거주자우선주차 (소재지도로명주소에서 district 추출)."""
    addr = (row.get("소재지도로명주소") or row.get("소재지지번주소") or "").strip()
    area = (row.get("거주자우선주차구역명") or "").strip()
    name = area or "거주자우선주차"
    district = extract_district(addr) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("거주자우선주차구획경도"))
    lat = parse_float(row.get("거주자우선주차구획위도"))
    if not sanity_wgs84(lng, lat):
        return None
    natural = (row.get("거주자우선주차구획번호") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("주차장", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "거주자우선", addr or None, district, lng, lat, None, raw, ctx["source_tag"])


def _noop_reference_fix():
    """keep helper references for future use (no-op)."""
    return None


def t_hangang_parking(row, ctx):
    """한강공원 주차장 정보."""
    name = ((row.get("지구별") or "").strip() + " " + (row.get("주차장별") or "").strip()).strip()
    if not name:
        return None
    lng = parse_float(row.get("위치정보(경도)"))
    lat = parse_float(row.get("위치정보(위도)"))
    if not sanity_wgs84(lng, lat):
        return None
    # 한강공원은 여러 구 걸침 — 주소 파싱 없으면 row idx 기반 dummy district 불가
    # 주요 지구별로 근사 매핑은 과도. 좌표에서 역지오코딩 대신 "영등포구" 기본 (한강공원 본부 위치)
    district = "영등포구"
    place_id = make_place_id(ctx["source_slug"], str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("주차장", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "한강공원", None, district, lng, lat, None, raw, ctx["source_tag"])


def t_public_toilet(row, ctx):
    """공중화장실 (x 좌표 / y 좌표 WGS84)."""
    name = (row.get("공중화장실명") or row.get("화장실명") or "").strip() or "공중화장실"
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("x 좌표"))
    lat = parse_float(row.get("y 좌표"))
    if not sanity_wgs84(lng, lat):
        return None
    place_id = make_place_id(ctx["source_slug"], str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "공중화장실", address, district, lng, lat, None, raw, ctx["source_tag"])


def t_water_fountain(row, ctx):
    """공원음수대 (X좌표(LNG) / Y좌표(LAT))."""
    park_name = (row.get("공원 명") or "").strip()
    name = (park_name + " 음수대") if park_name else "공원 음수대"
    address = (row.get("지번주소") or "").strip() or (row.get("도로명주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("X좌표(LNG)"))
    lat = parse_float(row.get("Y좌표(LAT)"))
    if not sanity_wgs84(lng, lat):
        return None
    natural = (row.get("컨텐츠 아이디") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "공원음수대", address, district, lng, lat, None, raw, ctx["source_tag"])


def t_safe_delivery_box(row, ctx):
    """안심택배함 (WGS X/Y 좌표, '자치구'/'안심 명'/'안심 주소')."""
    name = (row.get("안심 명") or "").strip() or "안심택배함"
    address = (row.get("안심 주소") or "").strip() or None
    district = (row.get("자치구") or "").strip()
    if district not in SEOUL_GU_SET:
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("WGS X 좌표"))
    lat = parse_float(row.get("WGS Y 좌표"))
    if not sanity_wgs84(lng, lat):
        return None
    place_id = make_place_id(ctx["source_slug"], str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "안심택배함", address, district, lng, lat, None, raw, ctx["source_tag"])


def t_tow_yard(row, ctx):
    """견인차량보관소."""
    name = (row.get("견인차량보관소명") or row.get("보관소명") or "").strip() or "견인차량보관소"
    address = (row.get("소재지도로명주소") or row.get("도로명주소") or row.get("소재지지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    phone = clip_phone(row.get("전화번호"))
    place_id = make_place_id(ctx["source_slug"], str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "견인차량보관소", address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_major_park(row, ctx):
    """서울시 주요 공원현황 (WGS84 + GRS80TM, WGS84 사용, '지역'/'공원주소'/'공원명')."""
    name = (row.get("공원명") or "").strip()
    if not name:
        return None
    address = (row.get("공원주소") or "").strip() or None
    district = (row.get("지역") or "").strip()
    if district not in SEOUL_GU_SET:
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("X좌표(WGS84)"))
    lat = parse_float(row.get("Y좌표(WGS84)"))
    if not sanity_wgs84(lng, lat):
        return None
    phone = clip_phone(row.get("전화번호"))
    natural = (row.get("연번") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("공원", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, "주요공원", address, district, lng, lat, phone, raw, ctx["source_tag"])


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

API_DIR = "의료 시설/국립중앙의료원_전국 약국 정보 조회 서비스(API)(202507)"

SOURCES: list = [
    # 의료 (6)
    {
        "name": "pharmacy",
        "glob": f"{API_DIR}/서울시 약국 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "pharm",
        "source_tag_template": "seoul_pharmacy_inheoga",
        "coord": "tm5174",
        "transform": t_pharmacy,
    },
    {
        "name": "hospital_loc",
        "glob": f"{API_DIR}/서울시 병의원 위치 정보.csv",
        "encoding": "cp949",
        "source_slug": "hoslo",
        "source_tag_template": "seoul_hospital_loc",
        "coord": "wgs84",
        "transform": t_hospital_loc,
    },
    {
        "name": "animal_hospital",
        "glob": "의료 시설/서울시 동물병원 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "ahosp",
        "source_tag_template": "seoul_animal_hospital_inheoga",
        "coord": "tm5174",
        "transform": t_animal_hospital,
    },
    {
        "name": "general_hospital",
        "glob": "의료 시설/서울시 병원 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "ghosp",
        "source_tag_template": "seoul_general_hospital_inheoga",
        "coord": "tm5174",
        "transform": t_general_hospital_inheoga,
    },
    {
        "name": "emergency",
        "glob": "의료 시설/서울시 응급실 위치 정보.csv",
        "encoding": "cp949",
        "source_slug": "emerg",
        "source_tag_template": "seoul_emergency_room",
        "coord": "wgs84",
        "transform": t_emergency,
    },
    {
        "name": "dementia",
        "glob": "의료 시설/서울시 치매안심센터(표준데이터).csv",
        "encoding": "cp949",
        "source_slug": "demen",
        "source_tag_template": "seoul_dementia_center",
        "coord": "wgs84",
        "transform": t_dementia,
    },
    # 체육시설 (5)
    {
        "name": "gym",
        "glob": "체육시설/서울시 체력단련장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "gym",
        "source_tag_template": "seoul_gym_inheoga",
        "coord": "tm5174",
        "transform": t_gym,
    },
    {
        "name": "dance_hall",
        "glob": "체육시설/서울시 무도장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "dance",
        "source_tag_template": "seoul_dance_hall_inheoga",
        "coord": "tm5174",
        "transform": t_dance_hall,
    },
    {
        "name": "sledding",
        "glob": "체육시설/서울시 썰매장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "sled",
        "source_tag_template": "seoul_sledding_inheoga",
        "coord": "tm5174",
        "transform": t_sledding,
    },
    {
        "name": "yacht",
        "glob": "체육시설/서울시 요트장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "yacht",
        "source_tag_template": "seoul_yacht_inheoga",
        "coord": "tm5174",
        "transform": t_yacht,
    },
    {
        "name": "swimming",
        "glob": f"{API_DIR}/서울시 수영장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "swim",
        "source_tag_template": "seoul_swimming_inheoga",
        "coord": "tm5174",
        "transform": t_swimming,
    },
    # 주차장 (3)
    {
        "name": "public_parking",
        "glob": "주차장/서울시 공영주차장 안내 정보.csv",
        "encoding": "cp949",
        "source_slug": "pkpub",
        "source_tag_template": "seoul_public_parking",
        "coord": "wgs84",
        "transform": t_public_parking,
    },
    {
        "name": "resident_parking",
        "glob": f"{API_DIR}/서울시 거주자우선주차정보(표준 데이터).csv",
        "encoding": "cp949",
        "source_slug": "pkres",
        "source_tag_template": "seoul_resident_parking",
        "coord": "wgs84",
        "transform": t_resident_parking,
    },
    {
        "name": "hangang_parking",
        "glob": "주차장/한강공원 주차장 정보.csv",
        "encoding": "cp949",
        "source_slug": "pkhan",
        "source_tag_template": "seoul_hangang_parking",
        "coord": "wgs84",
        "transform": t_hangang_parking,
    },
    # 공공시설 (5)
    {
        "name": "public_toilet",
        "glob": f"{API_DIR}/서울시 공중화장실 위치정보.csv",
        "encoding": "cp949",
        "source_slug": "toilet",
        "source_tag_template": "seoul_public_toilet",
        "coord": "wgs84",
        "transform": t_public_toilet,
    },
    {
        "name": "water_fountain",
        "glob": f"{API_DIR}/서울시 공원음수대 정보 조회.csv",
        "encoding": "cp949",
        "source_slug": "water",
        "source_tag_template": "seoul_water_fountain",
        "coord": "wgs84",
        "transform": t_water_fountain,
    },
    {
        "name": "safe_delivery_box",
        "glob": f"{API_DIR}/서울시 안심택배함 설치 장소.csv",
        "encoding": "cp949",
        "source_slug": "sdbox",
        "source_tag_template": "seoul_safe_delivery_box",
        "coord": "wgs84",
        "transform": t_safe_delivery_box,
    },
    {
        "name": "tow_yard",
        "glob": f"{API_DIR}/서울시 견인차량보관소(표준 데이터).csv",
        "encoding": "cp949",
        "source_slug": "towyd",
        "source_tag_template": "seoul_tow_yard",
        "coord": "wgs84",
        "transform": t_tow_yard,
    },
    # 공원 (1)
    {
        "name": "major_park",
        "glob": f"{API_DIR}/서울시 주요 공원현황.csv",
        "encoding": "cp949",
        "source_slug": "mpark",
        "source_tag_template": "seoul_major_park",
        "coord": "wgs84",
        "transform": t_major_park,
    },
]


# ---------------------------------------------------------------------------
# Execution (pattern copied from load_g2_public_cultural.py)
# ---------------------------------------------------------------------------


def iter_source_rows(spec: dict):
    pattern_nfc = str(CSV_ROOT / spec["glob"])
    pattern_nfd = unicodedata.normalize("NFD", pattern_nfc)
    raw_matches = list(glob.glob(pattern_nfc)) + list(glob.glob(pattern_nfd))
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
            with open(fp, encoding=spec["encoding"]) as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    ctx = {
                        "source_slug": spec["source_slug"],
                        "source_tag": spec["source_tag_template"],
                        "filepath": fp,
                        "row_idx": idx,
                    }
                    yield row, ctx, spec
        except Exception as e:
            logging.error("failed to read %s: %s", fp, e)
            continue


async def run(env: Optional[dict], dry_run: bool) -> dict:
    csv.field_size_limit(sys.maxsize)
    conn = None
    if not dry_run:
        conn = await asyncpg.connect(
            host=env["DB_HOST"],
            port=int(env["DB_PORT"]),
            user=env["DB_USER"],
            password=env["DB_PASSWORD"],
            database=env["DB_NAME"],
            timeout=60,
        )
    stats: dict = {"by_source": {}, "total_inserted": 0, "total_skipped": 0}
    t0 = time.time()
    tx = None
    try:
        if conn is not None:
            tx = conn.transaction()
            await tx.start()
        seen_ids: set = set()
        for spec in SOURCES:
            src_name = spec["name"]
            stats["by_source"][src_name] = {"inserted": 0, "skipped": 0, "dup": 0}
            batch_wgs: list = []
            batch_tm: list = []
            for row, ctx, _ in iter_source_rows(spec):
                result = spec["transform"](row, ctx)
                if result is None:
                    stats["by_source"][src_name]["skipped"] += 1
                    stats["total_skipped"] += 1
                    continue
                pid = result[0]
                if pid in seen_ids:
                    stats["by_source"][src_name]["dup"] += 1
                    stats["total_skipped"] += 1
                    continue
                seen_ids.add(pid)
                if spec["coord"] == "wgs84":
                    batch_wgs.append(result)
                else:
                    batch_tm.append(result)
                if conn is not None:
                    if len(batch_wgs) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL_WGS, batch_wgs)
                        stats["by_source"][src_name]["inserted"] += len(batch_wgs)
                        stats["total_inserted"] += len(batch_wgs)
                        batch_wgs = []
                    if len(batch_tm) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL_TM, batch_tm)
                        stats["by_source"][src_name]["inserted"] += len(batch_tm)
                        stats["total_inserted"] += len(batch_tm)
                        batch_tm = []
                else:
                    stats["by_source"][src_name]["inserted"] += 1
                    stats["total_inserted"] += 1
            if conn is not None:
                if batch_wgs:
                    await conn.executemany(INSERT_SQL_WGS, batch_wgs)
                    stats["by_source"][src_name]["inserted"] += len(batch_wgs)
                    stats["total_inserted"] += len(batch_wgs)
                if batch_tm:
                    await conn.executemany(INSERT_SQL_TM, batch_tm)
                    stats["by_source"][src_name]["inserted"] += len(batch_tm)
                    stats["total_inserted"] += len(batch_tm)
            logging.info(
                "source %-22s inserted=%-6d skipped=%-6d dup=%d",
                src_name,
                stats["by_source"][src_name]["inserted"],
                stats["by_source"][src_name]["skipped"],
                stats["by_source"][src_name]["dup"],
            )
        if conn is not None:
            null_geom = await conn.fetchval("SELECT COUNT(*) FROM places WHERE geom IS NULL")
            if null_geom > 0:
                raise RuntimeError("null geom count=" + str(null_geom))
            await tx.commit()
            logging.info("transaction committed (null_geom=0)")
    except Exception:
        if tx is not None:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global SOURCES
    if args.only:
        only_set = {s.strip() for s in args.only.split(",") if s.strip()}
        SOURCES = [s for s in SOURCES if s["name"] in only_set]
    if args.dry_run:
        stats = await run(env=None, dry_run=True)
    else:
        env = load_env(REPO_ROOT / "backend" / ".env")
        if not env.get("DB_HOST"):
            raise RuntimeError("DB_HOST not in backend/.env")
        stats = await run(env=env, dry_run=False)
    logging.info("STATS:\n%s", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
