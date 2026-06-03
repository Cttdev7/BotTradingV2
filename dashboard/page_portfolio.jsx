// ============================================================
// page_portfolio.jsx — global portfolio overview
// ============================================================
function PortfolioPage({ bots, onOpen, portfolio }) {
  const { MARKETS, RANGES, fmtUSD, fmtPct, sliceRange,
    Card, SectionTitle, AreaChart, Donut, Segmented, Stat, Delta, BotGlyph, Meter, Sparkline } = window;
  const [range, setRange] = React.useState('3M');
  const [allocMode, setAllocMode] = React.useState('bot');
  const series = sliceRange(portfolio.series, range);
  const periodPct = ((series[series.length - 1] - series[0]) / series[0]) * 100;

  const palette = ['var(--accent)', 'var(--green)', 'var(--purple)', 'var(--orange)', 'var(--teal)', 'var(--red)'];
  const allocByBot = bots.filter((b) => b.capital > 0).map((b, i) => ({
    label: b.name, value: b.capital, color: palette[i % palette.length], bot: b }));
  const byMarket = {};
  bots.forEach((b) => { byMarket[b.market] = (byMarket[b.market] || 0) + b.capital; });
  const allocByMarket = Object.entries(byMarket).filter(([, v]) => v > 0).map(([k, v]) => ({
    label: MARKETS[k].label, value: v, color: MARKETS[k].color }));
  allocByMarket.push({ label: 'Liquidités', value: portfolio.cash, color: 'var(--text-3)' });

  const alloc = allocMode === 'bot' ? allocByBot : allocByMarket;
  const investedPct = ((portfolio.totalCapital) / portfolio.totalValue) * 100;

  // aggregate risk
  const wAvg = (key) => bots.reduce((s, b) => s + b[key] * b.capital, 0) / (portfolio.totalCapital || 1);

  return (
    <div>
      <SectionTitle title="Portefeuille" sub="Vue agrégée de tous vos bots" />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', gap: 'var(--gap)' }} className="pf-cols">
        {/* equity */}
        <Card>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ fontSize: 12.5, color: 'var(--text-3)', fontWeight: 500 }}>Valeur totale</div>
              <div className="num" style={{ fontSize: 34, fontWeight: 700, letterSpacing: '-.03em', margin: '3px 0 5px' }}>
                {fmtUSD(portfolio.totalValue)}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <Delta pct={periodPct} showArrow />
                <span className="num" style={{ color: 'var(--text-3)', fontSize: 13 }}>
                  {fmtUSD(series[series.length - 1] - series[0])} sur {range}</span>
              </div>
            </div>
            <div style={{ width: 260, maxWidth: '46%' }}>
              <Segmented options={RANGES} value={range} onChange={setRange} size="sm" />
            </div>
          </div>
          <AreaChart data={series} height={250} color="var(--accent)" />
        </Card>

        {/* allocation */}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 650 }}>Allocation</h3>
            <div style={{ width: 150 }}>
              <Segmented options={[{ value: 'bot', label: 'Bot' }, { value: 'market', label: 'Marché' }]}
                value={allocMode} onChange={setAllocMode} size="sm" />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
            <Donut items={alloc} centerLabel={`${Math.round(investedPct)}%`} centerSub="investi" />
            <div style={{ flex: 1, minWidth: 130, display: 'flex', flexDirection: 'column', gap: 9 }}>
              {alloc.map((a, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 13 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: a.color, flexShrink: 0 }} />
                  <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-2)' }}>{a.label}</span>
                  <span className="num" style={{ fontWeight: 600 }}>{Math.round(a.value / (portfolio.totalValue) * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      {/* risk strip */}
      <Card style={{ margin: 'var(--gap) 0', display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: 18 }}>
        <Stat label="Gain cumulé" value={fmtUSD(portfolio.totalPnlAbs)} accent="var(--green)" sub={(() => { const base = portfolio.totalValue - portfolio.totalPnlAbs; return base > 0 ? fmtPct(portfolio.totalPnlAbs / base * 100) : '—'; })()} />
        <Stat label="Liquidités" value={fmtUSD(portfolio.cash)} sub={`${Math.round(portfolio.cash / portfolio.totalValue * 100)}% du total`} />
        <Stat label="Sharpe moyen" value={wAvg('sharpe').toFixed(2)} />
        <Stat label="Win rate moyen" value={Math.round(wAvg('winRate')) + '%'} />
        <Stat label="Drawdown max" value={Math.min(...bots.map((b) => b.maxDD)).toFixed(1) + '%'} accent="var(--red)" />
      </Card>

      {/* per-bot breakdown */}
      <Card pad={false}>
        <div style={{ padding: 'var(--pad) var(--pad) 12px' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 650 }}>Détail par bot</h3>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1.4fr', padding: '0 var(--pad) 8px',
          fontSize: 11.5, color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.03em' }} className="pf-head">
          <span>Bot</span><span>Capital</span><span>Part</span><span>24h</span><span style={{ textAlign: 'right' }}>P&L cumulé</span>
        </div>
        {bots.map((b) => (
          <div key={b.id} onClick={() => onOpen(b.id)} className="tap pf-row" style={{ display: 'grid',
            gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1.4fr', alignItems: 'center', gap: 8,
            padding: '12px var(--pad)', borderTop: '1px solid var(--separator)', cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
              <BotGlyph bot={b} size={34} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>{window.MARKETS[b.market].label}</div>
              </div>
            </div>
            <div className="num" style={{ fontSize: 14, fontWeight: 600 }}>{fmtUSD(b.capital)}</div>
            <div style={{ paddingRight: 14 }}><Meter value={b.allocPct} max={40} color="var(--accent)" h={6} />
              <span className="num" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>{b.allocPct}%</span></div>
            <window.Delta pct={b.pnlDayPct} size={13.5} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
              <Sparkline data={sliceRange(b.series, '1M')} w={64} h={26} up={b.pnlTotalPct >= 0} />
              <window.Delta pct={b.pnlTotalPct} size={14} />
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
window.PortfolioPage = PortfolioPage;
