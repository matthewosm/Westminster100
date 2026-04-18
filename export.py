"""Emit the Westminster Interests per-entity / per-window JSON tree.

Reads interests.db and writes a tree of static JSON files consumed by
the new Astro site under westminster-interests/src/data/. The old
Westminster 100 flat shape is no longer emitted; the astro/ site is
frozen at its last pre-rebuild build.

Output layout (see docs/plans/2026-04-18-001-...):

  meta.json                       build stamp + per-window as_of_date
  index/members.json              per-MP summary rows + per-window rank
  index/payers.json               per-payer summary rows + per-window rank
  index/parties.json              per-party aggregates per window
  index/appgs.json                per-APPG summary + per-window totals
  members/{mnis_id}.json          full per-MP detail with all 6 windows
  payers/{id}.json                full per-payer detail with all 6 windows
  appgs/{slug}.json               full per-APPG detail with all 6 windows
  build-warnings.json             data quality warnings for /methodology

Windows: 12m, ytd, 2025, 2024, since_election (2024-07-04), all_time.
A single nested totals block per entity carries all six windows so the
UI can swap windows client-side with a key lookup.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import windows as windows_mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = REPO_ROOT / "interests.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "westminster-interests" / "src" / "data"

SOURCE_URL_TEMPLATE = (
    "https://members.parliament.uk/member/{mnis_id}"
    "/registeredinterests?categoryId={category_id}"
)
THUMBNAIL_URL_TEMPLATE = (
    "https://members-api.parliament.uk/api/Members/{mnis_id}/Thumbnail"
)

# Schema categories → URL categoryId parameter. 1.1 and 1.2 both roll up
# to the Employment & Earnings view (categoryId=1) on parliament.uk.
CATEGORY_URL_ID = {
    "1.1": 1,
    "1.2": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
}

CONFIDENTIAL_PAYER_SLUG = "confidential"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _slugify(value: str | None) -> str:
    """Lowercase, strip accents, collapse non-alphanumerics to single hyphen."""
    if not value:
        return "independent"
    s = value.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "independent"


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    # SQLite stores as ISO string.
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _round(value: float, places: int = 2) -> float:
    return round(value, places)


def _is_confidential_payer_name(name: str | None) -> bool:
    if not name:
        return False
    return name.strip().lower().startswith("confidential")


# ---------------------------------------------------------------------------
# Load phase
# ---------------------------------------------------------------------------


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _load_members(conn: sqlite3.Connection) -> dict[int, dict]:
    rows = conn.execute(
        """
        SELECT mnis_id, name, party, constituency, house, gender, start_date
        FROM members
        """
    ).fetchall()
    return {r["mnis_id"]: dict(r) for r in rows}


def _load_payers(conn: sqlite3.Connection) -> dict[int, dict]:
    rows = conn.execute(
        """
        SELECT id, name, address, nature_of_business, is_private_individual,
               donor_status
        FROM payers
        """
    ).fetchall()
    return {r["id"]: dict(r) for r in rows}


def _load_appgs(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT slug, title, purpose, categories, source_url, secretariat,
               website, registered_contact_name, date_of_most_recent_agm
        FROM appgs
        """
    ).fetchall()
    appgs = {r["slug"]: dict(r) for r in rows}
    for slug, rec in appgs.items():
        rec["category_list"] = (
            rec["categories"].split("|") if rec.get("categories") else []
        )
    return appgs


