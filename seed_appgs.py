"""Seed APPG reference tables and canonicalise payments.appg_slug.

Third stage of the data pipeline (after import.py and rebuild_master.py).
Idempotent — wipes and reloads the four APPG tables on each run, then
backfills payments.appg_slug by exact-match lookup in appg_aliases.

Sources (all under Data/appg/, produced by scripts/convert_appg_xlsx.py):
  - register.csv    → appgs
  - appg_aliases.csv → appg_aliases
  - members.csv     → appg_memberships
  - categories.csv  → appg_categories

After seeding:
  UPDATE payments SET appg_slug = alias.appg_slug
  FROM appg_aliases alias
  WHERE alias.raw_name = payments.appg;

Distinct free-text payments.appg values that don't match any alias are
printed to stderr so the methodology page can surface the gap.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
APPG_DIR = REPO_ROOT / "Data" / "appg"
DB_PATH = REPO_ROOT / "interests.db"


def _open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _require_headers(path: Path, required: set[str]) -> None:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            headers = set(next(reader))
        except StopIteration:
            raise ValueError(f"{path} is empty — missing header row")
    missing = required - headers
    if missing:
        raise ValueError(
            f"{path} missing required columns: {sorted(missing)}. Found: {sorted(headers)}"
        )


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _wipe_appg_tables(conn: sqlite3.Connection) -> None:
    # Null-out payments.appg_slug first — it FKs to appgs(slug) and would
    # block DELETE FROM appgs on a re-run. Canonicalisation runs again
    # after reload.
    conn.execute("UPDATE payments SET appg_slug = NULL")
    # Then delete children before parents.
    for table in ("appg_categories", "appg_memberships", "appg_aliases", "appgs"):
        conn.execute(f"DELETE FROM {table}")


def _seed_appgs(conn: sqlite3.Connection, appg_dir: Path) -> int:
    rows = _read_csv(appg_dir / "register.csv")
    conn.executemany(
        """
        INSERT INTO appgs (slug, title, purpose, categories, source_url,
                           secretariat, website, registered_contact_name,
                           date_of_most_recent_agm)
        VALUES (:slug, :title, :purpose, :categories, :source_url,
                :secretariat, :website, :registered_contact_name,
                :date_of_most_recent_agm)
        """,
        rows,
    )
    return len(rows)


def _seed_aliases(conn: sqlite3.Connection, appg_dir: Path) -> int:
    path = appg_dir / "appg_aliases.csv"
    _require_headers(path, {"raw_name", "appg_slug"})
    rows = _read_csv(path)
    conn.executemany(
        "INSERT INTO appg_aliases (raw_name, appg_slug) VALUES (:raw_name, :appg_slug)",
        rows,
    )
    return len(rows)


def _seed_memberships(conn: sqlite3.Connection, appg_dir: Path) -> int:
    rows = _read_csv(appg_dir / "members.csv")
    # mysociety `members` sheet columns: name, officer_role, twfy_id, mnis_id,
    # canon_name, appg, is_officer, member_type, source, last_updated, url_source, removed.
    # Schema columns: appg_slug, mnis_id, name, canon_name, officer_role,
    # is_officer, member_type, last_updated, url_source, removed.
    # PK is (appg_slug, name) — the source has a small number of duplicate
    # (appg, name) pairs (same person appearing twice under one APPG), so dedup
    # keeping the last row.
    deduped: dict[tuple[str, str], dict] = {}
    for r in rows:
        deduped[(r["appg"], r["name"])] = r

    def project(r: dict) -> dict:
        mnis_raw = r.get("mnis_id") or ""
        mnis_id = int(mnis_raw) if mnis_raw.isdigit() else None
        is_officer_raw = (r.get("is_officer") or "").strip().lower()
        return {
            "appg_slug": r["appg"],
            "mnis_id": mnis_id,
            "name": r["name"],
            "canon_name": r.get("canon_name") or None,
            "officer_role": r.get("officer_role") or None,
            "is_officer": 1 if is_officer_raw == "true" else 0,
            "member_type": r.get("member_type") or None,
            "last_updated": r.get("last_updated") or None,
            "url_source": r.get("url_source") or None,
            "removed": r.get("removed") or None,
        }

    projected = [project(r) for r in deduped.values()]
    conn.executemany(
        """
        INSERT INTO appg_memberships (appg_slug, mnis_id, name, canon_name,
                                      officer_role, is_officer, member_type,
                                      last_updated, url_source, removed)
        VALUES (:appg_slug, :mnis_id, :name, :canon_name,
                :officer_role, :is_officer, :member_type,
                :last_updated, :url_source, :removed)
        """,
        projected,
    )
    return len(projected)


def _seed_categories(conn: sqlite3.Connection, appg_dir: Path) -> int:
    rows = _read_csv(appg_dir / "categories.csv")
    # mysociety source has duplicate (appg_slug, category_slug) rows; dedup.
    deduped = {(r["appg_slug"], r["category_slug"]): r for r in rows}
    conn.executemany(
        """
        INSERT INTO appg_categories (appg_slug, category_slug, category_name)
        VALUES (:appg_slug, :category_slug, :category_name)
        """,
        list(deduped.values()),
    )
    return len(deduped)


def _canonicalise_payments(conn: sqlite3.Connection) -> tuple[int, list[str]]:
    # Reset prior canonicalisation so re-runs are idempotent.
    conn.execute("UPDATE payments SET appg_slug = NULL")
    result = conn.execute(
        """
        UPDATE payments
        SET appg_slug = (
            SELECT appg_slug FROM appg_aliases WHERE raw_name = payments.appg
        )
        WHERE appg IS NOT NULL AND appg != ''
        """
    )
    matched_count = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE appg_slug IS NOT NULL"
    ).fetchone()[0]

    unmapped_rows = conn.execute(
        """
        SELECT DISTINCT appg
        FROM payments
        WHERE appg IS NOT NULL AND appg != '' AND appg_slug IS NULL
        ORDER BY appg
        """
    ).fetchall()
    _ = result  # silence unused
    return matched_count, [r[0] for r in unmapped_rows]


def seed(db_path: Path = DB_PATH, appg_dir: Path = APPG_DIR) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"interests.db not found at {db_path} — run import.py first")

    conn = _open_db(db_path)
    try:
        with conn:  # atomic: all-or-nothing
            _wipe_appg_tables(conn)
            counts = {
                "appgs": _seed_appgs(conn, appg_dir),
                "appg_aliases": _seed_aliases(conn, appg_dir),
                "appg_memberships": _seed_memberships(conn, appg_dir),
                "appg_categories": _seed_categories(conn, appg_dir),
            }
            matched, unmapped = _canonicalise_payments(conn)
            counts["payments_canonicalised"] = matched
            counts["payments_unmapped_distinct"] = len(unmapped)
    finally:
        conn.close()

    if unmapped:
        print(
            f"WARNING: {len(unmapped)} distinct payments.appg strings did not match any alias:",
            file=sys.stderr,
        )
        for s in unmapped:
            print(f"  {s!r}", file=sys.stderr)

    return counts


def main() -> int:
    counts = seed()
    print("APPG seeding complete:")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
