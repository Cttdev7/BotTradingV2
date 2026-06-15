// ============================================================
// page_deko.jsx — Analyse Deko : surveillance de sailor82
// ============================================================
function DekoPage({ onBack }) {
  const { Card, Button, Icon, StatusPill } = window;

  const SB_URL = 'https://obqkqhlqlowxrxbyvktl.supabase.co';
  const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728';

  const [trades,   setTrades]   = React.useState([]);
  const [stats,    setStats]    = React.useState(null);
  const [rapports, setRapports] = React.useState([]);
  const [loading,  setLoading]  = React.useState(true);
  const [tab,      setTab]      = React.useState('trades');

  const sbFetch = (table, params = '') =>
    fetch(`${SB_URL}/rest/v1/${table}?${params}`, {
      headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}` }
    }).then(r => r.json()).catch(() => []);

  const load = React.useCallback(() => {
    setLoading(true);
    Promise.all([
      sbFetch('deko_trades',   'order=detected_at.desc&limit=50'),
      sbFetch('deko_stats',    'id=eq.global&limit=1'),
      sbFetch('deko_rapports', 'order=created_at.desc&limit=5'),
    ]).then(([t, s, r]) => {
      if (Array.isArray(t)) setTrades(t);
      if (Array.isArray(s) && s[0]) setStats(s[0]);
      if (Array.isArray(r)) setRapports(r);
      setLoading(false);
    });
  }, []);

  React.useEffect(() => { load(); const id = setInterval(load, 5 * 60 * 1000); return () => clearInterval(id); }, [load]);

  const fmtPnl = (v) => v == null ? '—' : `${v >= 0 ? '+' : ''}$${Math.abs(v).toFixed(2)}`;
  const fmtPct = (v) => v == null ? '—' : `${v.toFixed(1)}%`;

  const cityStats = React.useMemo(() => {
    if (!stats?.cities) return [];
    try {
      const obj = JSON.parse(stats.cities);
      return Object.entries(obj)
        .map(([city, d]) => ({ city, ...d, wr: d.wins + d.losses > 0 ? Math.round(d.wins / (d.wins + d.losses) * 100) : 0 }))
        .sort((a, b) => b.vol - a.vol)
        .slice(0, 10);
    } catch { return []; }
  }, [stats]);

  const hourStats = React.useMemo(() => {
    if (!stats?.hours_et) return [];
    try {
      const obj = JSON.parse(stats.hours_et);
      return Object.entries(obj)
        .map(([h, n]) => ({ hour: parseInt(h), count: n }))
        .sort((a, b) => a.hour - b.hour);
    } catch { return []; }
  }, [stats]);

  const maxHour = hourStats.length ? Math.max(...hourStats.map(h => h.count)) : 1;

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border:'none', background:'var(--fill)',
          width:38, height:38, borderRadius:11, cursor:'pointer', display:'grid', placeItems:'center',
          color:'var(--accent)', transform:'scaleX(-1)' }}><Icon name="chevron" size={20} stroke={2.4} /></button>
        <div style={{ width:46, height:46, borderRadius:14, background:'color-mix(in oklab,#6366f1 15%,var(--bg-elev))',
          border:'1.5px solid color-mix(in oklab,#6366f1 40%,transparent)',
          display:'grid', placeItems:'center', fontSize:22 }}>🔍</div>
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <h2 style={{ margin:0, fontSize:22, fontWeight:700 }}>Analyse Deko</h2>
            <StatusPill status="running" />
          </div>
          <div style={{ fontSize:13, color:'var(--text-3)', marginTop:3 }}>
            Surveillance de sailor82 · @PolyDekos
          </div>
        </div>
        <button onClick={load} className="tap" style={{ border:'none', background:'var(--fill)',
          padding:'8px 16px', borderRadius:10, cursor:'pointer', fontSize:13,
          color:'var(--text-2)', display:'flex', alignItems:'center', gap:6 }}>
          <Icon name="refresh" size={14} stroke={2} /> Actualiser
        </button>
      </div>

      {/* Stats hero */}
      {stats && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',
          gap:10, marginBottom:'var(--gap)' }}>
          {[
            { l:'Trades suivis',  v: stats.total_trades,             c: 'var(--text)' },
            { l:'Win rate',       v: fmtPct(stats.win_rate),         c: stats.win_rate >= 70 ? 'var(--green)' : 'var(--orange)' },
            { l:'P&L détecté',    v: fmtPnl(stats.total_pnl),        c: stats.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' },
            { l:'Win rate NO',    v: fmtPct(stats.no_win_rate),      c: 'var(--accent)' },
            { l:'Win rate YES',   v: fmtPct(stats.yes_win_rate),     c: 'var(--text-2)' },
            { l:'Ouverts',        v: stats.open,                      c: 'var(--orange)' },
          ].map((s,i) => (
            <Card key={i} style={{ padding:'14px 16px', textAlign:'center' }}>
              <div style={{ fontSize:10.5, color:'var(--text-3)', fontWeight:600,
                textTransform:'uppercase', letterSpacing:'.06em', marginBottom:6 }}>{s.l}</div>
              <div style={{ fontSize:20, fontWeight:800, color:s.c }}>{s.v}</div>
            </Card>
          ))}
        </div>
      )}

      {/* Onglets */}
      <div style={{ display:'flex', gap:6, marginBottom:'var(--gap)', background:'var(--fill)',
        borderRadius:12, padding:4 }}>
        {[['trades','📋 Trades'],['villes','🏙️ Villes'],['timing','⏰ Timing'],['analyse','🧠 Analyse']].map(([v,l]) => (
          <button key={v} onClick={() => setTab(v)} style={{
            flex:1, border:'none', borderRadius:9, padding:'8px 4px',
            fontSize:13, fontWeight:600, cursor:'pointer', transition:'all .15s',
            background: tab === v ? 'var(--bg-elev)' : 'transparent',
            color: tab === v ? 'var(--text)' : 'var(--text-3)',
            boxShadow: tab === v ? '0 1px 3px rgba(0,0,0,.15)' : 'none',
          }}>{l}</button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign:'center', padding:40, color:'var(--text-3)', fontSize:14 }}>
          Chargement des données de sailor82…
        </div>
      )}

      {/* ── Trades ── */}
      {!loading && tab === 'trades' && (
        <div>
          <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
            textTransform:'uppercase', marginBottom:12 }}>
            Derniers trades détectés ({trades.length})
          </div>
          {trades.length === 0 ? (
            <Card style={{ padding:24, textAlign:'center', color:'var(--text-3)' }}>
              ⏳ En attente des premiers trades…<br/>
              <span style={{ fontSize:12 }}>L'agent Deko doit tourner en local ou Railway</span>
            </Card>
          ) : trades.map((t, i) => {
            const won  = t.result === 'GAGNANT';
            const lost = t.result === 'PERDANT';
            const open = !t.result;
            const outColor = (t.outcome||'').toLowerCase() === 'no' ? '#6366f1' : '#f59e0b';
            return (
              <Card key={i} style={{ marginBottom:8, padding:'12px 16px' }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:12 }}>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                      <span style={{ fontSize:11, fontWeight:700, color:outColor,
                        background:`color-mix(in oklab,${outColor} 12%,transparent)`,
                        padding:'2px 8px', borderRadius:999,
                        border:`1px solid color-mix(in oklab,${outColor} 30%,transparent)` }}>
                        {(t.outcome||'?').toUpperCase()}
                      </span>
                      <span style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>
                        {t.city || '?'}
                      </span>
                      {t.range_low && (
                        <span style={{ fontSize:12, color:'var(--text-3)' }}>
                          {t.range_low}–{t.range_high}°F
                        </span>
                      )}
                      <span style={{ fontSize:11, color:'var(--text-3)',
                        background:'var(--fill)', padding:'1px 6px', borderRadius:6 }}>
                        {t.certainty || '?'}
                      </span>
                    </div>
                    <div style={{ fontSize:11.5, color:'var(--text-3)', overflow:'hidden',
                      textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {t.question || '—'}
                    </div>
                  </div>
                  <div style={{ textAlign:'right', flexShrink:0 }}>
                    <div style={{ fontSize:15, fontWeight:700,
                      color: won ? 'var(--green)' : lost ? 'var(--red)' : 'var(--text-3)' }}>
                      {open ? '⏳' : won ? '✅' : '❌'} {t.pnl != null ? fmtPnl(t.pnl) : ''}
                    </div>
                    <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>
                      {t.price ? `${(t.price*100).toFixed(0)}¢` : '—'} · ${(t.amount_usdc||0).toFixed(0)} · {t.hour_et != null ? `${t.hour_et}h ET` : ''}
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* ── Villes ── */}
      {!loading && tab === 'villes' && (
        <div>
          <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
            textTransform:'uppercase', marginBottom:12 }}>Performance par ville</div>
          {cityStats.length === 0 ? (
            <Card style={{ padding:24, textAlign:'center', color:'var(--text-3)' }}>Pas encore de données</Card>
          ) : cityStats.map((c, i) => (
            <Card key={i} style={{ marginBottom:8, padding:'12px 16px' }}>
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                <div>
                  <div style={{ fontSize:14, fontWeight:700, color:'var(--text)', marginBottom:2 }}>
                    {c.city}
                  </div>
                  <div style={{ fontSize:11.5, color:'var(--text-3)' }}>
                    {c.wins}W / {c.losses}L · vol ${(c.vol||0).toFixed(0)}
                  </div>
                </div>
                <div style={{ textAlign:'right' }}>
                  <div style={{ fontSize:18, fontWeight:800,
                    color: c.wr >= 70 ? 'var(--green)' : c.wr >= 50 ? 'var(--orange)' : 'var(--red)' }}>
                    {c.wr}%
                  </div>
                  <div style={{ fontSize:11.5, color: (c.pnl||0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {fmtPnl(c.pnl)}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* ── Timing ── */}
      {!loading && tab === 'timing' && (
        <div>
          <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
            textTransform:'uppercase', marginBottom:12 }}>Distribution horaire (heure ET)</div>
          <Card style={{ padding:'20px 16px' }}>
            {hourStats.length === 0 ? (
              <div style={{ textAlign:'center', color:'var(--text-3)', fontSize:13 }}>Pas encore de données</div>
            ) : (
              <div>
                <div style={{ display:'flex', alignItems:'flex-end', gap:4, height:100, marginBottom:10 }}>
                  {Array.from({length:24}, (_, h) => {
                    const entry = hourStats.find(x => x.hour === h);
                    const count = entry ? entry.count : 0;
                    const barH  = count > 0 ? Math.max(4, Math.round(count / maxHour * 90)) : 0;
                    const isPeak = count === maxHour && count > 0;
                    return (
                      <div key={h} style={{ flex:1, display:'flex', flexDirection:'column',
                        alignItems:'center', justifyContent:'flex-end', height:100 }}>
                        <div style={{ width:'100%', height:barH, borderRadius:3,
                          background: isPeak ? 'var(--accent)' : count > 0 ? 'color-mix(in oklab,var(--accent) 50%,var(--fill))' : 'var(--fill)' }} />
                      </div>
                    );
                  })}
                </div>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:10,
                  color:'var(--text-3)' }}>
                  <span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span>
                </div>
                {hourStats.length > 0 && (() => {
                  const peak = hourStats.reduce((a,b) => a.count > b.count ? a : b);
                  return (
                    <div style={{ marginTop:14, padding:'10px 14px', borderRadius:'var(--r-md)',
                      background:'color-mix(in oklab,var(--accent) 8%,transparent)',
                      border:'1px solid color-mix(in oklab,var(--accent) 20%,transparent)' }}>
                      <div style={{ fontSize:13, fontWeight:600, color:'var(--accent)' }}>
                        ⏰ Heure de pointe : {peak.hour}h ET ({peak.count} trades)
                      </div>
                      <div style={{ fontSize:12, color:'var(--text-3)', marginTop:4 }}>
                        En heure locale : {peak.hour - 6}h Los Angeles · {peak.hour - 5}h Chicago · {peak.hour}h New York
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Analyse ── */}
      {!loading && tab === 'analyse' && (
        <div>
          <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
            textTransform:'uppercase', marginBottom:12 }}>Analyses Claude des patterns</div>
          {rapports.length === 0 ? (
            <Card style={{ padding:24, textAlign:'center', color:'var(--text-3)' }}>
              🧠 La première analyse sera générée après 4 cycles (1h de surveillance)
            </Card>
          ) : rapports.map((r, i) => (
            <Card key={i} style={{ marginBottom:'var(--gap)' }}>
              <div style={{ fontSize:11, color:'var(--text-3)', marginBottom:10 }}>
                {new Date(r.created_at).toLocaleString('fr-FR', { day:'2-digit', month:'short',
                  hour:'2-digit', minute:'2-digit' })} · {r.trades_count} trades analysés
              </div>
              <div style={{ fontSize:13.5, color:'var(--text)', lineHeight:1.75,
                whiteSpace:'pre-wrap', borderRadius:'var(--r-md)', padding:'14px 16px',
                background:'var(--fill)', border:'1px solid var(--separator)' }}>
                {r.analyse_text}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

window.DekoPage = DekoPage;
