/* ============================================================
   The Westminster 100 — Donors Page ("The Patrons")
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();
  const data = await loadData('donors.json');
  const donors = data.donors;
  const statusSummary = data.donor_status_summary;

  renderPatronPodium(donors.slice(0, 3));
  renderDonorTypeDonutSection(statusSummary);
  renderDiversified(donors);
  renderDonorTable(donors);
})();

function renderPatronPodium(top3) {
  const container = document.getElementById('patron-podium');
  if (!container) return;

  top3.forEach((d, i) => {
    const card = document.createElement('div');
    card.className = 'donor-card';

    const portfolioHTML = d.portfolio.slice(0, 5).map(mp => `
      <li>
        <span>
          <a href="mp.html?id=${mp.mnis_id}" class="port-name">${escapeHTML(mp.name)}</a>
          <a href="party.html?name=${encodeURIComponent(mp.party)}" class="port-party">(${escapeHTML(mp.party)})</a>
        </span>
        <span class="port-amount">${formatCurrency(mp.amount)}</span>
      </li>
    `).join('');

    const moreHTML = d.portfolio.length > 5
      ? `<li style="color:#999;font-style:italic">+ ${d.portfolio.length - 5} more recipients</li>`
      : '';

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <a href="patron.html?id=${d.payer_id}" class="donor-name" style="color:inherit">${escapeHTML(d.canonical_name)}</a>
          <div class="donor-status">${escapeHTML(d.donor_status)}</div>
        </div>
        <span class="mp-rank">#${i + 1}</span>
      </div>
      <div class="donor-total">${formatCurrencyFull(d.total_amount)}</div>
      <div style="font-size:0.8rem;color:#666;margin-bottom:0.5rem">
        ${d.mp_count} ${d.mp_count === 1 ? 'recipient' : 'recipients'} &middot;
        ${d.payment_count} ${d.payment_count === 1 ? 'payment' : 'payments'}
      </div>
      <ul class="donor-portfolio">${portfolioHTML}${moreHTML}</ul>
    `;
    container.appendChild(card);
  });
}

function renderDonorTypeDonutSection(statusSummary) {
  const canvas = document.getElementById('donor-type-donut');
  const legend = document.getElementById('donor-type-legend');
  if (!canvas || !legend) return;

  const colours = ['#D79938', '#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#EC4899', '#B57D22'];

  const segments = statusSummary.map((d, i) => ({
    value: d.total,
    colour: colours[i % colours.length],
    label: d.status,
  }));

  drawDonut(canvas, segments, { size: 220 });

  const total = statusSummary.reduce((s, d) => s + d.total, 0);
  legend.innerHTML = statusSummary.map((d, i) => {
    const pct = total > 0 ? (d.total / total * 100).toFixed(1) : '0';
    return `
      <div style="display:flex;align-items:center;gap:0.6rem;margin:0.4rem 0">
        <span class="cat-dot" style="background:${colours[i % colours.length]}"></span>
        <span style="flex:1;font-size:0.85rem">${escapeHTML(d.status)}</span>
        <span style="font-family:var(--font-mono);font-size:0.8rem">${formatCurrency(d.total)}</span>
        <span style="font-size:0.75rem;color:#999;width:40px;text-align:right">${pct}%</span>
      </div>
    `;
  }).join('');
}

function renderDiversified(donors) {
  const tbody = document.querySelector('#diversified-table tbody');
  if (!tbody) return;

  const diversified = donors.filter(d => d.mp_count >= 2).slice(0, 50);

  diversified.forEach(d => {
    const tr = document.createElement('tr');

    const portfolioDetail = d.portfolio.map(mp =>
      `<div style="display:flex;justify-content:space-between;padding:0.2rem 0">
        <span><span class="party-dot" style="background:${getPartyColour(mp.party)};width:8px;height:8px"></span><a href="mp.html?id=${mp.mnis_id}">${escapeHTML(mp.name)}</a></span>
        <span style="font-family:var(--font-mono);font-size:0.78rem">${formatCurrency(mp.amount)}</span>
      </div>`
    ).join('');

    const expandId = 'expand-' + d.payer_id;
    tr.innerHTML = `
      <td>
        <button class="expand-btn" onclick="toggleExpand('${expandId}', this)">+</button>
        <a href="patron.html?id=${d.payer_id}">${escapeHTML(d.canonical_name)}</a>
      </td>
      <td>${escapeHTML(d.donor_status)}</td>
      <td class="col-num" data-value="${d.mp_count}">${d.mp_count}</td>
      <td class="col-num" data-value="${d.total_amount}">${formatCurrencyFull(d.total_amount)}</td>
    `;
    tbody.appendChild(tr);

    // Expandable row
    const expandTr = document.createElement('tr');
    expandTr.id = expandId;
    expandTr.style.display = 'none';
    expandTr.innerHTML = `<td colspan="4" style="padding:0.5rem 1rem 0.5rem 2.5rem;background:var(--off-white)">${portfolioDetail}</td>`;
    tbody.appendChild(expandTr);
  });

  const table = document.getElementById('diversified-table');
  makeSortable(table);
}

function toggleExpand(id, btn) {
  const row = document.getElementById(id);
  if (!row) return;
  const open = row.style.display !== 'none';
  row.style.display = open ? 'none' : '';
  btn.textContent = open ? '+' : '−';
}

function renderDonorTable(donors) {
  const tbody = document.querySelector('#full-donor-table tbody');
  if (!tbody) return;

  donors.forEach((d, i) => {
    const tr = document.createElement('tr');
    tr.dataset.status = d.donor_status;
    tr.innerHTML = `
      <td class="col-rank">${i + 1}</td>
      <td><a href="patron.html?id=${d.payer_id}">${escapeHTML(d.canonical_name)}</a></td>
      <td class="col-hide-xs">${escapeHTML(d.donor_status)}</td>
      <td class="col-num" data-value="${d.mp_count}">${d.mp_count}</td>
      <td class="col-num col-hide-xs" data-value="${d.total_monetary}">${formatCurrencyFull(d.total_monetary)}</td>
      <td class="col-num col-hide-xs" data-value="${d.total_inkind}">${formatCurrency(d.total_inkind)}</td>
      <td class="col-num" data-value="${d.total_amount}">${formatCurrencyFull(d.total_amount)}</td>
    `;
    tbody.appendChild(tr);
  });

  const table = document.getElementById('full-donor-table');
  makeSortable(table);
  makeSearchable('donor-search', 'full-donor-table');

  // Donor type filter
  const filter = document.getElementById('donor-type-filter');
  if (filter) {
    const types = [...new Set(donors.map(d => d.donor_status))].sort();
    types.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      filter.appendChild(opt);
    });
    filter.addEventListener('change', () => {
      const val = filter.value;
      table.querySelectorAll('tbody tr').forEach(row => {
        row.style.display = (!val || row.dataset.status === val) ? '' : 'none';
      });
    });
  }
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
