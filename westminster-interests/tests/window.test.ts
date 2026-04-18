import { describe, expect, it } from "vitest";
import {
  DEFAULT_WINDOW,
  WINDOWS,
  WINDOW_LABELS,
  isWindow,
} from "@/types/window";

describe("window types", () => {
  it("enumerates all six windows in canonical order", () => {
    expect(WINDOWS).toEqual([
      "12m",
      "ytd",
      "2025",
      "2024",
      "since_election",
      "all_time",
    ]);
  });

  it("has a human label for every window", () => {
    for (const w of WINDOWS) {
      expect(WINDOW_LABELS[w]).toBeTruthy();
    }
  });

  it("defaults to 12m", () => {
    expect(DEFAULT_WINDOW).toBe("12m");
    expect(WINDOWS).toContain(DEFAULT_WINDOW);
  });

  it("isWindow narrows valid keys", () => {
    expect(isWindow("12m")).toBe(true);
    expect(isWindow("lifetime")).toBe(false);
    expect(isWindow(null)).toBe(false);
    expect(isWindow(undefined)).toBe(false);
  });
});
