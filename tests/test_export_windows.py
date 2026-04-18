"""Window-math tests for export.py using a seeded in-memory DB.

Tests the six-window attribution + pro-rata math end-to-end without
depending on the real interests.db.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"

sys.path.insert(0, str(REPO_ROOT))
import export  # noqa: E402


def _make_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT INTO members (mnis_id, name, party, constituency, house) VALUES (?, ?, ?, ?, ?)",
            [
                (1001, "Alice Earnest", "Labour", "Test North", "Commons"),
                (1002, "Bob Zeroes", "Conservative", "Test South", "Commons"),
            ],
        )
        conn.execute(
            "INSERT INTO payers (id, name, donor_status) VALUES (1, 'Test Donor Ltd', 'Company')"
        )
        conn.execute(
            "INSERT INTO payers (id, name) VALUES (2, 'Confidential')"
        )
        conn.execute(
            """
            INSERT INTO appgs (slug, title, source_url)
            VALUES ('ukraine', 'Ukraine APPG', 'https://example.com/ukraine')
            """
        )
        conn.executemany(
            """
            INSERT INTO payments
            (id, member_id, payer_id, category, summary, payment_type,
             is_regular, amount, period, payment_date, start_date, end_date,
             is_received, is_sole_beneficiary, is_donated, registered, appg,
             appg_slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                # One-off inside 12m, inside 2025, inside since-election.
                (1, 1001, 1, "2", "donation", "Monetary", 0, 10_000.0, None,
                 "2025-11-01", None, None, 1, 1, 0, "2025-11-02", None, None),
                # One-off just before the 2024 election (2024-07-03) — outside since_election.
                (2, 1001, 1, "2", "donation pre-election", "Monetary", 0,
                 5_000.0, None, "2024-07-03", None, None, 1, 1, 0,
                 "2024-07-04", None, None),
                # One-off exactly on election day — inside since_election.
                (3, 1001, 1, "2", "donation election day", "Monetary", 0,
                 7_500.0, None, "2024-07-04", None, None, 1, 1, 0,
                 "2024-07-05", None, None),
                # Regular £36,500/year, running Oct 2025 → indefinite.
                (4, 1001, 1, "1.2", "retainer", "Monetary", 1, 36_500.0,
                 "Yearly", None, "2025-10-01", None, 1, 1, 0, "2025-10-01",
                 None, None),
                # In-kind tagged with APPG.
                (5, 1001, 1, "3", "conference travel", "In kind", 0, 2_000.0,
                 None, "2025-11-10", None, None, 1, 1, 0, "2025-11-11",
                 "Ukraine", "ukraine"),
                # Confidential donation.
                (6, 1002, 2, "2", "confidential", "Monetary", 0, 3_000.0, None,
                 "2025-10-15", None, None, 1, 1, 0, "2025-10-16", None, None),
                # is_received = 0 — should be skipped everywhere.
                (7, 1002, 1, "1.1", "unpaid expected", "Monetary", 0, 99_999.0,
                 None, "2025-01-01", None, None, 0, 1, 0, "2025-01-02", None,
                 None),
            ],
        )
        conn.commit()
    finally:
        conn.close()


class ExportWindowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "fixture.db"
        self.out_dir = self.tmp / "out"
        _make_db(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _build(self, as_of: date = date(2026, 4, 18)) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return export.build_tree(conn, self.out_dir, as_of)
        finally:
            conn.close()

    def test_alice_totals_across_windows(self):
        self._build()
        with open(self.out_dir / "members" / "1001.json", encoding="utf-8") as f:
            alice = json.load(f)

        # 12m (2025-04-18 → 2026-04-18) includes payment 1 (Nov 2025),
        # payment 5 (in-kind £2k), pro-rata from payment 4 (Oct 2025 →
        # Apr 2026 = 199 days at £36,500/year ≈ £19,890).
        t12 = alice["totals"]["12m"]
        self.assertAlmostEqual(t12["inkind"], 2_000.0, places=0)
        self.assertGreater(t12["monetary"], 29_000)
        self.assertLess(t12["monetary"], 31_000)  # 10k + ~£19.9k pro-rata
        self.assertEqual(t12["payment_count"], 3)

        # since_election includes payments 1, 3, 4 pro-rata, 5.
        # Excludes payment 2 (2024-07-03, one day before election).
        se = alice["totals"]["since_election"]
        self.assertEqual(se["payment_count"], 4)

        # all_time excludes none of the received rows.
        at = alice["totals"]["all_time"]
        self.assertEqual(at["payment_count"], 5)

    def test_election_day_payment_included_and_day_before_excluded(self):
        self._build()
        with open(self.out_dir / "members" / "1001.json", encoding="utf-8") as f:
            alice = json.load(f)

        # Payment 2 (2024-07-03, £5,000) is the only payment that exists in
        # all_time but not in since_election. Everything else is the same.
        all_time = alice["totals"]["all_time"]["monetary"]
        since_election = alice["totals"]["since_election"]["monetary"]
        self.assertAlmostEqual(all_time - since_election, 5_000.0, places=2)

        # Payment counts tell the same story from a different angle.
        self.assertEqual(
            alice["totals"]["all_time"]["payment_count"]
            - alice["totals"]["since_election"]["payment_count"],
            1,
        )

    def test_unreceived_payment_is_excluded_entirely(self):
        self._build()
        with open(self.out_dir / "members" / "1002.json", encoding="utf-8") as f:
            bob = json.load(f)
        ids = {p["id"] for p in bob["payments"]}
        self.assertNotIn(7, ids, "is_received=0 payments must not be exported")

    def test_confidential_payer_not_in_individual_pages(self):
        self._build()
        payer_files = list((self.out_dir / "payers").glob("*.json"))
        # Confidential payer (id=2) should not have a 2.json.
        self.assertNotIn("2.json", {p.name for p in payer_files})
        self.assertIn("confidential.json", {p.name for p in payer_files})

    def test_confidential_payment_flagged_in_member_json(self):
        self._build()
        with open(self.out_dir / "members" / "1002.json", encoding="utf-8") as f:
            bob = json.load(f)
        [payment] = [p for p in bob["payments"] if p["id"] == 6]
        self.assertTrue(payment["is_confidential_payer"])

    def test_appg_tagged_payment_reaches_appg_file(self):
        self._build()
        ukraine = json.loads(
            (self.out_dir / "appgs" / "ukraine.json").read_text(encoding="utf-8")
        )
        ids = {p["id"] for p in ukraine["payments"]}
        self.assertIn(5, ids)

    def test_regular_payment_prorata_is_within_window(self):
        # Verify the pro-rata contribution of a year-long £36,500 payment
        # over the ~199-day overlap with 12m is roughly £19,890.
        self._build(date(2026, 4, 18))
        with open(self.out_dir / "members" / "1001.json", encoding="utf-8") as f:
            alice = json.load(f)
        payments = [p for p in alice["payments"] if p["id"] == 4]
        self.assertEqual(len(payments), 1)
        # all_time should include full year 2025-10-01 → 2026-04-18 = 199 days.
        at = alice["totals"]["all_time"]["monetary"]
        # 10k + 7.5k + 5k + pro-rata
        self.assertGreater(at - 22_500, 19_000)
        self.assertLess(at - 22_500, 20_500)

    def test_ranks_are_applied_in_index(self):
        self._build()
        idx = json.loads(
            (self.out_dir / "index" / "members.json").read_text(encoding="utf-8")
        )
        for row in idx:
            self.assertIn("rank", row["totals"]["12m"])
            self.assertIn("rank", row["totals"]["all_time"])
        ranks = sorted(r["totals"]["12m"]["rank"] for r in idx)
        self.assertEqual(ranks, list(range(1, len(idx) + 1)))


if __name__ == "__main__":
    unittest.main()
