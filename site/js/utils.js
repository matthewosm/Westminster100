/* ============================================================
   Shared utilities for The Westminster 100
   ============================================================ */

const dataCache = {};

async function loadData(filename) {
  if (dataCache[filename]) return dataCache[filename];
  const resp = await fetch(`data/${filename}`);
  const data = await resp.json();
  dataCache[filename] = data;
  return data;
}

// Smart currency formatting: £1.79M / £736.6K / £2,450
function formatCurrency(amount) {
  if (amount >= 1_000_000) return '£' + (amount / 1_000_000).toFixed(2) + 'M';
  if (amount >= 100_000)   return '£' + (amount / 1_000).toFixed(0) + 'K';
  if (amount >= 10_000)    return '£' + (amount / 1_000).toFixed(1) + 'K';
  if (amount >= 1_000)     return '£' + Math.round(amount).toLocaleString('en-GB');
  if (amount > 0)          return '£' + amount.toFixed(0);
  return '£0';
}

// Full currency: £1,790,454
function formatCurrencyFull(amount) {
  return '£' + Math.round(amount).toLocaleString('en-GB');
}

let _partyColours = {};

async function initMeta() {
  const meta = await loadData('meta.json');
  _partyColours = meta.party_colours || {};
  // Populate footer dates
  const genEls = document.querySelectorAll('.gen-date');
  genEls.forEach(el => {
    el.textContent = `Data as of ${meta.as_of_date} (12 months from ${meta.since_date})`;
  });
  // Populate hero stats if present
  const totalEl = document.getElementById('hero-total');
  if (totalEl) totalEl.textContent = formatCurrency(meta.total_monetary_12m);
  const mpsEl = document.getElementById('hero-mps');
  if (mpsEl) mpsEl.textContent = meta.total_mps_with_payments;
  return meta;
}

function getPartyColour(party) {
  return _partyColours[party] || '#AAAAAA';
}

// Highlight active nav link
function initNav() {
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === page || (page === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });
}

// Generic table sorting
function makeSortable(table) {
  const headers = table.querySelectorAll('thead th[data-sort]');
  headers.forEach((th, colIdx) => {
    th.addEventListener('click', () => {
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const sortKey = th.dataset.sort; // 'num' or 'text'
      const isDesc = th.classList.contains('sort-asc');

      // Clear other headers
      headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(isDesc ? 'sort-desc' : 'sort-asc');

      const idx = Array.from(th.parentNode.children).indexOf(th);
      rows.sort((a, b) => {
        let va = a.children[idx]?.dataset.value ?? a.children[idx]?.textContent.trim();
        let vb = b.children[idx]?.dataset.value ?? b.children[idx]?.textContent.trim();
        if (sortKey === 'num') {
          va = parseFloat(va) || 0;
          vb = parseFloat(vb) || 0;
          return isDesc ? va - vb : vb - va;
        }
        return isDesc ? va.localeCompare(vb) : vb.localeCompare(va);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

// Text search filter for tables
function makeSearchable(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    table.querySelectorAll('tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

// Category colours for donut charts
const CAT_COLOURS = {
  '1.1': '#D79938',  // gold
  '1.2': '#B57D22',  // dark gold
  '2':   '#3B82F6',  // blue
  '3':   '#8B5CF6',  // purple
  '4':   '#10B981',  // green
  '5':   '#F59E0B',  // amber
};

const CAT_LABELS = {
  '1.1': 'Freelance Enterprise',
  '1.2': 'Retained Services',
  '2':   'Philanthropic Support',
  '3':   'Lifestyle Benefits',
  '4':   'International Fact-Finding',
  '5':   'Diplomatic Gifts',
};
