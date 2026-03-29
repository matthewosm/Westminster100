/* ============================================================
   The Westminster 100 — Parties Page ("The Franchises")
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();
  const parties = await loadData('parties.json');

  renderPartyCards(parties);
  renderROIChart(parties);
  renderCategoryComparison(parties);
  renderStarPlayers(parties);
})();

function renderPartyCards(parties) {
  const container = document.getElementById('party-cards');
  if (!container) return;

  parties.forEach(p => {
    const card = document.createElement('div');
    card.className = 'party-card';
    card.style.setProperty('--party-colour', getPartyColour(p.party));

    const star = p.star_player;
    const starHTML = star ? `
      <div class="party-star">
        <img src="${star.thumbnail_url}" alt="${escapeHTML(star.name)}"
             onerror="this.style.background='#DDDBD8';this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
        <div>
          <div class="star-label">Star Player</div>
          <a href="mp.html?id=${star.mnis_id}" style="font-weight:600;color:inherit">${escapeHTML(star.name)}</a>
          <div style="font-family:var(--font-mono);font-size:0.82rem;color:var(--gold-dark)">${formatCurrency(star.total_monetary_12m)}</div>
        </div>
      </div>
    ` : '';

    card.innerHTML = `
      <h4><a href="party.html?name=${encodeURIComponent(p.party)}" style="color:inherit">${escapeHTML(p.party)}</a></h4>
      <div class="party-total">${formatCurrency(p.total_monetary_12m)}</div>
      <div class="party-meta">
        ${p.member_count_earning} earning members of ${p.member_count_total} &middot;
        ${formatCurrency(p.avg_per_earning_member)} avg per earner
      </div>
      ${starHTML}
    `;
    container.appendChild(card);
  });
}

function renderROIChart(parties) {
  const canvas = document.getElementById('roi-chart');
  if (!canvas) return;

  const bars = parties
    .filter(p => p.avg_per_earning_member > 0)
    .sort((a, b) => b.avg_per_earning_member - a.avg_per_earning_member)
    .slice(0, 12)
    .map(p => ({
      label: p.party,
      value: p.avg_per_earning_member,
      colour: getPartyColour(p.party),
    }));

  drawHorizontalBars(canvas, bars, { labelWidth: 160, maxBarWidth: 280, valueWidth: 100 });
}

function renderCategoryComparison(parties) {
  const container = document.getElementById('category-bars');
  if (!container) return;

  const topParties = parties.filter(p => p.total_monetary_12m > 0).slice(0, 6);

  topParties.forEach(p => {
    const row = document.createElement('div');
    row.className = 'chart-container';
    row.style.marginBottom = '1rem';

    const cats = p.categories;
    const total = Object.values(cats).reduce((s, v) => s + v.monetary + v.inkind, 0);
    if (total <= 0) return;

    const barsHTML = Object.entries(cats)
      .filter(([, v]) => v.monetary + v.inkind > 0)
      .sort(([, a], [, b]) => (b.monetary + b.inkind) - (a.monetary + a.inkind))
      .map(([cat, v]) => {
        const catTotal = v.monetary + v.inkind;
        const pct = (catTotal / total * 100).toFixed(1);
        return `
          <div style="display:flex;align-items:center;gap:0.8rem;margin:0.3rem 0">
            <span style="width:160px;font-size:0.8rem;text-align:right;color:#666">${CAT_LABELS[cat]}</span>
            <div style="flex:1;background:#F2F2F0;border-radius:3px;height:20px;overflow:hidden">
              <div style="width:${pct}%;background:${CAT_COLOURS[cat]};height:100%;border-radius:3px;min-width:2px"></div>
            </div>
            <span style="width:70px;font-family:var(--font-mono);font-size:0.78rem">${formatCurrency(catTotal)}</span>
          </div>
        `;
      }).join('');

    row.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:0.5rem">
        <span class="party-dot" style="background:${getPartyColour(p.party)}"></span>
        <strong style="font-family:var(--font-serif)">${escapeHTML(p.party)}</strong>
        <span style="color:#999;font-size:0.85rem">${formatCurrency(total)} total</span>
      </div>
      ${barsHTML}
    `;
    container.appendChild(row);
  });
}

function renderStarPlayers(parties) {
  const container = document.getElementById('star-players');
  if (!container) return;

  parties.forEach(p => {
    if (!p.star_player) return;
    const star = p.star_player;
    const card = document.createElement('div');
    card.className = 'mini-card';
    card.style.setProperty('--party-colour', getPartyColour(p.party));
    card.innerHTML = `
      <img class="mp-photo" src="${star.thumbnail_url}" alt="${escapeHTML(star.name)}"
           onerror="this.style.background='#DDDBD8';this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
      <div class="mini-info">
        <div class="mini-name">${escapeHTML(star.name)}</div>
        <div class="mini-party">${escapeHTML(p.party)} &middot; ${escapeHTML(star.constituency || '')}</div>
        <div class="mini-amount">${formatCurrency(star.total_monetary_12m)}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
