import type { Window } from "./window";

export interface WindowTotals {
  monetary: number;
  inkind: number;
  combined: number;
  payment_count: number;
  donor_count: number;
  /** Optional — present on index rows, absent on detail-page totals. */
  rank?: number;
  /** Optional — present on payer + appg totals to track MP reach. */
  mp_count?: number;
}

export type TotalsByWindow = Record<Window, WindowTotals>;
