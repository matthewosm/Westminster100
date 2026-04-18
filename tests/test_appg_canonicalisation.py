"""Seed + canonicalisation tests for the APPG pipeline (Unit 3).

Uses an in-memory DB seeded with a tiny fixture so the tests are fast
and deterministic. Integration assertions against the real
interests.db live alongside the main pipeline.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
DB_PATH = REPO_ROOT / "interests.db"

sys.path.insert(0, str(REPO_ROOT))
import seed_appgs  # noqa: E402


def _fixture_db(tmp_dir: Path) -> Path:
    """Build a fresh DB with a small fixture matching the production shape."""
    db_path = tmp_dir / "fixture.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO members (mnis_id, name) VALUES (1, 'Test MP')")
    # Four payments: one maps cleanly, one is NULL, one has an unrecognised
    # APPG string, one has a raw_name that needs the alias lookup.
    conn.executemany(
        """
        INSERT INTO payments (id, member_id, category, payment_type, appg)
        VALUES (?, 1, '3', 'In kind', ?)
        """,
        [
            (1, "Ukraine"),
            (2, None),
            (3, "Totally Made Up APPG"),
            (4, "APPG Aviation, Aerospace and Travel"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def _write_fixture_csvs(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with (target / "register.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([
            "slug", "title", "purpose", "categories", "source_url",
            "secretariat", "website", "registered_contact_name",
            "date_of_most_recent_agm",
        ])
        w.writerow(["ukraine", "Ukraine APPG", "", "", "", "", "", "", ""])
        w.writerow(["aviation-travel-and-aerospace", "Aviation APPG",
                    "", "", "", "", "", "", ""])
    with (target / "appg_aliases.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["raw_name", "appg_slug"])
        w.writerow(["Ukraine", "ukraine"])
        w.writerow(["APPG Aviation, Aerospace and Travel", "aviation-travel-and-aerospace"])
    with (target / "members.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["name", "officer_role", "twfy_id", "mnis_id", "canon_name",
                    "appg", "is_officer", "member_type", "source",
                    "last_updated", "url_source", "removed"])
        w.writerow(["Current MP", "Chair", "", "1", "Current MP",
                    "ukraine", "True", "mp", "parliament",
                    "2026-01-01", "", ""])
        w.writerow(["Removed Member", "", "", "2", "Removed Member",
                    "ukraine", "False", "lord", "parliament",
                    "2025-01-01", "", "2025-06-01"])
    with (target / "categories.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["appg_slug", "category_slug", "category_name"])
        w.writerow(["ukraine", "FOREIGN_AFFAIRS", "Foreign Affairs"])


class CanonicalisationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self._tmp.name)
        self.db_path = _fixture_db(self.tmp)
        self.appg_dir = self.tmp / "appg"
        _write_fixture_csvs(self.appg_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def _read(self, sql: str, params=()) -> list:
        """Open, query, close — keep Windows file locks short-lived."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def test_exact_match_canonicalises_payment(self):
        seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        [row] = self._read("SELECT appg_slug FROM payments WHERE id = 1")
        self.assertEqual(row["appg_slug"], "ukraine")

    def test_alias_lookup_canonicalises_payment(self):
        seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        [row] = self._read("SELECT appg_slug FROM payments WHERE id = 4")
        self.assertEqual(row["appg_slug"], "aviation-travel-and-aerospace")

    def test_null_payment_appg_stays_null(self):
        seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        [row] = self._read("SELECT appg, appg_slug FROM payments WHERE id = 2")
        self.assertIsNone(row["appg"])
        self.assertIsNone(row["appg_slug"])

    def test_unrecognised_string_logged_and_unmapped(self):
        captured = io.StringIO()
        real_stderr = sys.stderr
        sys.stderr = captured
        try:
            seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        finally:
            sys.stderr = real_stderr
        [row] = self._read("SELECT appg_slug FROM payments WHERE id = 3")
        self.assertIsNone(row["appg_slug"])
        self.assertIn("Totally Made Up APPG", captured.getvalue())

    def test_unmapped_count_matches_distinct_query(self):
        counts = seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        [row] = self._read(
            """
            SELECT COUNT(DISTINCT appg) FROM payments
            WHERE appg IS NOT NULL AND appg != '' AND appg_slug IS NULL
            """
        )
        self.assertEqual(row[0], counts["payments_unmapped_distinct"])

    def test_reseeding_is_idempotent(self):
        seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)

        def snapshot() -> dict:
            out = {
                t: [tuple(r) for r in self._read(f"SELECT * FROM {t} ORDER BY 1, 2")]
                for t in (
                    "appgs",
                    "appg_aliases",
                    "appg_memberships",
                    "appg_categories",
                )
            }
            out["payments_canon"] = [
                tuple(r)
                for r in self._read(
                    "SELECT id, appg, appg_slug FROM payments ORDER BY id"
                )
            ]
            return out

        before = snapshot()
        seed_appgs.seed(db_path=self.db_path, appg_dir=self.appg_dir)
        after = snapshot()
        for table, rows in before.items():
            self.assertEqual(rows, after[table], f"{table} not idempotent")

    def test_malformed_aliases_csv_aborts_with_clear_error(self):
        bad_dir = self.tmp / "bad_appg"
        bad_dir.mkdir()
        # Write all required files, but alias file lacks the required column.
        for name in ("register.csv", "members.csv", "categories.csv"):
            (bad_dir / name).write_text(
                (self.appg_dir / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        (bad_dir / "appg_aliases.csv").write_text(
            "wrong_col,another_col\nA,B\n", encoding="utf-8"
        )
        with self.assertRaises(ValueError) as ctx:
            seed_appgs.seed(db_path=self.db_path, appg_dir=bad_dir)
        self.assertIn("appg_aliases.csv", str(ctx.exception))


class RealPipelineSmokeTests(unittest.TestCase):
    """Sanity checks against the real interests.db if present."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest("interests.db not built yet")

    def test_canonicalisation_is_total(self):
        with sqlite3.connect(DB_PATH) as conn:
            unmapped = conn.execute(
                """
                SELECT COUNT(DISTINCT appg) FROM payments
                WHERE appg IS NOT NULL AND appg != '' AND appg_slug IS NULL
                """
            ).fetchone()[0]
        self.assertEqual(
            unmapped, 0, "expected 100% alias coverage per the plan"
        )

    def test_ukraine_payment_canonicalised(self):
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT appg_slug FROM payments
                WHERE appg = 'Ukraine' LIMIT 1
                """
            ).fetchone()
        self.assertIsNotNone(row, "expected at least one Ukraine payment in fixture")
        self.assertEqual(row[0], "ukraine")


if __name__ == "__main__":
    unittest.main()
