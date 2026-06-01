// ============================================================
// page_dashboard.jsx — list of all bots + portfolio summary
// ============================================================
function DashboardPage({ bots, onToggle, onOpen, onNewBot }) {
  const { PORTFOLIO, fmtUSD, sliceRange, Card, SectionTitle, BotGlyph, MarketChip,
    StatusPill, Toggle, Sparkline, Delta, Stat, Button, Icon } = window;
  const [filter, setFilter] = React.useState('all');

  const active = bots.filter((b) => b.status === 'running').length;
  const filtered = filter === 'all' ? bots : bots.filter((b) => b.market === filter);

  const filters = [
    { value: 'all', label: 'Tous' }, { value: 'crypto', label: 'Crypto' },
    { value: 'stocks', label: 'Actions' }, { value: 'polymarket', label: 'Polymarket' },
  ];

  return (
    <div>
      {/* hero summary */}
      <Card style={{ marginBottom: 'var(--gap)', padding: 'calc(var(--pad) + 4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', fontWeight: 500 }}>Valeur totale gérée</div>
          <div className="num" style={{ fontSize: 38, fontWeight: 700, letterSpacing: '-.03em', margin: '4px 0 6px' }}>
            {fmtUSD(PORTFOLIO.totalValue)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Delta pct={PORTFOLIO.dayPct} showArrow />
            <span className="num" style={{ color: 'var(--text-3)', fontSize: 13.5 }}>
              {window.fmtUSD(PORTFOLIO.dayAbs, 0).replace('$', PORTFOLIO.dayAbs >= 0 ? '+$' : '-$').replace('-$-', '-$')} aujourd'hui
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 26, alignItems: 'center' }}>
          <Stat label="Bots actifs" value={`${active}/${bots.length}`} />
          <div style={{ width: 1, height: 40, background: 'var(--separator)' }} />
          <Stat label="Gain cumulé" value={fmtUSD(PORTFOLIO.totalPnlAbs)} accent="var(--green)" />
          <div style={{ alignSelf: 'center' }}>
            <Sparkline data={sliceRange(PORTFOLIO.series, '1M')} w={140} h={46} color="var(--accent)" />
          </div>
        </div>
      </Card>

      <SectionTitle title="Mes bots" sub={`${active} en exécution · ${bots.length} au total`}
        trailing={<Button icon="plus" onClick={onNewBot}>Nouveau bot</Button>} />

      <div style={{ marginBottom: 'var(--gap)', maxWidth: 420 }}>
        <window.Segmented options={filters} value={filter} onChange={setFilter} size="sm" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--gap)' }}>
        {filtered.map((b) => {
          const paused = b.status !== 'running';
          return (
            <Card key={b.id} onClick={() => onOpen(b.id)} style={{ display: 'flex', flexDirection: 'column',
              gap: 14, opacity: paused ? 0.82 : 1 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <BotGlyph bot={b} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 16, fontWeight: 650, letterSpacing: '-.01em' }}>{b.name}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.strategy}</div>
                </div>
                <Toggle on={!paused} onChange={() => onToggle(b.id)} />
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginBottom: 2 }}>Capital alloué</div>
                  <div className="num" style={{ fontSize: 21, fontWeight: 700, letterSpacing: '-.02em' }}>{fmtUSD(b.capital)}</div>
                </div>
                <Sparkline data={sliceRange(b.series, '1M')} w={92} h={34}
                  up={b.series[b.series.length - 1] >= b.series[0]} />
              </div>

              <div style={{ height: 1, background: 'var(--separator)' }} />

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>24h</div>
                    <Delta pct={b.pnlDayPct} size={13.5} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Win rate</div>
                    <div className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>{b.winRate}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Positions</div>
                    <div className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>{b.openPos}</div>
                  </div>
                </div>
                <MarketChip market={b.market} />
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
window.DashboardPage = DashboardPage;
