// ============================================================
// page_bot.jsx — single bot data tracking
// ============================================================
function BotPage({ bot, onToggle, onBack, onSettings, onRename }) {
  const { POSITIONS, TXNS, RANGES, MARKETS, fmtUSD, fmtPct, sliceRange,
    Card, BotGlyph, MarketChip, StatusPill, Toggle, Segmented, AreaChart,
    Stat, Delta, Button, Icon, Meter } = window;
  const [range, setRange] = React.useState('1M');
  const [editingName, setEditingName] = React.useState(false);
  const [draftName, setDraftName] = React.useState(bot.name);
  React.useEffect(() => { if (!editingName) setDraftName(bot.name); }, [bot.name]);
  const series = sliceRange(bot.series, range);
  const periodPct = ((series[series.length - 1] - series[0]) / series[0]) * 100;
  const positions = POSITIONS[bot.id] || [];
  const isPoly = bot.market === 'polymarket';
  const trades = React.useMemo(() => TXNS.filter((t) => t.bot === bot.id).slice(0, 8), [bot.id]);
  const m = MARKETS[bot.market];

  const stats = [
    { label: 'P&L total', value: fmtPct(bot.pnlTotalPct), accent: bot.pnlTotalPct >= 0 ? 'var(--green)' : 'var(--red)' },
    { label: 'Win rate', value: bot.winRate + '%' },
    { label: 'Sharpe', value: (bot.sharpe ?? 0).toFixed(2) },
    { label: 'Max drawdown', value: bot.maxDD.toFixed(1) + '%', accent: 'var(--red)' },
    { label: 'Trades', value: window.fmtNum(bot.trades) },
  ];

  return (
    <div>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)',
          width: 38, height: 38, borderRadius: 11, cursor: 'pointer', display: 'grid', placeItems: 'center',
          color: 'var(--accent)', transform: 'scaleX(-1)' }}><Icon name="chevron" size={20} stroke={2.4} /></button>
        <BotGlyph bot={bot} size={46} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {editingName ? (
              <input autoFocus value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { const n = draftName.trim(); if (n) onRename(bot.id, n); setEditingName(false); }
                  if (e.key === 'Escape') { setEditingName(false); setDraftName(bot.name); }
                }}
                onBlur={() => { const n = draftName.trim(); if (n) onRename(bot.id, n); setEditingName(false); }}
                style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-.02em', background: 'transparent',
                  border: 'none', borderBottom: '2px solid var(--accent)', outline: 'none',
                  color: 'var(--text)', fontFamily: 'inherit', padding: '0 4px 2px', maxWidth: 260 }} />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.02em' }}>{bot.name}</h2>
                <button onClick={() => { setEditingName(true); setDraftName(bot.name); }}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer',
                    color: 'var(--text-3)', padding: 0, display: 'flex', alignItems: 'center' }}>
                  <Icon name="pencil" size={16} stroke={1.8} />
                </button>
              </div>
            )}
            <StatusPill status={bot.status} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3, color: 'var(--text-3)', fontSize: 13 }}>
            <MarketChip market={bot.market} /><span>·</span><span>{bot.venue}</span>
          </div>
        </div>
        <Button variant="secondary" icon="sliders" onClick={onSettings}>Réglages</Button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 13.5, color: 'var(--text-3)', fontWeight: 500 }}>{bot.status === 'running' ? 'Actif' : 'En pause'}</span>
          <Toggle on={bot.status === 'running'} onChange={() => onToggle(bot.id)} />
        </div>
      </div>

      {/* performance */}
      <Card style={{ marginBottom: 'var(--gap)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)', fontWeight: 500 }}>Équité du portefeuille du bot</div>
            <div className="num" style={{ fontSize: 30, fontWeight: 700, letterSpacing: '-.02em', margin: '3px 0 4px' }}>
              {fmtUSD(series[series.length - 1])}</div>
            <Delta pct={periodPct} showArrow size={14} />
            <span style={{ color: 'var(--text-3)', fontSize: 13, marginLeft: 8 }}>sur {range}</span>
          </div>
          <div style={{ width: 260, maxWidth: '42%' }}>
            <Segmented options={RANGES} value={range} onChange={setRange} size="sm" />
          </div>
        </div>
        <AreaChart data={series} height={240} color="auto" />
      </Card>

      {/* stats row */}
      <Card style={{ marginBottom: 'var(--gap)', display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))', gap: 18 }}>
        {stats.map((s, i) => <Stat key={i} {...s} />)}
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', gap: 'var(--gap)' }}
        className="bot-cols">
        {/* open positions */}
        <Card pad={false}>
          <div style={{ padding: 'var(--pad) var(--pad) 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 650 }}>Positions ouvertes</h3>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>
              <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--green)' }} />Temps réel
            </span>
          </div>
          {positions.length === 0 ? (
            <div style={{ padding: '28px var(--pad) 34px', textAlign: 'center', color: 'var(--text-3)', fontSize: 14 }}>
              Aucune position ouverte{bot.status !== 'running' ? ' — bot en pause.' : '.'}
            </div>
          ) : positions.map((p, i) => {
            const pnl = p.side === 'short' ? (p.entry - p.mark) * p.qty : (p.mark - p.entry) * p.qty;
            const pnlPct = ((p.mark - p.entry) / p.entry) * 100 * (p.side === 'short' ? -1 : 1);
            const sideColor = isPoly ? (p.side === 'yes' ? 'var(--green)' : 'var(--red)')
              : (p.side === 'short' ? 'var(--red)' : 'var(--accent)');
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px var(--pad)',
                borderTop: '1px solid var(--separator)' }}>
                <div style={{ minWidth: 52 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#fff', background: sideColor,
                    padding: '2px 7px', borderRadius: 6, textTransform: 'uppercase' }}>{p.side}</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {isPoly ? p.name : p.sym}</div>
                  <div className="num" style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 1 }}>
                    {isPoly ? `${p.qty} parts @ ${p.entry.toFixed(2)}` : `${p.qty} @ ${fmtUSD(p.entry, p.entry < 10 ? 2 : 0)}`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="num" style={{ fontSize: 14.5, fontWeight: 600 }}>{fmtUSD(p.value)}</div>
                  <div className="num" style={{ fontSize: 12, fontWeight: 600, color: pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {window.fmtSigned(pnlPct, 1)}%</div>
                </div>
              </div>
            );
          })}
        </Card>

        {/* risk + recent trades */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap)' }}>
          <Card>
            <h3 style={{ margin: '0 0 14px', fontSize: 16, fontWeight: 650 }}>Risque</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                { l: 'Exposition', v: Math.min(100, Math.round((bot.openPos / 12) * 100)), c: 'var(--accent)', t: `${bot.openPos} positions` },
                { l: 'Win rate', v: bot.winRate, c: 'var(--green)', t: bot.winRate + '%' },
                { l: 'Drawdown vs limite', v: Math.round(Math.abs(bot.maxDD) / 25 * 100), c: 'var(--orange)', t: bot.maxDD.toFixed(1) + '% / -25%' },
              ].map((r, i) => (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-2)' }}>{r.l}</span>
                    <span className="num" style={{ fontWeight: 600 }}>{r.t}</span>
                  </div>
                  <Meter value={r.v} color={r.c} />
                </div>
              ))}
            </div>
          </Card>
          <Card pad={false}>
            <h3 style={{ margin: 0, padding: 'var(--pad) var(--pad) 10px', fontSize: 16, fontWeight: 650 }}>Trades récents</h3>
            {trades.length === 0 ? (
              <div style={{ padding: '8px var(--pad) 22px', color: 'var(--text-3)', fontSize: 14 }}>Aucun trade.</div>
            ) : trades.map((t) => (
              <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px var(--pad)',
                borderTop: '1px solid var(--separator)' }}>
                <div style={{ width: 26, height: 26, borderRadius: 7, display: 'grid', placeItems: 'center',
                  background: t.side === 'buy' ? 'color-mix(in oklab, var(--green) 16%, transparent)' : 'color-mix(in oklab, var(--red) 16%, transparent)',
                  color: t.side === 'buy' ? 'var(--green)' : 'var(--red)' }}>
                  <Icon name={t.side === 'buy' ? 'down' : 'up'} size={16} stroke={2.6} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{t.side === 'buy' ? 'Achat' : 'Vente'} {t.sym}</div>
                  <div className="num" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>{new Date(t.time).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</div>
                </div>
                <div className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>{fmtUSD(t.value)}</div>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </div>
  );
}
window.BotPage = BotPage;
