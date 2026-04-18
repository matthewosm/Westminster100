"""Window definitions for the Westminster Interests exporter.

A window has a (since, end] range — payments whose effective date is
strictly greater than `since` and less than or equal to `end` count.
Regular (recurring) payments are pro-rated against the overlap of
their [start, end) with the window range.

Windows
-------
  12m             trailing 12 months ending at as_of_date
  ytd             1 January of as_of_date's year → as_of_date
  2025            calendar year 2025
  2024            calendar year 2024
  since_election  2024 UK general election (2024-07-04) → as_of_date
  all_time        earliest representable date → as_of_date

The general-election date is hardcoded. Flag for review at the next UK
general election — update ELECTION_DATE and the since_election window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator

# All available window keys, in canonical display order.
WINDOWS: tuple[str, ...] = (
    "12m",
    "ytd",
    "2025",
    "2024",
    "since_election",
    "all_time",
)

# UK general election date. Review at the next election.
ELECTION_DATE = date(2024, 7, 4)

# A sentinel "earliest possible date" — sqlite dates are ISO strings,
# so we just use a year low enough that no payment predates it.
EPOCH = date(1900, 1, 1)


@dataclass(frozen=True)
class WindowRange:
    """Half-open date range: payments with since < dt <= end belong."""

    key: str
    since: date  # exclusive lower bound
    end: date    # inclusive upper bound

    @property
    def days(self) -> int:
        return (self.end - self.since).days


def window_range(key: str, as_of_date: date) -> WindowRange:
    """Return the (since, end] range for the given window key."""
    if key == "12m":
        return WindowRange(key, as_of_date - timedelta(days=365), as_of_date)
    if key == "ytd":
        return WindowRange(key, date(as_of_date.year - 1, 12, 31), as_of_date)
    if key == "2025":
        return WindowRange(key, date(2024, 12, 31), date(2025, 12, 31))
    if key == "2024":
        return WindowRange(key, date(2023, 12, 31), date(2024, 12, 31))
    if key == "since_election":
        return WindowRange(key, ELECTION_DATE - timedelta(days=1), as_of_date)
    if key == "all_time":
        return WindowRange(key, EPOCH - timedelta(days=1), as_of_date)
    raise ValueError(f"unknown window key: {key!r}")


def iter_windows(as_of_date: date) -> Iterator[WindowRange]:
    for key in WINDOWS:
        yield window_range(key, as_of_date)


def contains_date(window: WindowRange, dt: date | None) -> bool:
    """True when `dt` falls inside the (since, end] half-open range."""
    if dt is None:
        return False
    return window.since < dt <= window.end


def regular_overlap_days(
    window: WindowRange,
    start: date | None,
    end: date | None,
    fallback_start: date | None = None,
) -> int:
    """Days of overlap between a regular payment and a window.

    A regular payment is "active" from `start` (or `fallback_start` when
    start is NULL) through `end` (or forever when end is NULL). The
    overlap uses half-open math aligned with window_range: overlap starts
    at max(since, effective_start) and ends at min(window.end, effective_end).
    """
    effective_start = start or fallback_start
    if effective_start is None:
        return 0
    overlap_start = max(window.since, effective_start)
    effective_end = end if end is not None else window.end
    overlap_end = min(window.end, effective_end)
    return max(0, (overlap_end - overlap_start).days)


PERIOD_DAYS = {
    "Weekly": 7.0,
    "Monthly": 30.4375,
    "Quarterly": 91.3125,
    "Yearly": 365.25,
}


def prorata_amount(amount: float, period: str, overlap_days: int) -> float:
    """Pro-rata a regular payment by overlap days against its period."""
    if overlap_days <= 0:
        return 0.0
    divisor = PERIOD_DAYS.get(period)
    if divisor is None:
        raise ValueError(f"unknown period: {period!r}")
    return amount * (overlap_days / divisor)
