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

  const SB_URL = window.SB_URL;
  const SB_KEY = window.SB_KEY;
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  const sbFetch = (table, limit = 100) =>
    fetch(`${SB_URL}/rest/v1/${table}?order=id.desc&limit=${limit}`, {
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

  // bot_strategies n'accepte plus l'écriture anon (faille corrigée le 23/06 — le prompt
  // pilote le trading réel). L'écriture passe désormais par server.py (clé service, local uniquement).
  const saveBotStrategy = (data) => {
    if (!isLocal) return Promise.reject(new Error('Modification disponible uniquement en local (serveur bot/server.py requis).'));
    return fetch(`http://127.0.0.1:5050/api/bot_strategies/${bot.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json()).then(d => { if (d.error) throw new Error(d.error); return d; });
  };

  // ── P&L horaire ──
  const [pnlHoraire, setPnlHoraire] = React.useState([]);
  React.useEffect(() => {
    if (tab !== 'apercu' || !isLocal) return;
    const load = () => fetch('http://127.0.0.1:5050/api/pnl/hourly')
      .then(r => r.json()).then(d => { if (Array.isArray(d)) setPnlHoraire(d); }).catch(() => {});
    load();
    const id = setInterval(load, 60 * 60 * 1000);
    return () => clearInterval(id);
  }, [tab, bot.id, isLocal]);

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
    saveBotStrategy({
      prompt: stratPrompt,
      enabled: stratEnabled,
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

  const stratExamples = React.useMemo(() => {
    if (bot.id === 'polyedge') return [
      'Achète YES sur les marchés température (YES 0.76–0.87) où un bot d\'analyse a détecté un signal ≥ 75%. Favorise les villes Tier 1 (win rate > 65%) : Toronto, Miami, Houston, Singapour, Tokyo. Taille : 15% du solde, min $10. Max 4 positions simultanées.',
      'Signal fort (ville Tier 1 + win rate > 65% + analyse Mistral positive + YES 0.76–0.84) → 20% du solde. Signal exceptionnel (convergence bots + Mistral sur même ville) → 25% du solde. Jamais si YES ≥ 0.95 ou < 0.76.',
      'Si aucun signal qualifié ce cycle → retourner []. Mieux vaut attendre que forcer un trade douteux. Volume minimum sur le marché : 1 000 USDC. Max 55% du solde total engagé simultanément.',
    ];
    if (bot.id === 'polyedge2') return [
      'Stratégie à définir par l\'utilisateur.',
    ];
    return [
      'Achète YES quand la probabilité est < 40% et que le volume dépasse 10 000 USDC.',
      'Mise sur NO pour les marchés électoraux quand le favori dépasse 70%.',
      'Arbitrage : achète le côté sous-évalué quand YES + NO ≠ 1.00 avec un écart > 3%.',
    ];
  }, [bot.id]);

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
          options={[{ value: 'apercu', label: 'Aperçu' }, { value: 'strategie', label: 'Stratégie' }]} />
      </div>

      {/* ── onglet Stratégie ── */}
      {tab === 'strategie' && (
        <div style={{ maxWidth: 680 }}>

          {/* ── Schéma de réflexion ProfitWeather V2.0 ── */}
          {bot.id === 'polyedge2' && (() => {
            const steps = [
              { icon:'📋', title:'Charge la stratégie', desc:'Supabase → bot_strategies (polyedge2)', sub:'Prompt + historique des versions auto-améliorées', color:'#6366f1' },
              { icon:'🌦️', title:'Scrape Polymarket', desc:'45 villes · marchés J+0 et J+1 · fourchettes température', sub:'Filtre : NO price entre 60 et 99 cents', color:'#0ea5e9' },
              { icon:'🌤️', title:'Enrichissement météo', desc:'Open-Meteo · ECMWF ensemble 51 membres · 4 modèles', sub:'band_prob = % des modèles dans la fourchette exacte ← clé V2', color:'#a855f7' },
              { icon:'🤖', title:'Claude Haiku décide', desc:'Identifie les cas où temp prévue est clairement hors fourchette → JSON', sub:'NO 70–95 cents · fourchette ECMWF < 30% · villes US préférées', color:'#f59e0b', highlight:true },
              { icon:'🛡️', title:'Filtres hard-coded', desc:'NO 0.70–0.95 · Min $20 · Max $1 400 · double vérification CLOB', sub:'Ces règles s\'appliquent après Claude — il ne peut pas les contourner', color:'#ef4444' },
              { icon:'✅', title:'Ordre NO exécuté', desc:'polymarket-client · Polygon blockchain · wallet Safe', sub:'Stop-loss -20% automatique · Take-profit à 99% NO', color:'#22c55e' },
            ];
            return (
              <div style={{ marginBottom:'var(--gap)' }}>
                <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em', marginBottom:14, textTransform:'uppercase' }}>
                  Processus de décision V2 — cycle toutes les 5 min
                </div>
                <div style={{ display:'flex', flexDirection:'column' }}>
                  {steps.map((step, i) => (
                    <div key={i} style={{ display:'flex', gap:0 }}>
                      <div style={{ display:'flex', flexDirection:'column', alignItems:'center', width:44, flexShrink:0 }}>
                        <div style={{ width:34, height:34, borderRadius:'50%', flexShrink:0, zIndex:1,
                          background:`color-mix(in oklab,${step.color} 15%,var(--bg-elev))`,
                          border:`2px solid color-mix(in oklab,${step.color} 60%,transparent)`,
                          display:'grid', placeItems:'center', fontSize:15 }}>
                          {step.icon}
                        </div>
                        {i < steps.length - 1 && (
                          <div style={{ width:2, flex:1, minHeight:14,
                            background:`linear-gradient(${step.color}80, ${steps[i+1].color}40)` }} />
                        )}
                      </div>
                      <div style={{ flex:1, paddingLeft:12, paddingBottom: i < steps.length - 1 ? 10 : 0 }}>
                        <div style={{ padding:'10px 14px', borderRadius:'var(--r-md)',
                          background: step.highlight
                            ? `color-mix(in oklab,${step.color} 10%,var(--bg-elev))`
                            : 'var(--bg-elev)',
                          border:`1px solid ${step.highlight
                            ? `color-mix(in oklab,${step.color} 50%,transparent)`
                            : 'var(--separator)'}` }}>
                          <div style={{ fontSize:13.5, fontWeight:700,
                            color: step.highlight ? step.color : 'var(--text)', marginBottom:2 }}>
                            {step.title}
                          </div>
                          <div style={{ fontSize:12.5, color:'var(--text-2)', marginBottom:3 }}>{step.desc}</div>
                          <div style={{ fontSize:11.5, color:'var(--text-3)', lineHeight:1.5 }}>{step.sub}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* ── Schéma de réflexion ProfitWeather ── */}
          {bot.id === 'polyedge' && (() => {
            const steps = [
              { icon:'📋', title:'Charge la stratégie', desc:'Supabase → bot_strategies', sub:'Prompt + historique des versions auto-améliorées', color:'#6366f1' },
              { icon:'🌦️', title:'Scrape Polymarket', desc:'45 villes · marchés J+0 et J+1 · max 60 marchés', sub:'Prix YES/NO, volume USDC, condition_id par ville', color:'#0ea5e9' },
              { icon:'🧠', title:'Contexte d\'analyse', desc:'Signaux actifs ≥ 75% · Stats par ville · Analyse Mistral', sub:'45 requêtes Supabase en parallèle (tracking + stats)', color:'#a855f7' },
              { icon:'🤖', title:'Claude Haiku décide', desc:'Croise signaux actifs + marchés disponibles → JSON', sub:'Zone idéale 0.76–0.87 · Villes Tier 1 · Win rate historique', color:'#f59e0b', highlight:true },
              { icon:'🛡️', title:'Filtres hard-coded', desc:'Prix 0.76–0.95 · Min $10 · Max 4 positions · 55% du solde', sub:'Ces règles s\'appliquent après Claude — il ne peut pas les contourner', color:'#ef4444' },
              { icon:'🌤️', title:'Veto météo Open-Meteo', desc:'Confirme la prévision de température avant d\'acheter', sub:'Annule l\'ordre si la météo contredit le signal Polymarket', color:'#10b981' },
              { icon:'✅', title:'Ordre exécuté', desc:'polymarket-client · Polygon blockchain · wallet Safe', sub:'Stop-loss -15% automatique · Take-profit à 99.9% YES', color:'#22c55e' },
            ];
            return (
              <div style={{ marginBottom:'var(--gap)' }}>
                <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.07em', marginBottom:14, textTransform:'uppercase' }}>
                  Processus de décision — cycle toutes les 5 min
                </div>
                <div style={{ display:'flex', flexDirection:'column' }}>
                  {steps.map((step, i) => (
                    <div key={i} style={{ display:'flex', gap:0 }}>
                      {/* Colonne icône + connecteur */}
                      <div style={{ display:'flex', flexDirection:'column', alignItems:'center', width:44, flexShrink:0 }}>
                        <div style={{ width:34, height:34, borderRadius:'50%', flexShrink:0, zIndex:1,
                          background:`color-mix(in oklab,${step.color} 15%,var(--bg-elev))`,
                          border:`2px solid color-mix(in oklab,${step.color} 60%,transparent)`,
                          display:'grid', placeItems:'center', fontSize:15 }}>
                          {step.icon}
                        </div>
                        {i < steps.length - 1 && (
                          <div style={{ width:2, flex:1, minHeight:14,
                            background:`linear-gradient(${step.color}80, ${steps[i+1].color}40)` }} />
                        )}
                      </div>
                      {/* Carte contenu */}
                      <div style={{ flex:1, paddingLeft:12, paddingBottom: i < steps.length - 1 ? 10 : 0 }}>
                        <div style={{ padding:'10px 14px', borderRadius:'var(--r-md)',
                          background: step.highlight
                            ? `color-mix(in oklab,${step.color} 10%,var(--bg-elev))`
                            : 'var(--bg-elev)',
                          border:`1px solid ${step.highlight
                            ? `color-mix(in oklab,${step.color} 50%,transparent)`
                            : 'var(--separator)'}` }}>
                          <div style={{ fontSize:13.5, fontWeight:700,
                            color: step.highlight ? step.color : 'var(--text)', marginBottom:2 }}>
                            {step.title}
                          </div>
                          <div style={{ fontSize:12.5, color:'var(--text-2)', marginBottom:3 }}>{step.desc}</div>
                          <div style={{ fontSize:11.5, color:'var(--text-3)', lineHeight:1.5 }}>{step.sub}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* ── Stratégie ProfitWeather : lecture seule ── */}
          {(bot.id === 'polyedge' || bot.id === 'polyedge2') ? (
            <>
              {/* Stratégie active */}
              <Card style={{ marginBottom: 'var(--gap)' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
                  <div style={{ fontSize:12.5, fontWeight:700, color:'var(--text-3)', letterSpacing:'.05em' }}>STRATÉGIE ACTIVE</div>
                  <div style={{ display:'flex', alignItems:'center', gap:6,
                    fontSize:11.5, fontWeight:600, color:'var(--green)',
                    background:'color-mix(in oklab,var(--green) 10%,transparent)',
                    padding:'3px 10px', borderRadius:999, border:'1px solid color-mix(in oklab,var(--green) 25%,transparent)' }}>
                    <span style={{ width:6, height:6, borderRadius:999, background:'var(--green)',
                      boxShadow:'0 0 0 2px color-mix(in oklab,var(--green) 30%,transparent)' }} />
                    🧠 Auto-améliorée par Claude toutes les 6h
                  </div>
                </div>
                {stratPrompt ? (
                  <div style={{ background:'var(--fill)', borderRadius:'var(--r-md)', padding:'14px 16px',
                    fontSize:13.5, color:'var(--text)', lineHeight:1.75, whiteSpace:'pre-wrap',
                    fontFamily:'inherit', border:'1px solid var(--separator)' }}>
                    {stratPrompt}
                  </div>
                ) : (
                  <div style={{ background:'var(--fill)', borderRadius:'var(--r-md)', padding:'18px 16px',
                    fontSize:13.5, color:'var(--text-3)', textAlign:'center', border:'1px solid var(--separator)' }}>
                    ⏳ Chargement de la stratégie depuis Supabase…
                  </div>
                )}
                {stratVersion > 1 && (
                  <div style={{ marginTop:12, padding:'10px 14px', borderRadius:'var(--r-md)',
                    background:'color-mix(in oklab,var(--green) 8%,transparent)',
                    border:'1px solid color-mix(in oklab,var(--green) 20%,transparent)' }}>
                    <div style={{ fontSize:12.5, fontWeight:700, color:'var(--green)', marginBottom:stratLastReason?4:0 }}>
                      Version {stratVersion}
                    </div>
                    {stratLastReason && (
                      <div style={{ fontSize:12.5, color:'var(--text-2)', lineHeight:1.5 }}>{stratLastReason}</div>
                    )}
                    {stratLastImproved && (
                      <div style={{ fontSize:11.5, color:'var(--text-3)', marginTop:3 }}>
                        Dernière mise à jour : {new Date(stratLastImproved).toLocaleString('fr-FR', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' })}
                      </div>
                    )}
                  </div>
                )}
              </Card>

              {/* Activer / désactiver */}
              <Card style={{ marginBottom: 'var(--gap)', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                <div>
                  <div style={{ fontSize:15, fontWeight:500 }}>Activer {bot.name}</div>
                  <div style={{ fontSize:12.5, color:'var(--text-3)', marginTop:2 }}>
                    Active ou met en pause le bot de trading
                  </div>
                </div>
                <Toggle on={stratEnabled} onChange={() => {
                  const next = !stratEnabled;
                  setStratEnabled(next);
                  saveBotStrategy({ enabled: next }).catch(() => setStratEnabled(!next));
                }} />
              </Card>
            </>
          ) : (
            <>
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
            </>
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
