/* ============================================================
   The Westminster 100 — Patron Detail Page
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();

  const params = new URLSearchParams(location.search);
  const patronId = params.get('id');
  const patronName = params.get('name');
  if (!patronId && !patronName) { document.getElementById('patron-name').textContent = 'No patron specified'; return; }

  const data = await loadData('donors.json');
  const donors = data.donors;

  // Find by id or name
  const donor = patronId
    ? donors.find(d => String(d.payer_id) === patronId)
    : donors.find(d => d.canonical_name === patronName);

  if (!donor) { document.getElementById('patron-name').textContent = 'Patron not found'; return; }

  document.title = `${donor.canonical_name} — The Westminster 100`;
  renderHero(donor);
  renderCategoryBreakdown(donor);
  renderPartyBreakdown(donor);
  renderPortfolio(donor);
})();

function renderHero(donor) {
  document.getElementById('patron-name').textContent = donor.canonical_name;
  document.getElementById('patron-type').textContent = donor.donor_status;

  document.getElementById('patron-stats').innerHTML = `
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(donor.total_amount)}</div>
      <div class="sc-label">Total Invested</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(donor.total_monetary)}</div>
      <div class="sc-label">Monetary</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(donor.total_inkind)}</div>
      <div class="sc-label">In-Kind</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${donor.mp_count}</div>
      <div class="sc-label">Recipients</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${donor.payment_count}</div>
      <div class="sc-label">Payments</div>
    </div>
  `;
}

function renderCategoryBreakdown(donor) {
  const canvas = document.getElementById('patron-donut');
  const legend = document.getElementById('patron-cat-legend');

  const segments = Object.entries(donor.category_breakdown)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([k, v]) => ({
      value: v,
      colour: CAT_COLOURS[k],
      label: CAT_LABELS[k],
    }));

  drawDonut(canvas, segments, { size: 160 });

  legend.innerHTML = segments.map(s => `
    <div style="display:flex;align-items:center;gap:0.6rem;margin:0.5rem 0">
      <span class="cat-dot" style="background:${s.colour}"></span>
      <span style="flex:1;font-size:0.9rem">${s.label}</span>
      <span style="font-family:var(--font-mono);font-weight:500">${formatCurrency(s.value)}</span>
    </div>
  `).join('');
}

function renderPartyBreakdown(donor) {
  const canvas = document.getElementById('patron-party-donut');
  const legend = document.getElementById('patron-party-legend');

  // Aggregate by party
  const partyTotals = {};
  donor.portfolio.forEach(mp => {
    const p = mp.party || 'Unknown';
    partyTotals[p] = (partyTotals[p] || 0) + mp.amount;
  });

  const segments = Object.entries(partyTotals)
    .sort(([, a], [, b]) => b - a)
    .map(([party, total]) => ({
      value: total,
      colour: getPartyColour(party),
      label: party,
    }));

  drawDonut(canvas, segments, { size: 160 });

  legend.innerHTML = segments.map(s => `
    <div style="display:flex;align-items:center;gap:0.6rem;margin:0.5rem 0">
      <span class="cat-dot" style="background:${s.colour}"></span>
      <a href="party.html?name=${encodeURIComponent(s.label)}" style="flex:1;font-size:0.9rem;color:inherit">${esc(s.label)}</a>
      <span style="font-family:var(--font-mono);font-weight:500">${formatCurrency(s.value)}</span>
    </div>
  `).join('');
}

function renderPortfolio(donor) {
  const tbody = document.querySelector('#portfolio-table tbody');

  donor.portfolio.forEach(mp => {
    const catLabels = mp.categories.map(c => CAT_LABELS[c] || c).join(', ');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <span class="party-dot" style="background:${getPartyColour(mp.party)}"></span>
        <a href="mp.html?id=${mp.mnis_id}">${esc(mp.name)}</a>
      </td>
      <td><a href="party.html?name=${encodeURIComponent(mp.party)}">${esc(mp.party)}</a></td>
      <td>${esc(mp.constituency || '')}</td>
      <td class="col-num" data-value="${mp.amount}">${formatCurrencyFull(mp.amount)}</td>
      <td style="font-size:0.8rem">${esc(catLabels)}</td>
    `;
    tbody.appendChild(tr);
  });

  makeSortable(document.getElementById('portfolio-table'));
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
