"""Tree-shape tests for export.py — asserts file layout and contents
against the real interests.db build.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "interests.db"


def _run_export(output_dir: Path) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    subprocess.check_call(
        [
            sys.executable,
            str(REPO_ROOT / "export.py"),
            "--output-dir",
            str(output_dir),
            "--as-of",
            "2026-04-18",
        ],
        cwd=str(REPO_ROOT),
        env=env,
    )


class ExportTreeShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest("interests.db not built yet")
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.out = Path(cls._tmp.name)
        _run_export(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_meta_json_present_with_all_windows(self):
        meta = json.loads((self.out / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(meta["as_of_dates"].keys()),
            {"12m", "ytd", "2025", "2024", "since_election", "all_time"},
        )
        self.assertEqual(meta["as_of_date"], "2026-04-18")

    def test_index_files_present(self):
        for name in ("members", "payers", "parties", "appgs"):
            self.assertTrue(
                (self.out / "index" / f"{name}.json").exists(),
                f"missing index/{name}.json",
            )

    def test_members_directory_has_one_file_per_member(self):
        idx = json.loads((self.out / "index" / "members.json").read_text(encoding="utf-8"))
        expected = {m["mnis_id"] for m in idx}
        on_disk = {int(p.stem) for p in (self.out / "members").glob("*.json")}
        self.assertEqual(expected, on_disk)

    def test_every_member_has_six_window_totals(self):
        idx = json.loads((self.out / "index" / "members.json").read_text(encoding="utf-8"))
        for row in idx[:50]:
            self.assertEqual(
                set(row["totals"].keys()),
                {"12m", "ytd", "2025", "2024", "since_election", "all_time"},
            )
            for bucket in row["totals"].values():
                for field in ("monetary", "inkind", "combined", "payment_count", "donor_count", "rank"):
                    self.assertIn(field, bucket)

    def test_member_detail_payments_carry_source_url(self):
        idx = json.loads((self.out / "index" / "members.json").read_text(encoding="utf-8"))
        top = sorted(idx, key=lambda m: m["totals"]["all_time"]["combined"], reverse=True)[0]
        detail = json.loads((self.out / "members" / f"{top['mnis_id']}.json").read_text(encoding="utf-8"))
        self.assertTrue(detail["payments"], "top MP must have payments")
        for p in detail["payments"]:
            self.assertIsNotNone(p.get("source_url"), p)
            self.assertIn("members.parliament.uk/member/", p["source_url"])
            self.assertIn("categoryId=", p["source_url"])
            # 1.1/1.2 → categoryId=1; others match the category number.
            expected_id = {"1.1": 1, "1.2": 1, "2": 2, "3": 3, "4": 4, "5": 5}[p["category"]]
            self.assertIn(f"categoryId={expected_id}", p["source_url"])

    def test_confidential_payer_has_aggregate_page_and_no_individual_pages(self):
        confidential_path = self.out / "payers" / "confidential.json"
        self.assertTrue(confidential_path.exists())
        confidential = json.loads(confidential_path.read_text(encoding="utf-8"))
        self.assertTrue(confidential["is_confidential"])
        # No individual payer page for "Confidential" names — the three
        # payer rows with that name are not written out as separate files.
        for p in (self.out / "payers").glob("*.json"):
            if p.stem == "confidential":
                continue
            doc = json.loads(p.read_text(encoding="utf-8"))
            self.assertFalse(
                doc.get("name", "").lower().startswith("confidential"),
                f"confidential payer leaked: {p.name}",
            )

    def test_appg_detail_carries_register_metadata(self):
        ukraine = self.out / "appgs" / "ukraine.json"
        self.assertTrue(ukraine.exists())
        detail = json.loads(ukraine.read_text(encoding="utf-8"))
        self.assertEqual(detail["slug"], "ukraine")
        self.assertTrue(detail["title"])
        self.assertIsInstance(detail["members"], list)
        self.assertIsInstance(detail["officers"], list)
        self.assertIsInstance(detail["payments"], list)

    def test_party_index_has_independent_bucket(self):
        parties = json.loads((self.out / "index" / "parties.json").read_text(encoding="utf-8"))
        slugs = {p["party_slug"] for p in parties}
        self.assertIn("independent", slugs)
        labour = next((p for p in parties if p["party_slug"] == "labour"), None)
        self.assertIsNotNone(labour)
        conservative = next(
            (p for p in parties if p["party_slug"] == "conservative"), None
        )
        self.assertIsNotNone(conservative)

    def test_build_warnings_json_present(self):
        warnings = json.loads(
            (self.out / "build-warnings.json").read_text(encoding="utf-8")
        )
        self.assertIn("unmapped_appgs", warnings)
        # Full coverage was achieved in Unit 3.
        self.assertEqual(warnings["unmapped_appgs"], [])

    def test_appg_tagged_payment_appears_in_both_member_and_appg_json(self):
        idx = json.loads((self.out / "index" / "members.json").read_text(encoding="utf-8"))
        # Find a member with an APPG-tagged payment.
        found_pair = None
        for m in idx:
            detail = json.loads(
                (self.out / "members" / f"{m['mnis_id']}.json").read_text(encoding="utf-8")
            )
            for p in detail["payments"]:
                if p["appg_slug"]:
                    found_pair = (detail, p)
                    break
            if found_pair:
                break
        self.assertIsNotNone(found_pair, "expected at least one APPG-tagged payment")
        member_detail, payment = found_pair
        appg_detail = json.loads(
            (self.out / "appgs" / f"{payment['appg_slug']}.json").read_text(encoding="utf-8")
        )
        appg_payment_ids = {p["id"] for p in appg_detail["payments"]}
        self.assertIn(payment["id"], appg_payment_ids)


if __name__ == "__main__":
    unittest.main()
