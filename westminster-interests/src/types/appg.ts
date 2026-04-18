import type { Payment } from "./payment";
import type { TotalsByWindow } from "./totals";

export interface AppgMembership {
  appg_slug: string;
  mnis_id: number | null;
  name: string;
  canon_name: string | null;
  officer_role: string | null;
  is_officer: boolean;
  member_type: "mp" | "lord" | null;
  last_updated: string | null;
  url_source: string | null;
  removed: string | null;
}

export interface Appg {
  slug: string;
  title: string;
  purpose: string | null;
  categories: string[];
  source_url: string | null;
  secretariat: string | null;
  website: string | null;
  registered_contact_name: string | null;
  date_of_most_recent_agm: string | null;
  totals: TotalsByWindow;
  officers: AppgMembership[];
  members: AppgMembership[];
  payments: Payment[];
}

export interface AppgIndexRow {
  slug: string;
  title: string;
  categories: string[];
  member_count: number;
  officer_count: number;
  totals: TotalsByWindow;
}
