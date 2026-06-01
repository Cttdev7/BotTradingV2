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

const BOTS = [
  {
    id: 'momentum', name: 'Momentum Alpha', market: 'crypto', glyph: '↗',
    strategy: 'Momentum cross-actifs', venue: 'Binance · Coinbase',
    status: 'running', capital: 42500, allocPct: 34,
    pnlDayPct: 2.34, pnlDayAbs: 970, pnlTotalPct: 38.2, pnlTotalAbs: 11740,
    winRate: 64, sharpe: 1.82, maxDD: -12.4, trades: 1284, openPos: 3,
    series: makeSeries(11, 90, 0.0042, 0.022, 30800),
  },
  {
    id: 'meanrev', name: 'Mean Reversion', market: 'stocks', glyph: '⇄',
    strategy: 'Retour à la moyenne intraday', venue: 'Alpaca · IBKR',
    status: 'running', capital: 31200, allocPct: 25,
    pnlDayPct: -0.62, pnlDayAbs: -195, pnlTotalPct: 19.7, pnlTotalAbs: 5135,
    winRate: 71, sharpe: 2.04, maxDD: -7.8, trades: 2641, openPos: 5,
    series: makeSeries(27, 90, 0.0026, 0.012, 26060),
  },
  {
    id: 'polyedge', name: 'Polymarket Edge', market: 'polymarket', glyph: '◑',
    strategy: 'Arbitrage de probabilités', venue: 'Polymarket',
    status: 'running', capital: 18600, allocPct: 15,
    pnlDayPct: 4.10, pnlDayAbs: 732, pnlTotalPct: 52.6, pnlTotalAbs: 6410,
    winRate: 58, sharpe: 1.39, maxDD: -18.9, trades: 312, openPos: 7,
    series: makeSeries(44, 90, 0.0058, 0.031, 12190),
  },
  {
    id: 'grid', name: 'Grid Trader', market: 'crypto', glyph: '▦',
    strategy: 'Grille range-bound', venue: 'Kraken',
    status: 'running', capital: 21000, allocPct: 17,
    pnlDayPct: 0.41, pnlDayAbs: 86, pnlTotalPct: 11.3, pnlTotalAbs: 2134,
    winRate: 82, sharpe: 1.61, maxDD: -5.2, trades: 5820, openPos: 12,
    series: makeSeries(63, 90, 0.0016, 0.008, 18866),
  },
  {
    id: 'earnings', name: 'Earnings Drift', market: 'stocks', glyph: '◆',
    strategy: 'Dérive post-résultats', venue: 'IBKR',
    status: 'paused', capital: 11500, allocPct: 9,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 8.4, pnlTotalAbs: 891,
    winRate: 55, sharpe: 1.12, maxDD: -14.1, trades: 184, openPos: 0,
    series: makeSeries(81, 90, 0.0021, 0.018, 10609),
  },
  {
    id: 'arb', name: 'Arbitrage X', market: 'crypto', glyph: '∞',
    strategy: 'Arb. inter-exchange', venue: 'Multi-venue',
    status: 'paused', capital: 0, allocPct: 0,
    pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 4.1, pnlTotalAbs: 410,
    winRate: 91, sharpe: 2.51, maxDD: -2.1, trades: 9210, openPos: 0,
    series: makeSeries(99, 90, 0.0009, 0.004, 10000),
  },
];

// open positions per bot
const POSITIONS = {
  momentum: [
    { sym: 'BTC', name: 'Bitcoin', side: 'long', qty: 0.42, entry: 61240, mark: 63110, value: 26506 },
    { sym: 'ETH', name: 'Ethereum', side: 'long', qty: 3.1, entry: 3380, mark: 3512, value: 10887 },
    { sym: 'SOL', name: 'Solana', side: 'short', qty: 38, entry: 148, mark: 142, value: 5396 },
  ],
  meanrev: [
    { sym: 'AAPL', name: 'Apple', side: 'long', qty: 40, entry: 212.4, mark: 209.8, value: 8392 },
    { sym: 'MSFT', name: 'Microsoft', side: 'long', qty: 12, entry: 438, mark: 441.2, value: 5294 },
    { sym: 'NVDA', name: 'Nvidia', side: 'short', qty: 30, entry: 124.5, mark: 121.9, value: 3657 },
    { sym: 'AMZN', name: 'Amazon', side: 'long', qty: 28, entry: 186.2, mark: 188.4, value: 5275 },
    { sym: 'TSLA', name: 'Tesla', side: 'long', qty: 18, entry: 244, mark: 241.6, value: 4349 },
  ],
  polyedge: [
    { sym: 'YES', name: 'Fed baisse les taux en juin', side: 'yes', qty: 4200, entry: 0.62, mark: 0.71, value: 2982 },
    { sym: 'NO', name: 'Récession US en 2026', side: 'no', qty: 6100, entry: 0.55, mark: 0.61, value: 3721 },
    { sym: 'YES', name: 'BTC > 100k fin 2026', side: 'yes', qty: 3300, entry: 0.41, mark: 0.48, value: 1584 },
    { sym: 'YES', name: 'Élection — candidat A', side: 'yes', qty: 2800, entry: 0.34, mark: 0.39, value: 1092 },
  ],
  grid: [
    { sym: 'ETH', name: 'Ethereum', side: 'long', qty: 2.0, entry: 3460, mark: 3512, value: 7024 },
    { sym: 'BNB', name: 'BNB', side: 'long', qty: 9, entry: 588, mark: 601, value: 5409 },
  ],
  earnings: [],
  arb: [],
};

// transaction history (newest first)
const SIDES = ['buy', 'sell'];
function makeTxns() {
  const rnd = mulberry32(7);
  const pool = [
    ['momentum', 'crypto', 'BTC', 63000, 0.01], ['momentum', 'crypto', 'ETH', 3500, 0.4],
    ['momentum', 'crypto', 'SOL', 145, 6], ['meanrev', 'stocks', 'AAPL', 210, 5],
    ['meanrev', 'stocks', 'MSFT', 440, 2], ['meanrev', 'stocks', 'NVDA', 122, 8],
    ['grid', 'crypto', 'ETH', 3500, 0.2], ['grid', 'crypto', 'BNB', 600, 1],
    ['polyedge', 'polymarket', 'Fed juin · YES', 0.68, 800],
    ['polyedge', 'polymarket', 'Récession · NO', 0.59, 1200],
    ['earnings', 'stocks', 'TSLA', 242, 4],
  ];
  const out = [];
  let t = Date.now();
  for (let i = 0; i < 60; i++) {
    const p = pool[Math.floor(rnd() * pool.length)];
    const [bot, market, sym, base, q] = p;
    const side = SIDES[Math.floor(rnd() * 2)];
    const price = +(base * (1 + (rnd() - 0.5) * 0.04)).toFixed(base < 10 ? 3 : 2);
    const qty = +(q * (0.5 + rnd())).toFixed(market === 'polymarket' ? 0 : 3);
    const value = price * qty;
    const pnl = side === 'sell' ? +((rnd() - 0.42) * value * 0.08).toFixed(2) : null;
    t -= Math.floor(rnd() * 5400_000) + 600_000;
    out.push({ id: i, bot, market, sym, side, price, qty, value, pnl, time: t });
  }
  return out;
}
const TXNS = makeTxns();

// portfolio aggregates — recalculable depuis les bots courants
function computePortfolio(bots) {
  const totalCapital = bots.reduce((s, b) => s + b.capital, 0);
  const cash = 28800;
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
