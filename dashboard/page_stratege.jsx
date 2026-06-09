// ============================================================
// page_stratege.jsx — Analyse Mistral cross-ville
// ============================================================
function StratègePage({ onBack }) {
  const { Card, Icon } = window;
  const SB_URL = 'https://obqkqhlqlowxrxbyvktl.supabase.co';
  const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728';

  const VILLES = [
    { id: 'chengdu',   label: 'Chengdu',    glyph: '🌡️', flag: '🇨🇳' },
    { id: 'seoul',     label: 'Séoul',      glyph: '🏙️', flag: '🇰🇷' },
    { id: 'hong_kong', label: 'Hong Kong',  glyph: '🌆', flag: '🇭🇰' },
    { id: 'nyc',       label: 'New-York',   glyph: '🗽', flag: '🇺🇸' },
    { id: 'london',    label: 'Londres',    glyph: '🎡', flag: '🇬🇧' },
    { id: 'tokyo',     label: 'Tokyo',      glyph: '🗼', flag: '🇯🇵' },
    { id: 'atlanta',   label: 'Atlanta',    glyph: '🍑', flag: '🇺🇸' },
    { id: 'seattle',   label: 'Seattle',    glyph: '🌲', flag: '🇺🇸' },
    { id: 'miami',     label: 'Miami',      glyph: '🌴', flag: '🇺🇸' },
    { id: 'singapore', label: 'Singapour',  glyph: '🦁', flag: '🇸🇬' },
    { id: 'madrid',      label: 'Madrid',      glyph: '🐂', flag: '🇪🇸' },
    { id: 'shanghai',    label: 'Shanghai',    glyph: '🏮', flag: '🇨🇳' },
    { id: 'los_angeles', label: 'Los Angeles', glyph: '🎬', flag: '🇺🇸' },
  ];

  const [analyses, setAnalyses]     = React.useState([]);
  const [loading, setLoading]       = React.useState(true);
  const [triggering, setTriggering] = React.useState(false);
  const [expanded, setExpanded]     = React.useState({});
  const [cityStats, setCityStats]   = React.useState({});

  // ─── fetch analyses Mistral ───────────────────────────────
  const fetchAnalyses = React.useCallback(() => {
    fetch(`${SB_URL}/rest/v1/strategie_analyses?order=created_at.desc&limit=30&select=id,date,nb_signaux,nb_villes,nb_resolus,nb_gagnes,taux_global,analyse_text,created_at`, {
      headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
    })
      .then(r => r.json())
      .then(data => { setAnalyses(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // ─── fetch stats par ville ────────────────────────────────
  const fetchCityStats = React.useCallback(() => {
    Promise.all(VILLES.map(v =>
      fetch(`${SB_URL}/rest/v1/${v.id}_tracking?select=yes_price_au_signal,yes_price_actuel,resultat&limit=500`, {
        headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
      }).then(r => r.json()).then(rows => {
        const data = Array.isArray(rows) ? rows : [];
        const resolved = data.filter(t => t.resultat);
        const won = resolved.filter(t => t.resultat === 'GAGNANT').length;
        const total = data.length;
        const taux = resolved.length > 0 ? Math.round(won / resolved.length * 100) : null;
        return { id: v.id, total, won, lost: resolved.filter(t => t.resultat === 'PERDANT').length,
          pending: total - resolved.length, taux };
      }).catch(() => ({ id: v.id, total: 0, won: 0, lost: 0, pending: 0, taux: null }))
    )).then(results => {
      const map = {};
      results.forEach(r => { map[r.id] = r; });
      setCityStats(map);
    });
  }, []);

  React.useEffect(() => {
    fetchAnalyses();
    fetchCityStats();
    const id = setInterval(() => { fetchAnalyses(); fetchCityStats(); }, 2 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchAnalyses, fetchCityStats]);

  const triggerAnalyse = () => {
    setTriggering(true);
    fetch(`${SB_URL}/rest/v1/strategie_config?id=eq.main`, {
      method: 'PATCH',
      headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`,
        'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify({ trigger: true })
    }).then(() => setTimeout(() => { setTriggering(false); fetchAnalyses(); }, 3000))
      .catch(() => setTriggering(false));
  };

  // ─── parsing sections Mistral ─────────────────────────────
  const parseSections = (text) => {
    if (!text) return [];
    const sections = [];
    let current = null;
    for (const line of text.split('\n')) {
      const m = line.match(/^#{1,3}\s+(.+)|^\*\*(\d+\..+?)\*\*\s*$|^(\d+)\.\s+\*\*(.+?)\*\*/);
      if (m) {
        if (current) sections.push(current);
        const title = (m[1] || m[2] || m[4] || '').replace(/\*\*/g, '').trim();
        current = { title, body: '' };
      } else if (current) {
        current.body += (current.body ? '\n' : '') + line;
      } else {
        if (!current) current = { title: '', body: '' };
        current.body += (current.body ? '\n' : '') + line;
      }
    }
    if (current && (current.title || current.body.trim())) sections.push(current);
    return sections;
  };

  const SECTION_META = {
    bilan:  { icon: '📊', color: '#3b82f6', bg: 'color-mix(in oklab,#3b82f6 10%,transparent)' },
    reco:   { icon: '💡', color: '#f59e0b', bg: 'color-mix(in oklab,#f59e0b 10%,transparent)' },
    route:  { icon: '🚀', color: '#10b981', bg: 'color-mix(in oklab,#10b981 10%,transparent)' },
    other:  { icon: '📋', color: 'var(--text-3)', bg: 'var(--fill)' },
  };

  const getSectionMeta = (title) => {
    const t = (title || '').toUpperCase();
    if (t.includes('BILAN') || t.includes('PERFORMANCE')) return SECTION_META.bilan;
    if (t.includes('RECOMM') || t.includes('CONSEIL') || t.includes('ACTION')) return SECTION_META.reco;
    if (t.includes('FEUILLE') || t.includes('ROUTE') || t.includes('PRIORIT')) return SECTION_META.route;
    return SECTION_META.other;
  };

  // ─── totaux globaux ────────────────────────────────────────
  const allStats = Object.values(cityStats);
  const totalSignaux  = allStats.reduce((s, c) => s + c.total, 0);
  const totalGagnes   = allStats.reduce((s, c) => s + c.won, 0);
  const totalPerdus   = allStats.reduce((s, c) => s + c.lost, 0);
  const totalPending  = allStats.reduce((s, c) => s + c.pending, 0);
  const totalResolved = totalGagnes + totalPerdus;
  const tauxGlobal    = totalResolved > 0 ? Math.round(totalGagnes / totalResolved * 100) : null;

  const latest  = analyses[0];
  const history = analyses.slice(1);

  // Courbe de progression du taux de victoire (chronologique)
  const progression = [...analyses].reverse().filter(a => a.taux_global != null);
  const tauxMax = progression.length ? Math.max(...progression.map(a => a.taux_global), 100) : 100;
  const tauxMin = 0;

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>

      {/* ── Hero header ── */}
      <div style={{ borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)', overflow: 'hidden',
        background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4c1d95 100%)',
        padding: '28px 28px 24px', position: 'relative' }}>
        <button onClick={onBack} className="tap" style={{ border: 'none', background: 'rgba(255,255,255,.12)',
          borderRadius: 999, width: 32, height: 32, display: 'grid', placeItems: 'center',
          cursor: 'pointer', color: '#fff', marginBottom: 20, backdropFilter: 'blur(8px)' }}>
          <Icon name="chevron-left" size={17} stroke={2.4} />
        </button>

        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 32 }}>🧠</span>
              <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900, color: '#fff',
                letterSpacing: '-.02em' }}>Mistral Stratège</h1>
            </div>
            <p style={{ margin: 0, fontSize: 13.5, color: 'rgba(255,255,255,.65)', lineHeight: 1.5 }}>
              Analyse IA cross-ville · Bilan de performance · Recommandations<br/>
              Objectif : construire un bot météo rentable sur Polymarket
            </p>
            {latest && (
              <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
                {[
                  { label: 'Dernière analyse', val: latest.date },
                  { label: 'Signaux analysés', val: latest.nb_signaux },
                  { label: 'Villes', val: latest.nb_villes },
                ].map((s, i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,.12)', borderRadius: 8,
                    padding: '5px 12px', backdropFilter: 'blur(8px)' }}>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,.55)', textTransform: 'uppercase',
                      letterSpacing: '.05em' }}>{s.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{s.val}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
            <button onClick={triggerAnalyse} disabled={triggering} className="tap" style={{
              border: 'none', cursor: triggering ? 'default' : 'pointer',
              background: triggering ? 'rgba(255,255,255,.1)' : 'rgba(255,255,255,.95)',
              color: triggering ? 'rgba(255,255,255,.5)' : '#312e81',
              borderRadius: 'var(--r-md)', padding: '9px 16px',
              fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all .2s', whiteSpace: 'nowrap' }}>
              <Icon name={triggering ? 'clock' : 'sparkles'} size={15} stroke={2} />
              {triggering ? 'En cours… (~15 min)' : 'Analyser maintenant'}
            </button>
            <button onClick={() => { fetchAnalyses(); fetchCityStats(); }} className="tap" style={{
              border: '1px solid rgba(255,255,255,.2)', background: 'transparent',
              color: 'rgba(255,255,255,.7)', borderRadius: 'var(--r-md)', padding: '8px 16px',
              fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="refresh" size={14} stroke={2} />
              Rafraîchir
            </button>
          </div>
        </div>
      </div>

      {/* ── Courbe de progression ── */}
      {progression.length >= 2 && (
        <div style={{ borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)',
          background: 'var(--bg-elev)', border: '1px solid var(--separator)', padding: '16px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 700 }}>📈 Progression du taux de victoire</span>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{progression.length} analyses</span>
          </div>
          {/* Mini sparkline SVG — labels en HTML pour éviter la distorsion */}
          {(() => {
            const n = progression.length;
            const range = tauxMax - tauxMin || 1;
            const pts = progression.map((a, i) => {
              const x = n === 1 ? 20 : i * 40 + 20;
              const y = 55 - ((a.taux_global - tauxMin) / range) * 50;
              const prev = progression[i - 1];
              return { x, y, taux: a.taux_global, up: !prev || a.taux_global >= prev.taux_global };
            });
            const lineStr = pts.map(p => `${p.x},${p.y}`).join(' ');
            const areaStr = `${pts[0].x},55 ${lineStr} ${pts[pts.length - 1].x},55`;
            return (
              <div style={{ position: 'relative' }}>
                <svg width="100%" height="60" viewBox={`0 0 ${n * 40} 60`} preserveAspectRatio="none"
                  style={{ display: 'block', overflow: 'visible' }}>
                  <defs>
                    <linearGradient id="prog-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--green)" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="var(--green)" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <polyline points={lineStr} fill="none" stroke="var(--green)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  <polygon points={areaStr} fill="url(#prog-grad)" />
                  {pts.map((p, i) => (
                    <circle key={i} cx={p.x} cy={p.y} r="4" fill={p.up ? 'var(--green)' : 'var(--red)'} />
                  ))}
                </svg>
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none' }}>
                  {pts.map((p, i) => (
                    <div key={i} style={{
                      position: 'absolute',
                      left: n === 1 ? '50%' : `${(i / (n - 1)) * 100}%`,
                      top: Math.max(0, p.y - 18) + 'px',
                      transform: 'translateX(-50%)',
                      fontSize: 9, fontWeight: 700,
                      color: p.up ? 'var(--green)' : 'var(--red)',
                      whiteSpace: 'nowrap',
                    }}>
                      {p.taux}%
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
          {/* Dates en bas */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{progression[0]?.date?.slice(0,10)}</span>
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{progression.at(-1)?.date?.slice(0,10)}</span>
          </div>
          {/* Delta */}
          {progression.length >= 2 && (() => {
            const delta = (progression.at(-1).taux_global - progression[0].taux_global).toFixed(1);
            const up = delta >= 0;
            return (
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 12, color: up ? 'var(--green)' : 'var(--red)' }}>
                <span style={{ fontSize: 16 }}>{up ? '↗' : '↘'}</span>
                <strong>{up ? '+' : ''}{delta}%</strong>
                <span style={{ color: 'var(--text-3)' }}>depuis la 1ère analyse</span>
              </div>
            );
          })()}
        </div>
      )}

      {/* ── Tableau de bord des bots météo ── */}
      <div style={{ borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)',
        background: 'var(--bg-elev)', border: '1px solid var(--separator)', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '13px 20px', background: 'var(--fill)',
          borderBottom: '1px solid var(--separator)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16 }}>🌍</span>
            <span style={{ fontSize: 14, fontWeight: 700 }}>Performance des bots météo</span>
          </div>
          {tauxGlobal !== null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Global</span>
              <span style={{ fontSize: 15, fontWeight: 800,
                color: tauxGlobal >= 70 ? 'var(--green)' : tauxGlobal >= 50 ? 'var(--orange)' : 'var(--red)' }}>
                {tauxGlobal}%
              </span>
            </div>
          )}
        </div>

        {/* Résumé global */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          borderBottom: '1px solid var(--separator)' }}>
          {[
            { label: 'Signaux totaux', val: totalSignaux, color: 'var(--text)' },
            { label: 'Gagnés', val: totalGagnes, color: 'var(--green)' },
            { label: 'Perdus', val: totalPerdus, color: 'var(--red)' },
            { label: 'En attente', val: totalPending, color: 'var(--text-3)' },
          ].map((s, i) => (
            <div key={i} style={{ padding: '14px 16px', textAlign: 'center',
              borderRight: i < 3 ? '1px solid var(--separator)' : 'none' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.val}</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Détail par ville */}
        {VILLES.map((v, i) => {
          const s = cityStats[v.id];
          const taux = s?.taux;
          const tauxColor = taux == null ? 'var(--text-3)'
            : taux >= 70 ? 'var(--green)' : taux >= 50 ? 'var(--orange)' : 'var(--red)';
          const barWidth = taux ?? 0;
          return (
            <div key={v.id} style={{ padding: '13px 20px',
              borderBottom: i < VILLES.length - 1 ? '1px solid var(--separator)' : 'none',
              display: 'flex', alignItems: 'center', gap: 14 }}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>{v.glyph}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 600 }}>{v.flag} {v.label}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                    {s ? `${s.won}G / ${s.lost}P — ${s.total} signaux` : '—'}
                  </span>
                </div>
                {/* Barre de progression */}
                <div style={{ height: 6, borderRadius: 999, background: 'var(--fill)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${barWidth}%`, borderRadius: 999,
                    background: taux == null ? 'var(--fill)'
                      : taux >= 70 ? 'var(--green)' : taux >= 50 ? 'var(--orange)' : 'var(--red)',
                    transition: 'width .6s ease' }} />
                </div>
              </div>
              <div style={{ flexShrink: 0, width: 44, textAlign: 'right' }}>
                {taux !== null ? (
                  <span style={{ fontSize: 16, fontWeight: 800, color: tauxColor }}>{taux}%</span>
                ) : (
                  <span style={{ fontSize: 12, color: 'var(--text-3)' }}>—</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Analyse Mistral ── */}
      {loading ? (
        <Card style={{ padding: 40, textAlign: 'center', color: 'var(--text-3)', fontSize: 14 }}>
          Chargement…
        </Card>
      ) : !latest ? (
        <Card style={{ padding: 40, textAlign: 'center' }}>
          <div style={{ fontSize: 52, marginBottom: 14 }}>🧠</div>
          <div style={{ fontSize: 17, fontWeight: 800, marginBottom: 8 }}>Aucune analyse disponible</div>
          <div style={{ fontSize: 13.5, color: 'var(--text-3)', lineHeight: 1.6, marginBottom: 24 }}>
            La première analyse se génère automatiquement à <strong>18h</strong>,<br/>
            ou clique <strong>"Analyser maintenant"</strong> — résultat dans ~15 min.
          </div>
          <div style={{ fontSize: 12, color: 'var(--orange)', background: 'color-mix(in oklab,var(--orange) 10%,transparent)',
            borderRadius: 'var(--r-md)', padding: '10px 18px', display: 'inline-flex', gap: 7, alignItems: 'center' }}>
            <Icon name="bolt" size={14} style={{ color: 'var(--orange)' }} />
            Vérifie que <strong>MISTRAL_API_KEY</strong> est configurée dans Railway
          </div>
        </Card>
      ) : (
        <>
          {/* Sections de la dernière analyse */}
          {parseSections(latest.analyse_text).map((s, i) => {
            const meta = getSectionMeta(s.title);
            return (
              <div key={i} style={{ borderRadius: 'var(--r-card)', marginBottom: 12, overflow: 'hidden',
                border: `1px solid color-mix(in oklab,${meta.color} 20%,var(--separator))`,
                background: 'var(--bg-elev)' }}>
                {s.title && (
                  <div style={{ padding: '11px 18px', background: meta.bg,
                    borderBottom: `1px solid color-mix(in oklab,${meta.color} 15%,var(--separator))`,
                    display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }}>{meta.icon}</span>
                    <span style={{ fontSize: 12, fontWeight: 800, color: meta.color,
                      textTransform: 'uppercase', letterSpacing: '.06em' }}>
                      {s.title.replace(/^\d+\.\s*/, '')}
                    </span>
                  </div>
                )}
                <div style={{ padding: '16px 20px', fontSize: 14, color: 'var(--text)',
                  lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                  {s.body.trim()}
                </div>
              </div>
            );
          })}

          {/* Info auto */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
            borderRadius: 'var(--r-md)', background: 'var(--fill)', fontSize: 12,
            color: 'var(--text-3)', marginBottom: 'var(--gap)' }}>
            <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--green)', flexShrink: 0 }} />
            Analyse auto quotidienne à <strong style={{ color: 'var(--text-2)' }}>18h Paris</strong>
            &nbsp;· "Analyser maintenant" → résultat dans ~15 min (prochain cycle Railway)
          </div>

          {/* Historique */}
          {history.length > 0 && (
            <Card style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '13px 20px', background: 'var(--fill)',
                borderBottom: '1px solid var(--separator)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 700 }}>📅 Analyses précédentes</span>
                <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{history.length} entrées</span>
              </div>
              {history.map((a, i) => (
                <div key={a.id} style={{ borderBottom: i < history.length - 1 ? '1px solid var(--separator)' : 'none' }}>
                  <button onClick={() => setExpanded(e => ({ ...e, [a.id]: !e[a.id] }))}
                    className="tap" style={{ width: '100%', border: 'none', background: 'transparent',
                      cursor: 'pointer', padding: '12px 20px', display: 'flex',
                      justifyContent: 'space-between', alignItems: 'center', textAlign: 'left' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text)' }}>{a.date}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-3)', background: 'var(--fill)',
                        padding: '2px 8px', borderRadius: 999 }}>
                        {a.nb_signaux} signaux · {a.nb_villes} villes
                      </span>
                      {a.taux_global != null && (() => {
                        const idx = history.indexOf(a);
                        const prev = history[idx + 1];
                        const up = !prev?.taux_global || a.taux_global >= prev.taux_global;
                        return (
                          <span style={{ fontSize: 11, fontWeight: 700,
                            color: up ? 'var(--green)' : 'var(--red)' }}>
                            {up ? '↗' : '↘'} {a.taux_global}%
                          </span>
                        );
                      })()}
                    </div>
                    <Icon name={expanded[a.id] ? 'chevron-up' : 'chevron-down'} size={14} stroke={2.2}
                      style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                  </button>
                  {expanded[a.id] && (
                    <div style={{ padding: '14px 20px 18px', fontSize: 13.5, color: 'var(--text)',
                      lineHeight: 1.7, whiteSpace: 'pre-wrap',
                      borderTop: '1px solid var(--separator)',
                      background: 'color-mix(in oklab,var(--fill) 50%,transparent)' }}>
                      {a.analyse_text}
                    </div>
                  )}
                </div>
              ))}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

window.StratègePage = StratègePage;
