// ============================================================
// page_dashboard.jsx — bots actifs uniquement
// ============================================================
function DashboardPage({ bots, onToggle, onOpen, onNewBot, portfolio }) {
  const { fmtUSD, fmtSignedUSD, sliceRange, Card, BotGlyph,
    Toggle, Sparkline, Delta, Stat } = window;
  const [pwHistory, setPwHistory] = React.useState([]);
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  React.useEffect(() => {
    if (!isLocal) return;
    const load = () => fetch('http://127.0.0.1:5050/api/pnl/hourly')
      .then(r => r.json()).then(d => { if (Array.isArray(d)) setPwHistory(d); }).catch(() => {});
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const pw2Bot = bots.find(b => b.id === 'polyedge2');
  const pw1Bot = bots.find(b => b.id === 'polyedge');

  const pwTotalPnl = pwHistory.length > 0 ? pwHistory[pwHistory.length - 1].pnl_cumul : null;
  const pwTrades   = pwHistory.reduce((a, b) => a + b.trades, 0);
  const pwGagnes   = pwHistory.reduce((a, b) => a + b.gagnes, 0);
  const pwWinRate  = pwTrades > 0 ? Math.round(pwGagnes / pwTrades * 100) : null;

  const active = bots.filter(b => b.status === 'running').length;

  return (
    <div>
      {/* ── Hero portfolio ── */}
      <Card style={{ marginBottom: 'var(--gap)', padding: 'calc(var(--pad) + 4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', fontWeight: 500 }}>Valeur totale gérée</div>
          <div className="num" style={{ fontSize: 38, fontWeight: 700, letterSpacing: '-.03em', margin: '4px 0 6px' }}>
            {fmtUSD(portfolio.totalValue)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Delta pct={portfolio.dayPct} showArrow />
            <span className="num" style={{ color: 'var(--text-3)', fontSize: 13.5 }}>
              {fmtSignedUSD(portfolio.dayAbs)} aujourd'hui
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 26, alignItems: 'center' }}>
          <Stat label="Bots actifs" value={`${active}/${bots.length}`} />
          <div style={{ width: 1, height: 40, background: 'var(--separator)' }} />
          <Stat label="Gain cumulé" value={fmtUSD(portfolio.totalPnlAbs)} accent="var(--green)" />
          <div style={{ alignSelf: 'center' }}>
            <Sparkline data={sliceRange(portfolio.series, '1M')} w={140} h={46} color="var(--accent)" />
          </div>
        </div>
      </Card>

      {/* ── Bots actifs ── */}
      <div>
        {/* ProfitWeather V2.0 — hero actif */}
        {pw2Bot && (
          <Card style={{ marginBottom: 'var(--gap)', padding: 0, overflow: 'hidden', cursor: 'pointer' }}
            onClick={() => onOpen('polyedge2')}>
            <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', gap: 16, flexWrap: 'wrap',
              background: 'linear-gradient(135deg,#0f2027,#1a3040,#0d4040)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 24 }}>🌤️</span>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', letterSpacing: '-.01em' }}>
                    ProfitWeather V2.0
                  </div>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 5,
                    background: 'rgba(74,222,128,.15)', border: '1px solid rgba(74,222,128,.3)',
                    borderRadius: 20, padding: '2px 9px', fontSize: 11, color: '#4ade80', fontWeight: 600 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80',
                      boxShadow: '0 0 6px #4ade80', display: 'inline-block' }} />
                    EN LIGNE
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                {pwTotalPnl !== null ? (
                  <>
                    <div className="num" style={{ fontSize: 28, fontWeight: 900, lineHeight: 1,
                      color: pwTotalPnl >= 0 ? '#4ade80' : '#f87171' }}>
                      {pwTotalPnl >= 0 ? '+' : ''}{fmtUSD(Math.abs(pwTotalPnl), 2)}
                    </div>
                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,.45)', marginTop: 3 }}>
                      P&L cumulé · {pwTrades} trade{pwTrades !== 1 ? 's' : ''}{pwWinRate !== null ? ` · ${pwWinRate}% win` : ''}
                    </div>
                  </>
                ) : (
                  <div style={{ fontSize: 12.5, color: 'rgba(255,255,255,.35)', fontStyle: 'italic' }}>
                    {isLocal ? 'Lancez le serveur pour voir les profits' : 'Données locales requises'}
                  </div>
                )}
              </div>
            </div>

            {pwHistory.length > 0 && (
              <div style={{ padding: '14px 20px 16px' }}>
                <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end', height: 44, marginBottom: 12 }}>
                  {pwHistory.slice(-30).map((h, i, arr) => {
                    const maxAbs = Math.max(...arr.map(x => Math.abs(x.pnl)), 0.01);
                    const barH   = Math.max(Math.round((Math.abs(h.pnl) / maxAbs) * 36), 3);
                    const isLast = i === arr.length - 1;
                    return (
                      <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column',
                        justifyContent: 'flex-end', height: 44 }}>
                        <div style={{ width: '100%', height: barH, borderRadius: 2,
                          background: h.pnl >= 0 ? 'var(--green)' : 'var(--red)',
                          opacity: isLast ? 1 : 0.45 }} />
                      </div>
                    );
                  })}
                </div>
                <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                  {[
                    { l: 'P&L total', v: (pwTotalPnl >= 0 ? '+' : '') + fmtUSD(Math.abs(pwTotalPnl), 2), c: pwTotalPnl >= 0 ? 'var(--green)' : 'var(--red)' },
                    { l: 'Trades',    v: pwTrades },
                    { l: 'Win rate',  v: pwWinRate !== null ? `${pwWinRate}%` : '—' },
                    { l: '✅ Gagnés', v: pwGagnes, c: 'var(--green)' },
                    { l: '❌ Perdus', v: pwTrades - pwGagnes, c: 'var(--red)' },
                  ].map((s, i) => (
                    <div key={i}>
                      <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginBottom: 2 }}>{s.l}</div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: s.c || 'var(--text)' }}>{s.v}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {pwHistory.length === 0 && isLocal && (
              <div style={{ padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 12,
                color: 'var(--text-3)' }}>
                <span style={{ fontSize: 20 }}>⏳</span>
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-2)', marginBottom: 2 }}>
                    En attente du premier trade
                  </div>
                  <div style={{ fontSize: 12.5 }}>
                    Les profits s'afficheront ici dès que ProfitWeather passera un ordre.
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* ProfitWeather V1.0 — hors ligne */}
        {pw1Bot && (
          <>
            <div style={{ fontSize: 11.5, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '.07em', color: 'var(--text-3)', marginBottom: 10 }}>
              Inactif
            </div>
            <Card onClick={() => onOpen('polyedge')} style={{ display: 'flex', flexDirection: 'column',
              gap: 14, opacity: 0.55, cursor: 'pointer' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <BotGlyph bot={pw1Bot} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 650, letterSpacing: '-.01em' }}>{pw1Bot.name}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1 }}>{pw1Bot.strategy}</div>
                </div>
                <Toggle on={false} onChange={() => onToggle('polyedge')} />
              </div>
              <div style={{ display: 'flex', gap: 20, paddingTop: 10, borderTop: '1px solid var(--separator)' }}>
                {[{ l: 'Capital', v: fmtUSD(pw1Bot.capital) }, { l: 'Trades', v: pw1Bot.trades }, { l: 'Win rate', v: `${pw1Bot.winRate}%` }]
                  .map((s, i) => (
                    <div key={i}>
                      <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginBottom: 2 }}>{s.l}</div>
                      <div style={{ fontSize: 15, fontWeight: 700 }}>{s.v}</div>
                    </div>
                  ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
window.DashboardPage = DashboardPage;
