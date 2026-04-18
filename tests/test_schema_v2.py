"""Schema v2 shape tests — verify APPG reference model is present and wired up."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _fresh_db() -> sqlite3.Connection:
    """In-memory DB loaded from schema.sql."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


class SchemaV2Tests(unittest.TestCase):
    """Shape-level assertions — no seed data required."""

    def test_appgs_table_has_expected_columns(self):
        conn = _fresh_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(appgs)")}
        expected = {
            "slug",
            "title",
            "purpose",
            "categories",
            "source_url",
            "secretariat",
            "website",
            "registered_contact_name",
            "date_of_most_recent_agm",
        }
        self.assertEqual(cols, expected)

    def test_appgs_slug_is_primary_key(self):
        conn = _fresh_db()
        pk_cols = [r[1] for r in conn.execute("PRAGMA table_info(appgs)") if r[5] == 1]
        self.assertEqual(pk_cols, ["slug"])

    def test_appg_aliases_table_shape(self):
        conn = _fresh_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(appg_aliases)")}
        self.assertEqual(cols, {"raw_name", "appg_slug"})
        fks = list(conn.execute("PRAGMA foreign_key_list(appg_aliases)"))
        self.assertTrue(any(fk[2] == "appgs" for fk in fks), "appg_aliases must FK to appgs")

    def test_appg_memberships_table_shape(self):
        conn = _fresh_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(appg_memberships)")}
        expected = {
            "appg_slug",
            "mnis_id",
            "name",
            "canon_name",
            "officer_role",
            "is_officer",
            "member_type",
            "last_updated",
            "url_source",
            "removed",
        }
        self.assertEqual(cols, expected)

    def test_appg_categories_table_shape(self):
        conn = _fresh_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(appg_categories)")}
        self.assertEqual(cols, {"appg_slug", "category_slug", "category_name"})

    def test_payments_gains_appg_slug_column(self):
        conn = _fresh_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(payments)")}
        self.assertIn("appg_slug", cols)
        self.assertIn("appg", cols, "free-text appg column preserved for provenance")

    def test_payments_full_view_surfaces_appg_fields(self):
        conn = _fresh_db()
        conn.execute("INSERT INTO members (mnis_id, name) VALUES (1, 'Sample MP')")
        conn.execute(
            "INSERT INTO appgs (slug, title, source_url) VALUES (?, ?, ?)",
            ("ukraine", "Ukraine All-Party Parliamentary Group", "https://example.com"),
        )
        conn.execute(
            """
            INSERT INTO payments (id, member_id, category, payment_type, appg, appg_slug)
            VALUES (1, 1, '3', 'In kind', 'Ukraine', 'ukraine')
            """
        )
        row = dict(
            zip(
                [c[0] for c in conn.execute("SELECT * FROM payments_full LIMIT 0").description],
                conn.execute(
                    "SELECT * FROM payments_full WHERE id = 1"
                ).fetchone(),
            )
        )
        self.assertEqual(row["appg_slug"], "ukraine")
        self.assertEqual(row["appg_canonical_name"], "Ukraine All-Party Parliamentary Group")
        self.assertEqual(row["appg_source_url"], "https://example.com")
        self.assertEqual(row["appg"], "Ukraine")  # free-text provenance preserved

    def test_payments_full_handles_null_appg(self):
        conn = _fresh_db()
        conn.execute("INSERT INTO members (mnis_id, name) VALUES (1, 'Sample MP')")
        conn.execute(
            """
            INSERT INTO payments (id, member_id, category, payment_type, appg, appg_slug)
            VALUES (2, 1, '2', 'Monetary', NULL, NULL)
            """
        )
        row = dict(
            zip(
                [c[0] for c in conn.execute("SELECT * FROM payments_full LIMIT 0").description],
                conn.execute("SELECT * FROM payments_full WHERE id = 2").fetchone(),
            )
        )
        self.assertIsNone(row["appg_slug"])
        self.assertIsNone(row["appg_canonical_name"])
        self.assertIsNone(row["appg_source_url"])

    def test_appg_aliases_fk_enforced_with_pragma(self):
        conn = _fresh_db()
        conn.execute("PRAGMA foreign_keys = ON")
        # Inserting an alias pointing at a non-existent slug must fail.
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO appg_aliases (raw_name, appg_slug) VALUES (?, ?)",
                ("bogus alias", "no-such-appg"),
            )


if __name__ == "__main__":
    unittest.main()
