import type { TotalsByWindow } from "./totals";

export interface PartyIndexRow {
  party_slug: string;
  party: string;
  member_count: number;
  totals: TotalsByWindow;
}
