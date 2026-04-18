/** Client-side renderers for Grid.js payment rows across detail pages.
 *
 * Mirrors the SSR-side Astro components (PaymentFlags, CitationLink,
 * PaymentDetails) so the JS-enhanced Grid.js tables stay visually
 * consistent with the no-JS fallback tables.
 */

import { html as gridHtml } from "gridjs";
import { escapeHtml } from "@/lib/client-chart";
import { CATEGORY_SHORT } from "@/consts";

const GBP_PENNY = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const UK_DATE = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "numeric",
});

export interface PaymentLike {
  date: string | null;
  category: string;
  member_id: number | null;
  member_name: string | null;
  payer_id: number | null;
  payer_name: string | null;
  amount: number;
  payment_type: string;
  is_regular: boolean;
  period: string | null;
  start_date: string | null;
  end_date: string | null;
  is_sole_beneficiary: boolean;
  is_donated: boolean;
  is_ultimate_payer_override: boolean;
  is_confidential_payer: boolean;
  appg_slug: string | null;
  appg_name: string | null;
  source_url: string | null;
  summary: string | null;
  description: string | null;
}

export function fmtDateCell(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : UK_DATE.format(d);
}

export function fmtAmount(value: number) {
  return GBP_PENNY.format(value);
}

export function categoryCell(category: string): string {
  return CATEGORY_SHORT[category] ?? category;
}

export function memberCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  if (!p.member_name) return gridHtml("—");
  if (p.member_id) {
    return gridHtml(
      `<a href="/member/${p.member_id}">${escapeHtml(p.member_name)}</a>`,
    );
  }
  return gridHtml(escapeHtml(p.member_name));
}

export function payerCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  let inner: string;
  if (p.is_confidential_payer) {
    inner = `<a href="/payer/confidential">Confidential</a>`;
  } else if (p.payer_id) {
    inner = `<a href="/payer/${p.payer_id}">${escapeHtml(p.payer_name ?? "")}</a>`;
  } else {
    inner = escapeHtml(p.payer_name ?? "—");
  }
  if (p.is_regular && p.period) {
    inner += ` <span class="text-xs" style="color: var(--color-muted);">(${p.period.toLowerCase()})</span>`;
  }
  return gridHtml(inner);
}

export function appgCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  if (!p.appg_slug) return gridHtml("—");
  return gridHtml(
    `<a href="/appg/${escapeHtml(p.appg_slug)}">${escapeHtml(p.appg_name ?? p.appg_slug)}</a>`,
  );
}

export function flagsCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  const flags: { label: string; title: string; href?: string }[] = [];
  if (!p.is_sole_beneficiary) {
    flags.push({
      label: "Shared",
      title: "MP was not the sole beneficiary — value may overstate personal benefit.",
    });
  }
  if (p.is_ultimate_payer_override) {
    flags.push({
      label: "Ultimate payer",
      title: "The direct payer differs from the parent engagement's employer.",
    });
  }
  if (p.is_confidential_payer) {
    flags.push({
      label: "Confidential",
      title: "Payer is confidential under the Code of Conduct.",
      href: "/payer/confidential",
    });
  }
  if (flags.length === 0) return gridHtml("");

  const badgeStyle =
    "color: var(--color-muted); border-color: var(--color-border); background: var(--color-surface);";
  const pieces = flags.map((f) => {
    if (f.href) {
      return `<a href="${escapeHtml(f.href)}" title="${escapeHtml(f.title)}" class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold rounded-sm border no-underline" style="${badgeStyle}">${escapeHtml(f.label)}</a>`;
    }
    return `<span title="${escapeHtml(f.title)}" class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold rounded-sm border" style="${badgeStyle}">${escapeHtml(f.label)}</span>`;
  });
  return gridHtml(`<span class="inline-flex flex-wrap gap-1">${pieces.join("")}</span>`);
}

export function sourceCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  if (!p.source_url) {
    return gridHtml(
      `<span class="text-xs" style="color: var(--color-muted);" title="No source URL available.">—</span>`,
    );
  }
  return gridHtml(
    `<a href="${escapeHtml(p.source_url)}" target="_blank" rel="noopener" class="text-xs no-underline hover:underline" title="Opens parliament.uk in a new tab.">source <span aria-hidden="true">↗</span></a>`,
  );
}

export function detailsCell(p: PaymentLike): ReturnType<typeof gridHtml> {
  const candidates = [p.description, p.summary].filter(
    (s): s is string => typeof s === "string" && s.trim().length > 0,
  );
  if (candidates.length === 0) {
    return gridHtml(`<span class="text-xs" style="color: var(--color-muted);">—</span>`);
  }
  const full = candidates.sort((a, b) => b.length - a.length)[0].replace(/\s+/g, " ").trim();
  const max = 90;
  const excerpt = full.length > max ? full.slice(0, max - 1) + "…" : full;
  return gridHtml(
    `<span class="wi-details-cell text-xs" title="${escapeHtml(full)}">${escapeHtml(excerpt)}</span>`,
  );
}

// Window helpers duplicated here rather than importing windows.ts to
// keep the bundle lean for pages that only need table rendering.
export function overlapDays(
  sinceIso: string,
  endIso: string,
  start: string | null,
  end: string | null,
  fallbackStart: string | null,
): number {
  const effectiveStart = start || fallbackStart;
  if (!effectiveStart) return 0;
  const startDay = effectiveStart > sinceIso ? effectiveStart : sinceIso;
  const endDay = (end ?? endIso) < endIso ? (end ?? endIso) : endIso;
  const ms =
    new Date(endDay + "T00:00:00Z").getTime() -
    new Date(startDay + "T00:00:00Z").getTime();
  return Math.max(0, Math.floor(ms / 86_400_000));
}

export function paymentParticipatesInWindow(
  p: { is_regular: boolean; date: string | null; start_date: string | null; end_date: string | null },
  sinceIso: string,
  endIso: string,
): boolean {
  if (p.is_regular) {
    return overlapDays(sinceIso, endIso, p.start_date, p.end_date, p.start_date) > 0;
  }
  if (!p.date) return false;
  const d = p.date.slice(0, 10);
  return d > sinceIso && d <= endIso;
}
