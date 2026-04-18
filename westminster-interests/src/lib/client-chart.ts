/** Client-side SVG chart renderer — re-renders the SummaryChart SVG
 * into a host element when the window changes. Matches the server-side
 * SummaryChart.astro layout (same bar height, label width, colours)
 * so there's no visual jump on first window swap.
 */

const GBP = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});
const NUM = new Intl.NumberFormat("en-GB");

export interface ChartRow {
  label: string;
  monetary?: number;
  inkind?: number;
  value?: number;
  href?: string;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const LABEL_CHAR_LIMIT = 32;

function truncateLabel(s: string): string {
  if (s.length <= LABEL_CHAR_LIMIT) return s;
  return s.slice(0, LABEL_CHAR_LIMIT - 1) + "…";
}

export function renderSummaryChart(
  host: HTMLElement,
  rows: ChartRow[],
  opts: {
    unit?: "currency" | "number";
    emptyMessage?: string;
    limit?: number;
    expanded?: boolean;
  } = {},
): void {
  const unit = opts.unit ?? "currency";
  const fmt = (v: number): string => (unit === "currency" ? GBP.format(v) : NUM.format(v));
  const stacked = rows.some(
    (r) => r.monetary !== undefined || r.inkind !== undefined,
  );
  const rowTotal = (r: ChartRow): number =>
    stacked ? (r.monetary ?? 0) + (r.inkind ?? 0) : r.value ?? 0;

  if (rows.length === 0) {
    host.innerHTML = `<p class="text-sm" style="color: var(--color-muted);">${escapeHtml(
      opts.emptyMessage ?? "No data in the selected window.",
    )}</p>`;
    return;
  }

  const limit = opts.limit;
  const canTruncate = typeof limit === "number" && rows.length > limit;
  const showingAll = !canTruncate || opts.expanded === true;
  const visibleRows = showingAll ? rows : rows.slice(0, limit as number);
  const peak = Math.max(...visibleRows.map(rowTotal), 1);
  const barHeight = 18;
  const barGap = 6;
  const labelWidth = 220;
  const valueWidth = 140;
  const trackWidth = 360;
  const svgWidth = labelWidth + trackWidth + valueWidth + 16;

  const parts: string[] = [];
  const chartHeightForRows = visibleRows.length * (barHeight + barGap) + 4;
  visibleRows.forEach((r, i) => {
    const y = i * (barHeight + barGap);
    const total = rowTotal(r);
    const totalW = (total / peak) * trackWidth;
    const monetaryValue = stacked ? r.monetary ?? 0 : 0;
    const inkindValue = stacked ? r.inkind ?? 0 : 0;
    const monetaryW = stacked ? (monetaryValue / peak) * trackWidth : totalW;
    const inkindW = stacked ? (inkindValue / peak) * trackWidth : 0;

    const labelText = `<text x="${labelWidth - 6}" y="${y + barHeight / 2 + 4}" text-anchor="end" font-size="12" fill="currentColor"><title>${escapeHtml(r.label)}</title>${escapeHtml(truncateLabel(r.label))}</text>`;
    const labelNode = r.href
      ? `<a href="${escapeHtml(r.href)}">${labelText}</a>`
      : labelText;

    parts.push(
      labelNode +
        `<rect x="${labelWidth}" y="${y}" width="${trackWidth}" height="${barHeight}" fill="var(--color-ink-100)"/>` +
        `<rect x="${labelWidth}" y="${y}" width="${monetaryW}" height="${barHeight}" fill="var(--color-accent-600)">${
          stacked ? `<title>Monetary ${fmt(monetaryValue)}</title>` : ""
        }</rect>` +
        (stacked
          ? `<rect x="${labelWidth + monetaryW}" y="${y}" width="${inkindW}" height="${barHeight}" fill="var(--color-ink-400)"><title>In kind ${fmt(inkindValue)}</title></rect>`
          : "") +
        `<text x="${labelWidth + trackWidth + 6}" y="${y + barHeight / 2 + 4}" font-size="12" fill="currentColor">${fmt(total)}</text>`,
    );
  });

  const legend = stacked
    ? `<div class="flex gap-4 text-xs mt-2" style="color: var(--color-muted);">
         <span class="inline-flex items-center gap-1"><span class="inline-block w-3 h-3 rounded-sm" style="background: var(--color-accent-600);"></span>Monetary (cash)</span>
         <span class="inline-flex items-center gap-1"><span class="inline-block w-3 h-3 rounded-sm" style="background: var(--color-ink-400);"></span>In kind</span>
       </div>`
    : "";

  const toggle = canTruncate
    ? `<button type="button" class="wi-chart-toggle" data-chart-toggle>${
        showingAll ? "Show top " + limit : "Show all " + rows.length
      }</button>`
    : "";

  host.innerHTML = `
    <figure class="my-4">
      <svg viewBox="0 0 ${svgWidth} ${chartHeightForRows}" role="img" aria-label="Summary" class="w-full max-w-3xl" style="height: auto; font-family: var(--font-sans);">${parts.join("")}</svg>
      ${legend}
      ${toggle}
    </figure>`;

  if (canTruncate) {
    host.querySelector<HTMLButtonElement>("[data-chart-toggle]")?.addEventListener(
      "click",
      () => renderSummaryChart(host, rows, { ...opts, expanded: !showingAll }),
    );
  }
}

/** Category → pill colour. Mirrors CATEGORY_COLOURS in @/consts. */
const CATEGORY_BG: Record<string, string> = {
  "1.1": "#dbeafe",
  "1.2": "#e0e7ff",
  "2": "#fee2e2",
  "3": "#fef3c7",
  "4": "#dcfce7",
  "5": "#f3e8ff",
};

const CATEGORY_ORDER = ["1.1", "1.2", "2", "3", "4", "5"] as const;
const CATEGORY_LABEL_FULL: Record<string, string> = {
  "1.1": "Employment — ad hoc",
  "1.2": "Employment — regular",
  "2": "Donations",
  "3": "Gifts & hospitality",
  "4": "Visits abroad",
  "5": "Overseas gifts",
};

/** Update the segments inside a .wi-catbar host element in place.
 *
 * `categories` maps category code → combined £ for the active window.
 * `normaliseTo` lets callers pin the bar scale for side-by-side bars.
 */
export function renderCategoryBar(
  host: HTMLElement,
  categories: Record<string, number>,
  opts: { normaliseTo?: number } = {},
): void {
  const track = host.querySelector<HTMLElement>(".wi-catbar-track");
  const totalEl = host.querySelector<HTMLElement>(".wi-catbar-total");
  if (!track) return;

  const segs = CATEGORY_ORDER.map((cat) => ({
    cat,
    value: categories[cat] ?? 0,
  }));
  const barTotal = segs.reduce((a, s) => a + s.value, 0);
  const denom = opts.normaliseTo && opts.normaliseTo > 0 ? opts.normaliseTo : barTotal;

  if (barTotal <= 0) {
    track.innerHTML =
      '<div class="wi-catbar-empty">No category data in this window.</div>';
    if (totalEl) totalEl.textContent = GBP.format(0);
    return;
  }

  const parts: string[] = [];
  for (const s of segs) {
    if (s.value <= 0) continue;
    const pct = denom > 0 ? (s.value / denom) * 100 : 0;
    if (pct <= 0) continue;
    const bg = CATEGORY_BG[s.cat] ?? "var(--color-ink-300)";
    const label = CATEGORY_LABEL_FULL[s.cat] ?? s.cat;
    parts.push(
      `<div class="wi-catbar-seg" style="width: ${pct}%; background: ${bg};" data-cat="${escapeHtml(
        s.cat,
      )}" title="${escapeHtml(label)} — ${GBP.format(s.value)}"></div>`,
    );
  }
  track.innerHTML = parts.join("");
  if (totalEl) totalEl.textContent = GBP.format(barTotal);
}

export { escapeHtml };
