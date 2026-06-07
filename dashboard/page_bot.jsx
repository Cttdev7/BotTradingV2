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
  const [meteoRapports,   setMeteoRapports]   = React.useState([]);
  const [meteoTracking,   setMeteoTracking]   = React.useState([]);
  const [meteoResumes,    setMeteoResumes]    = React.useState([]);
  const [meteoLastSync,   setMeteoLastSync]   = React.useState(null);
  const [meteoStats,      setMeteoStats]      = React.useState(null);

  const agentPrefix = bot.id === 'chengdu' ? 'chengdu' : bot.id === 'polycrypto' ? 'crypto' : bot.id === 'polycrypto4h' ? 'crypto_4h' : 'meteo';
  const agentLabel  = bot.id === 'polyedge' || bot.id === 'chengdu' ? 'Mistral' : 'Gemini';
  const agentEmoji  = bot.id === 'polyedge' ? '🌦' : bot.id === 'chengdu' ? '🌡️' : bot.id === 'polycrypto4h' ? '⏱' : '₿';
  const agentAnalyseKey = bot.id === 'polyedge' ? 'analyse_mistral' : 'analyse_gemini';

  const SB_URL = 'https://obqkqhlqlowxrxbyvktl.supabase.co';
  const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728';
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  const sbFetch = (table, limit = 100) =>
    fetch(`${SB_URL}/rest/v1/${table}?order=created_at.desc&limit=${limit}`, {
      headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}` }
    }).then(r => r.json());

  const sbUpsert = (table, data) =>
    fetch(`${SB_URL}/rest/v1/${table}`, {
      method: 'POST',
      headers: {
        'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
      },
      body: JSON.stringify(data)
    });

  const refreshMeteo = React.useCallback(() => {
    const tableRapports = bot.id === 'chengdu' ? 'chengdu_rapports' : bot.id === 'polycrypto' ? 'crypto_rapports' : bot.id === 'polycrypto4h' ? 'crypto_4h_rapports' : 'meteo_rapports';
    const tableTracking = bot.id === 'chengdu' ? 'chengdu_tracking' : bot.id === 'polycrypto' ? 'crypto_tracking' : bot.id === 'polycrypto4h' ? 'crypto_4h_tracking' : 'meteo_tracking';
    const tableResumes  = bot.id === 'chengdu' ? 'chengdu_resumes'  : bot.id === 'polycrypto' ? 'crypto_resumes'  : bot.id === 'polycrypto4h' ? 'crypto_4h_resumes'  : 'meteo_resumes';

    sbFetch(tableRapports, 48).then(d => {
      if (Array.isArray(d) && d.length) { setMeteoRapports(d); setMeteoRapport(d[0]); setMeteoLastSync(new Date()); }
    }).catch(() => {});
    sbFetch(tableTracking, 100).then(d => {
      if (Array.isArray(d)) setMeteoTracking(d);
    }).catch(() => {});
    sbFetch(tableResumes, 90).then(d => {
      if (Array.isArray(d)) setMeteoResumes(d);
    }).catch(() => {});
    const statsTable = agentPrefix === 'chengdu' ? 'chengdu_stats?id=eq.chengdu'
      : agentPrefix === 'meteo' ? 'meteo_stats?id=eq.meteo'
      : agentPrefix === 'crypto_4h' ? 'crypto_4h_stats?id=eq.crypto_4h'
      : 'crypto_stats?id=eq.crypto';
    sbFetch(statsTable, 1).then(d => {
      if (Array.isArray(d) && d[0]) setMeteoStats(d[0]);
    }).catch(() => {});
  }, [agentPrefix, isLocal]);

  // Charge instructions + données météo au montage
  React.useEffect(() => {
    sbFetch(`bot_strategies?bot_id=eq.${bot.id}`, 1)
      .then(d => {
        const s = d[0];
        if (!s) return;
        if (s.analyse_instructions !== undefined) setAnalyseInstructions(s.analyse_instructions);
        if (s.analyse_category     !== undefined) setAnalyseCategory(s.analyse_category);
      })
      .catch(() => {});
    refreshMeteo();
    const id = setInterval(refreshMeteo, 30 * 60 * 1000);
    return () => clearInterval(id);
  }, [bot.id, refreshMeteo]);

  // ── P&L horaire ──
  const [pnlHoraire, setPnlHoraire] = React.useState([]);
  React.useEffect(() => {
    if (tab !== 'apercu' || !isLocal) return;
    const load = () => fetch('http://127.0.0.1:5000/api/pnl/hourly')
      .then(r => r.json()).then(d => { if (Array.isArray(d)) setPnlHoraire(d); }).catch(() => {});
    load();
    const id = setInterval(load, 60 * 60 * 1000);
    return () => clearInterval(id);
  }, [tab, bot.id, isLocal]);

  const saveAnalyseInstructions = () => {
    sbUpsert('bot_strategies', {
      bot_id: bot.id,
      analyse_instructions: analyseInstructions,
      analyse_category: analyseCategory,
      updated_at: new Date().toISOString(),
    }).catch(() => {});
  };

  const runBotAnalysis = async () => {
    setAnalyseLoading(true);
    setAnalyseError(null);
    setAnalyseResult(null);
    try {
      const r = await fetch('http://127.0.0.1:5000/api/analyse', {
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

  // Charge la stratégie depuis Supabase
  React.useEffect(() => {
    sbFetch(`bot_strategies?bot_id=eq.${bot.id}`, 1)
      .then((d) => {
        const s = d[0];
        if (!s) return;
        if (s.prompt        !== undefined) setStratPrompt(s.prompt);
        if (s.enabled       !== undefined) setStratEnabled(s.enabled);
        if (s.version       !== undefined) setStratVersion(s.version);
        if (s.last_improved)              setStratLastImproved(s.last_improved);
        if (s.last_reason)                setStratLastReason(s.last_reason);
        if (Array.isArray(s.history))     setStratHistory(s.history);
      })
      .catch(() => {});
  }, [bot.id]);

  const saveStrategy = () => {
    setStratStatus('saving');
    sbUpsert('bot_strategies', {
      bot_id: bot.id,
      prompt: stratPrompt,
      enabled: stratEnabled,
      updated_at: new Date().toISOString(),
    })
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

          {/* ── Hero stratégie ── */}
          <div style={{ marginBottom:'var(--gap)', borderRadius:'var(--r-card)', overflow:'hidden',
            background: bot.id === 'polycrypto'
              ? 'linear-gradient(135deg,#0f0c29,#302b63,#24243e)'
              : 'linear-gradient(135deg,#0f2027,#203a43,#2c5364)',
            padding:'20px 24px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10, flexWrap:'wrap' }}>
              <span style={{ fontSize:24 }}>{agentEmoji}</span>
              <div style={{ fontSize:17, fontWeight:800, color:'#fff', letterSpacing:'-.01em' }}>
                Stratégie {bot.id === 'chengdu' ? 'Chengdu' : bot.id === 'polycrypto' ? 'crypto' : 'météo'} à 80%+
              </div>
              <span style={{ fontSize:11, fontWeight:700, color:'rgba(255,255,255,.5)',
                background:'rgba(255,255,255,.1)', padding:'3px 10px', borderRadius:999 }}>
                AUTO · {bot.id === 'chengdu' ? 'Railway' : 'GitHub Actions'}
              </span>
              <span style={{ fontSize:11, fontWeight:700, color:'rgba(255,255,255,.5)',
                background:'rgba(255,255,255,.1)', padding:'3px 10px', borderRadius:999 }}>
                🤖 {agentLabel}
              </span>
            </div>
            <div style={{ fontSize:13.5, color:'rgba(255,255,255,.65)', lineHeight:1.7, maxWidth:560 }}>
              L'agent scrute Polymarket toutes les <strong style={{ color:'rgba(255,255,255,.9)' }}>{bot.id === 'chengdu' ? '15' : '30'} minutes</strong> et tracke{' '}
              {bot.id === 'chengdu'
                ? <><strong style={{ color:'rgba(255,255,255,.9)' }}>la température max à Chengdu</strong></>
                : <>tous les paris <strong style={{ color:'rgba(255,255,255,.9)' }}>{bot.id === 'polycrypto' ? 'crypto' : 'météo'}</strong></>
              } dont la probabilité YES dépasse <strong style={{ color:'rgba(255,255,255,.9)' }}>80%</strong>.
              Analysé par <strong style={{ color:'rgba(255,255,255,.9)' }}>{agentLabel}</strong> à chaque rapport.
            </div>
          </div>

          {/* ── Taux global + stats ── */}
          {(() => {
            const stats = meteoStats;
            const taux  = stats?.taux_victoire_global ?? stats?.taux_victoire ?? null;
            const col   = taux >= 60 ? 'var(--green)' : taux >= 50 ? 'var(--orange)' : taux !== null ? 'var(--red)' : 'var(--text-3)';
            if (!stats && !meteoRapport) return null;
            return (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:10, marginBottom:'var(--gap)' }}>
                {/* Taux all-time depuis meteo_stats */}
                <div style={{ gridColumn:'1/-1', borderRadius:'var(--r-card)',
                  background: taux !== null ? `color-mix(in oklab,${col} 12%,var(--bg-elev))` : 'var(--bg-elev)',
                  border:`1.5px solid color-mix(in oklab,${col} 30%,transparent)`,
                  padding:'16px 22px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <div>
                    <div style={{ fontSize:11, fontWeight:700, color:'var(--text-3)', letterSpacing:'.06em', marginBottom:6 }}>
                      TAUX DE RÉUSSITE — TOUTES DONNÉES (SINCE DÉBUT)
                    </div>
                    <div style={{ fontSize:46, fontWeight:900, lineHeight:1, color: taux !== null ? col : 'var(--text-3)' }}>
                      {taux !== null ? `${taux}%` : '—'}
                    </div>
                    <div style={{ fontSize:12.5, color:'var(--text-3)', marginTop:6 }}>
                      {stats ? `${stats.total_gagnes ?? stats.gagnes ?? 0} gagnés · ${stats.total_perdus ?? stats.perdus ?? 0} perdus · ${stats.total_resolus ?? stats.resolus ?? 0} résolus depuis le début` : 'En attente de données…'}
                    </div>
                  </div>
                  <div style={{ fontSize:48, opacity:.15 }}>{taux >= 60 ? '✅' : taux >= 50 ? '⚠️' : taux !== null ? '❌' : '⏳'}</div>
                </div>
                {/* Stats du dernier rapport */}
                {meteoRapport && [
                  { label:'Trackés (actuel)', value: meteoRapport.trackes ?? 0, color:'var(--text)' },
                  { label:'En attente', value: meteoRapport.en_attente ?? 0, color:'var(--text-3)' },
                  { label:'✅ Gagnés', value: meteoRapport.gagnes ?? 0, color:'var(--green)' },
                  { label:'❌ Perdus', value: meteoRapport.perdus ?? 0, color:'var(--red)' },
                ].map((s,i) => (
                  <div key={i} style={{ borderRadius:'var(--r-card)', background:'var(--bg-elev)',
                    border:'1px solid var(--separator)', padding:'14px 16px', textAlign:'center' }}>
                    <div style={{ fontSize:28, fontWeight:800, color:s.color, lineHeight:1 }}>{s.value}</div>
                    <div style={{ fontSize:11.5, color:'var(--text-3)', marginTop:5, fontWeight:500 }}>{s.label}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* ── Pools en surveillance ── */}
          {meteoTracking.length > 0 && (
            <Card style={{ marginBottom:'var(--gap)', padding:0, overflow:'hidden' }}>
              <div style={{ padding:'13px 20px', borderBottom:'1px solid var(--separator)',
                display:'flex', justifyContent:'space-between', alignItems:'center',
                background:'var(--fill)' }}>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <span style={{ width:7, height:7, borderRadius:999, background:'var(--green)',
                    boxShadow:'0 0 0 3px color-mix(in oklab,var(--green) 25%,transparent)' }} />
                  <span style={{ fontSize:14, fontWeight:700 }}>Pools en surveillance</span>
                  <span style={{ fontSize:12, color:'var(--text-3)', fontWeight:500 }}>
                    {meteoTracking.length} pari{meteoTracking.length>1?'s':''}
                  </span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  {meteoRapport?.heure && (
                    <span style={{ fontSize:11, color:'var(--text-3)' }}>
                      Dernier agent : {meteoRapport.heure}
                    </span>
                  )}
                  <button onClick={refreshMeteo} className="tap"
                    style={{ border:'1px solid var(--separator)', background:'var(--bg-elev)',
                      borderRadius:'var(--r-sm)', padding:'4px 10px', fontSize:12,
                      fontWeight:600, cursor:'pointer', color:'var(--accent)' }}>
                    ↻
                  </button>
                </div>
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 120px 110px 130px',
                padding:'8px 20px', fontSize:10.5, fontWeight:700, color:'var(--text-3)',
                letterSpacing:'.07em', borderBottom:'1px solid var(--separator)', background:'var(--fill)' }}>
                <span>PARI MÉTÉO</span>
                <span style={{textAlign:'center'}}>INITIAL → ACTUEL</span>
                <span style={{textAlign:'center'}}>TRACKÉ LE</span>
                <span style={{textAlign:'center'}}>RÉSULTAT</span>
              </div>
              {meteoTracking.map((t,i) => {
                const termine = t.resultat && t.resultat.startsWith('TERMINÉ');
                const actuel  = t.yes_price_actuel ?? t.yes_price_au_track;
                const delta   = actuel - t.yes_price_au_track;
                const col     = actuel >= 90 ? 'var(--green)' : actuel >= 70 ? 'var(--orange)' : 'var(--text-2)';
                return (
                  <div key={i} style={{ display:'grid', gridTemplateColumns:'1fr 120px 110px 130px',
                    padding:'12px 20px', alignItems:'center',
                    borderBottom: i<meteoTracking.length-1 ? '1px solid var(--separator)':'none',
                    background: termine ? 'color-mix(in oklab,var(--accent) 4%,transparent)' : 'transparent' }}>
                    <div style={{ fontSize:13.5, color:'var(--text)', lineHeight:1.4, paddingRight:16 }}>{t.question}</div>
                    <div style={{ textAlign:'center' }}>
                      <span style={{ fontSize:11, color:'var(--text-3)' }}>{t.yes_price_au_track}%</span>
                      <span style={{ fontSize:11, color:'var(--text-3)', margin:'0 4px' }}>→</span>
                      <span style={{ fontSize:15, fontWeight:900, color:col }}>{actuel}%</span>
                      {delta !== 0 && (
                        <span style={{ fontSize:10, color: delta>0?'var(--green)':'var(--red)', marginLeft:4 }}>
                          {delta>0?'+':''}{delta.toFixed(1)}
                        </span>
                      )}
                    </div>
                    <div style={{ textAlign:'center', fontSize:11.5, color:'var(--text-3)' }}>{t.tracke_le || t.detecte_le}</div>
                    <div style={{ textAlign:'center' }}>
                      {t.resultat === 'GAGNANT' && <span style={{ fontSize:12, fontWeight:700, color:'var(--green)',
                        background:'color-mix(in oklab,var(--green) 15%,transparent)',
                        padding:'4px 10px', borderRadius:999 }}>✅ Gagnant</span>}
                      {t.resultat === 'PERDANT' && <span style={{ fontSize:12, fontWeight:700, color:'var(--red)',
                        background:'color-mix(in oklab,var(--red) 15%,transparent)',
                        padding:'4px 10px', borderRadius:999 }}>❌ Perdant</span>}
                      {t.resultat && t.resultat !== 'GAGNANT' && t.resultat !== 'PERDANT' && (
                        <span style={{ fontSize:11, fontWeight:600, color:'var(--text-3)',
                          background:'var(--fill)', padding:'4px 8px', borderRadius:999 }}>{t.resultat}</span>
                      )}
                      {!t.resultat && <span style={{ fontSize:12, color:'var(--text-3)',
                        background:'var(--fill)', padding:'4px 12px', borderRadius:999,
                        border:'1px solid var(--separator)' }}>⏳ En cours</span>}
                    </div>
                  </div>
                );
              })}
            </Card>
          )}

          {/* ── Historique des rapports toutes les 2h ── */}
          {meteoRapports.length > 0 && (
            <Card style={{ padding:0, overflow:'hidden' }}>
              <div style={{ padding:'13px 20px', background:'var(--fill)',
                borderBottom:'1px solid var(--separator)',
                display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <span style={{ fontSize:14, fontWeight:700 }}>📋 Historique des rapports</span>
                <span style={{ fontSize:12, color:'var(--text-3)', fontWeight:500 }}>
                  {meteoRapports.length} rapport{meteoRapports.length>1?'s':''} · toutes les {bot.id === 'chengdu' ? '15' : '30'} min
                </span>
              </div>
              {meteoRapports.map((r,i) => {
                const taux = r.taux_victoire;
                const col = taux>=60?'var(--green)':taux>=50?'var(--orange)':taux!==null?'var(--red)':'var(--text-3)';
                return (
                  <div key={i} style={{ borderBottom: i<meteoRapports.length-1?'1px solid var(--separator)':'none' }}>
                    {/* En-tête */}
                    <div style={{ padding:'14px 20px 10px', display:'flex',
                      justifyContent:'space-between', alignItems:'center' }}>
                      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                        <div style={{ fontSize:13.5, fontWeight:700 }}>🕐 {r.heure}</div>
                        {r.verdict && (
                          <span style={{ fontSize:11.5, fontWeight:600, padding:'2px 10px',
                            borderRadius:999, background:'var(--fill)',
                            color: r.verdict.includes('✅')?'var(--green)':r.verdict.includes('⚠️')?'var(--orange)':'var(--text-3)' }}>
                            {r.verdict}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize:24, fontWeight:900, color:col }}>
                        {taux!==null ? `${taux}%` : '—'}
                      </div>
                    </div>
                    {/* Stats compactes */}
                    <div style={{ display:'flex', gap:8, padding:'0 20px 12px' }}>
                      {[
                        {l:'Trackés', v:r.trackes, c:'var(--text-3)'},
                        {l:'✅ Gagnants', v:r.gagnes, c:'var(--green)'},
                        {l:'❌ Perdants', v:r.perdus, c:'var(--red)'},
                        {l:'ROI théorique', v: r.roi != null ? `${r.roi > 0 ? '+' : ''}${r.roi}%` : '—', c: r.roi > 0 ? 'var(--green)' : r.roi < 0 ? 'var(--red)' : 'var(--text-3)'},
                      ].map((s,j) => (
                        <div key={j} style={{ flex:1, textAlign:'center', padding:'8px 6px',
                          background:'var(--fill)', borderRadius:'var(--r-md)' }}>
                          <div style={{ fontSize:18, fontWeight:800, color:s.c }}>{s.v}</div>
                          <div style={{ fontSize:10.5, color:'var(--text-3)', marginTop:2 }}>{s.l}</div>
                        </div>
                      ))}
                    </div>
                    {/* Analyse IA */}
                    {r[agentAnalyseKey] && (
                      <div style={{ margin:'0 20px 10px', padding:'11px 14px',
                        borderRadius:'var(--r-md)', background:'var(--fill)',
                        fontSize:13, color:'var(--text-2)', lineHeight:1.65, whiteSpace:'pre-wrap' }}>
                        {r[agentAnalyseKey]}
                      </div>
                    )}
                    {/* Stratégie */}
                    {r.strategie_proposee && (
                      <div style={{ margin:'0 20px 14px', padding:'10px 14px',
                        borderRadius:'var(--r-md)',
                        background:'color-mix(in oklab,var(--accent) 8%,var(--bg-elev))',
                        border:'1.5px solid color-mix(in oklab,var(--accent) 25%,transparent)' }}>
                        <div style={{ fontSize:10.5, fontWeight:800, color:'var(--accent)',
                          letterSpacing:'.06em', marginBottom:5 }}>💡 STRATÉGIE SUIVANTE</div>
                        <div style={{ fontSize:13, color:'var(--text)', lineHeight:1.6, fontStyle:'italic' }}>
                          « {r.strategie_proposee} »
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </Card>
          )}

          {/* ── Résumés quotidiens à 17h ── */}
          {meteoResumes.length > 0 && (
            <Card style={{ marginTop:'var(--gap)', padding:0, overflow:'hidden' }}>
              <div style={{ padding:'13px 20px', background:'var(--fill)',
                borderBottom:'1px solid var(--separator)',
                display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <span style={{ fontSize:18 }}>📋</span>
                  <span style={{ fontSize:14, fontWeight:700 }}>Résumés quotidiens à 17h</span>
                </div>
                <span style={{ fontSize:12, color:'var(--text-3)', fontWeight:500 }}>
                  {meteoResumes.length} jour{meteoResumes.length>1?'s':''}
                </span>
              </div>
              {meteoResumes.map((r,i) => {
                const taux = r.taux_victoire;
                const col = taux>=60?'var(--green)':taux>=50?'var(--orange)':taux!==null?'var(--red)':'var(--text-3)';
                return (
                  <div key={i} style={{ borderBottom: i<meteoResumes.length-1?'1px solid var(--separator)':'none',
                    padding:'16px 20px' }}>
                    {/* En-tête date + taux */}
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                        <span style={{ fontSize:14, fontWeight:800, color:'var(--text)' }}>
                          📅 {r.date}
                        </span>
                        <span style={{ fontSize:11.5, color:'var(--text-3)',
                          background:'var(--fill)', padding:'2px 8px', borderRadius:999,
                          border:'1px solid var(--separator)' }}>
                          17h00
                        </span>
                      </div>
                      <div style={{ fontSize:28, fontWeight:900, color:col }}>
                        {taux!==null ? `${taux}%` : '—'}
                      </div>
                    </div>
                    {/* Stats du jour */}
                    <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8, marginBottom:12 }}>
                      {[
                        {l:'Trackés', v:r.trackes, c:'var(--text-3)'},
                        {l:'Résolus', v:r.resolus, c:'var(--text-2)'},
                        {l:'✅ Gagnés', v:r.gagnes, c:'var(--green)'},
                        {l:'❌ Perdus', v:r.perdus, c:'var(--red)'},
                      ].map((s,j) => (
                        <div key={j} style={{ textAlign:'center', padding:'8px 6px',
                          background:'var(--fill)', borderRadius:'var(--r-md)' }}>
                          <div style={{ fontSize:20, fontWeight:800, color:s.c, lineHeight:1 }}>{s.v}</div>
                          <div style={{ fontSize:10.5, color:'var(--text-3)', marginTop:4 }}>{s.l}</div>
                        </div>
                      ))}
                    </div>
                    {/* Analyse Mistral */}
                    {(r.analyse || r.analyse_text) && (
                      <div style={{ padding:'12px 14px', borderRadius:'var(--r-md)',
                        background:'color-mix(in oklab,var(--accent) 6%,var(--bg-elev))',
                        border:'1px solid color-mix(in oklab,var(--accent) 20%,transparent)' }}>
                        <div style={{ fontSize:10.5, fontWeight:800, color:'var(--accent)',
                          letterSpacing:'.07em', marginBottom:7 }}>🤖 ANALYSE MISTRAL</div>
                        <div style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7,
                          whiteSpace:'pre-wrap' }}>{r.analyse || r.analyse_text}</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </Card>
          )}

          {/* Empty state */}
          {meteoRapports.length === 0 && meteoTracking.length === 0 && meteoResumes.length === 0 && (
            <div style={{ textAlign:'center', padding:'56px 24px', color:'var(--text-3)',
              borderRadius:'var(--r-card)', border:'1.5px dashed var(--separator)' }}>
              <div style={{ fontSize:40, marginBottom:14 }}>🌦</div>
              <div style={{ fontSize:16, fontWeight:700, color:'var(--text-2)', marginBottom:8 }}>
                Premier rapport à 17h00
              </div>
              <div style={{ fontSize:13.5, lineHeight:1.7, maxWidth:360, margin:'0 auto' }}>
                L'agent tourne sur {bot.id === 'chengdu' ? 'Railway' : 'GitHub'} et scrappe Polymarket toutes les {bot.id === 'chengdu' ? '15' : '30'} min.
                Le premier rapport apparaîtra ici aujourd'hui à 17h.
              </div>
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

      {/* ── Gains horaires ── */}
      {pnlHoraire.length > 0 ? (
        <Card style={{ marginBottom: 'var(--gap)', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '13px 20px', background: 'var(--fill)',
            borderBottom: '1px solid var(--separator)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 700 }}>📈 Gains horaires</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                {pnlHoraire.length}h de données
              </span>
              <span style={{ fontSize: 14, fontWeight: 800,
                color: pnlHoraire[pnlHoraire.length-1]?.pnl_cumul >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {pnlHoraire[pnlHoraire.length-1]?.pnl_cumul >= 0 ? '+' : ''}
                {fmtUSD(pnlHoraire[pnlHoraire.length-1]?.pnl_cumul || 0, 2)} cumulé
              </span>
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <div style={{ display: 'grid',
              gridTemplateColumns: `repeat(${pnlHoraire.length}, minmax(72px, 1fr))`,
              gap: 0, minWidth: Math.max(pnlHoraire.length * 72, 300) }}>
              {pnlHoraire.map((h, i) => {
                const pos = h.pnl >= 0;
                const maxAbs = Math.max(...pnlHoraire.map(x => Math.abs(x.pnl)), 0.01);
                const barH = Math.max(Math.round((Math.abs(h.pnl) / maxAbs) * 60), 4);
                return (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column',
                    alignItems: 'center', padding: '12px 4px 10px',
                    borderRight: i < pnlHoraire.length-1 ? '1px solid var(--separator)' : 'none',
                    background: i === pnlHoraire.length-1 ? 'color-mix(in oklab,var(--accent) 5%,transparent)' : 'transparent' }}>
                    {/* Barre */}
                    <div style={{ height: 60, display: 'flex', alignItems: 'flex-end', marginBottom: 6 }}>
                      <div style={{ width: 28, height: barH,
                        borderRadius: 4,
                        background: pos ? 'var(--green)' : 'var(--red)',
                        opacity: i === pnlHoraire.length-1 ? 1 : 0.6 }} />
                    </div>
                    {/* Valeur */}
                    <div className="num" style={{ fontSize: 11.5, fontWeight: 700,
                      color: pos ? 'var(--green)' : 'var(--red)' }}>
                      {pos ? '+' : ''}{h.pnl.toFixed(2)}
                    </div>
                    {/* Heure */}
                    <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 3 }}>{h.heure}</div>
                    {/* Trades */}
                    <div style={{ fontSize: 10, color: 'var(--text-3)' }}>
                      {h.trades} trade{h.trades > 1 ? 's' : ''}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      ) : bot.status === 'running' ? (
        <Card style={{ marginBottom: 'var(--gap)', padding: '18px 20px',
          display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ fontSize: 22 }}>⏳</div>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 3 }}>En attente du premier trade</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)' }}>
              Les gains horaires s'afficheront ici dès que le bot passera son premier ordre.
            </div>
          </div>
        </Card>
      ) : null}

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
