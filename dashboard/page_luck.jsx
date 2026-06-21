// page_luck.jsx — Analyse onlylucknobrain
const SB_URL_L = window.SB_URL;
const SB_KEY_L = window.SB_KEY;
const LUCK_ADDR = '0x6a8d1709bfb718d8555d315a983c4816278350f9';

function LuckPage({ onBack }) {
  const { Card, Icon, StatusPill } = window;
  const [positions, setPositions] = React.useState([]);
  const [rapports,  setRapports]  = React.useState([]);
  const [livePos,   setLivePos]   = React.useState([]);
  const [loading,   setLoading]   = React.useState(true);
  const [tab,       setTab]       = React.useState('positions');
  const [lastUpdate, setLastUpdate] = React.useState(null);

  const sbFetch = (table, params='') =>
    fetch(`${SB_URL_L}/rest/v1/${table}?${params}`, {
      headers: { apikey: SB_KEY_L, Authorization: `Bearer ${SB_KEY_L}` }
    }).then(r => r.json()).catch(() => []);

  const load = React.useCallback(async () => {
    setLoading(true);
    const [pos, rap, live] = await Promise.all([
      sbFetch('positions_tracker', 'trader=eq.onlylucknobrain&order=detected_at.desc&limit=200'),
      sbFetch('tracker_rapports',  'trader=eq.onlylucknobrain&order=created_at.desc&limit=5'),
      fetch(`https://data-api.polymarket.com/positions?user=${LUCK_ADDR}&sizeThreshold=0.01&limit=200`)
        .then(r => r.json()).catch(() => []),
    ]);
    if (Array.isArray(pos))  setPositions(pos);
    if (Array.isArray(rap))  setRapports(rap);
    if (Array.isArray(live)) setLivePos(live);
    setLastUpdate(new Date());
    setLoading(false);
  }, []);

  React.useEffect(() => { load(); const id = setInterval(load, 5*60*1000); return () => clearInterval(id); }, [load]);

  const won     = livePos.filter(p => p.redeemable);
  const lost    = livePos.filter(p => parseFloat(p.currentValue||0) < 0.01 && !p.redeemable);
  const open    = livePos.filter(p => parseFloat(p.currentValue||0) > 0.01);
  const closed  = won.length + lost.length;
  const winRate = closed > 0 ? (won.length / closed * 100) : 0;
  const wonVal  = won.reduce((s,p) => s + parseFloat(p.initialValue||0) / parseFloat(p.avgPrice||1), 0);
  const wonCost = won.reduce((s,p) => s + parseFloat(p.initialValue||0), 0);
  const lostC   = lost.reduce((s,p) => s + parseFloat(p.initialValue||0), 0);
  const pnlNet  = wonVal - wonCost - lostC;
  const openPnl = open.reduce((s,p) => s + parseFloat(p.cashPnl||0), 0);

  const col  = v => v >= 0 ? 'var(--green)' : 'var(--red)';
  const fmtD = v => (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2);
  const timeAgo = d => { if(!d) return '—'; const s=Math.floor((Date.now()-d)/1000); return s<60?'à l\'instant':`il y a ${Math.floor(s/60)}min`; };
  const certColor = c => ({ high:'#6366f1', medium:'#f59e0b', low:'#ef4444', speculative:'#8b5cf6', moonshot:'#ec4899', standard:'#10b981' })[c] || 'var(--text-3)';
  const outcomeColor = o => o?.toLowerCase()==='no' ? '#6366f1' : '#f59e0b';

  return (
    <div>
      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:14,marginBottom:'var(--gap)'}}>
        <button onClick={onBack} className="tap" style={{border:'none',background:'var(--fill)',width:38,height:38,borderRadius:11,cursor:'pointer',display:'grid',placeItems:'center',color:'var(--accent)',transform:'scaleX(-1)'}}>
          <Icon name="chevron" size={20} stroke={2.4}/>
        </button>
        <div style={{width:46,height:46,borderRadius:14,background:'color-mix(in oklab,#10b981 15%,var(--bg-elev))',border:'1.5px solid color-mix(in oklab,#10b981 40%,transparent)',display:'grid',placeItems:'center',fontSize:22}}>🍀</div>
        <div style={{flex:1}}>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <h2 style={{margin:0,fontSize:22,fontWeight:700}}>Analyse onlylucknobrain</h2>
            <StatusPill status="running"/>
          </div>
          <div style={{fontSize:12,color:'var(--text-3)',marginTop:2}}>Mis à jour {timeAgo(lastUpdate)}</div>
        </div>
        <button onClick={load} className="tap" style={{border:'none',background:'var(--fill)',padding:'8px 14px',borderRadius:10,cursor:'pointer',fontSize:13,color:'var(--text-2)',display:'flex',alignItems:'center',gap:6}}>
          <Icon name="refresh" size={14} stroke={2}/> Refresh
        </button>
      </div>

      {loading && <div style={{textAlign:'center',padding:40,color:'var(--text-3)',fontSize:14}}>Chargement…</div>}

      {!loading && (<>
        {/* Hero stats */}
        <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8,marginBottom:'var(--gap)'}}>
          {[
            {l:'Win Rate', v:`${winRate.toFixed(0)}%`, c:winRate>=80?'var(--green)':'var(--orange)', sub:`${won.length}G / ${lost.length}P`},
            {l:'P&L résolu', v:fmtD(pnlNet), c:col(pnlNet), sub:'marchés fermés'},
            {l:'P&L live', v:fmtD(openPnl), c:col(openPnl), sub:`${open.length} ouvertes`},
            {l:'Positions trackées', v:positions.length, c:'var(--text)', sub:'depuis suivi'},
          ].map((s,i)=>(
            <Card key={i} style={{padding:'14px 12px',textAlign:'center'}}>
              <div style={{fontSize:9.5,fontWeight:700,color:'var(--text-3)',letterSpacing:'.07em',textTransform:'uppercase',marginBottom:5}}>{s.l}</div>
              <div style={{fontSize:20,fontWeight:900,color:s.c}}>{s.v}</div>
              <div style={{fontSize:10,color:'var(--text-3)',marginTop:2}}>{s.sub}</div>
            </Card>
          ))}
        </div>

        {/* Onglets */}
        <div style={{display:'flex',gap:6,marginBottom:'var(--gap)',background:'var(--fill)',borderRadius:12,padding:4}}>
          {[['positions','📋 Positions'],['rapport','🧠 Stratégie'],['live','📊 Live']].map(([v,l])=>(
            <button key={v} onClick={()=>setTab(v)} style={{flex:1,border:'none',borderRadius:9,padding:'8px 4px',fontSize:13,fontWeight:600,cursor:'pointer',transition:'all .15s',background:tab===v?'var(--bg-elev)':'transparent',color:tab===v?'var(--text)':'var(--text-3)',boxShadow:tab===v?'0 1px 3px rgba(0,0,0,.15)':'none'}}>{l}</button>
          ))}
        </div>

        {/* ── Positions ── */}
        {tab==='positions' && (
          <div>
            <div style={{fontSize:11,fontWeight:700,color:'var(--text-3)',letterSpacing:'.07em',textTransform:'uppercase',marginBottom:12}}>
              {positions.length} positions détectées par l'agent
            </div>
            {positions.length === 0 ? (
              <Card style={{padding:28,textAlign:'center',color:'var(--text-3)'}}>
                ⏳ Agent en train de scanner…<br/>
                <span style={{fontSize:12}}>Les positions apparaîtront au prochain cycle (10 min)</span>
              </Card>
            ) : positions.map((p,i) => {
              const gap = p.gap != null ? parseFloat(p.gap) : null;
              const riskLevel = gap != null && Math.abs(gap) < 3 ? '⚠️' : gap != null && Math.abs(gap) >= 6 ? '✅' : '🟡';
              return (
                <Card key={i} style={{marginBottom:10,padding:'14px 16px'}}>
                  <div style={{display:'flex',alignItems:'flex-start',gap:12}}>
                    <div style={{fontSize:11,fontWeight:700,color:outcomeColor(p.outcome),background:`color-mix(in oklab,${outcomeColor(p.outcome)} 12%,transparent)`,padding:'3px 10px',borderRadius:999,border:`1px solid color-mix(in oklab,${outcomeColor(p.outcome)} 30%,transparent)`,flexShrink:0,marginTop:2}}>
                      {(p.outcome||'?').toUpperCase()}
                    </div>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4,flexWrap:'wrap'}}>
                        <span style={{fontSize:13.5,fontWeight:700,color:'var(--text)',textTransform:'capitalize'}}>{p.city||p.title?.slice(0,30)||'?'}</span>
                        {p.range_low && <span style={{fontSize:12,color:'var(--text-2)'}}>{p.range_low}–{p.range_high}°F</span>}
                        <span style={{fontSize:11,fontWeight:700,color:certColor(p.certainty),background:`color-mix(in oklab,${certColor(p.certainty)} 10%,transparent)`,padding:'1px 7px',borderRadius:6}}>{p.certainty}</span>
                        {gap != null && <span style={{fontSize:12}}>{riskLevel}</span>}
                      </div>
                      {(p.forecast_temp || gap != null) && (
                        <div style={{display:'flex',gap:12,marginBottom:6,fontSize:11.5,color:'var(--text-3)'}}>
                          {p.forecast_temp && <span>🌡️ <strong style={{color:'var(--text)'}}>{p.forecast_temp}°F</strong></span>}
                          {gap != null && <span>Écart : <strong style={{color:Math.abs(gap)<3?'var(--red)':Math.abs(gap)>=6?'var(--green)':'var(--orange)'}}>{gap>0?'+':''}{gap.toFixed(1)}°F</strong></span>}
                          {p.price && <span>Prix : <strong style={{color:'var(--text)'}}>{(parseFloat(p.price)*100).toFixed(0)}¢</strong></span>}
                          {p.amount_usdc && <span>Mise : <strong style={{color:'var(--text)'}}>${parseFloat(p.amount_usdc).toFixed(0)}</strong></span>}
                        </div>
                      )}
                      {p.analysis && (
                        <div style={{fontSize:12.5,color:'var(--text-2)',lineHeight:1.6,padding:'8px 12px',borderRadius:8,background:'var(--fill)',borderLeft:'3px solid color-mix(in oklab,#10b981 40%,transparent)'}}>
                          {p.analysis}
                        </div>
                      )}
                      <div style={{fontSize:10.5,color:'var(--text-3)',marginTop:5}}>
                        {p.detected_at ? new Date(p.detected_at).toLocaleString('fr-FR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : ''}
                        {p.title && <span style={{marginLeft:8,opacity:.6}}>{p.title.slice(0,60)}</span>}
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* ── Rapport ── */}
        {tab==='rapport' && (
          <div>
            {rapports.length === 0 ? (
              <Card style={{padding:28,textAlign:'center',color:'var(--text-3)'}}>
                🧠 Le rapport sera généré après le premier cycle<br/>
                <span style={{fontSize:12}}>Reviens dans ~10 min</span>
              </Card>
            ) : rapports.map((r,i) => (
              <div key={i} style={{marginBottom:'var(--gap)'}}>
                {i===0 && (
                  <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8,marginBottom:12}}>
                    {[
                      {l:'Positions',v:r.nb_positions,c:'var(--text)'},
                      {l:'NO',v:`${r.nb_no} (${(r.prix_no_moyen*100||0).toFixed(0)}¢)`,c:'#6366f1'},
                      {l:'YES',v:`${r.nb_yes} (${(r.prix_yes_moyen*100||0).toFixed(0)}¢)`,c:'#f59e0b'},
                    ].map((s,j)=>(
                      <Card key={j} style={{padding:'12px',textAlign:'center'}}>
                        <div style={{fontSize:9.5,fontWeight:700,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{s.l}</div>
                        <div style={{fontSize:17,fontWeight:800,color:s.c}}>{s.v}</div>
                      </Card>
                    ))}
                  </div>
                )}
                <Card style={{padding:'18px 20px'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:12}}>
                    📊 Rapport du {new Date(r.created_at).toLocaleString('fr-FR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})} · {r.nb_positions} positions analysées
                  </div>
                  <div style={{fontSize:13.5,color:'var(--text)',lineHeight:1.8,whiteSpace:'pre-wrap'}}>
                    {r.analyse_text}
                  </div>
                </Card>
              </div>
            ))}
          </div>
        )}

        {/* ── Live ── */}
        {tab==='live' && (
          <div>
            <div style={{fontSize:11,fontWeight:700,color:'var(--text-3)',letterSpacing:'.07em',textTransform:'uppercase',marginBottom:12}}>
              {open.length} positions ouvertes en ce moment
            </div>
            {open.sort((a,b)=>Math.abs(parseFloat(b.cashPnl||0))-Math.abs(parseFloat(a.cashPnl||0))).map((p,i)=>{
              const pnl=parseFloat(p.cashPnl||0),pct=parseFloat(p.percentPnl||0),avg=parseFloat(p.avgPrice||0),cur=parseFloat(p.curPrice||0),init=parseFloat(p.initialValue||0);
              const title=(p.title||'').replace('Will the highest temperature in ','').replace(' be between ',' ').replace(' on ',' · ');
              return (
                <Card key={i} style={{marginBottom:8,padding:'12px 16px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:12}}>
                    <div style={{fontSize:11,fontWeight:700,color:outcomeColor(p.outcome),background:`color-mix(in oklab,${outcomeColor(p.outcome)} 12%,transparent)`,padding:'3px 9px',borderRadius:999,border:`1px solid color-mix(in oklab,${outcomeColor(p.outcome)} 30%,transparent)`,flexShrink:0}}>
                      {(p.outcome||'?').toUpperCase()}
                    </div>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{fontSize:12.5,fontWeight:600,color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{title}</div>
                      <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>avg {(avg*100).toFixed(0)}¢ → {(cur*100).toFixed(0)}¢ · ${init.toFixed(0)}</div>
                    </div>
                    <div style={{textAlign:'right',flexShrink:0}}>
                      <div style={{fontSize:15,fontWeight:800,color:col(pnl)}}>{pnl>=0?'+':''}{pnl.toFixed(0)}$</div>
                      <div style={{fontSize:11,color:col(pct)}}>{pct>=0?'+':''}{pct.toFixed(0)}%</div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </>)}
    </div>
  );
}

window.LuckPage = LuckPage;
