/* ============================================================
   The Westminster 100 — Individual MP Detail Page
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();

  const params = new URLSearchParams(location.search);
  const mpId = params.get('id');
  if (!mpId) { document.getElementById('mp-name').textContent = 'No MP specified'; return; }

  const [individuals, allPayments] = await Promise.all([
    loadData('individuals.json'),
    loadData('payments_detail.json'),
  ]);

  const mp = individuals.find(m => String(m.mnis_id) === mpId);
  if (!mp) { document.getElementById('mp-name').textContent = 'MP not found'; return; }

  const payments = allPayments[mpId] || [];

  document.title = `${mp.name} — The Westminster 100`;
  renderProfile(mp);
  renderCategories(mp);
  renderPayers(mp);
  renderRetainers(mp);
  renderPayments(payments);
})();

function renderProfile(mp) {
  const photo = document.getElementById('mp-photo');
  photo.src = mp.thumbnail_url;
  photo.alt = mp.name;
  photo.onerror = function() { this.style.background = '#E0DDD6'; };

  document.getElementById('mp-name').textContent = mp.name;
  document.getElementById('mp-meta').textContent = `${mp.constituency || ''} ${mp.constituency ? '·' : ''} ${mp.house || ''}`;

  const badge = document.getElementById('mp-badge');
  badge.innerHTML = `<span class="profile-party-badge" style="background:${getPartyColour(mp.party)}">${esc(mp.party)}</span>`;

  const activeCats = Object.entries(mp.categories).filter(([, v]) => v.monetary + v.inkind > 0).length;

  document.getElementById('mp-stats').innerHTML = `
    <div class="stat-card">
      <div class="sc-value">#${mp.rank}</div>
      <div class="sc-label">Overall Rank</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(mp.total_monetary_12m)}</div>
      <div class="sc-label">Monetary (12m)</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(mp.total_inkind_12m)}</div>
      <div class="sc-label">In-Kind (12m)</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${mp.donor_count}</div>
      <div class="sc-label">Benefactors</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${activeCats}</div>
      <div class="sc-label">Revenue Streams</div>
    </div>
  `;
}

function renderCategories(mp) {
  const canvas = document.getElementById('mp-donut');
  const legend = document.getElementById('mp-cat-legend');

  const segments = Object.entries(mp.categories).map(([k, v]) => ({
    value: v.monetary + v.inkind,
    colour: CAT_COLOURS[k],
    label: CAT_LABELS[k],
    cat: k,
    monetary: v.monetary,
    inkind: v.inkind,
    count: v.count,
  })).filter(s => s.value > 0).sort((a, b) => b.value - a.value);

  drawDonut(canvas, segments, { size: 160 });

  legend.innerHTML = segments.map(s => `
    <div style="display:flex;align-items:center;gap:0.6rem;margin:0.5rem 0">
      <span class="cat-dot" style="background:${s.colour}"></span>
      <div style="flex:1">
        <div style="font-weight:600;font-size:0.9rem">${s.label}</div>
        <div style="font-size:0.78rem;color:#666">
          ${formatCurrencyFull(s.monetary)} monetary
          ${s.inkind > 0 ? ` + ${formatCurrencyFull(s.inkind)} in-kind` : ''}
          &middot; ${s.count} ${s.count === 1 ? 'payment' : 'payments'}
        </div>
      </div>
      <div style="font-family:var(--font-mono);font-weight:500">${formatCurrency(s.value)}</div>
    </div>
  `).join('');
}

function renderPayers(mp) {
  const tbody = document.querySelector('#payers-table tbody');
  mp.top_payers.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><a href="patron.html?id=${encodeURIComponent(p.name)}">${esc(p.name)}</a></td>
      <td class="col-num" data-value="${p.total}">${formatCurrencyFull(p.total)}</td>
    `;
    tbody.appendChild(tr);
  });
  makeSortable(document.getElementById('payers-table'));
}

function renderRetainers(mp) {
  if (!mp.active_regular_payments.length) return;
  document.getElementById('retainers-section').style.display = '';

  const tbody = document.querySelector('#retainers-table tbody');
  mp.active_regular_payments.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${esc(p.payer)}</td>
      <td>${esc(p.job_title || '—')}</td>
      <td class="col-num" data-value="${p.annual_rate}">${formatCurrencyFull(p.annual_rate)}<span style="color:#999;font-size:0.75rem">/yr</span></td>
      <td>${esc(p.period)}</td>
      <td>${p.start_date || '—'}</td>
    `;
    tbody.appendChild(tr);
  });
  makeSortable(document.getElementById('retainers-table'));
}

function renderPayments(payments) {
  const tbody = document.querySelector('#payments-table tbody');

  payments.forEach(p => {
    const flags = [];
    if (p.is_donated) flags.push('<span style="color:#2E7D32" title="Donated to ' + esc(p.donated_to || '') + '">Donated</span>');
    if (p.is_regular) flags.push('<span style="color:#3B82F6">Regular</span>');
    if (!p.is_sole_beneficiary) flags.push('<span style="color:#F59E0B" title="Benefit shared with others">Shared</span>');

    const dateStr = p.is_regular
      ? `${p.start_date || '?'} → ${p.end_date || 'ongoing'}`
      : (p.payment_date || p.registered || '—');

    const amountStr = p.is_regular
      ? `${formatCurrencyFull(p.amount)}/${p.period?.toLowerCase() || '?'}`
      : formatCurrencyFull(p.amount);

    const desc = p.description || p.summary || p.job_title || '';
    const shortDesc = desc.length > 80 ? desc.slice(0, 77) + '…' : desc;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${esc(p.payer)}</td>
      <td>${CAT_LABELS[p.category] || p.category}</td>
      <td>${esc(p.payment_type)}</td>
      <td class="col-num" data-value="${p.amount}">${amountStr}</td>
      <td style="white-space:nowrap">${dateStr}</td>
      <td style="font-size:0.8rem;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(desc)}">${esc(shortDesc)}</td>
      <td style="font-size:0.75rem">${flags.join(' ')}</td>
    `;
    tbody.appendChild(tr);
  });

  makeSortable(document.getElementById('payments-table'));
  makeSearchable('payments-search', 'payments-table');
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
