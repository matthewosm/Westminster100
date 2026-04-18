import { describe, expect, it } from "vitest";
import {
  containsDate,
  overlapDays,
  windowRange,
} from "@/lib/windows";

describe("windowRange", () => {
  it("12m range is 365 days ending at as_of_date", () => {
    const r = windowRange("12m", "2026-04-18");
    expect(r.since).toBe("2025-04-18");
    expect(r.end).toBe("2026-04-18");
  });

  it("ytd starts at Dec 31 of the prior year (exclusive)", () => {
    const r = windowRange("ytd", "2026-04-18");
    expect(r.since).toBe("2025-12-31");
    expect(r.end).toBe("2026-04-18");
    expect(containsDate(r, "2026-01-01")).toBe(true);
    expect(containsDate(r, "2025-12-31")).toBe(false);
  });

  it("since_election includes election day and excludes the day before", () => {
    const r = windowRange("since_election", "2026-04-18");
    expect(containsDate(r, "2024-07-04")).toBe(true);
    expect(containsDate(r, "2024-07-03")).toBe(false);
  });

  it("calendar-year windows cover just that year", () => {
    const r = windowRange("2024", "2026-04-18");
    expect(containsDate(r, "2024-01-01")).toBe(true);
    expect(containsDate(r, "2024-12-31")).toBe(true);
    expect(containsDate(r, "2023-12-31")).toBe(false);
    expect(containsDate(r, "2025-01-01")).toBe(false);
  });

  it("all_time includes ancient history", () => {
    const r = windowRange("all_time", "2026-04-18");
    expect(containsDate(r, "2015-06-01")).toBe(true);
    expect(containsDate(r, "2026-04-19")).toBe(false);
  });
});

describe("overlapDays", () => {
  it("regular payment partially overlapping 12m window", () => {
    const r = windowRange("12m", "2026-04-18");
    expect(overlapDays(r, "2025-10-01", null, null)).toBe(199);
  });

  it("regular payment fully before the window returns zero", () => {
    const r = windowRange("12m", "2026-04-18");
    expect(overlapDays(r, "2023-01-01", "2024-01-01", null)).toBe(0);
  });

  it("uses fallback start when start_date is null", () => {
    const r = windowRange("12m", "2026-04-18");
    expect(overlapDays(r, null, null, "2025-10-01")).toBe(199);
  });
});
