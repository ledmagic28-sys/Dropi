/* ═══════════════════════════════════════════════════
   Dropi Market Radar — Dashboard JS
═══════════════════════════════════════════════════ */

const FLAGS = { CO: '🇨🇴', MX: '🇲🇽', AR: '🇦🇷', CL: '🇨🇱', PE: '🇵🇪' };
const CURRENCY_FORMAT = {
  COP: v => `$${Math.round(v).toLocaleString('es-CO')} COP`,
  MXN: v => `$${Math.round(v).toLocaleString('es-MX')} MXN`,
  ARS: v => `$${Math.round(v).toLocaleString('es-AR')} ARS`,
  CLP: v => `$${Math.round(v).toLocaleString('es-CL')} CLP`,
  PEN: v => `S/${Math.round(v).toLocaleString('es-PE')}`,
  USD: v => `$${Math.round(v).toLocaleString('en-US')} USD`,
};

const $ = id => document.getElementById(id);
const STATES = ['empty-state', 'loading-state', 'error-state', 'results'];
function show(which) {
  STATES.forEach(s => $(s).hidden = (s !== which));
}

// ─── Historial en localStorage ───
const HIST_KEY = 'dropi_history';
function getHistory() {
  try { return JSON.parse(localStorage.getItem(HIST_KEY) || '[]'); }
  catch { return []; }
}
function addHistory(entry) {
  const h = getHistory().filter(x => x.query !== entry.query).slice(0, 9);
  h.unshift(entry);
  localStorage.setItem(HIST_KEY, JSON.stringify(h));
  renderHistory();
}
function renderHistory() {
  const list = getHistory();
  const section = $('history-section');
  const container = $('history-list');
  if (!list.length) { section.hidden = true; return; }
  section.hidden = false;
  container.innerHTML = '';
  list.forEach(item => {
    const el = document.createElement('div');
    el.className = 'history-item';
    const levelColor = {
      TESTEAR: 'green',
      TESTEAR_DIFERENCIACION: 'yellow',
      EVITAR: 'red',
      SIN_DATOS: 'grey',
    }[item.level] || 'grey';
    el.innerHTML = `
      <span class="dot-lvl ${levelColor}"></span>
      <span>${item.query}</span>
      <span style="color: var(--muted-2); font-size: 11px;">${FLAGS[item.country] || ''}</span>
    `;
    el.onclick = () => {
      $('query').value = item.query;
      $('country').value = item.country;
      $('search-form').dispatchEvent(new Event('submit', { cancelable: true }));
    };
    container.appendChild(el);
  });
}

// ─── Fetch ───
async function triangulate(query, country) {
  const resp = await fetch('/api/triangulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, country }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Error ${resp.status}`);
  }
  return resp.json();
}

// ─── Render ───
let LAST_RESULT = null;

