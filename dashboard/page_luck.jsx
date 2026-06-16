// page_luck.jsx — Analyse onlylucknobrain : rapport en temps réel
const LUCK_ADDR = '0x6a8d1709bfb718d8555d315a983c4816278350f9';

function LuckPage({ onBack }) {
  const { Card, Icon, StatusPill } = window;

  const [positions, setPositions] = React.useState([]);
  const [loading,   setLoading]   = React.useState(true);
  const [tab,       setTab]       = React.useState('rapport');
  const [lastUpdate, setLastUpdate] = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const posRes = await fetch(
        `https://data-api.polymarket.com/positions?user=${LUCK_ADDR}&sizeThreshold=0.01&limit=200`
      ).then(r => r.json()).catch(() => []);
      setPositions(Array.isArray(posRes) ? posRes : []);
      setLastUpdate(new Date());
    } catch(e) {}
    setLoading(false);
  }, []);

  React.useEffect(() => {
    load();
    const id = setInterval(load, 3 * 60 * 1000);
    return () => clearInterval(id);
  }, [load]);

  // ── Calculs ──
  const won    = positions.filter(p => p.redeemable === true);
  const lost   = positions.filter(p => parseFloat(p.currentValue||0) < 0.01 && !p.redeemable);
  const open   = positions.filter(p => parseFloat(p.currentValue||0) > 0.01);
  const closed = won.length + lost.length;
  const winRate = closed > 0 ? (won.length / closed * 100) : 0;

  const wonValue = won.reduce((s,p) => s + parseFloat(p.initialValue||0) / parseFloat(p.avgPrice||1), 0);
  const wonCost  = won.reduce((s,p) => s + parseFloat(p.initialValue||0), 0);
  const lostCost = lost.reduce((s,p) => s + parseFloat(p.initialValue||0), 0);
  const pnlNet   = wonValue - wonCost - lostCost;

  const openPnl  = open.reduce((s,p) => s + parseFloat(p.cashPnl||0), 0);
  const totalVol = positions.reduce((s,p) => s + parseFloat(p.initialValue||0), 0);

  const openNo   = open.filter(p => (p.outcome||'').toLowerCase() === 'no');
  const openYes  = open.filter(p => (p.outcome||'').toLowerCase() === 'yes');
  const noPnl    = openNo.reduce((s,p)  => s + parseFloat(p.cashPnl||0), 0);
  const yesPnl   = openYes.reduce((s,p) => s + parseFloat(p.cashPnl||0), 0);

  // Par ville
  const byCity = React.useMemo(() => {
    const map = {};
    open.forEach(p => {
      const title = (p.title||'').toLowerCase();
      let city = '?';
      for (const c of ['new york city','san francisco','los angeles','seattle','houston','austin','atlanta','miami','dallas','chicago','denver','boston','phoenix']) {
        if (title.includes(c)) { city = c; break; }
      }
      if (!map[city]) map[city] = { no:0, yes:0, vol:0, pnl:0 };
      const side = (p.outcome||'').toLowerCase();
      map[city][side === 'no' ? 'no' : 'yes']++;
      map[city].vol += parseFloat(p.initialValue||0);
      map[city].pnl += parseFloat(p.cashPnl||0);
    });
    return Object.entries(map).sort((a,b) => b[1].vol - a[1].vol);
  }, [open]);

  // Fourchettes favorites (top ranges dans positions ouvertes)
  const byRange = React.useMemo(() => {
    const map = {};
    open.forEach(p => {
      const title = p.title || '';
      const m = title.match(/between (\d+)-(\d+)/i);
      if (!m) return;
      const key = `${m[1]}-${m[2]}°F`;
      if (!map[key]) map[key] = { count:0, vol:0, pnl:0 };
      map[key].count++;
      map[key].vol += parseFloat(p.initialValue||0);
      map[key].pnl += parseFloat(p.cashPnl||0);
    });
    return Object.entries(map).sort((a,b) => b[1].vol - a[1].vol).slice(0,8);
  }, [open]);

  const fmt  = v => v >= 0 ? `+$${v.toFixed(0)}` : `-$${Math.abs(v).toFixed(0)}`;
  const fmtD = v => v >= 0 ? `+$${v.toFixed(2)}` : `-$${Math.abs(v).toFixed(2)}`;
  const col  = v => v >= 0 ? 'var(--green)' : 'var(--red)';
  const timeAgo = d => {
    if (!d) return '—';
    const s = Math.floor((Date.now() - d) / 1000);
    return s < 60 ? 'à l\'instant' : `il y a ${Math.floor(s/60)}min`;
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border:'none', background:'var(--fill)',
          width:38, height:38, borderRadius:11, cursor:'pointer', display:'grid', placeItems:'center',
          color:'var(--accent)', transform:'scaleX(-1)' }}>
          <Icon name="chevron" size={20} stroke={2.4} />
        </button>
        <div style={{ width:46, height:46, borderRadius:14,
          background:'color-mix(in oklab,#10b981 15%,var(--bg-elev))',
          border:'1.5px solid color-mix(in oklab,#10b981 40%,transparent)',
          display:'grid', placeItems:'center', fontSize:22 }}>🍀</div>
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <h2 style={{ margin:0, fontSize:22, fontWeight:700 }}>Analyse onlylucknobrain</h2>
            <StatusPill status="running" />
          </div>
          <div style={{ fontSize:12, color:'var(--text-3)', marginTop:2 }}>
            @onlylucknobrain · Mis à jour {timeAgo(lastUpdate)}
          </div>
        </div>
        <button onClick={load} className="tap" style={{ border:'none', background:'var(--fill)',
          padding:'8px 14px', borderRadius:10, cursor:'pointer', fontSize:13,
          color:'var(--text-2)', display:'flex', alignItems:'center', gap:6 }}>
          <Icon name="refresh" size={14} stroke={2} /> Refresh
        </button>
      </div>

      {loading && (
        <div style={{ textAlign:'center', padding:40, color:'var(--text-3)', fontSize:14 }}>
          Chargement depuis Polymarket…
        </div>
      )}

      {!loading && positions.length === 0 && (
        <div style={{ textAlign:'center', padding:40, color:'var(--text-3)', fontSize:14 }}>
          Aucune position trouvée pour ce wallet.
        </div>
      )}

      {!loading && positions.length > 0 && (
        <>
          {/* Hero stats */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:'var(--gap)' }}>
            <Card style={{ padding:'16px', textAlign:'center',
              background: winRate >= 70
                ? 'color-mix(in oklab,var(--green) 8%,var(--bg-elev))'
                : 'color-mix(in oklab,var(--orange) 8%,var(--bg-elev))',
              border:`1px solid color-mix(in oklab,${winRate >= 70 ? 'var(--green)' : 'var(--orange)'} 25%,transparent)` }}>
              <div style={{ fontSize:10, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                textTransform:'uppercase', marginBottom:6 }}>Win Rate</div>
              <div style={{ fontSize:28, fontWeight:900,
                color: winRate >= 70 ? 'var(--green)' : 'var(--orange)' }}>{winRate.toFixed(0)}%</div>
              <div style={{ fontSize:11, color:'var(--text-3)', marginTop:3 }}>{won.length}G / {lost.length}P</div>
            </Card>
            <Card style={{ padding:'16px', textAlign:'center' }}>
              <div style={{ fontSize:10, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                textTransform:'uppercase', marginBottom:6 }}>P&L net</div>
              <div style={{ fontSize:24, fontWeight:900, color: col(pnlNet) }}>{fmt(pnlNet)}</div>
              <div style={{ fontSize:11, color:'var(--text-3)', marginTop:3 }}>marchés résolus</div>
            </Card>
            <Card style={{ padding:'16px', textAlign:'center' }}>
              <div style={{ fontSize:10, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                textTransform:'uppercase', marginBottom:6 }}>Volume total</div>
              <div style={{ fontSize:22, fontWeight:900, color:'var(--text)' }}>${totalVol.toFixed(0)}</div>
              <div style={{ fontSize:11, color:'var(--text-3)', marginTop:3 }}>{positions.length} positions</div>
            </Card>
          </div>

          {/* Onglets */}
          <div style={{ display:'flex', gap:6, marginBottom:'var(--gap)', background:'var(--fill)',
            borderRadius:12, padding:4 }}>
            {[['rapport','📋 Rapport'],['positions','📊 Positions'],['villes','🏙️ Villes']].map(([v,l]) => (
              <button key={v} onClick={() => setTab(v)} style={{
                flex:1, border:'none', borderRadius:9, padding:'8px 4px',
                fontSize:13, fontWeight:600, cursor:'pointer', transition:'all .15s',
                background: tab===v ? 'var(--bg-elev)' : 'transparent',
                color: tab===v ? 'var(--text)' : 'var(--text-3)',
                boxShadow: tab===v ? '0 1px 3px rgba(0,0,0,.15)' : 'none',
              }}>{l}</button>
            ))}
          </div>

          {/* ── Rapport ── */}
          {tab === 'rapport' && (
            <div style={{ display:'flex', flexDirection:'column', gap:12 }}>

              {/* Répartition NO/YES */}
              <Card style={{ padding:'18px 20px' }}>
                <div style={{ fontSize:11, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                  textTransform:'uppercase', marginBottom:14 }}>Répartition des positions ouvertes</div>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
                  <div style={{ padding:'14px', borderRadius:12,
                    background:'color-mix(in oklab,#6366f1 8%,transparent)',
                    border:'1px solid color-mix(in oklab,#6366f1 20%,transparent)' }}>
                    <div style={{ fontSize:12, fontWeight:700, color:'#818cf8', marginBottom:6 }}>NO</div>
                    <div style={{ fontSize:22, fontWeight:900, color:'#818cf8' }}>{openNo.length}</div>
                    <div style={{ fontSize:11, color: col(noPnl), marginTop:4 }}>{fmtD(noPnl)}</div>
                  </div>
                  <div style={{ padding:'14px', borderRadius:12,
                    background:'color-mix(in oklab,#f59e0b 8%,transparent)',
                    border:'1px solid color-mix(in oklab,#f59e0b 20%,transparent)' }}>
                    <div style={{ fontSize:12, fontWeight:700, color:'#fbbf24', marginBottom:6 }}>YES</div>
                    <div style={{ fontSize:22, fontWeight:900, color:'#fbbf24' }}>{openYes.length}</div>
                    <div style={{ fontSize:11, color: col(yesPnl), marginTop:4 }}>{fmtD(yesPnl)}</div>
                  </div>
                </div>
                <div style={{ marginTop:12, padding:'10px 14px', borderRadius:10,
                  background:'var(--fill)', border:'1px solid var(--separator)',
                  display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <span style={{ fontSize:13, color:'var(--text-2)' }}>P&L live total</span>
                  <span style={{ fontSize:15, fontWeight:800, color: col(openPnl) }}>{fmtD(openPnl)}</span>
                </div>
              </Card>

              {/* Fourchettes favorites */}
              {byRange.length > 0 && (
                <Card style={{ padding:'18px 20px' }}>
                  <div style={{ fontSize:11, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                    textTransform:'uppercase', marginBottom:12 }}>Fourchettes les plus tradées</div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
                    {byRange.map(([range, s], i) => (
                      <div key={i} style={{ padding:'8px 14px', borderRadius:10,
                        background:'var(--fill)', border:'1px solid var(--separator)' }}>
                        <div style={{ fontSize:13, fontWeight:700, color:'var(--text)' }}>{range}</div>
                        <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>
                          ×{s.count} · ${s.vol.toFixed(0)}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Marchés gagnés/perdus */}
              <Card style={{ padding:'18px 20px' }}>
                <div style={{ fontSize:11, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                  textTransform:'uppercase', marginBottom:12 }}>Résumé marchés résolus</div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8 }}>
                  {[
                    { l:'Gagnés', v:won.length, c:'var(--green)' },
                    { l:'Perdus', v:lost.length, c:'var(--red)' },
                    { l:'Ouverts', v:open.length, c:'var(--orange)' },
                  ].map((s,i) => (
                    <div key={i} style={{ padding:'12px', borderRadius:10,
                      background:'var(--fill)', textAlign:'center' }}>
                      <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:4,
                        textTransform:'uppercase', letterSpacing:'.05em' }}>{s.l}</div>
                      <div style={{ fontSize:22, fontWeight:900, color:s.c }}>{s.v}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* ── Positions ── */}
          {tab === 'positions' && (
            <div>
              <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                textTransform:'uppercase', marginBottom:12 }}>
                {open.length} positions ouvertes
              </div>
              {open
                .sort((a,b) => Math.abs(parseFloat(b.cashPnl||0)) - Math.abs(parseFloat(a.cashPnl||0)))
                .map((p,i) => {
                  const pnl  = parseFloat(p.cashPnl||0);
                  const pct  = parseFloat(p.percentPnl||0);
                  const avg  = parseFloat(p.avgPrice||0);
                  const cur  = parseFloat(p.curPrice||0);
                  const init = parseFloat(p.initialValue||0);
                  const side = (p.outcome||'').toLowerCase();
                  const outColor = side === 'no' ? '#6366f1' : '#f59e0b';
                  const title = (p.title||'')
                    .replace('Will the highest temperature in ','')
                    .replace(' be between ',' ')
                    .replace(' on ',' · ');
                  return (
                    <Card key={i} style={{ marginBottom:8, padding:'12px 16px' }}>
                      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                        <div style={{ fontSize:11, fontWeight:700, color:outColor,
                          background:`color-mix(in oklab,${outColor} 12%,transparent)`,
                          padding:'3px 9px', borderRadius:999, flexShrink:0,
                          border:`1px solid color-mix(in oklab,${outColor} 30%,transparent)` }}>
                          {(p.outcome||'?').toUpperCase()}
                        </div>
                        <div style={{ flex:1, minWidth:0 }}>
                          <div style={{ fontSize:12.5, fontWeight:600, color:'var(--text)',
                            overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                            {title}
                          </div>
                          <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>
                            avg {(avg*100).toFixed(0)}¢ → {(cur*100).toFixed(0)}¢ · investi ${init.toFixed(0)}
                          </div>
                        </div>
                        <div style={{ textAlign:'right', flexShrink:0 }}>
                          <div style={{ fontSize:15, fontWeight:800, color: col(pnl) }}>
                            {pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}$
                          </div>
                          <div style={{ fontSize:11, color: col(pct), marginTop:1 }}>
                            {pct >= 0 ? '+' : ''}{pct.toFixed(0)}%
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
              })}
            </div>
          )}

          {/* ── Villes ── */}
          {tab === 'villes' && (
            <div>
              <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em',
                textTransform:'uppercase', marginBottom:12 }}>Performance par ville (positions ouvertes)</div>
              {byCity.map(([city, s], i) => (
                <Card key={i} style={{ marginBottom:8, padding:'14px 16px' }}>
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                    <div>
                      <div style={{ fontSize:14, fontWeight:700, color:'var(--text)',
                        textTransform:'capitalize', marginBottom:3 }}>{city}</div>
                      <div style={{ fontSize:11.5, color:'var(--text-3)' }}>
                        NO×{s.no} YES×{s.yes} · ${s.vol.toFixed(0)} investis
                      </div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:18, fontWeight:800, color: col(s.pnl) }}>
                        {s.pnl >= 0 ? '+' : ''}{s.pnl.toFixed(0)}$
                      </div>
                      <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>
                        {s.no + s.yes} positions
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

window.LuckPage = LuckPage;
