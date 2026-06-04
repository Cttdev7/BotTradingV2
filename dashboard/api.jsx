// ============================================================
// api.jsx — connexion dashboard ↔ serveur bot (localhost:5000)
// Récupère les données réelles et les convertit au format attendu
// par les composants existants.
// ============================================================

const API = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:5000'
  : (window.BOT_API_URL || '');

// ── Fetch helpers ─────────────────────────────────────────────────────────────

async function apiFetch(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

// ── Mappers : format API → format composants ──────────────────────────────────

function mapPosition(p) {
  const outcome = p.outcome || p.side || 'YES';
  const entry   = parseFloat(p.avgPrice   || p.price       || 0);
  const mark    = parseFloat(p.curPrice   || p.currentPrice || entry);
  const qty     = parseFloat(p.size       || p.shares      || 0);
  const value   = parseFloat(p.cashBalance|| p.currentValue|| qty * mark);
  return {
    sym:   outcome,
    name:  p.title || p.question || p.conditionId?.slice(0, 32) || 'Marché',
    side:  outcome.toLowerCase(),
    qty,
    entry,
    mark,
    value,
  };
}

function mapActivity(a) {
  // Polymarket data-api retourne { action: "BUY"/"SELL" } ou { side: "buy"/"sell" }
  const rawSide = (a.action || a.side || 'buy').toLowerCase();
  const side    = rawSide.includes('sell') ? 'sell' : 'buy';
  const price   = parseFloat(a.price || 0);
  const qty     = parseFloat(a.size  || a.shares || 0);
  const ts      = a.timestamp ? new Date(a.timestamp).getTime()
                : a.createdAt ? new Date(a.createdAt).getTime()
                : Date.now();
  return {
    id:     a.id || a.transactionHash || Math.random(),
    bot:    'polyedge',
    market: 'polymarket',
    sym:    a.outcome || a.asset || 'YES',
    side,
    price,
    qty,
    value:  price * qty,
    pnl:    null,
    time:   ts,
  };
}

// ── Fetch principal ───────────────────────────────────────────────────────────

async function fetchBotData() {
  const [status, positions, activity, wallet] = await Promise.all([
    apiFetch('/api/status'),
    apiFetch('/api/positions').catch(() => []),
    apiFetch('/api/activity?limit=50').catch(() => []),
    apiFetch('/api/wallet').catch(() => ({})),
  ]);

  const usdc       = parseFloat(status?.balance?.usdc || 0);
  const connected  = status?.connected === true;
  const mappedPos  = Array.isArray(positions) ? positions.map(mapPosition) : [];
  const mappedAct  = Array.isArray(activity)  ? activity.map(mapActivity)  : [];

  return { connected, usdc, positions: mappedPos, activity: mappedAct, wallet };
}

// ── Hook React ────────────────────────────────────────────────────────────────

function usePolymarketData(intervalMs = 30000) {
  const [data, setData] = React.useState({
    connected: false,
    usdc: 0,
    positions: [],
    activity: [],
  });
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const result = await fetchBotData();
      setData(result);
    } catch {
      setData(d => ({ ...d, connected: false }));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { ...data, loading, refresh };
}

Object.assign(window, { usePolymarketData, fetchBotData });