def _load_appg_memberships(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Return memberships grouped by appg_slug. Excludes removed rows."""
    rows = conn.execute(
        """
        SELECT appg_slug, mnis_id, name, canon_name, officer_role, is_officer,
               member_type, last_updated, url_source, removed
        FROM appg_memberships
        WHERE removed IS NULL
        """
    ).fetchall()
    by_slug: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_slug[r["appg_slug"]].append(dict(r))
    return by_slug


def _load_payments(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT pf.id, pf.member_id, pf.member_name,
               pf.resolved_payer_id, pf.payer_name, pf.payer_address,
               pf.category, pf.summary, pf.description, pf.payment_type,
               pf.is_regular, pf.amount, pf.period,
               pf.payment_date, pf.start_date, pf.end_date,
               pf.is_received, pf.is_sole_beneficiary, pf.is_donated,
               pf.donated_to, pf.registered, pf.appg, pf.appg_slug,
               pf.appg_canonical_name, pf.source_interest_id,
               p.payer_id AS direct_payer_id,
               i.payer_id AS parent_payer_id
        FROM payments_full pf
        JOIN payments p ON p.id = pf.id
        LEFT JOIN interests i ON i.id = p.interest_id
        WHERE pf.is_received = 1
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Payment derivation
# ---------------------------------------------------------------------------


def _derive_payment_flags(row: dict, payers: dict[int, dict]) -> dict:
    """Compute source_url, effective_date, override/confidential flags."""
    mnis_id = row["member_id"]
    category = row["category"]
    category_id = CATEGORY_URL_ID.get(category)
    source_url = (
        SOURCE_URL_TEMPLATE.format(mnis_id=mnis_id, category_id=category_id)
        if category_id is not None
        else None
    )

    # Ultimate-payer override: Cat 1.1/1.2 with a direct payer that differs
    # from the parent interest's payer.
    direct = row.get("direct_payer_id")
    parent = row.get("parent_payer_id")
    is_override = bool(
        category in ("1.1", "1.2") and direct is not None and direct != parent
    )

    # Confidential payer: resolved payer name starts with "Confidential".
    payer = payers.get(row["resolved_payer_id"]) if row["resolved_payer_id"] else None
    is_confidential = _is_confidential_payer_name(payer["name"] if payer else None)

    return {
        "source_url": source_url,
        "is_ultimate_payer_override": is_override,
        "is_confidential_payer": is_confidential,
    }


def _effective_one_off_date(row: dict) -> date | None:
    """Date used to place one-off payments in a window."""
    return _parse_date(row["payment_date"]) or _parse_date(row["registered"])


def _window_contribution(
    row: dict,
    window: windows_mod.WindowRange,
) -> float:
    """Return the monetary amount this payment contributes to the window."""
    amount = float(row["amount"] or 0)
    if amount == 0:
        return 0.0
    if row["is_regular"]:
        overlap = windows_mod.regular_overlap_days(
            window,
            start=_parse_date(row["start_date"]),
            end=_parse_date(row["end_date"]),
            fallback_start=_parse_date(row["registered"]),
        )
        return windows_mod.prorata_amount(amount, row["period"], overlap)
    dt = _effective_one_off_date(row)
    return amount if windows_mod.contains_date(window, dt) else 0.0


def _payment_in_window_any_type(row: dict, window: windows_mod.WindowRange) -> bool:
    """Whether the payment contributes to the window at all (for counts)."""
    if row["is_regular"]:
        overlap = windows_mod.regular_overlap_days(
            window,
            start=_parse_date(row["start_date"]),
            end=_parse_date(row["end_date"]),
            fallback_start=_parse_date(row["registered"]),
        )
        return overlap > 0
    return windows_mod.contains_date(window, _effective_one_off_date(row))


def _empty_window_totals() -> dict:
    return {
        "monetary": 0.0,
        "inkind": 0.0,
        "combined": 0.0,
        "payment_count": 0,
        "donor_count": 0,
    }


def _new_totals_by_window(window_ranges: list[windows_mod.WindowRange]) -> dict:
    return {w.key: _empty_window_totals() for w in window_ranges}


def _add_payment_to_totals(
    totals: dict,
    row: dict,
    window_ranges: list[windows_mod.WindowRange],
    donor_tracker: dict[str, set],
) -> None:
    payer_id = row["resolved_payer_id"]
    for w in window_ranges:
        amt = _window_contribution(row, w)
        in_window = amt > 0 or _payment_in_window_any_type(row, w)
        if not in_window:
            continue
        bucket = totals[w.key]
        if row["payment_type"] == "Monetary":
            bucket["monetary"] += amt
        else:
            bucket["inkind"] += amt
        bucket["combined"] += amt
        bucket["payment_count"] += 1
        if payer_id is not None:
            donor_tracker[w.key].add(payer_id)


def _finalise_totals(totals: dict, donor_tracker: dict[str, set]) -> None:
    for key, bucket in totals.items():
        bucket["monetary"] = _round(bucket["monetary"])
        bucket["inkind"] = _round(bucket["inkind"])
        bucket["combined"] = _round(bucket["combined"])
        bucket["donor_count"] = len(donor_tracker.get(key, ()))


# ---------------------------------------------------------------------------
# Tree writer
# ---------------------------------------------------------------------------


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")


def _payment_json(row: dict, appgs: dict[str, dict]) -> dict:
    """Shape a payment row for inclusion in per-entity JSON."""
    appg_slug = row["appg_slug"]
    appg_name = None
    if appg_slug and appg_slug in appgs:
        appg_name = appgs[appg_slug]["title"]
    return {
        "id": row["id"],
        "date": (row["payment_date"] or row["registered"]),
        "category": row["category"],
        "payer_id": row["resolved_payer_id"],
        "payer_name": row["payer_name"],
        "amount": float(row["amount"] or 0),
        "payment_type": row["payment_type"],
        "is_regular": bool(row["is_regular"]),
        "period": row["period"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "is_sole_beneficiary": bool(row["is_sole_beneficiary"]),
        "is_donated": bool(row["is_donated"]),
        "donated_to": row["donated_to"],
        "is_ultimate_payer_override": row["_derived"]["is_ultimate_payer_override"],
        "is_confidential_payer": row["_derived"]["is_confidential_payer"],
        "appg_slug": appg_slug,
        "appg_name": appg_name,
        "source_url": row["_derived"]["source_url"],
        "summary": row["summary"],
        "description": row["description"],
    }


def _rank_index(
    rows: list[dict],
    totals_field: str = "totals",
    rank_key: str = "combined",
) -> None:
    """Attach per-window rank to each index row by combined total (desc)."""
    if not rows:
        return
    windows = list(rows[0][totals_field].keys())
    for w in windows:
        ordered = sorted(
            rows, key=lambda r: r[totals_field][w][rank_key], reverse=True
        )
        for i, r in enumerate(ordered, start=1):
            r[totals_field][w]["rank"] = i


def build_tree(
    conn: sqlite3.Connection,
    out_dir: Path,
    as_of_date: date,
) -> dict:
    window_ranges = list(windows_mod.iter_windows(as_of_date))

    members = _load_members(conn)
    payers = _load_payers(conn)
    appgs = _load_appgs(conn)
    memberships_by_slug = _load_appg_memberships(conn)
    raw_payments = _load_payments(conn)

    # Precompute derived flags per payment.
    for row in raw_payments:
        row["_derived"] = _derive_payment_flags(row, payers)

    # Per-MP aggregation.
    per_member_payments: dict[int, list[dict]] = defaultdict(list)
    per_payer_payments: dict[int, list[dict]] = defaultdict(list)
    per_appg_payments: dict[str, list[dict]] = defaultdict(list)

    for row in raw_payments:
        per_member_payments[row["member_id"]].append(row)
        if row["resolved_payer_id"] is not None:
            per_payer_payments[row["resolved_payer_id"]].append(row)
        if row["appg_slug"]:
            per_appg_payments[row["appg_slug"]].append(row)

    # MP memberships lookup for member pages.
    appgs_by_mnis: dict[int, list[dict]] = defaultdict(list)
    for slug, entries in memberships_by_slug.items():
        for entry in entries:
            if entry["mnis_id"] is None:
                continue
            appg_rec = appgs.get(slug)
            appgs_by_mnis[entry["mnis_id"]].append(
                {
                    "appg_slug": slug,
                    "appg_name": appg_rec["title"] if appg_rec else slug,
                    "officer_role": entry["officer_role"],
                    "is_officer": bool(entry["is_officer"]),
                }
            )

    # ----- Member JSON files + index -----
    member_index: list[dict] = []
    for mnis_id, member in members.items():
        rows = sorted(
            per_member_payments.get(mnis_id, []),
            key=lambda r: (r["payment_date"] or r["registered"] or ""),
            reverse=True,
        )
        totals = _new_totals_by_window(window_ranges)
        donor_tracker: dict[str, set] = {w.key: set() for w in window_ranges}
        category_totals: dict[str, dict] = {}
        for row in rows:
            _add_payment_to_totals(totals, row, window_ranges, donor_tracker)
            cat = row["category"]
            cat_bucket = category_totals.setdefault(cat, _new_totals_by_window(window_ranges))
            _add_payment_to_totals(
                cat_bucket, row, window_ranges, defaultdict(set)
            )
        _finalise_totals(totals, donor_tracker)
        for cat_bucket in category_totals.values():
            _finalise_totals(cat_bucket, defaultdict(set))

        member_memberships = sorted(
            appgs_by_mnis.get(mnis_id, []),
            key=lambda m: (not m["is_officer"], m["appg_name"]),
        )

        doc = {
            "mnis_id": mnis_id,
            "name": member["name"],
            "party": member["party"],
            "party_slug": _slugify(member["party"]),
            "constituency": member["constituency"],
            "house": member["house"],
            "start_date": member["start_date"],
            "photo_url": THUMBNAIL_URL_TEMPLATE.format(mnis_id=mnis_id),
            "totals": totals,
            "categories": category_totals,
            "appg_memberships": member_memberships,
            "payments": [_payment_json(r, appgs) for r in rows],
        }
        _write_json(out_dir / "members" / f"{mnis_id}.json", doc)

        member_index.append(
            {
                "mnis_id": mnis_id,
                "name": member["name"],
                "party": member["party"],
                "party_slug": _slugify(member["party"]),
                "constituency": member["constituency"],
                "house": member["house"],
                "totals": totals,
            }
        )

    _rank_index(member_index)
    _write_json(out_dir / "index" / "members.json", member_index)

    # ----- Payer JSON files + index -----
    payer_index: list[dict] = []
    for payer_id, payer in payers.items():
        if _is_confidential_payer_name(payer["name"]):
            continue
        rows = sorted(
            per_payer_payments.get(payer_id, []),
            key=lambda r: (r["payment_date"] or r["registered"] or ""),
            reverse=True,
        )
        totals = _new_totals_by_window(window_ranges)
        mp_tracker: dict[str, set] = {w.key: set() for w in window_ranges}
        donor_tracker: dict[str, set] = {w.key: set() for w in window_ranges}
        for row in rows:
            _add_payment_to_totals(totals, row, window_ranges, donor_tracker)
            for w in window_ranges:
                if _payment_in_window_any_type(row, w):
                    mp_tracker[w.key].add(row["member_id"])
        _finalise_totals(totals, donor_tracker)
        # Payer-side donor_count is the count of MPs, not payers.
        for key, bucket in totals.items():
            bucket["mp_count"] = len(mp_tracker[key])

        doc = {
            "id": payer_id,
            "name": payer["name"],
            "address": payer["address"],
            "nature_of_business": payer["nature_of_business"],
            "donor_status": payer["donor_status"],
            "is_private_individual": bool(payer["is_private_individual"]),
            "totals": totals,
            "payments": [_payment_json(r, appgs) for r in rows],
        }
        _write_json(out_dir / "payers" / f"{payer_id}.json", doc)

        payer_index.append(
            {
                "id": payer_id,
                "name": payer["name"],
                "donor_status": payer["donor_status"],
                "is_private_individual": bool(payer["is_private_individual"]),
                "totals": totals,
            }
        )

    _rank_index(payer_index)
    _write_json(out_dir / "index" / "payers.json", payer_index)

    # ----- Confidential aggregate -----
    confidential_rows = [
        r
        for r in raw_payments
        if r["_derived"]["is_confidential_payer"]
    ]
    if confidential_rows:
        confidential_totals = _new_totals_by_window(window_ranges)
        mp_tracker = {w.key: set() for w in window_ranges}
        donor_tracker = {w.key: set() for w in window_ranges}
        for row in confidential_rows:
            _add_payment_to_totals(
                confidential_totals, row, window_ranges, donor_tracker
            )
            for w in window_ranges:
                if _payment_in_window_any_type(row, w):
                    mp_tracker[w.key].add(row["member_id"])
        _finalise_totals(confidential_totals, donor_tracker)
        for key, bucket in confidential_totals.items():
            bucket["mp_count"] = len(mp_tracker[key])
        _write_json(
            out_dir / "payers" / f"{CONFIDENTIAL_PAYER_SLUG}.json",
            {
                "id": CONFIDENTIAL_PAYER_SLUG,
                "name": "Confidential",
                "is_confidential": True,
                "totals": confidential_totals,
                "payments": [_payment_json(r, appgs) for r in confidential_rows],
            },
        )

    # ----- Party index -----
    party_aggregates: dict[str, dict] = {}
    for m in member_index:
        slug = m["party_slug"]
        rec = party_aggregates.setdefault(
            slug,
            {
                "party_slug": slug,
                "party": m["party"] or "Independent",
                "member_count": 0,
                "totals": _new_totals_by_window(window_ranges),
            },
        )
        rec["member_count"] += 1
        for key, bucket in m["totals"].items():
            for field in ("monetary", "inkind", "combined", "payment_count"):
                rec["totals"][key][field] += bucket[field]
    # Round and drop the donor_count from party aggregates — it would
    # require cross-member deduplication; keep it at 0 for now.
    for rec in party_aggregates.values():
        for bucket in rec["totals"].values():
            bucket["monetary"] = _round(bucket["monetary"])
            bucket["inkind"] = _round(bucket["inkind"])
            bucket["combined"] = _round(bucket["combined"])

    party_index = list(party_aggregates.values())
    _rank_index(party_index)
    _write_json(out_dir / "index" / "parties.json", party_index)

    # ----- APPG JSON files + index -----
    appg_index: list[dict] = []
    for slug, appg in appgs.items():
        rows = sorted(
            per_appg_payments.get(slug, []),
            key=lambda r: (r["payment_date"] or r["registered"] or ""),
            reverse=True,
        )
        totals = _new_totals_by_window(window_ranges)
        donor_tracker = {w.key: set() for w in window_ranges}
        mp_tracker = {w.key: set() for w in window_ranges}
        for row in rows:
            _add_payment_to_totals(totals, row, window_ranges, donor_tracker)
            for w in window_ranges:
                if _payment_in_window_any_type(row, w):
                    mp_tracker[w.key].add(row["member_id"])
        _finalise_totals(totals, donor_tracker)
        for key, bucket in totals.items():
            bucket["mp_count"] = len(mp_tracker[key])

        appg_members = sorted(
            memberships_by_slug.get(slug, []),
            key=lambda m: (not m["is_officer"], m["name"]),
        )
        officers = [m for m in appg_members if m["is_officer"]]

        doc = {
            "slug": slug,
            "title": appg["title"],
            "purpose": appg["purpose"],
            "categories": appg["category_list"],
            "source_url": appg["source_url"],
            "secretariat": appg["secretariat"],
            "website": appg["website"],
            "registered_contact_name": appg["registered_contact_name"],
            "date_of_most_recent_agm": appg["date_of_most_recent_agm"],
            "totals": totals,
            "officers": officers,
            "members": appg_members,
            "payments": [_payment_json(r, appgs) for r in rows],
        }
        _write_json(out_dir / "appgs" / f"{slug}.json", doc)

        appg_index.append(
            {
                "slug": slug,
                "title": appg["title"],
                "categories": appg["category_list"],
                "member_count": len(appg_members),
                "officer_count": len(officers),
                "totals": totals,
            }
        )

    _rank_index(appg_index)
    _write_json(out_dir / "index" / "appgs.json", appg_index)

    # ----- build-warnings.json -----
    unmapped_appgs = [
        r[0]
        for r in conn.execute(
            """
            SELECT DISTINCT appg FROM payments
            WHERE appg IS NOT NULL AND appg != '' AND appg_slug IS NULL
            ORDER BY appg
            """
        ).fetchall()
    ]
    _write_json(
        out_dir / "build-warnings.json",
        {"unmapped_appgs": unmapped_appgs},
    )

    # ----- meta.json -----
    meta = {
        "build_timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "as_of_date": as_of_date.isoformat(),
        "as_of_dates": {w.key: w.end.isoformat() for w in window_ranges},
        "counts": {
            "members": len(members),
            "payers_with_pages": len(payer_index),
            "confidential_payer_rows": len(confidential_rows),
            "appgs": len(appgs),
            "payments": len(raw_payments),
            "parties": len(party_index),
            "unmapped_appg_strings": len(unmapped_appgs),
        },
        "source_url_template": SOURCE_URL_TEMPLATE,
        "thumbnail_url_template": THUMBNAIL_URL_TEMPLATE,
    }
    _write_json(out_dir / "meta.json", meta)

    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Path to interests.db (default: {DB_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for JSON tree (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--as-of",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="ISO date (YYYY-MM-DD) to use as the 'as of' date. Defaults to today.",
    )
    args = parser.parse_args(argv)

    as_of = args.as_of or date.today()
    conn = _connect(args.db)
    try:
        meta = build_tree(conn, args.output_dir, as_of)
    finally:
        conn.close()
    print(f"Wrote tree to {args.output_dir}")
    print(f"  members: {meta['counts']['members']}")
    print(f"  payers (public pages): {meta['counts']['payers_with_pages']}")
    print(f"  confidential payer rows: {meta['counts']['confidential_payer_rows']}")
    print(f"  appgs: {meta['counts']['appgs']}")
    print(f"  payments: {meta['counts']['payments']}")
    print(f"  unmapped appg strings: {meta['counts']['unmapped_appg_strings']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
