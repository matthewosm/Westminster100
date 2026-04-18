import type { Window } from "./window";

export interface Meta {
  build_timestamp: string;
  as_of_date: string;
  as_of_dates: Record<Window, string>;
  counts: {
    members: number;
    payers_with_pages: number;
    confidential_payer_rows: number;
    appgs: number;
    payments: number;
    parties: number;
    unmapped_appg_strings: number;
  };
  source_url_template: string;
  thumbnail_url_template: string;
}

export interface BuildWarnings {
  unmapped_appgs: string[];
}
