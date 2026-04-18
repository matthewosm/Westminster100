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

export function renderSummaryChart(
  host: HTMLElement,
  rows: ChartRow[],
  opts: { unit?: "currency" | "number"; emptyMessage?: string } = {},
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

  const peak = Math.max(...rows.map(rowTotal), 1);
  const barHeight = 18;
  const barGap = 6;
  const labelWidth = 220;
  const valueWidth = 140;
  const trackWidth = 360;
  const chartHeight = rows.length * (barHeight + barGap) + 4;
  const svgWidth = labelWidth + trackWidth + valueWidth + 16;

  const parts: string[] = [];
  rows.forEach((r, i) => {
    const y = i * (barHeight + barGap);
    const total = rowTotal(r);
    const totalW = (total / peak) * trackWidth;
    const monetaryValue = stacked ? r.monetary ?? 0 : 0;
    const inkindValue = stacked ? r.inkind ?? 0 : 0;
    const monetaryW = stacked ? (monetaryValue / peak) * trackWidth : totalW;
    const inkindW = stacked ? (inkindValue / peak) * trackWidth : 0;

    const labelText = `<text x="${labelWidth - 6}" y="${y + barHeight / 2 + 4}" text-anchor="end" font-size="12" fill="currentColor">${escapeHtml(r.label)}</text>`;
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

  host.innerHTML = `
    <figure class="my-4">
      <svg viewBox="0 0 ${svgWidth} ${chartHeight}" role="img" aria-label="Summary" class="w-full max-w-3xl" style="height: auto;">${parts.join("")}</svg>
      ${legend}
    </figure>`;
}

export { escapeHtml };
