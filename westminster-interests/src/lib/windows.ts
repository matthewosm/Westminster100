/** TypeScript mirror of scripts/windows.py — used for client-side
 * window-based filtering on detail pages. Kept in lockstep with the
 * Python module; drift will surface in test_windows.test.ts.
 */

import type { Window } from "@/types/window";

const MS_PER_DAY = 86_400_000;

export const ELECTION_DATE = "2024-07-04";

export interface WindowRange {
  key: Window;
  /** Exclusive lower bound — ISO date string. */
  since: string;
  /** Inclusive upper bound — ISO date string. */
  end: string;
}

function isoDaysBefore(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

export function windowRange(key: Window, asOfDate: string): WindowRange {
  switch (key) {
    case "12m":
      return { key, since: isoDaysBefore(asOfDate, 365), end: asOfDate };
    case "ytd": {
      const year = parseInt(asOfDate.slice(0, 4), 10);
      return { key, since: `${year - 1}-12-31`, end: asOfDate };
    }
    case "2025":
      return { key, since: "2024-12-31", end: "2025-12-31" };
    case "2024":
      return { key, since: "2023-12-31", end: "2024-12-31" };
    case "since_election":
      return { key, since: isoDaysBefore(ELECTION_DATE, 1), end: asOfDate };
    case "all_time":
      return { key, since: "1899-12-31", end: asOfDate };
  }
}

export function containsDate(
  range: WindowRange,
  dt: string | null | undefined,
): boolean {
  if (!dt) return false;
  const day = dt.slice(0, 10);
  return day > range.since && day <= range.end;
}

export function overlapDays(
  range: WindowRange,
  start: string | null,
  end: string | null,
  fallbackStart: string | null,
): number {
  const effectiveStart = start || fallbackStart;
  if (!effectiveStart) return 0;
  const overlapStart = effectiveStart > range.since ? effectiveStart : range.since;
  const effectiveEnd = end ?? range.end;
  const overlapEnd = effectiveEnd < range.end ? effectiveEnd : range.end;
  const diffMs =
    new Date(overlapEnd + "T00:00:00Z").getTime() -
    new Date(overlapStart + "T00:00:00Z").getTime();
  return Math.max(0, Math.floor(diffMs / MS_PER_DAY));
}

/** Whether a payment participates in the given window at all — used for
 * row visibility on detail pages. */
export function paymentInWindow(
  payment: {
    is_regular: boolean;
    date: string | null;
    start_date: string | null;
    end_date: string | null;
  },
  registered: string | null,
  range: WindowRange,
): boolean {
  if (payment.is_regular) {
    return (
      overlapDays(range, payment.start_date, payment.end_date, registered) > 0
    );
  }
  return containsDate(range, payment.date);
}
