export type PaymentType = "Monetary" | "In kind";
export type PaymentPeriod = "Weekly" | "Monthly" | "Quarterly" | "Yearly";

/** Shape emitted by export.py's _payment_json. */
export interface Payment {
  id: number;
  date: string | null;
  category: "1.1" | "1.2" | "2" | "3" | "4" | "5";
  payer_id: number | null;
  payer_name: string | null;
  amount: number;
  payment_type: PaymentType;
  is_regular: boolean;
  period: PaymentPeriod | null;
  start_date: string | null;
  end_date: string | null;
  is_sole_beneficiary: boolean;
  is_donated: boolean;
  donated_to: string | null;
  is_ultimate_payer_override: boolean;
  is_confidential_payer: boolean;
  appg_slug: string | null;
  appg_name: string | null;
  source_url: string | null;
  summary: string | null;
  description: string | null;
}
