// ============================================================
// page_bot.jsx — single bot data tracking
// ============================================================
function BotPage({ bot, onToggle, onBack, onSettings, onRename, livePositions, liveActivity }) {
  const { POSITIONS, TXNS, RANGES, MARKETS, fmtUSD, fmtPct, sliceRange,
    Card, BotGlyph, MarketChip, StatusPill, Toggle, Segmented, AreaChart,
    Stat, Delta, Button, Icon, Meter } = window;
  const [tab, setTab] = React.useState('apercu');
  const [range, setRange] = React.useState('1M');
  const [editingName, setEditingName] = React.useState(false);
  const [draftName, setDraftName] = React.useState(bot.name);

  // ── Analyse Mistral par bot ──
  const [analyseCategory,  setAnalyseCategory]  = React.useState('tout');
  const [analyseVolume,    setAnalyseVolume]     = React.useState(0);
  const [analyseLoading,   setAnalyseLoading]    = React.useState(false);
  const [analyseResult,    setAnalyseResult]     = React.useState(null);
  const [analyseError,     setAnalyseError]      = React.useState(null);
  const [analyseCopied,    setAnalyseCopied]     = React.useState(false);
  const [analyseHistory,   setAnalyseHistory]    = React.useState([]);
  const [showAnalyseHist,  setShowAnalyseHist]   = React.useState(false);
  const [analyseInstructions, setAnalyseInstructions] = React.useState('');
  const [meteoRapport,    setMeteoRapport]    = React.useState(null);
  const [meteoResumes,    setMeteoResumes]    = React.useState([]);
  const [meteoTracking,   setMeteoTracking]   = React.useState([]);
  const [meteoLastSync,   setMeteoLastSync]   = React.useState(null);

  const refreshMeteo = React.useCallback(() => {
    fetch('http://localhost:5000/api/meteo/rapport')
      .then(r => r.json())
      .then(d => { if (d && (d.stats || d.trackes)) setMeteoRapport(d); })
      .catch(() => {});
    fetch('http://localhost:5000/api/meteo/resumes')
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) setMeteoResumes(d); })
      .catch(() => {});
    fetch('http://localhost:5000/api/meteo/tracking')
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) { setMeteoTracking(d); setMeteoLastSync(new Date()); } })
      .catch(() => {});
  }, []);

  // Charge l'historique + instructions + données météo au montage
  React.useEffect(() => {
    fetch('http://localhost:5000/api/analyse/history')
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setAnalyseHistory(data); })
      .catch(() => {});
    fetch(`http://localhost:5000/api/strategy/${bot.id}`)
      .then(r => r.json())
      .then(d => {
        if (d.analyse_instructions !== undefined) setAnalyseInstructions(d.analyse_instructions);
        if (d.analyse_category     !== undefined) setAnalyseCategory(d.analyse_category);
      })
      .catch(() => {});
    refreshMeteo();
    // Auto-refresh toutes les 30 min
    const id = setInterval(refreshMeteo, 30 * 60 * 1000);
    return () => clearInterval(id);
  }, [bot.id, refreshMeteo]);

  const saveAnalyseInstructions = () => {
    fetch(`http://localhost:5000/api/strategy/${bot.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analyse_instructions: analyseInstructions, analyse_category: analyseCategory }),
    }).catch(() => {});
  };

  const runBotAnalysis = async () => {
    setAnalyseLoading(true);
    setAnalyseError(null);
    setAnalyseResult(null);
    try {
      const r = await fetch('http://localhost:5000/api/analyse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: analyseCategory, min_volume: analyseVolume, instructions: analyseInstructions }),
      });
      const data = await r.json();
      if (data.error) throw new Error(data.error);
      setAnalyseResult(data);
      setAnalyseHistory(h => [{ time: new Date().toISOString(), ...data }, ...h.slice(0, 19)]);
    } catch (e) {
      setAnalyseError(e.message);
    } finally {
      setAnalyseLoading(false);
    }
  };

  const copyAnalyseStrategy = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setStratPrompt(text);
      setStratStatus('unsaved');
      setAnalyseCopied(true);
      setTab('strategie');
      setTimeout(() => setAnalyseCopied(false), 2000);
    });
  };

  // ── Stratégie par bot ──
  const [stratPrompt, setStratPrompt] = React.useState('');
  const [stratEnabled, setStratEnabled] = React.useState(false);
  const [stratStatus,  setStratStatus]  = React.useState(null);
  const [stratVersion, setStratVersion] = React.useState(1);
  const [stratLastImproved, setStratLastImproved] = React.useState(null);
  const [stratLastReason,   setStratLastReason]   = React.useState('');
  const [stratHistory, setStratHistory] = React.useState([]);
  const [showStratHist, setShowStratHist] = React.useState(false);

  React.useEffect(() => { if (!editingName) setDraftName(bot.name); }, [bot.name]);

  // Charge la stratégie + historique au montage
  React.useEffect(() => {
    fetch(`http://localhost:5000/api/strategy/${bot.id}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.prompt   !== undefined) setStratPrompt(d.prompt);
        if (d.enabled  !== undefined) setStratEnabled(d.enabled);
        if (d.version  !== undefined) setStratVersion(d.version);
        if (d.last_improved)         setStratLastImproved(d.last_improved);
        if (d.last_reason)           setStratLastReason(d.last_reason);
      })
      .catch(() => {});
    fetch(`http://localhost:5000/api/strategy/${bot.id}/history`)
      .then((r) => r.json())
      .then((d) => { if (Array.isArray(d)) setStratHistory(d); })
      .catch(() => {});
  }, [bot.id]);

  const saveStrategy = () => {
    setStratStatus('saving');
    fetch(`http://localhost:5000/api/strategy/${bot.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: stratPrompt, enabled: stratEnabled }),
    })
      .then((r) => r.json())
      .then(() => setStratStatus('saved'))
      .catch(() => setStratStatus('error'));
  };

  const series = sliceRange(bot.series, range);
  const periodPct = ((series[series.length - 1] - series[0]) / series[0]) * 100;
  const positions = livePositions ?? POSITIONS[bot.id] ?? [];
  const isPoly = bot.market === 'polymarket';
  const trades = React.useMemo(() => {
    const src = (liveActivity && liveActivity.length > 0) ? liveActivity : TXNS;
    return src.filter((t) => t.bot === bot.id).slice(0, 8);
  }, [bot.id, liveActivity]);
  const m = MARKETS[bot.market];

  const stats = [
    { label: 'P&L total', value: fmtPct(bot.pnlTotalPct), accent: bot.pnlTotalPct >= 0 ? 'var(--green)' : 'var(--red)' },
    { label: 'Win rate', value: bot.winRate + '%' },
    { label: 'Sharpe', value: (bot.sharpe ?? 0).toFixed(2) },
    { label: 'Max drawdown', value: bot.maxDD.toFixed(1) + '%', accent: 'var(--red)' },
    { label: 'Trades', value: window.fmtNum(bot.trades) },
  ];

  const stratExamples = React.useMemo(() => [
    'Achète YES quand la probabilité est < 40% et que le volume dépasse 10 000 USDC.',
    'Mise sur NO pour les marchés électoraux quand le favori dépasse 70%.',
    'Arbitrage : achète le côté sous-évalué quand YES + NO ≠ 1.00 avec un écart > 3%.',
  ], []);

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

      {/* onglets */}
      <div style={{ marginBottom: 'var(--gap)', maxWidth: 380 }}>
        <Segmented size="sm" value={tab} onChange={setTab}
          options={[{ value: 'apercu', label: 'Aperçu' }, { value: 'strategie', label: 'Stratégie' }, { value: 'analyse', label: 'Analyse' }]} />
      </div>

      {/* ── onglet Stratégie ── */}
      {tab === 'strategie' && (
        <div style={{ maxWidth: 680 }}>
          <Card style={{ marginBottom: 'var(--gap)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>PROMPT DE STRATÉGIE</div>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{stratPrompt.length} caractères</span>
            </div>
            <textarea value={stratPrompt} onChange={(e) => setStratPrompt(e.target.value)}
              placeholder="Décris en détail ce que ce bot doit faire : quand acheter, quand vendre, quel montant, quels types de marchés cibler..."
              rows={7}
              style={{ width: '100%', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-md)',
                padding: '12px 14px', fontSize: 14.5, color: 'var(--text)', outline: 'none',
                fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.6 }} />
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 600, marginBottom: 7 }}>EXEMPLES</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {stratExamples.map((ex, i) => (
                  <button key={i} onClick={() => setStratPrompt(ex)} className="tap"
                    style={{ textAlign: 'left', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-sm)',
                      padding: '8px 12px', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer', lineHeight: 1.5 }}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card style={{ marginBottom: 'var(--gap)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>Activer ce bot</div>
              <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 2 }}>
                Le bot utilisera ce prompt pour prendre ses décisions
              </div>
            </div>
            <Toggle on={stratEnabled} onChange={setStratEnabled} />
          </Card>

          {/* Infos auto-amélioration */}
          {stratVersion > 1 && (
            <div style={{ marginBottom: 'var(--gap)', padding: '10px 14px',
              borderRadius: 'var(--r-md)', background: 'color-mix(in oklab, var(--green) 10%, transparent)',
              border: '1px solid color-mix(in oklab, var(--green) 25%, transparent)' }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--green)', marginBottom: 4 }}>
                🧠 Stratégie v{stratVersion} — améliorée automatiquement par Claude
              </div>
              {stratLastReason && <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>{stratLastReason}</div>}
              {stratLastImproved && (
                <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4 }}>
                  Dernière mise à jour : {new Date(stratLastImproved).toLocaleString('fr-FR', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' })}
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: stratHistory.length ? 'var(--gap)' : 0 }}>
            <Button variant="primary" icon="check" onClick={saveStrategy}>
              {stratStatus === 'saving' ? 'Sauvegarde…' : 'Sauvegarder'}
            </Button>
            {stratStatus === 'saved' && (
              <span style={{ fontSize: 13.5, color: 'var(--green)', fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 5 }}>
                <Icon name="check" size={16} stroke={2.4} />Sauvegardé
              </span>
            )}
            {stratStatus === 'unsaved' && (
              <span style={{ fontSize: 13, color: 'var(--orange)', fontWeight: 500 }}>
                ⚠️ Stratégie Mistral copiée — pense à sauvegarder
              </span>
            )}
            {stratStatus === 'error' && (
              <span style={{ fontSize: 13.5, color: 'var(--red)', fontWeight: 500 }}>
                Erreur — le serveur bot est-il lancé ?
              </span>
            )}
          </div>

          {/* Historique des versions */}
          {stratHistory.length > 0 && (
            <div>
              <button onClick={() => setShowStratHist(!showStratHist)} className="tap"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 7, fontSize: 13.5,
                  fontWeight: 600, color: 'var(--text-2)', padding: '4px 0' }}>
                <Icon name={showStratHist ? 'chevdown' : 'chevron'} size={15} stroke={2} />
                Historique des versions ({stratHistory.length})
              </button>
              {showStratHist && (
                <Card pad={false} style={{ marginTop: 10 }}>
                  {[...stratHistory].reverse().map((v, i) => (
                    <div key={i} style={{ padding: '12px var(--pad)',
                      borderBottom: i < stratHistory.length - 1 ? '1px solid var(--separator)' : 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-3)' }}>Version {v.version}</span>
                        <span style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                          {new Date(v.time).toLocaleString('fr-FR', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' })}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5, marginBottom: 4 }}>
                        {v.prompt?.slice(0, 120)}{v.prompt?.length > 120 ? '…' : ''}
                      </div>
                      {v.reason && <div style={{ fontSize: 12, color: 'var(--text-3)', fontStyle: 'italic' }}>→ {v.reason}</div>}
                    </div>
                  ))}
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── onglet Analyse ── */}
      {tab === 'analyse' && (
        <div style={{ maxWidth: 760 }}>

          {/* ── Description stratégie ── */}
          <Card style={{ marginBottom:'var(--gap)', display:'flex', gap:16, alignItems:'flex-start' }}>
            <div style={{ fontSize:28, flexShrink:0 }}>🌦</div>
            <div>
              <div style={{ fontSize:15, fontWeight:700, marginBottom:4 }}>Stratégie météo à 80%+</div>
              <div style={{ fontSize:13.5, color:'var(--text-2)', lineHeight:1.6 }}>
                L'agent scrute Polymarket toutes les 30 min et tracke tous les paris météo dont la probabilité YES dépasse <strong>80%</strong>.
                Il vérifie chaque jour si ces paris ont été gagnants ou perdants, et génère un rapport à <strong>17h</strong>.
                Mistral analyse les résultats et propose une stratégie améliorée chaque jour.
              </div>
            </div>
          </Card>

          {/* ── Taux de réussite global ── */}
          {(() => {
            const totalGagnes = meteoResumes.reduce((s, r) => s + (r.gagnes || 0), 0);
            const totalResolus = meteoResumes.reduce((s, r) => s + (r.resolus || 0), 0);
            const tauxGlobal = totalResolus > 0 ? Math.round(totalGagnes / totalResolus * 100) : null;
            return tauxGlobal !== null ? (
              <div style={{ marginBottom:'var(--gap)', borderRadius:'var(--r-card)',
                background: tauxGlobal >= 60 ? 'color-mix(in oklab,var(--green) 10%,transparent)'
                  : tauxGlobal >= 50 ? 'color-mix(in oklab,var(--orange) 10%,transparent)'
                  : 'color-mix(in oklab,var(--red) 10%,transparent)',
                border: `1.5px solid color-mix(in oklab,${tauxGlobal >= 60 ? 'var(--green)' : tauxGlobal >= 50 ? 'var(--orange)' : 'var(--red)'} 25%,transparent)`,
                padding:'18px 22px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div>
                  <div style={{ fontSize:12, fontWeight:700, color:'var(--text-3)', letterSpacing:'.05em', marginBottom:4 }}>TAUX DE RÉUSSITE GLOBAL</div>
                  <div style={{ fontSize:38, fontWeight:900, lineHeight:1,
                    color: tauxGlobal >= 60 ? 'var(--green)' : tauxGlobal >= 50 ? 'var(--orange)' : 'var(--red)' }}>
                    {tauxGlobal}%
                  </div>
                </div>
                <div style={{ textAlign:'right', fontSize:13, color:'var(--text-3)' }}>
                  <div>{totalGagnes} gagnés</div>
                  <div>{totalResolus - totalGagnes} perdus</div>
                  <div>{totalResolus} résolus</div>
                </div>
              </div>
            ) : null;
          })()}

          {/* ── Pools trackés en live ── */}


          {/* ── Rapport en cours (dernière heure) ── */}
          {meteoRapport && (
            <Card style={{ marginBottom:'var(--gap)', padding:0, overflow:'hidden' }}>
              <div style={{ background:'linear-gradient(135deg,#1a5c8a,#0d3a5c)', padding:'14px 20px',
                display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:700, color:'#fff' }}>🌦 Agent Météo — Rapport en direct</div>
                  <div style={{ fontSize:11, color:'rgba(255,255,255,.5)', marginTop:2 }}>{meteoRapport.heure}</div>
                </div>
                <div style={{ fontSize:13, fontWeight:700,
                  color: meteoRapport.verdict?.includes('✅') ? '#4ade80' : meteoRapport.verdict?.includes('⚠️') ? '#fbbf24' : '#f87171' }}>
                  {meteoRapport.verdict}
                </div>
              </div>
              <div style={{ padding:'14px 20px' }}>
                {/* Stats */}
                <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:10, marginBottom:14 }}>
                  {[
                    { label:'Trackés',  value: meteoRapport.trackes    ?? 0, color:'var(--text)' },
                    { label:'Résolus',  value: meteoRapport.resolus    ?? 0, color:'var(--text)' },
                    { label:'✅ Gagnés', value: meteoRapport.gagnes    ?? 0, color:'var(--green)' },
                    { label:'❌ Perdus', value: meteoRapport.perdus    ?? 0, color:'var(--red)' },
                  ].map((s,i) => (
                    <div key={i} style={{ textAlign:'center', padding:'10px 6px',
                      background:'var(--fill)', borderRadius:'var(--r-md)' }}>
                      <div style={{ fontSize:22, fontWeight:700, color:s.color }}>{s.value}</div>
                      <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
                {/* Taux */}
                {meteoRapport.taux_victoire !== null && meteoRapport.taux_victoire !== undefined && (
                  <div style={{ padding:'10px 16px', borderRadius:'var(--r-md)', marginBottom:12,
                    background: meteoRapport.taux_victoire >= 60 ? 'color-mix(in oklab,var(--green) 10%,transparent)'
                      : meteoRapport.taux_victoire >= 50 ? 'color-mix(in oklab,var(--orange) 10%,transparent)'
                      : 'color-mix(in oklab,var(--red) 10%,transparent)' }}>
                    <div style={{ fontSize:26, fontWeight:800,
                      color: meteoRapport.taux_victoire >= 60 ? 'var(--green)'
                        : meteoRapport.taux_victoire >= 50 ? 'var(--orange)' : 'var(--red)' }}>
                      {meteoRapport.taux_victoire}% de réussite à 85%+
                    </div>
                  </div>
                )}
                {/* Marchés actifs à 85%+ */}
                {meteoRapport.actifs_85?.length > 0 && (
                  <div style={{ borderTop:'1px solid var(--separator)', paddingTop:12 }}>
                    <div style={{ fontSize:11, fontWeight:700, color:'var(--text-3)', marginBottom:8, letterSpacing:'.05em' }}>
                      MARCHÉS ACTIFS À 85%+
                    </div>
                    {meteoRapport.actifs_85.map((m,i) => (
                      <div key={i} style={{ display:'flex', justifyContent:'space-between',
                        padding:'6px 0', borderBottom: i < meteoRapport.actifs_85.length-1 ? '1px solid var(--separator)' : 'none' }}>
                        <div style={{ fontSize:13, color:'var(--text-2)', flex:1, marginRight:10 }}>{m.question}</div>
                        <div style={{ fontSize:13.5, fontWeight:700, color:'var(--green)', flexShrink:0 }}>{m.pct}%</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* ── Pools trackés en live ── */}
          {meteoTracking.length > 0 && (
            <Card style={{ marginBottom:'var(--gap)', padding:0, overflow:'hidden' }}>
              <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--separator)',
                display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div>
                  <div style={{ fontSize:13.5, fontWeight:650 }}>📌 Pools trackés à 85%+</div>
                  <div style={{ fontSize:11.5, color:'var(--text-3)', marginTop:1 }}>
                    {meteoTracking.length} pari{meteoTracking.length > 1 ? 's' : ''} en surveillance
                  </div>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  {meteoLastSync && (
                    <span style={{ fontSize:11, color:'var(--text-3)' }}>
                      Sync {meteoLastSync.toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' })}
                    </span>
                  )}
                  <button onClick={refreshMeteo} className="tap"
                    style={{ border:'none', background:'var(--fill)', borderRadius:'var(--r-sm)',
                      padding:'5px 10px', fontSize:12, fontWeight:600, cursor:'pointer', color:'var(--accent)' }}>
                    ↻ Rafraîchir
                  </button>
                </div>
              </div>
              {/* En-tête tableau */}
              <div style={{ display:'grid', gridTemplateColumns:'1fr 80px 100px 90px',
                padding:'8px 20px', background:'var(--fill)',
                fontSize:11, fontWeight:700, color:'var(--text-3)', letterSpacing:'.05em' }}>
                <span>PARI MÉTÉO</span>
                <span style={{ textAlign:'center' }}>CONFIANCE</span>
                <span style={{ textAlign:'center' }}>TRACKÉ LE</span>
                <span style={{ textAlign:'center' }}>RÉSULTAT</span>
              </div>
              {meteoTracking.map((t, i) => {
                const isGagne = t.resultat === 'GAGNE';
                const isPerdu = t.resultat === 'PERDU';
                return (
                  <div key={i} style={{ display:'grid', gridTemplateColumns:'1fr 80px 100px 90px',
                    padding:'11px 20px', alignItems:'center',
                    borderTop:'1px solid var(--separator)',
                    background: isGagne ? 'color-mix(in oklab,var(--green) 5%,transparent)'
                      : isPerdu ? 'color-mix(in oklab,var(--red) 5%,transparent)' : 'transparent' }}>
                    <div style={{ fontSize:13, color:'var(--text)', lineHeight:1.4, paddingRight:12 }}>
                      {t.question}
                    </div>
                    <div style={{ textAlign:'center' }}>
                      <span style={{ fontSize:14, fontWeight:800,
                        color: t.yes_price_au_track >= 99 ? 'var(--green)'
                          : t.yes_price_au_track >= 90 ? 'var(--orange)' : 'var(--text)' }}>
                        {t.yes_price_au_track}%
                      </span>
                    </div>
                    <div style={{ textAlign:'center', fontSize:11.5, color:'var(--text-3)' }}>
                      {t.tracke_le}
                    </div>
                    <div style={{ textAlign:'center' }}>
                      {isGagne && <span style={{ fontSize:12, fontWeight:700, color:'var(--green)',
                        background:'color-mix(in oklab,var(--green) 15%,transparent)',
                        padding:'3px 10px', borderRadius:999 }}>✅ Gagné</span>}
                      {isPerdu && <span style={{ fontSize:12, fontWeight:700, color:'var(--red)',
                        background:'color-mix(in oklab,var(--red) 15%,transparent)',
                        padding:'3px 10px', borderRadius:999 }}>❌ Perdu</span>}
                      {!t.resultat && <span style={{ fontSize:12, color:'var(--text-3)',
                        background:'var(--fill)', padding:'3px 10px', borderRadius:999 }}>⏳ Attente</span>}
                    </div>
                  </div>
                );
              })}
            </Card>
          )}

          {/* ── Historique des rapports ── */}
          {meteoResumes.length > 0 && (
            <Card style={{ padding:0, overflow:'hidden' }}>
              <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--separator)',
                display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div style={{ fontSize:14, fontWeight:700 }}>📋 Rapports quotidiens</div>
                <div style={{ fontSize:12, color:'var(--text-3)' }}>{meteoResumes.length} jour{meteoResumes.length > 1 ? 's' : ''}</div>
              </div>
              {meteoResumes.map((r, i) => {
                const taux = r.taux_victoire;
                const couleur = taux >= 60 ? 'var(--green)' : taux >= 50 ? 'var(--orange)' : taux !== null ? 'var(--red)' : 'var(--text-3)';
                return (
                  <div key={i} style={{ padding:'16px 20px',
                    borderBottom: i < meteoResumes.length-1 ? '1px solid var(--separator)' : 'none' }}>
                    {/* Header */}
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                      <div style={{ fontSize:13.5, fontWeight:700 }}>📅 {r.date} — 17h00</div>
                      <div style={{ fontSize:20, fontWeight:900, color:couleur }}>
                        {taux !== null ? `${taux}%` : '—'}
                      </div>
                    </div>
                    {/* Stats */}
                    <div style={{ display:'flex', gap:10, marginBottom:12 }}>
                      {[
                        { label:'Trackés',  value: r.trackes, color:'var(--text-3)' },
                        { label:'Résolus',  value: r.resolus, color:'var(--text-3)' },
                        { label:'✅ Gagnés', value: r.gagnes,  color:'var(--green)' },
                        { label:'❌ Perdus', value: r.perdus,  color:'var(--red)' },
                      ].map((s,j) => (
                        <div key={j} style={{ textAlign:'center', padding:'7px 10px',
                          background:'var(--fill)', borderRadius:'var(--r-md)', flex:1 }}>
                          <div style={{ fontSize:17, fontWeight:700, color:s.color }}>{s.value}</div>
                          <div style={{ fontSize:10.5, color:'var(--text-3)', marginTop:1 }}>{s.label}</div>
                        </div>
                      ))}
                    </div>
                    {/* Analyse Mistral */}
                    {r.analyse_mistral && (
                      <div style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.6,
                        background:'var(--fill)', borderRadius:'var(--r-md)',
                        padding:'10px 14px', marginBottom: r.strategie_proposee ? 10 : 0, whiteSpace:'pre-wrap' }}>
                        {r.analyse_mistral}
                      </div>
                    )}
                    {/* Stratégie proposée */}
                    {r.strategie_proposee && (
                      <div style={{ padding:'10px 14px', borderRadius:'var(--r-md)',
                        background:'color-mix(in oklab,var(--accent) 8%,transparent)',
                        border:'1px solid color-mix(in oklab,var(--accent) 20%,transparent)' }}>
                        <div style={{ fontSize:11, fontWeight:700, color:'var(--accent)',
                          letterSpacing:'.05em', marginBottom:5 }}>💡 STRATÉGIE POUR DEMAIN</div>
                        <div style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.6, fontStyle:'italic' }}>
                          {r.strategie_proposee}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </Card>
          )}

          {/* Empty state */}
          {meteoResumes.length === 0 && !meteoRapport && (
            <Card style={{ textAlign:'center', padding:'48px 24px', color:'var(--text-3)' }}>
              <div style={{ fontSize:36, marginBottom:12 }}>🌦</div>
              <div style={{ fontSize:15, fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>
                Premier rapport à 17h00
              </div>
              <div style={{ fontSize:13.5, lineHeight:1.6 }}>
                L'agent tourne en arrière-plan sur GitHub.<br/>
                Le premier rapport apparaîtra ici ce soir à 17h.
              </div>
            </Card>
          )}

          {/* Empty state */}
          {!analyseResult && !analyseLoading && !analyseError && !meteoRapport && (
            <Card style={{ textAlign:'center', padding:'40px 24px', color:'var(--text-3)' }}>
              <div style={{ fontSize:32, marginBottom:10 }}>🔍</div>
              <div style={{ fontSize:15, fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Analyse les pools Polymarket</div>
              <div style={{ fontSize:13.5, lineHeight:1.6 }}>
                Mistral va scanner les marchés en temps réel et identifier<br/>les meilleures opportunités pour ce bot.
              </div>
            </Card>
          )}

          {/* Historique des analyses */}
          {analyseHistory.length > 0 && (
            <div style={{ marginTop: analyseResult ? 'var(--gap)' : 0 }}>
              <button onClick={() => setShowAnalyseHist(!showAnalyseHist)} className="tap"
                style={{ border:'none', background:'transparent', cursor:'pointer',
                  display:'flex', alignItems:'center', gap:7, fontSize:13.5,
                  fontWeight:600, color:'var(--text-2)', padding:'4px 0', marginBottom:6 }}>
                <Icon name={showAnalyseHist ? 'chevdown' : 'chevron'} size={15} stroke={2} />
                Historique des analyses ({analyseHistory.length})
              </button>
              {showAnalyseHist && (
                <Card pad={false}>
                  {analyseHistory.map((h, i) => (
                    <div key={i} style={{ padding:'11px var(--pad)',
                      borderBottom: i < analyseHistory.length - 1 ? '1px solid var(--separator)' : 'none',
                      display:'flex', gap:12, alignItems:'flex-start' }}>
                      <div style={{ fontSize:11.5, color:'var(--text-3)', fontWeight:500, flexShrink:0, minWidth:80 }}>
                        {new Date(h.time).toLocaleString('fr-FR', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' })}
                      </div>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:13, fontWeight:500,
                          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginBottom:2 }}>
                          {h.summary || 'Analyse sans résumé'}
                        </div>
                        <div style={{ fontSize:11.5, color:'var(--text-3)' }}>
                          {h.opportunities?.length || 0} opportunité(s) · {h.category}
                        </div>
                      </div>
                      <button onClick={() => setAnalyseResult(h)} className="tap"
                        style={{ border:'none', background:'var(--fill)', cursor:'pointer',
                          borderRadius:7, padding:'4px 10px', fontSize:12,
                          color:'var(--text-2)', fontWeight:500, flexShrink:0 }}>
                        Voir
                      </button>
                    </div>
                  ))}
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── onglet Aperçu ── */}
      {tab === 'apercu' && <>

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

      </>} {/* fin onglet apercu */}
    </div>
  );
}
window.BotPage = BotPage;
