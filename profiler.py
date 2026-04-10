#!/usr/bin/env python3
"""
LocalBiz Intelligence — CSV 데이터 프로파일링 스크립트
=====================================================
Google Drive에서 다운받은 CSV 폴더를 순회하면서
각 파일의 메타 정보, 샘플, 카테고리 값 등을 추출합니다.

사용법:
    python csv_profiler.py --input-dir ./csv_data/ --output ./profile_report.md

요구사항:
    pip install pandas
"""

import os
import sys
import argparse
import glob
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    print("❌ pandas가 설치되어 있지 않습니다. 먼저 설치해주세요:")
    print("   pip install pandas")
    sys.exit(1)


# ============================================================
# 설정
# ============================================================

SAMPLE_ROWS = 3  # 샘플 튜플 수
CATEGORY_THRESHOLD = 30  # distinct 값이 이 이하면 "카테고리성"으로 판단
COORD_KEYWORDS = [
    "위도",
    "경도",
    "lat",
    "lng",
    "longitude",
    "latitude",
    "x좌표",
    "y좌표",
    "x",
    "y",
]
ADDRESS_KEYWORDS = ["주소", "도로명", "지번", "address", "소재지", "위치"]
NAME_KEYWORDS = [
    "상호",
    "이름",
    "명칭",
    "name",
    "시설명",
    "장소명",
    "업소명",
    "사업장명",
]
CATEGORY_KEYWORDS = ["업종", "분류", "카테고리", "category", "유형", "종류", "업태"]

# 인코딩 후보 (한국 공공데이터 CSV에서 흔한 인코딩)
ENCODINGS = ["utf-8", "cp949", "euc-kr", "utf-8-sig", "latin1"]


# ============================================================
# 유틸리티
# ============================================================


def read_csv_safe(filepath, nrows=None):
    """여러 인코딩을 시도하여 CSV를 읽습니다."""
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(filepath, encoding=enc, nrows=nrows, low_memory=False)
            return df, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            # 인코딩 외 에러는 바로 반환
            return None, f"Error: {e}"
    return None, "인코딩 실패"


def detect_column_role(col_name):
    """칼럼명으로 역할을 추정합니다."""
    col_lower = str(col_name).lower().strip()

    for kw in COORD_KEYWORDS:
        if kw in col_lower:
            return "📍좌표"
    for kw in ADDRESS_KEYWORDS:
        if kw in col_lower:
            return "🏠주소"
    for kw in NAME_KEYWORDS:
        if kw in col_lower:
            return "🏪이름"
    for kw in CATEGORY_KEYWORDS:
        if kw in col_lower:
            return "📂카테고리"
    return ""


