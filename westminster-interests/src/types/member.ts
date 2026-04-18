import type { Payment } from "./payment";
import type { TotalsByWindow } from "./totals";

export interface MemberAppgMembership {
  appg_slug: string;
  appg_name: string;
  officer_role: string | null;
  is_officer: boolean;
}

/** Shape of members/{mnis_id}.json. */
export interface Member {
  mnis_id: number;
  name: string;
  party: string | null;
  party_slug: string;
  constituency: string | null;
  house: string | null;
  start_date: string | null;
  photo_url: string;
  totals: TotalsByWindow;
  categories: Record<string, TotalsByWindow>;
  /** 12 trailing ~30-day buckets, oldest first. Combined £ per bucket. */
  trend_12m: number[];
  appg_memberships: MemberAppgMembership[];
  payments: Payment[];
}

/** Shape of a row in index/members.json. */
export interface MemberIndexRow {
  mnis_id: number;
  name: string;
  party: string | null;
  party_slug: string;
  constituency: string | null;
  house: string | null;
  totals: TotalsByWindow;
  /** 12 trailing ~30-day buckets, oldest first. Combined £ per bucket. */
  trend_12m: number[];
}
