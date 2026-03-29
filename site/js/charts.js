/* ============================================================
   Lightweight Canvas 2D charts — no dependencies
   ============================================================ */

// Draw a donut chart on a canvas element
// segments: [{value, colour, label}]
function drawDonut(canvas, segments, opts = {}) {
  const size = opts.size || 80;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width = size + 'px';
  canvas.style.height = size + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const cx = size / 2, cy = size / 2;
  const outerR = size / 2 - 2;
  const innerR = outerR * 0.55;
  const total = segments.reduce((s, seg) => s + seg.value, 0);

  if (total <= 0) {
    // Empty state
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.arc(cx, cy, innerR, 0, Math.PI * 2, true);
    ctx.fillStyle = '#DDDBD8';
    ctx.fill();
    return;
  }

  let startAngle = -Math.PI / 2;
  segments.forEach(seg => {
    if (seg.value <= 0) return;
    const slice = (seg.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, startAngle, startAngle + slice);
    ctx.arc(cx, cy, innerR, startAngle + slice, startAngle, true);
    ctx.closePath();
    ctx.fillStyle = seg.colour;
    ctx.fill();
    startAngle += slice;
  });

  // Centre text
  if (opts.centreText) {
    ctx.fillStyle = opts.centreColour || '#292724';
    ctx.font = `700 ${size * 0.15}px 'Playfair Display', serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(opts.centreText, cx, cy);
  }
}

// Draw horizontal bar chart
// bars: [{label, value, colour}]
function drawHorizontalBars(canvas, bars, opts = {}) {
  if (!bars.length) return;

  const dpr = window.devicePixelRatio || 1;
  const barHeight = opts.barHeight || 28;
  const gap = opts.gap || 6;
  const labelWidth = opts.labelWidth || 140;
  const valueWidth = opts.valueWidth || 80;

  // Fill parent container width
  const containerWidth = canvas.parentElement ? canvas.parentElement.clientWidth : 600;
  const width = Math.max(containerWidth, 400);
  const maxBarWidth = width - labelWidth - valueWidth - 20;
  const height = bars.length * (barHeight + gap) + gap;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = '100%';
  canvas.style.height = height + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const maxVal = Math.max(...bars.map(b => b.value));

  bars.forEach((bar, i) => {
    const y = i * (barHeight + gap) + gap;
    const barW = maxVal > 0 ? (bar.value / maxVal) * maxBarWidth : 0;

    // Label
    ctx.fillStyle = '#292724';
    ctx.font = '500 12px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const labelText = bar.label.length > 18 ? bar.label.slice(0, 17) + '…' : bar.label;
    ctx.fillText(labelText, labelWidth - 8, y + barHeight / 2);

    // Bar
    ctx.beginPath();
    const radius = 3;
    const bx = labelWidth, by = y + 2, bw = barW, bh = barHeight - 4;
    ctx.moveTo(bx + radius, by);
    ctx.lineTo(bx + bw - radius, by);
    ctx.quadraticCurveTo(bx + bw, by, bx + bw, by + radius);
    ctx.lineTo(bx + bw, by + bh - radius);
    ctx.quadraticCurveTo(bx + bw, by + bh, bx + bw - radius, by + bh);
    ctx.lineTo(bx + radius, by + bh);
    ctx.quadraticCurveTo(bx, by + bh, bx, by + bh - radius);
    ctx.lineTo(bx, by + radius);
    ctx.quadraticCurveTo(bx, by, bx + radius, by);
    ctx.fillStyle = bar.colour || '#D79938';
    ctx.fill();

    // Value
    ctx.fillStyle = '#292724';
    ctx.font = "500 12px 'JetBrains Mono', monospace";
    ctx.textAlign = 'left';
    ctx.fillText(formatCurrency(bar.value), labelWidth + barW + 8, y + barHeight / 2);
  });
}

// Draw a donut chart for donor type breakdown
function drawDonorTypeDonut(canvas, data, opts = {}) {
  const colours = ['#D79938', '#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#EC4899', '#B57D22'];
  const segments = data.map((d, i) => ({
    value: d.total,
    colour: colours[i % colours.length],
    label: d.status,
  }));
  drawDonut(canvas, segments, { ...opts, size: opts.size || 200 });
}
