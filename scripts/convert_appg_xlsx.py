"""
Convert the mysociety APPG workbook to filtered CSV siblings.

Reads the `register`, `members`, and `categories` sheets from the workbook,
filters to UK-parliament APPGs only (devolved groups excluded per plan),
and writes three CSVs next to the workbook:

  - register.csv   (one row per UK APPG, slimmed column set)
  - members.csv    (memberships whose appg_slug is in the UK register)
  - categories.csv (category links whose appg_slug is in the UK register)

Re-running against the same workbook produces byte-identical output.

Source: https://pages.mysociety.org/appg_membership
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import openpyxl

DATA_DIR = Path(__file__).resolve().parent.parent / "Data" / "appg"
DEFAULT_XLSX = DATA_DIR / "appg_groups_and_memberships.xlsx"

REGISTER_COLUMNS = [
    "slug",
    "title",
    "purpose",
    "categories",
    "source_url",
    "secretariat",
    "website",
    "registered_contact_name",
    "date_of_most_recent_agm",
]

MEMBERS_COLUMNS = [
    "name",
    "officer_role",
    "twfy_id",
    "mnis_id",
    "canon_name",
    "appg",
    "is_officer",
    "member_type",
    "source",
    "last_updated",
    "url_source",
    "removed",
]

CATEGORIES_COLUMNS = [
    "appg_slug",
    "category_slug",
    "category_name",
]

UK_PARLIAMENT = "uk"


def _sheet_rows(wb, sheet_name: str) -> tuple[list[str], list[dict]]:
    ws = wb[sheet_name]
    headers: list[str] | None = None
    rows: list[dict] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = list(row)
            continue
        rows.append(dict(zip(headers, row)))
    if headers is None:
        raise ValueError(f"sheet {sheet_name!r} has no header row")
    return headers, rows


def _format_cell(value):
    """Stable string rendering for CSV output.

    Booleans → 'True'/'False' (matches openpyxl/source conventions).
    Datetimes → ISO 'YYYY-MM-DD HH:MM:SS' (matches source formatting).
    None → empty string.
    Everything else → str().
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    # datetime is a subclass of date; handle datetime first
    try:
        import datetime as _dt

        if isinstance(value, _dt.datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, _dt.date):
            return value.strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(value)


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_format_cell(row.get(col)) for col in columns])
    return len(rows)


def convert(xlsx_path: Path, out_dir: Path) -> dict[str, int]:
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"APPG workbook not found at {xlsx_path}. "
            f"Expected the mysociety xlsx at Data/appg/appg_groups_and_memberships.xlsx"
        )

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        _, register = _sheet_rows(wb, "register")
        _, members = _sheet_rows(wb, "members")
        _, categories = _sheet_rows(wb, "categories")
    finally:
        wb.close()

    uk_register = sorted(
        (r for r in register if r.get("parliament") == UK_PARLIAMENT),
        key=lambda r: r.get("slug") or "",
    )
    uk_slugs = {r["slug"] for r in uk_register if r.get("slug")}

    uk_members = sorted(
        (m for m in members if m.get("appg") in uk_slugs),
        key=lambda m: (m.get("appg") or "", m.get("mnis_id") or "", m.get("name") or ""),
    )
    uk_categories = sorted(
        (c for c in categories if c.get("appg_slug") in uk_slugs),
        key=lambda c: (c.get("appg_slug") or "", c.get("category_slug") or ""),
    )

    register_rows = _write_csv(out_dir / "register.csv", REGISTER_COLUMNS, uk_register)
    members_rows = _write_csv(out_dir / "members.csv", MEMBERS_COLUMNS, uk_members)
    categories_rows = _write_csv(out_dir / "categories.csv", CATEGORIES_COLUMNS, uk_categories)

    return {
        "register": register_rows,
        "members": members_rows,
        "categories": categories_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=DEFAULT_XLSX,
        help=f"Path to the APPG workbook (default: {DEFAULT_XLSX})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Output directory for CSVs (default: {DATA_DIR})",
    )
    args = parser.parse_args(argv)

    counts = convert(args.xlsx, args.out_dir)
    for name, count in counts.items():
        print(f"{name}.csv: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
