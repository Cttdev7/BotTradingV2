// page_zerotohero_results.jsx — Résultats DRY_RUN de ZeroToHeroBTC
const ZTH_SB_URL = window.SB_URL;
const ZTH_SB_KEY = window.SB_KEY;

function ZeroToHeroResultsPage({ onBack }) {
  const { Card, Icon, StatusPill } = window;
  const [trades,     setTrades]     = React.useState([]);
  const [loading,    setLoading]    = React.useState(true);
  const [lastUpdate, setLastUpdate] = React.useState(null);

  const sbFetch = (table, params = '') =>
    fetch(`${ZTH_SB_URL}/rest/v1/${table}?${params}`, {
      headers: { apikey: ZTH_SB_KEY, Authorization: `Bearer ${ZTH_SB_KEY}` }
    }).then(r => r.json()).catch(() => []);

  const load = React.useCallback(async () => {
    setLoading(true);
    const t = await sbFetch('zerotoherobtc_trades', 'order=id.desc&limit=200');
    if (Array.isArray(t)) setTrades(t);
    setLastUpdate(new Date());
    setLoading(false);
  }, []);

  React.useEffect(() => { load(); const id = setInterval(load, 60 * 1000); return () => clearInterval(id); }, [load]);

  const resolved = trades.filter(t => t.resolved);
  const pending  = trades.filter(t => !t.resolved);
  const won      = resolved.filter(t => t.win);
  const lost     = resolved.filter(t => !t.win);
  const winRate  = resolved.length > 0 ? (won.length / resolved.length * 100) : 0;
  const totalStaked = trades.reduce((s, t) => s + parseFloat(t.amount_usdc || 0), 0);

  const timeAgo = d => { if (!d) return '—'; const s = Math.floor((Date.now() - d) / 1000); return s < 60 ? "à l'instant" : `il y a ${Math.floor(s / 60)}min`; };
  const outcomeColor = o => (o || '').toLowerCase() === 'up' ? 'var(--green)' : 'var(--red)';

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)', width: 38, height: 38, borderRadius: 11, cursor: 'pointer', display: 'grid', placeItems: 'center', color: 'var(--accent)', transform: 'scaleX(-1)' }}>
          <Icon name="chevron" size={20} stroke={2.4} />
        </button>
        <div style={{ width: 46, height: 46, borderRadius: 14, background: 'color-mix(in oklab,#f59e0b 15%,var(--bg-elev))', border: '1.5px solid color-mix(in oklab,#f59e0b 40%,transparent)', display: 'grid', placeItems: 'center', fontSize: 22 }}>📝</div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Résultats ZeroToHero</h2>
            <StatusPill status="running" />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>DRY_RUN — mis à jour {timeAgo(lastUpdate)}</div>
        </div>
        <button onClick={load} className="tap" style={{ border: 'none', background: 'var(--fill)', padding: '8px 14px', borderRadius: 10, cursor: 'pointer', fontSize: 13, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="refresh" size={14} stroke={2} /> Refresh
        </button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)', fontSize: 14 }}>Chargement…</div>}

      {!loading && (<>
        {/* Hero stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 'var(--gap)' }}>
          {[
            { l: 'Win Rate', v: `${winRate.toFixed(0)}%`, c: winRate >= 50 ? 'var(--green)' : 'var(--orange)', sub: `${won.length}G / ${lost.length}P` },
            { l: 'Résolus', v: resolved.length, c: 'var(--text)', sub: `sur ${trades.length} trades` },
            { l: 'En attente', v: pending.length, c: 'var(--orange)', sub: 'résolution en cours' },
            { l: 'Mise simulée', v: `$${totalStaked.toFixed(0)}`, c: 'var(--text)', sub: 'cumulée (DRY_RUN)' },
          ].map((s, i) => (
            <Card key={i} style={{ padding: '14px 12px', textAlign: 'center' }}>
              <div style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--text-3)', letterSpacing: '.07em', textTransform: 'uppercase', marginBottom: 5 }}>{s.l}</div>
              <div style={{ fontSize: 20, fontWeight: 900, color: s.c }}>{s.v}</div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>{s.sub}</div>
            </Card>
          ))}
        </div>

        {/* Liste des trades */}
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', letterSpacing: '.07em', textTransform: 'uppercase', marginBottom: 12 }}>
          {trades.length} trades simulés
        </div>
        {trades.length === 0 ? (
          <Card style={{ padding: 28, textAlign: 'center', color: 'var(--text-3)' }}>
            ⏳ Aucun trade encore enregistré…<br />
            <span style={{ fontSize: 12 }}>Le bot tourne en DRY_RUN, les trades apparaîtront ici dès le premier achat simulé</span>
          </Card>
        ) : trades.map((t, i) => {
          const statusLabel = !t.resolved ? '⏳ En attente' : t.win ? '✅ Gagné' : '❌ Perdu';
          const statusColor = !t.resolved ? 'var(--orange)' : t.win ? 'var(--green)' : 'var(--red)';
          return (
            <Card key={t.id || i} style={{ marginBottom: 8, padding: '12px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: outcomeColor(t.outcome), background: `color-mix(in oklab,${outcomeColor(t.outcome)} 12%,transparent)`, padding: '3px 9px', borderRadius: 999, border: `1px solid color-mix(in oklab,${outcomeColor(t.outcome)} 30%,transparent)`, flexShrink: 0 }}>
                  {(t.outcome || '?').toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text)' }}>{t.slug || '—'}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                    achat {((parseFloat(t.price_at_buy || 0)) * 100).toFixed(0)}¢ · ${parseFloat(t.amount_usdc || 0).toFixed(0)}
                    {t.resolved && t.actual_outcome && <> · résultat réel {t.actual_outcome}</>}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, fontSize: 12.5, fontWeight: 700, color: statusColor }}>
                  {statusLabel}
                </div>
              </div>
            </Card>
          );
        })}
      </>)}
    </div>
  );
}

window.ZeroToHeroResultsPage = ZeroToHeroResultsPage;
