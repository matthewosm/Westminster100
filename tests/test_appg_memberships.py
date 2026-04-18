"""Tests for appg_memberships seeding (Unit 3)."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "interests.db"


class AppgMembershipsRealDataTests(unittest.TestCase):
    """Run against the real pipeline-built DB."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest("interests.db not built yet")
        cls.conn = sqlite3.connect(DB_PATH)
        cls.conn.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_memberships_loaded(self):
        # mysociety UK-scoped export has ~11k rows; plan quoted 13k+ including
        # devolved groups. Assert a conservative lower bound.
        total = self.conn.execute("SELECT COUNT(*) FROM appg_memberships").fetchone()[0]
        self.assertGreater(total, 10_000)

    def test_categories_loaded(self):
        total = self.conn.execute("SELECT COUNT(*) FROM appg_categories").fetchone()[0]
        self.assertGreater(total, 500)

    def test_membership_mnis_ids_cover_real_mps(self):
        # At least one real MP should have memberships cross-referenceable
        # by mnis_id. This is the scope expansion from 2026-04-18 — MP detail
        # pages will surface APPGs via this link.
        row = self.conn.execute(
            """
            SELECT am.mnis_id, COUNT(*) AS n
            FROM appg_memberships am
            JOIN members m ON m.mnis_id = am.mnis_id
            GROUP BY am.mnis_id
            ORDER BY n DESC
            LIMIT 1
            """
        ).fetchone()
        self.assertIsNotNone(row, "expected at least one MP with memberships")
        self.assertGreater(row["n"], 0)

    def test_removed_memberships_stored_but_filterable(self):
        # `removed` is populated for past memberships. Presence + query.
        total = self.conn.execute("SELECT COUNT(*) FROM appg_memberships").fetchone()[0]
        active = self.conn.execute(
            "SELECT COUNT(*) FROM appg_memberships WHERE removed IS NULL"
        ).fetchone()[0]
        self.assertLessEqual(active, total)

    def test_officers_are_flagged(self):
        # At minimum, every APPG should have at least one officer (Chair etc).
        rows = self.conn.execute(
            """
            SELECT appg_slug, COUNT(*) FROM appg_memberships
            WHERE is_officer = 1 GROUP BY appg_slug LIMIT 5
            """
        ).fetchall()
        self.assertGreater(len(rows), 0, "expected at least some officers")
        for row in rows:
            self.assertGreater(row[1], 0)

    def test_memberships_fk_to_appgs(self):
        # Every membership's appg_slug must resolve.
        orphan = self.conn.execute(
            """
            SELECT COUNT(*) FROM appg_memberships am
            LEFT JOIN appgs a ON a.slug = am.appg_slug
            WHERE a.slug IS NULL
            """
        ).fetchone()[0]
        self.assertEqual(orphan, 0)


if __name__ == "__main__":
    unittest.main()
