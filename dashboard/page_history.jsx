// ============================================================
// page_history.jsx — transaction history across all bots
// ============================================================
function HistoryPage({ bots, transactions }) {
  const { MARKETS, fmtUSD, Card, SectionTitle, Segmented, Icon, MarketChip } = window;
  const TXNS = transactions || [];
  const [q, setQ] = React.useState('');
  const [market, setMarket] = React.useState('all');
  const [side, setSide] = React.useState('all');
  const botName = (id) => (bots.find((b) => b.id === id) || {}).name || id;

  const rows = React.useMemo(() => TXNS.filter((t) => {
    if (market !== 'all' && t.market !== market) return false;
    if (side !== 'all' && t.side !== side) return false;
    if (q && !(t.sym.toLowerCase().includes(q.toLowerCase()) || botName(t.bot).toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  }), [q, market, side, bots]);

  const groups = React.useMemo(() => {
    const g = {};
    rows.forEach((t) => {
      const d = new Date(t.time).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
      (g[d] = g[d] || []).push(t);
    });
    return g;
  }, [rows]);

  const realized = rows.reduce((s, t) => s + (t.pnl || 0), 0);
  const filled = rows.length;

  return (
    <div>
      <SectionTitle title="Historique" sub={`${filled} transactions`} />

      <Card style={{ marginBottom: 'var(--gap)', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)' }}>
            <Icon name="search" size={18} /></span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un actif ou un bot…"
            style={{ width: '100%', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-md)',
              padding: '11px 14px 11px 38px', fontSize: 14.5, color: 'var(--text)', outline: 'none', fontFamily: 'inherit' }} />
        </div>
        <div style={{ width: 280 }}>
          <Segmented value={market} onChange={setMarket} size="sm" options={[
            { value: 'all', label: 'Tous' }, { value: 'crypto', label: 'Crypto' },
            { value: 'stocks', label: 'Actions' }, { value: 'polymarket', label: 'Poly' }]} />
        </div>
        <div style={{ width: 170 }}>
          <Segmented value={side} onChange={setSide} size="sm" options={[
            { value: 'all', label: 'Tous' }, { value: 'buy', label: 'Achats' }, { value: 'sell', label: 'Ventes' }]} />
        </div>
      </Card>

      <Card style={{ marginBottom: 'var(--gap)', display: 'flex', gap: 30 }}>
        <window.Stat label="Transactions affichées" value={window.fmtNum(filled)} />
        <div style={{ width: 1, background: 'var(--separator)' }} />
        <window.Stat label="P&L réalisé (filtré)" value={fmtUSD(realized)} accent={realized >= 0 ? 'var(--green)' : 'var(--red)'} />
      </Card>

      <Card pad={false}>
        {/* header */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1.3fr .7fr .8fr 1fr 1fr', gap: 10,
          padding: '13px var(--pad)', fontSize: 11.5, color: 'var(--text-3)', fontWeight: 600,
          textTransform: 'uppercase', letterSpacing: '.03em', borderBottom: '1px solid var(--separator)' }} className="hist-head">
          <span>Actif</span><span>Bot</span><span>Sens</span><span>Quantité</span><span style={{ textAlign: 'right' }}>Montant</span><span style={{ textAlign: 'right' }}>P&L</span>
        </div>
        {filled === 0 && (
          <div style={{ padding: '48px 40px', textAlign: 'center', color: 'var(--text-3)' }}>
            {TXNS.length === 0
              ? 'Aucun trade pour l\'instant — les transactions apparaîtront ici dès que le bot tradера.'
              : 'Aucune transaction ne correspond aux filtres.'}
          </div>
        )}
        {Object.entries(groups).map(([day, items]) => (
          <div key={day}>
            <div style={{ padding: '9px var(--pad)', fontSize: 12, fontWeight: 600, color: 'var(--text-3)',
              background: 'var(--fill)', textTransform: 'capitalize' }}>{day}</div>
            {items.map((t) => (
              <div key={t.id} style={{ display: 'grid', gridTemplateColumns: '1.4fr 1.3fr .7fr .8fr 1fr 1fr', gap: 10,
                alignItems: 'center', padding: '11px var(--pad)', borderBottom: '1px solid var(--separator)' }} className="hist-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: (MARKETS[t.market] || MARKETS.polymarket).color, flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.sym}</span>
                </div>
                <span style={{ fontSize: 13.5, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{botName(t.bot)}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: t.side === 'buy' ? 'var(--green)' : 'var(--red)' }}>
                  {t.side === 'buy' ? 'ACHAT' : 'VENTE'}</span>
                <span className="num" style={{ fontSize: 13.5 }}>{t.qty}</span>
                <span className="num" style={{ fontSize: 14, fontWeight: 600, textAlign: 'right' }}>{fmtUSD(t.value, t.value < 100 ? 2 : 0)}</span>
                <span className="num" style={{ fontSize: 13.5, fontWeight: 600, textAlign: 'right',
                  color: t.pnl == null ? 'var(--text-3)' : t.pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {t.pnl == null ? '—' : (t.pnl >= 0 ? '+' : '') + fmtUSD(t.pnl, 2).replace('$', '$')}</span>
              </div>
            ))}
          </div>
        ))}
      </Card>
    </div>
  );
}
window.HistoryPage = HistoryPage;
