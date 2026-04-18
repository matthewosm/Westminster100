export type Window =
  | "12m"
  | "ytd"
  | "2025"
  | "2024"
  | "since_election"
  | "all_time";

export const WINDOWS: readonly Window[] = [
  "12m",
  "ytd",
  "2025",
  "2024",
  "since_election",
  "all_time",
] as const;

export const WINDOW_LABELS: Record<Window, string> = {
  "12m": "Trailing 12 months",
  ytd: "Year to date",
  "2025": "2025",
  "2024": "2024",
  since_election: "Since 2024 election",
  all_time: "All time",
};

export const DEFAULT_WINDOW: Window = "12m";

export function isWindow(value: string | null | undefined): value is Window {
  return !!value && (WINDOWS as readonly string[]).includes(value);
}