function render(data) {
  LAST_RESULT = data;

  $('result-query').textContent = data.query;
  $('result-country-flag').textContent = FLAGS[data.country] || '🌍';

  // Veredicto
  const levelMap = {
    TESTEAR:               { color: 'green',  icon: '🟢', label: 'TESTEAR' },
    TESTEAR_DIFERENCIACION:{ color: 'yellow', icon: '⚡', label: 'TESTEAR CON DIFERENCIACIÓN' },
    EVITAR:                { color: 'red',    icon: '🔴', label: 'EVITAR / PIVOTAR' },
    SIN_DATOS:             { color: 'grey',   icon: '❓', label: 'SIN DATOS' },
  };
  const v = levelMap[data.recommendation_level] || levelMap.SIN_DATOS;
  const box = $('verdict-box');
  box.className = `verdict-box verdict-${v.color}`;
  $('verdict-icon').textContent = v.icon;
  $('verdict-level').textContent = v.label;
  $('verdict-text').textContent = data.recommendation;

  // Gauges
  $('demand-bar').style.width = `${data.demand_score}%`;
  $('sat-bar').style.width    = `${data.saturation_score}%`;
  $('demand-value').textContent = demandLabel(data.demand_score);
  $('sat-value').textContent    = saturationLabel(data.saturation_score);
  $('demand-label').textContent = `${data.demand_score}/100`;
  $('sat-label').textContent    = `${data.saturation_score}/100`;

  // Totales
  $('total-sellers').textContent = fmt(data.total_sellers);
  $('total-ads').textContent     = fmt(data.total_ads);
  $('oldest-days').textContent   = data.oldest_ad_days > 0 ? `${data.oldest_ad_days}d` : '—';

  // Mercado Libre
  if (data.mercadolibre) {
    const ml = data.mercadolibre;
    const fmtP = CURRENCY_FORMAT[ml.currency] || (v => `$${fmt(v)}`);
    $('ml-sellers').textContent   = fmt(ml.unique_sellers);
    $('ml-listings').textContent  = fmt(ml.total_listings);
    $('ml-avg-price').textContent = ml.avg_price ? fmtP(ml.avg_price) : '—';
    $('ml-range').textContent     = (ml.min_price && ml.max_price) ? `${fmtP(ml.min_price)} – ${fmtP(ml.max_price)}` : '—';
    $('ml-sales').textContent     = fmt(ml.estimated_monthly_sales);
  } else {
    ['ml-sellers','ml-listings','ml-avg-price','ml-range','ml-sales'].forEach(id => $(id).textContent = '—');
  }

  // Ads Library
  if (data.ads_library) {
    const a = data.ads_library;
    $('ads-advertisers').textContent = fmt(a.unique_advertisers);
    $('ads-total').textContent  = fmt(a.total_ads);
    $('ads-oldest').textContent = a.oldest_ad_days > 0 ? `${a.oldest_ad_days} días` : '—';
    $('ads-new7').textContent   = fmt(a.new_entrants_7d);
    $('ads-avg').textContent    = a.avg_days_running ? `${Math.round(a.avg_days_running)} días` : '—';
  } else {
    ['ads-advertisers','ads-total','ads-oldest','ads-new7','ads-avg'].forEach(id => $(id).textContent = '—');
  }

  // Marketplace
  if (data.marketplace) {
    const m = data.marketplace;
    const fmtP = CURRENCY_FORMAT[m.currency] || (v => `$${fmt(v)}`);
    $('mkt-listings').textContent = fmt(m.total_listings);
    $('mkt-min').textContent      = m.min_price ? fmtP(m.min_price) : '—';
    $('mkt-max').textContent      = m.max_price ? fmtP(m.max_price) : '—';
    $('mkt-currency').textContent = m.currency || '—';
    if (m.error) {
      $('mkt-error-row').hidden = false;
      $('mkt-error').textContent = m.error;
    } else {
      $('mkt-error-row').hidden = true;
    }
  } else {
    ['mkt-listings','mkt-min','mkt-max','mkt-currency'].forEach(id => $(id).textContent = '—');
  }

  addHistory({
    query: data.query,
    country: data.country,
    level: data.recommendation_level,
    at: Date.now(),
  });

  show('results');
  window.scrollTo({ top: $('results').offsetTop - 40, behavior: 'smooth' });
}

function demandLabel(s) {
  if (s >= 70) return 'ALTA';
  if (s >= 40) return 'MEDIA';
  if (s >= 15) return 'BAJA';
  return 'MUY BAJA';
}
function saturationLabel(s) {
  if (s >= 75) return 'MUY ALTA';
  if (s >= 50) return 'MEDIA';
  if (s >= 25) return 'BAJA';
  return 'MUY BAJA';
}
function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n/1_000_000).toFixed(1) + 'M';
  if (n >= 10_000) return (n/1_000).toFixed(1) + 'K';
  return new Intl.NumberFormat('es-CO').format(Math.round(n));
}

// ─── Submit flow ───
async function onSubmit(e) {
  e.preventDefault();
  const query = $('query').value.trim();
  const country = $('country').value;
  if (!query) return;

  const btn = $('analyze-btn');
  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Analizando…';
  btn.querySelector('.btn-loader').hidden = false;

  show('loading-state');

  try {
    const data = await triangulate(query, country);
    render(data);
  } catch (err) {
    $('error-title').textContent = 'No pudimos analizar este producto';
    $('error-message').textContent = err.message || String(err);
    show('error-state');
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Analizar';
    btn.querySelector('.btn-loader').hidden = true;
  }
}

function resetToEmpty() {
  $('query').value = '';
  LAST_RESULT = null;
  show('empty-state');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function downloadJson() {
  if (!LAST_RESULT) return;
  const blob = new Blob([JSON.stringify(LAST_RESULT, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `triangulacion_${LAST_RESULT.query.replace(/\s+/g, '_')}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  $('search-form').addEventListener('submit', onSubmit);
  $('download-btn').addEventListener('click', downloadJson);

  // Demo chips
  document.querySelectorAll('.chip').forEach(c => {
    c.addEventListener('click', () => {
      $('query').value = c.dataset.q;
      $('search-form').dispatchEvent(new Event('submit', { cancelable: true }));
    });
  });

  renderHistory();
});
