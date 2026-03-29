/* ============================================================
   The Westminster 100 — Philanthropists Page
   ============================================================ */

(async function() {
  const meta = await initMeta();
  initNav();
  const philanthropists = await loadData('philanthropists.json');

  const totalDonated = philanthropists.reduce((s, p) => s + p.total_donated, 0);
  const heroTotal = document.getElementById('hero-donated');
  if (heroTotal) heroTotal.textContent = formatCurrency(totalDonated);
  const heroCount = document.getElementById('hero-philanthropists');
  if (heroCount) heroCount.textContent = philanthropists.length;

  renderPhilanthropistPodium(philanthropists.slice(0, 3));
  renderPhilanthropistTable(philanthropists);
})();

function renderPhilanthropistPodium(top3) {
  const container = document.getElementById('philanthropist-podium');
  if (!container) return;

  top3.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'donor-card';
    card.style.borderTopColor = '#2E7D32'; // green for giving

    const donationsHTML = p.donations.slice(0, 5).map(d => `
      <li>
        <span>
          <span class="port-name">${escapeHTML(d.payer)}</span>
          <span class="port-party">&rarr; ${escapeHTML(d.donated_to)}</span>
        </span>
        <span class="port-amount">${formatCurrency(d.amount)}</span>
      </li>
    `).join('');

    const moreHTML = p.donations.length > 5
      ? `<li style="color:#999;font-style:italic">+ ${p.donations.length - 5} more donations</li>`
      : '';

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <a href="mp.html?id=${p.mnis_id}" class="donor-name" style="color:inherit">${escapeHTML(p.name)}</a>
          <div class="donor-status"><a href="party.html?name=${encodeURIComponent(p.party)}" style="color:inherit">${escapeHTML(p.party)}</a> &middot; ${escapeHTML(p.constituency || '')}</div>
        </div>
        <span class="mp-rank" style="color:#2E7D32">#${p.rank}</span>
      </div>
      <div style="display:flex;align-items:center;gap:1rem;margin:0.8rem 0">
        <img class="mp-photo" src="${p.thumbnail_url}" alt="${escapeHTML(p.name)}" style="width:56px;height:70px"
             onerror="this.style.background='#DDDBD8';this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
        <div class="donor-total" style="color:#2E7D32">${formatCurrencyFull(p.total_donated)}</div>
      </div>
      <div style="font-size:0.8rem;color:#666;margin-bottom:0.5rem">
        ${p.donations.length} ${p.donations.length === 1 ? 'donation' : 'donations'} to ${[...new Set(p.donations.map(d => d.donated_to))].join(', ')}
      </div>
      <ul class="donor-portfolio">${donationsHTML}${moreHTML}</ul>
    `;
    container.appendChild(card);
  });
}

function renderPhilanthropistTable(philanthropists) {
  const tbody = document.querySelector('#philanthropist-table tbody');
  if (!tbody) return;

  philanthropists.forEach(p => {
    const recipients = [...new Set(p.donations.map(d => d.donated_to))].join(', ');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-rank">${p.rank}</td>
      <td>
        <span class="party-dot" style="background:${getPartyColour(p.party)}"></span>
        <a href="mp.html?id=${p.mnis_id}">${escapeHTML(p.name)}</a>
      </td>
      <td><a href="party.html?name=${encodeURIComponent(p.party)}">${escapeHTML(p.party)}</a></td>
      <td class="col-num" data-value="${p.total_donated}">${formatCurrencyFull(p.total_donated)}</td>
      <td class="col-num" data-value="${p.donations.length}">${p.donations.length}</td>
      <td>${escapeHTML(recipients)}</td>
    `;
    tbody.appendChild(tr);
  });

  const table = document.getElementById('philanthropist-table');
  makeSortable(table);
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
