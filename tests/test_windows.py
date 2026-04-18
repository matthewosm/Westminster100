"""Unit tests for scripts/windows.py — window definition + pro-rata math."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import windows  # noqa: E402


class WindowKeyTests(unittest.TestCase):
    def test_all_six_windows_enumerated(self):
        self.assertEqual(
            tuple(windows.WINDOWS),
            ("12m", "ytd", "2025", "2024", "since_election", "all_time"),
        )

    def test_12m_range(self):
        r = windows.window_range("12m", date(2026, 4, 18))
        self.assertEqual(r.since, date(2025, 4, 18))
        self.assertEqual(r.end, date(2026, 4, 18))
        self.assertEqual(r.days, 365)

    def test_ytd_starts_at_start_of_year(self):
        r = windows.window_range("ytd", date(2026, 4, 18))
        # Since is inclusive-exclusive: since < date → first in-range date is since+1.
        self.assertEqual(r.since, date(2025, 12, 31))
        self.assertEqual(r.end, date(2026, 4, 18))

    def test_calendar_year_windows(self):
        r = windows.window_range("2025", date(2026, 4, 18))
        self.assertEqual(r.since, date(2024, 12, 31))
        self.assertEqual(r.end, date(2025, 12, 31))
        r = windows.window_range("2024", date(2026, 4, 18))
        self.assertEqual(r.since, date(2023, 12, 31))
        self.assertEqual(r.end, date(2024, 12, 31))

    def test_since_election_boundary(self):
        r = windows.window_range("since_election", date(2026, 4, 18))
        # Election day itself counts.
        self.assertTrue(windows.contains_date(r, date(2024, 7, 4)))
        # Day before does not.
        self.assertFalse(windows.contains_date(r, date(2024, 7, 3)))
        # Further-back date does not.
        self.assertFalse(windows.contains_date(r, date(2024, 6, 30)))

    def test_all_time_contains_old_dates(self):
        r = windows.window_range("all_time", date(2026, 4, 18))
        self.assertTrue(windows.contains_date(r, date(2020, 1, 1)))
        self.assertTrue(windows.contains_date(r, date(2026, 4, 18)))
        self.assertFalse(windows.contains_date(r, date(2026, 4, 19)))

    def test_unknown_window_raises(self):
        with self.assertRaises(ValueError):
            windows.window_range("lifetime", date(2026, 4, 18))


class ProRataTests(unittest.TestCase):
    def test_regular_payment_partially_overlapping(self):
        w = windows.window_range("12m", date(2026, 4, 18))
        overlap = windows.regular_overlap_days(
            w, start=date(2025, 10, 1), end=None
        )
        # Oct 1 2025 → Apr 18 2026 = 199 days.
        self.assertEqual(overlap, 199)

    def test_regular_payment_fully_covering_window(self):
        w = windows.window_range("12m", date(2026, 4, 18))
        overlap = windows.regular_overlap_days(
            w, start=date(2020, 1, 1), end=None
        )
        self.assertEqual(overlap, 365)

    def test_regular_payment_ending_before_window(self):
        w = windows.window_range("12m", date(2026, 4, 18))
        overlap = windows.regular_overlap_days(
            w, start=date(2023, 1, 1), end=date(2024, 1, 1)
        )
        self.assertEqual(overlap, 0)

    def test_regular_payment_without_start_uses_fallback(self):
        w = windows.window_range("12m", date(2026, 4, 18))
        overlap = windows.regular_overlap_days(
            w, start=None, end=None, fallback_start=date(2025, 10, 1)
        )
        self.assertEqual(overlap, 199)

    def test_prorata_yearly_payment_over_full_window(self):
        # £36,500/year for 365 days = £36,500.
        amount = windows.prorata_amount(36_500.0, "Yearly", 365)
        self.assertAlmostEqual(amount, 36_500 * (365 / 365.25), places=2)


if __name__ == "__main__":
    unittest.main()
