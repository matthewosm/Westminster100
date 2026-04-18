"""Tests for scripts/convert_appg_xlsx.py."""

from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

# Make scripts/ importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import convert_appg_xlsx  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
APPG_DIR = REPO_ROOT / "Data" / "appg"
XLSX = APPG_DIR / "appg_groups_and_memberships.xlsx"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class ConvertAppgXlsxTests(unittest.TestCase):
    """Happy path + edge cases for the APPG xlsx → CSV converter."""

    @classmethod
    def setUpClass(cls):
        if not XLSX.exists():
            raise unittest.SkipTest(f"workbook missing at {XLSX}")

    def test_source_xlsx_present(self):
        self.assertTrue(XLSX.exists(), f"workbook must live at {XLSX}")

    def test_register_csv_is_uk_only(self):
        # register.csv should only contain UK APPGs.
        rows = _read_csv(APPG_DIR / "register.csv")
        self.assertGreater(len(rows), 500, "expected ~599 UK APPGs")
        # The filtered file drops the parliament column, so we verify via the
        # source_url pattern (devolved rows point at senedd.wales /
        # parliament.scot / niassembly.gov.uk).
        for row in rows:
            url = row.get("source_url") or ""
            self.assertNotIn("senedd.wales", url, f"senedd row leaked: {row['slug']}")
            self.assertNotIn("parliament.scot", url, f"scottish row leaked: {row['slug']}")
            self.assertNotIn("niassembly", url, f"NI row leaked: {row['slug']}")

    def test_members_csv_only_references_uk_appgs(self):
        register = {row["slug"] for row in _read_csv(APPG_DIR / "register.csv")}
        members = _read_csv(APPG_DIR / "members.csv")
        self.assertGreater(len(members), 1000, "expected thousands of memberships")
        orphan = [m for m in members if m["appg"] not in register]
        self.assertEqual(orphan, [], "every membership must reference a UK APPG")

    def test_categories_csv_only_references_uk_appgs(self):
        register = {row["slug"] for row in _read_csv(APPG_DIR / "register.csv")}
        categories = _read_csv(APPG_DIR / "categories.csv")
        self.assertGreater(len(categories), 500)
        orphan = [c for c in categories if c["appg_slug"] not in register]
        self.assertEqual(orphan, [], "every category link must reference a UK APPG")

    def test_unicode_round_trip_without_mojibake(self):
        # Unicode names should round-trip without mojibake. Pick rows with
        # smart quotes or accented characters from the real register.
        content = (APPG_DIR / "register.csv").read_text(encoding="utf-8")
        self.assertNotIn("â€™", content, "mojibake'd apostrophe found")
        self.assertNotIn("Ã©", content, "mojibake'd é found")

    def test_idempotent_reconversion(self):
        # Re-running the converter should produce byte-identical files.
        before = {
            name: (APPG_DIR / f"{name}.csv").read_bytes()
            for name in ("register", "members", "categories")
        }
        convert_appg_xlsx.convert(XLSX, APPG_DIR)
        after = {
            name: (APPG_DIR / f"{name}.csv").read_bytes()
            for name in ("register", "members", "categories")
        }
        self.assertEqual(before, after, "re-running converter changed outputs")

    def test_missing_xlsx_raises_clear_error(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            convert_appg_xlsx.convert(
                APPG_DIR / "does-not-exist.xlsx", APPG_DIR
            )
        self.assertIn("appg_groups_and_memberships.xlsx", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
