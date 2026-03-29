/* ============================================================
   The Westminster 100 — Party Detail Page
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();

  const params = new URLSearchParams(location.search);
  const partyName = params.get('name');
  if (!partyName) { document.getElementById('party-name').textContent = 'No party specified'; return; }

  const [parties, individuals] = await Promise.all([
    loadData('parties.json'),
    loadData('individuals.json'),
  ]);

  const party = parties.find(p => p.party === partyName);
  if (!party) { document.getElementById('party-name').textContent = 'Party not found'; return; }

  const members = individuals.filter(m => m.party === partyName)
    .sort((a, b) => b.total_monetary_12m - a.total_monetary_12m);

  document.title = `${partyName} — The Westminster 100`;
  renderHero(party);
  renderCategories(party);
  renderTopEarners(party);
  renderMembers(members);
})();

function renderHero(party) {
  const colour = getPartyColour(party.party);
  document.getElementById('party-hero-bar').style.background = colour;
  document.getElementById('party-name').textContent = party.party;
  document.getElementById('party-subtitle').textContent =
    `${party.member_count_earning} earning members of ${party.member_count_total}`;

  document.getElementById('party-stats').innerHTML = `
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(party.total_monetary_12m)}</div>
      <div class="sc-label">Market Cap</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(party.total_inkind_12m)}</div>
      <div class="sc-label">In-Kind Benefits</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${formatCurrency(party.avg_per_earning_member)}</div>
      <div class="sc-label">Avg Per Earner</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${party.member_count_earning}</div>
      <div class="sc-label">Earning Members</div>
    </div>
    <div class="stat-card">
      <div class="sc-value">${party.member_count_total}</div>
      <div class="sc-label">Total Members</div>
    </div>
  `;
}

function renderCategories(party) {
  const canvas = document.getElementById('party-donut');
  const legend = document.getElementById('party-cat-legend');

  const segments = Object.entries(party.categories).map(([k, v]) => ({
    value: v.monetary + v.inkind,
    colour: CAT_COLOURS[k],
    label: CAT_LABELS[k],
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
          &middot; ${s.count} payments
        </div>
      </div>
      <div style="font-family:var(--font-mono);font-weight:500">${formatCurrency(s.value)}</div>
    </div>
  `).join('');
}

function renderTopEarners(party) {
  const container = document.getElementById('party-top-earners');
  party.top_earners.forEach((e, i) => {
    const card = document.createElement('div');
    card.className = 'mini-card';
    card.style.setProperty('--party-colour', getPartyColour(party.party));
    card.style.marginBottom = '0.8rem';
    card.innerHTML = `
      <img class="mp-photo" src="${e.thumbnail_url}" alt="${esc(e.name)}"
           onerror="this.style.background='#E0DDD6';this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
      <div class="mini-info">
        <a href="mp.html?id=${e.mnis_id}" class="mini-name" style="color:inherit">${esc(e.name)}</a>
        <div class="mini-party">${esc(e.constituency || '')}</div>
        <div class="mini-amount">${formatCurrency(e.total_monetary_12m)}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderMembers(members) {
  const tbody = document.querySelector('#members-table tbody');
  members.forEach((m, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-rank">${i + 1}</td>
      <td><a href="mp.html?id=${m.mnis_id}">${esc(m.name)}</a></td>
      <td>${esc(m.constituency || '')}</td>
      <td class="col-num" data-value="${m.total_monetary_12m}">${formatCurrencyFull(m.total_monetary_12m)}</td>
      <td class="col-num" data-value="${m.total_inkind_12m}">${formatCurrency(m.total_inkind_12m)}</td>
      <td class="col-num" data-value="${m.donor_count}">${m.donor_count}</td>
    `;
    tbody.appendChild(tr);
  });
  makeSortable(document.getElementById('members-table'));
  makeSearchable('members-search', 'members-table');
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
