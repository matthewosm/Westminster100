import type { Payment } from "./payment";
import type { TotalsByWindow } from "./totals";

export interface Payer {
  id: number | string; // confidential aggregate uses slug 'confidential'
  name: string;
  address?: string | null;
  nature_of_business?: string | null;
  donor_status?: string | null;
  is_private_individual?: boolean;
  is_confidential?: boolean;
  totals: TotalsByWindow;
  payments: Payment[];
}

export interface PayerIndexRow {
  id: number;
  name: string;
  donor_status: string | null;
  is_private_individual: boolean;
  totals: TotalsByWindow;
  trend_12m?: number[];
}
