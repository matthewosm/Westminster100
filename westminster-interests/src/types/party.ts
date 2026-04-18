import type { Window } from "./window";
import type { TotalsByWindow } from "./totals";

/** Per-category totals for a party — summed from member categories. */
export type PartyCategoryTotals = Record<
  string,
  Record<Window, { monetary: number; inkind: number; combined: number }>
>;

export interface PartyIndexRow {
  party_slug: string;
  party: string;
  member_count: number;
  totals: TotalsByWindow;
  categories: PartyCategoryTotals;
}