def format_filesize(size_bytes):
    """파일 크기를 사람이 읽기 쉬운 형태로 변환합니다."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# ============================================================
# 프로파일링 함수
# ============================================================


def profile_csv(filepath):
    """단일 CSV 파일을 프로파일링합니다."""
    result = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "folder": os.path.basename(os.path.dirname(filepath)),
        "filesize": format_filesize(os.path.getsize(filepath)),
        "error": None,
    }

    # 전체 읽기 (건수 파악용)
    df_full, enc = read_csv_safe(filepath)
    if df_full is None:
        result["error"] = enc
        return result

    result["encoding"] = enc
    result["row_count"] = len(df_full)
    result["col_count"] = len(df_full.columns)
    result["columns"] = []

    for col in df_full.columns:
        col_info = {
            "name": str(col),
            "dtype": str(df_full[col].dtype),
            "null_count": int(df_full[col].isna().sum()),
            "null_pct": round(df_full[col].isna().sum() / len(df_full) * 100, 1)
            if len(df_full) > 0
            else 0,
            "nunique": int(df_full[col].nunique()),
            "role": detect_column_role(col),
        }

        # 카테고리성 칼럼이면 distinct 값 전체 나열
        if col_info["nunique"] <= CATEGORY_THRESHOLD and col_info["nunique"] > 0:
            distinct_vals = df_full[col].dropna().unique().tolist()
            col_info["distinct_values"] = [
                str(v)[:50] for v in sorted(distinct_vals, key=str)
            ]
        else:
            col_info["distinct_values"] = None

        result["columns"].append(col_info)

    # 샘플 데이터
    sample_df = df_full.head(SAMPLE_ROWS)
    result["sample"] = sample_df.to_dict("records")

    # 좌표 유무
    coord_cols = [c for c in result["columns"] if c["role"] == "📍좌표"]
    result["has_coordinates"] = len(coord_cols) > 0
    result["coord_cols"] = [c["name"] for c in coord_cols]

    # 주소 유무
    addr_cols = [c for c in result["columns"] if c["role"] == "🏠주소"]
    result["has_address"] = len(addr_cols) > 0
    result["addr_cols"] = [c["name"] for c in addr_cols]

    # 이름 칼럼
    name_cols = [c for c in result["columns"] if c["role"] == "🏪이름"]
    result["name_cols"] = [c["name"] for c in name_cols]

    # 카테고리 칼럼
    cat_cols = [c for c in result["columns"] if c["role"] == "📂카테고리"]
    result["category_cols"] = [c["name"] for c in cat_cols]

    return result


# ============================================================
# 보고서 생성
# ============================================================


def generate_report(profiles, output_path):
    """프로파일링 결과를 마크다운 보고서로 생성합니다."""
    lines = []

    # 헤더
    lines.append("# 📊 CSV 데이터 프로파일링 보고서")
    lines.append(f"> 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 총 파일 수: {len(profiles)}개")
    lines.append("")

    # 전체 요약
    lines.append("---")
    lines.append("## 1. 전체 요약")
    lines.append("")
    lines.append("| No | 폴더 | 파일명 | 건수 | 칼럼수 | 크기 | 좌표 | 주소 | 인코딩 |")
    lines.append("| --- | --- | --- | ---: | ---: | --- | :---: | :---: | --- |")

    for i, p in enumerate(profiles, 1):
        if p.get("error"):
            lines.append(
                f"| {i} | {p['folder']} | {p['filename']} | ❌ | - | {p['filesize']} | - | - | {p['error']} |"
            )
        else:
            coord = "✅" if p["has_coordinates"] else "❌"
            addr = "✅" if p["has_address"] else "❌"
            lines.append(
                f"| {i} | {p['folder']} | {p['filename']} | {p['row_count']:,} | {p['col_count']} | {p['filesize']} | {coord} | {addr} | {p['encoding']} |"
            )

    lines.append("")

    # 총 건수
    total_rows = sum(p.get("row_count", 0) for p in profiles)
    lines.append(f"**총 레코드 수: {total_rows:,}건**")
    lines.append("")

    # 폴더별 상세
    lines.append("---")
    lines.append("## 2. 파일별 상세")
    lines.append("")

    # 폴더별 그룹핑
    folders = {}
    for p in profiles:
        folder = p["folder"]
        if folder not in folders:
            folders[folder] = []
        folders[folder].append(p)

    file_no = 0
    for folder, folder_profiles in folders.items():
        lines.append(f"### 📁 {folder}")
        lines.append("")

        for p in folder_profiles:
            file_no += 1
            lines.append(f"#### {file_no}. {p['filename']}")

            if p.get("error"):
                lines.append(f"> ❌ 읽기 실패: {p['error']}")
                lines.append("")
                continue

            lines.append(
                f"- 건수: **{p['row_count']:,}**건 | 칼럼: **{p['col_count']}**개 | 크기: {p['filesize']} | 인코딩: {p['encoding']}"
            )

            # 감지된 역할
            if p["name_cols"]:
                lines.append(f"- 🏪 이름 칼럼: {', '.join(p['name_cols'])}")
            if p["coord_cols"]:
                lines.append(f"- 📍 좌표 칼럼: {', '.join(p['coord_cols'])}")
            if p["addr_cols"]:
                lines.append(f"- 🏠 주소 칼럼: {', '.join(p['addr_cols'])}")
            if p["category_cols"]:
                lines.append(f"- 📂 카테고리 칼럼: {', '.join(p['category_cols'])}")

            lines.append("")

            # 칼럼 테이블
            lines.append("**칼럼 구조:**")
            lines.append("")
            lines.append("| 칼럼명 | 타입 | NULL% | 유니크 | 역할 | 비고 |")
            lines.append("| --- | --- | ---: | ---: | --- | --- |")

            for col in p["columns"]:
                note = ""
                if (
                    col["distinct_values"] is not None
                    and len(col["distinct_values"]) <= 10
                ):
                    note = f"값: {', '.join(col['distinct_values'][:10])}"
                elif col["distinct_values"] is not None:
                    note = f"값: {', '.join(col['distinct_values'][:5])}... (총 {col['nunique']}종)"

                lines.append(
                    f"| {col['name']} | {col['dtype']} | {col['null_pct']}% | {col['nunique']:,} | {col['role']} | {note} |"
                )

            lines.append("")

            # 샘플 데이터
            lines.append("**샘플 데이터 (상위 3건):**")
            lines.append("")

            if p["sample"]:
                # 칼럼명이 많으면 세로로 표시
                if p["col_count"] > 8:
                    for si, row in enumerate(p["sample"], 1):
                        lines.append(f"<details><summary>샘플 {si}</summary>")
                        lines.append("")
                        for k, v in row.items():
                            val_str = str(v)[:80] if pd.notna(v) else "(NULL)"
                            lines.append(f"- **{k}**: {val_str}")
                        lines.append("")
                        lines.append("</details>")
                        lines.append("")
                else:
                    # 칼럼이 적으면 테이블로
                    cols = list(p["sample"][0].keys())
                    lines.append("| " + " | ".join(str(c)[:15] for c in cols) + " |")
                    lines.append("| " + " | ".join("---" for _ in cols) + " |")
                    for row in p["sample"]:
                        vals = []
                        for c in cols:
                            v = row[c]
                            vals.append(str(v)[:20] if pd.notna(v) else "(NULL)")
                        lines.append("| " + " | ".join(vals) + " |")
                    lines.append("")

            lines.append("---")
            lines.append("")

    # 카테고리 칼럼 종합
    lines.append("## 3. 카테고리성 칼럼 종합")
    lines.append("")
    lines.append("표준 카테고리 매핑 설계를 위한 참고 자료:")
    lines.append("")

    for p in profiles:
        if p.get("error"):
            continue
        for col in p["columns"]:
            if col["role"] == "📂카테고리" and col["distinct_values"]:
                lines.append(
                    f"**{p['folder']}/{p['filename']} → {col['name']}** ({col['nunique']}종)"
                )
                for v in col["distinct_values"]:
                    lines.append(f"  - {v}")
                lines.append("")

    # ETL 매핑 체크리스트
    lines.append("---")
    lines.append("## 4. ETL 매핑 체크리스트")
    lines.append("")
    lines.append("각 파일에서 places/events 테이블로 매핑할 때 확인할 사항:")
    lines.append("")
    lines.append("| 타겟 칼럼 | 확인 사항 |")
    lines.append("| --- | --- |")
    lines.append("| name | 🏪이름 칼럼이 감지되었는가? |")
    lines.append(
        "| category / sub_category | 📂카테고리 칼럼의 distinct 값을 우리 표준으로 매핑 |"
    )
    lines.append("| address | 🏠주소 칼럼이 있는가? 도로명/지번 구분 |")
    lines.append("| lat / lng | 📍좌표 칼럼이 있는가? NULL 비율은? |")
    lines.append("| district | 주소에서 자치구 추출 가능한가? |")
    lines.append("| phone | 전화번호 칼럼이 있는가? |")
    lines.append("| raw_data | 나머지 전체 칼럼 → JSONB 보존 |")
    lines.append("")

    # 파일 저장
    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return report_text


# ============================================================
# 메인
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="CSV 데이터 프로파일링 스크립트")
    parser.add_argument(
        "--input-dir", required=True, help="CSV 파일이 있는 최상위 디렉토리"
    )
    parser.add_argument(
        "--output",
        default="./profile_report.md",
        help="보고서 출력 경로 (기본: ./profile_report.md)",
    )
    parser.add_argument(
        "--max-files", type=int, default=None, help="최대 처리 파일 수 (테스트용)"
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    if not os.path.isdir(input_dir):
        print(f"❌ 디렉토리가 존재하지 않습니다: {input_dir}")
        sys.exit(1)

    # CSV 파일 탐색 (하위 폴더 포함)
    csv_files = sorted(
        glob.glob(os.path.join(input_dir, "**", "*.csv"), recursive=True)
    )

    # TSV도 포함
    csv_files += sorted(
        glob.glob(os.path.join(input_dir, "**", "*.tsv"), recursive=True)
    )

    if not csv_files:
        print(f"❌ CSV 파일이 없습니다: {input_dir}")
        sys.exit(1)

    if args.max_files:
        csv_files = csv_files[: args.max_files]

    print("📊 CSV 프로파일링 시작")
    print(f"   입력: {input_dir}")
    print(f"   파일: {len(csv_files)}개")
    print(f"   출력: {args.output}")
    print()

    profiles = []
    for i, filepath in enumerate(csv_files, 1):
        rel_path = os.path.relpath(filepath, input_dir)
        print(f"  [{i}/{len(csv_files)}] {rel_path} ...", end=" ", flush=True)

        try:
            profile = profile_csv(filepath)
            profiles.append(profile)

            if profile.get("error"):
                print(f"❌ {profile['error']}")
            else:
                print(f"✅ {profile['row_count']:,}건, {profile['col_count']}칼럼")
        except Exception as e:
            print(f"❌ 예외: {e}")
            profiles.append(
                {
                    "filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "folder": os.path.basename(os.path.dirname(filepath)),
                    "filesize": format_filesize(os.path.getsize(filepath)),
                    "error": str(e),
                }
            )

    print()
    print("📝 보고서 생성 중...")
    generate_report(profiles, args.output)
    print(f"✅ 완료: {args.output}")
    print()

    # 간단 통계
    success = [p for p in profiles if not p.get("error")]
    total_rows = sum(p.get("row_count", 0) for p in success)
    print(f"   성공: {len(success)}/{len(profiles)}개 파일")
    print(f"   총 레코드: {total_rows:,}건")


if __name__ == "__main__":
    main()
