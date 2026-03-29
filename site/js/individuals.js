/* ============================================================
   The Westminster 100 — Individuals Page
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();
  const individuals = await loadData('individuals.json');

  renderPodium(individuals.slice(0, 3));
  renderEliteTen(individuals.slice(0, 10));
  renderRetained(individuals);
  renderLeaderboard(individuals);
})();

function createMPCard(mp, isHero = false) {
  const card = document.createElement('div');
  card.className = 'mp-card' + (isHero ? ' hero-card' : '');
  card.style.setProperty('--party-colour', getPartyColour(mp.party));

  const cats = mp.categories;
  const catEntries = Object.entries(cats)
    .map(([k, v]) => ({ cat: k, total: v.monetary + v.inkind }))
    .filter(c => c.total > 0)
    .sort((a, b) => b.total - a.total);

  const catListHTML = catEntries.slice(0, 4).map(c => `
    <li>
      <span><span class="cat-dot" style="background:${CAT_COLOURS[c.cat]}"></span><span class="cat-label">${CAT_LABELS[c.cat]}</span></span>
      <span class="cat-value">${formatCurrency(c.total)}</span>
    </li>
  `).join('');

  const topPayer = mp.top_payers[0];
  const patronHTML = topPayer
    ? `<div class="patron-line">Principal Patron: <span class="patron-name">${escapeHTML(topPayer.name)}</span></div>`
    : '';

  card.innerHTML = `
    <div class="mp-card-header">
      <span class="mp-rank">#${mp.rank}</span>
      <a href="party.html?name=${encodeURIComponent(mp.party)}" class="mp-party-label" style="background:${getPartyColour(mp.party)}">${escapeHTML(mp.party)}</a>
    </div>
    <div class="mp-profile">
      <img class="mp-photo" src="${mp.thumbnail_url}" alt="${escapeHTML(mp.name)}"
           onerror="this.style.background='#DDDBD8';this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
      <div class="mp-info">
        <a href="mp.html?id=${mp.mnis_id}" class="mp-name" style="color:inherit">${escapeHTML(mp.name)}</a>
        <div class="mp-constituency">${escapeHTML(mp.constituency || '')}</div>
      </div>
    </div>
    <div class="mp-categories">
      <div class="mp-donut-wrap"><canvas class="mp-donut"></canvas></div>
      <ul class="mp-cat-list">${catListHTML}</ul>
    </div>
    <div class="mp-total">
      <div class="mp-total-label">Total Earnings (12m)</div>
      <div class="mp-total-value">${formatCurrencyFull(mp.total_monetary_12m)}</div>
    </div>
    <div class="mp-footer">
      ${patronHTML}
      <div class="mp-stats-row">
        <div class="mp-stat">
          <div class="mp-stat-value">${mp.payment_count}</div>
          <div class="mp-stat-label">Revenue Streams</div>
        </div>
        <div class="mp-stat">
          <div class="mp-stat-value">${mp.donor_count}</div>
          <div class="mp-stat-label">Benefactors</div>
        </div>
      </div>
    </div>
  `;

  // Draw donut after DOM insertion
  requestAnimationFrame(() => {
    const canvas = card.querySelector('.mp-donut');
    if (canvas) {
      const segments = Object.entries(cats).map(([k, v]) => ({
        value: v.monetary + v.inkind,
        colour: CAT_COLOURS[k],
        label: CAT_LABELS[k],
      }));
      drawDonut(canvas, segments, {
        size: 80,
        centreColour: isHero ? '#E4BA6A' : '#292724',
      });
    }
  });

  return card;
}

function renderPodium(top3) {
  const container = document.getElementById('podium');
  if (!container) return;
  top3.forEach((mp, i) => {
    container.appendChild(createMPCard(mp, i === 0));
  });
}

function renderEliteTen(top10) {
  const container = document.getElementById('elite-ten');
  if (!container) return;
  // Skip top 3, show 4-10
  top10.slice(3).forEach(mp => {
    container.appendChild(createMPCard(mp, false));
  });
}

function renderRetained(individuals) {
  const tbody = document.querySelector('#retained-table tbody');
  if (!tbody) return;

  const retained = individuals
    .filter(mp => mp.active_regular_payments.length > 0)
    .sort((a, b) => {
      const rateA = Math.max(...a.active_regular_payments.map(p => p.annual_rate));
      const rateB = Math.max(...b.active_regular_payments.map(p => p.annual_rate));
      return rateB - rateA;
    });

  retained.forEach(mp => {
    mp.active_regular_payments.forEach(payment => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <span class="party-dot" style="background:${getPartyColour(mp.party)}"></span>
          <a href="mp.html?id=${mp.mnis_id}">${escapeHTML(mp.name)}</a>
        </td>
        <td class="col-hide-xs"><a href="party.html?name=${encodeURIComponent(mp.party)}">${escapeHTML(mp.party)}</a></td>
        <td>${escapeHTML(payment.payer)}</td>
        <td class="col-hide-xs">${escapeHTML(payment.job_title || '—')}</td>
        <td class="col-num" data-value="${payment.annual_rate}">${formatCurrencyFull(payment.annual_rate)}<span style="color:#999;font-size:0.75rem">/yr</span></td>
        <td class="col-hide-xs">${payment.start_date || '—'}</td>
      `;
      tbody.appendChild(tr);
    });
  });
}

function renderLeaderboard(individuals) {
  const tbody = document.querySelector('#leaderboard-table tbody');
  if (!tbody) return;

  individuals.forEach(mp => {
    const activeCats = Object.entries(mp.categories)
      .filter(([, v]) => v.monetary + v.inkind > 0)
      .length;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-rank">${mp.rank}</td>
      <td>
        <span class="party-dot" style="background:${getPartyColour(mp.party)}"></span>
        <a href="mp.html?id=${mp.mnis_id}">${escapeHTML(mp.name)}</a>
      </td>
      <td><a href="party.html?name=${encodeURIComponent(mp.party)}">${escapeHTML(mp.party)}</a></td>
      <td class="col-hide-xs">${escapeHTML(mp.constituency || '')}</td>
      <td class="col-num" data-value="${mp.total_monetary_12m}">${formatCurrencyFull(mp.total_monetary_12m)}</td>
      <td class="col-num col-hide-xs" data-value="${mp.total_inkind_12m}">${formatCurrency(mp.total_inkind_12m)}</td>
      <td class="col-num col-hide-xs" data-value="${activeCats}">${activeCats}</td>
    `;
    tbody.appendChild(tr);
  });

  const table = document.getElementById('leaderboard-table');
  makeSortable(table);
  makeSearchable('leaderboard-search', 'leaderboard-table');
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
