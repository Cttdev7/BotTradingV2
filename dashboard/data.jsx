// ============================================================
// data.jsx — mock data + helpers for TradingBot
// Deterministic seeded series so charts look real & stable.
// ============================================================

// --- seeded RNG ---
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// equity curve: gentle drift + volatility random walk, normalized to start
function makeSeries(seed, n, drift, vol, start = 100) {
  const rnd = mulberry32(seed);
  const out = [];
  let v = start;
  for (let i = 0; i < n; i++) {
    const shock = (rnd() - 0.5) * 2 * vol;
    v = v * (1 + drift + shock);
    out.push(Math.max(1, v));
  }
  return out;
}

// money / pct formatting
const fmtUSD = (n, dp = 0) =>
  (n < 0 ? '-' : '') + '$' + Math.abs(n).toLocaleString('en-US', {
    minimumFractionDigits: dp, maximumFractionDigits: dp });
const fmtSigned = (n, dp = 2) => (n >= 0 ? '+' : '') + n.toFixed(dp);
const fmtPct = (n, dp = 2) => fmtSigned(n, dp) + '%';
const fmtNum = (n) => n.toLocaleString('en-US');
const fmtSignedUSD = (n, dp = 0) => (n >= 0 ? '+' : '-') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });

const MARKETS = {
  crypto:     { label: 'Crypto',     color: 'var(--orange)', tint: '#FF9500' },
  stocks:     { label: 'Actions',    color: 'var(--green)',  tint: '#34C759' },
  polymarket: { label: 'Polymarket', color: 'var(--purple)', tint: '#5E5CE6' },
};

// TODO: API — capital, status et openPos sont mis à jour en temps réel par api.jsx
const BOTS = [
  {
    id: 'polyedge', name: 'Polymarket Weather', market: 'polymarket', glyph: '🌦',
    strategy: 'Arbitrage météo 80%+', venue: 'Polymarket',
    status: 'paused', capital: 0, allocPct: 50,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
    winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
    series: Array(90).fill(0),
  },
  {
    id: 'polycrypto', name: 'Crypto Horaire', market: 'polymarket', glyph: '₿',
    strategy: 'Arbitrage crypto horaire 80%+', venue: 'Polymarket',
    status: 'paused', capital: 0, allocPct: 33,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
    winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
    series: Array(90).fill(0),
  },
  {
    id: 'polycrypto4h', name: 'Crypto 4H', market: 'polymarket', glyph: '⏱',
    strategy: 'Arbitrage crypto 4h 80%+', venue: 'Polymarket',
    status: 'paused', capital: 0, allocPct: 17,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
    winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
    series: Array(90).fill(0),
  },
  {
    id: 'chengdu', name: 'Chengdu Temp', market: 'polymarket', glyph: '🌡️',
    type: 'temperature', citySlug: 'chengdu',
    strategy: 'Température max Chengdu 80%+', venue: 'Polymarket',
    status: 'running', capital: 0, allocPct: 0,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
    winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
    series: Array(90).fill(0),
  },
  {
    id: 'seoul', name: 'Séoul Temp', market: 'polymarket', glyph: '🏙️',
    type: 'temperature', citySlug: 'seoul',
    strategy: 'Température max Séoul 80%+', venue: 'Polymarket',
    status: 'running', capital: 0, allocPct: 0,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
    winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
    series: Array(90).fill(0),
  },
];

// TODO: API — positions mises à jour en temps réel par api.jsx
const POSITIONS = {
  polyedge:     [],
  polycrypto:   [],
  polycrypto4h: [],
};

// TODO: API — transactions chargées depuis api.jsx (get_activity)
const TXNS = [];

// portfolio aggregates — recalculable depuis les bots courants
function computePortfolio(bots) {
  const totalCapital = bots.reduce((s, b) => s + b.capital, 0);
  const cash = 0; // pas de liquidités séparées — capital = solde USDC du wallet
  const totalValue = totalCapital + cash;
  const dayAbs = bots.reduce((s, b) => s + b.pnlDayAbs, 0);
  const dayPct = totalValue > dayAbs ? (dayAbs / (totalValue - dayAbs)) * 100 : 0;
  const totalPnlAbs = bots.reduce((s, b) => s + b.pnlTotalAbs, 0);
  const n = 90;
  const agg = Array.from({ length: n }, (_, i) =>
    bots.reduce((s, b) => s + (b.series[i] || 0), 0) + cash);
  return { totalCapital, cash, totalValue, dayAbs, dayPct, totalPnlAbs, series: agg };
}
const PORTFOLIO = computePortfolio(BOTS);

const RANGES = ['1J', '1S', '1M', '3M', '1A', 'Max'];
// slice a 90-pt series to a range (approx)
function sliceRange(series, range) {
  const map = { '1J': 14, '1S': 24, '1M': 38, '3M': 64, '1A': 90, 'Max': 90 };
  const k = map[range] || 90;
  return series.slice(series.length - k);
}

Object.assign(window, {
  BOTS, POSITIONS, TXNS, PORTFOLIO, MARKETS, RANGES,
  fmtUSD, fmtSigned, fmtPct, fmtNum, fmtSignedUSD, sliceRange, makeSeries, computePortfolio,
});
