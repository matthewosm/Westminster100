/** UK-locale formatters used across list views + detail pages. */

const GBP = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

const GBP_PENNY = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const UK_NUMBER = new Intl.NumberFormat("en-GB");

const UK_DATE = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "numeric",
});

export function formatGbp(value: number | null | undefined, withPence = false): string {
  if (value == null) return "—";
  return (withPence ? GBP_PENNY : GBP).format(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return UK_NUMBER.format(value);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : UK_DATE.format(d);
}
