// ============================================================
// page_stratege.jsx — Analyse Mistral cross-ville
// ============================================================
function StratègePage({ onBack }) {
  const { Card, Icon } = window;
  const SB_URL = 'https://obqkqhlqlowxrxbyvktl.supabase.co';
  const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728';

  const VILLES = [
    { id: 'chengdu',       label: 'Chengdu',       flag: '🇨🇳' },
    { id: 'seoul',         label: 'Séoul',         flag: '🇰🇷' },
    { id: 'hong_kong',     label: 'Hong Kong',     flag: '🇭🇰' },
    { id: 'nyc',           label: 'New York',      flag: '🇺🇸' },
    { id: 'london',        label: 'Londres',       flag: '🇬🇧' },
    { id: 'tokyo',         label: 'Tokyo',         flag: '🇯🇵' },
    { id: 'atlanta',       label: 'Atlanta',       flag: '🇺🇸' },
    { id: 'seattle',       label: 'Seattle',       flag: '🇺🇸' },
    { id: 'miami',         label: 'Miami',         flag: '🇺🇸' },
    { id: 'singapore',     label: 'Singapour',     flag: '🇸🇬' },
    { id: 'madrid',        label: 'Madrid',        flag: '🇪🇸' },
    { id: 'shanghai',      label: 'Shanghai',      flag: '🇨🇳' },
    { id: 'los_angeles',   label: 'Los Angeles',   flag: '🇺🇸' },
    { id: 'guangzhou',     label: 'Guangzhou',     flag: '🇨🇳' },
    { id: 'mexico_city',   label: 'Mexico City',   flag: '🇲🇽' },
    { id: 'amsterdam',     label: 'Amsterdam',     flag: '🇳🇱' },
    { id: 'paris',         label: 'Paris',         flag: '🇫🇷' },
    { id: 'toronto',       label: 'Toronto',       flag: '🇨🇦' },
    { id: 'chicago',       label: 'Chicago',       flag: '🇺🇸' },
    { id: 'denver',        label: 'Denver',        flag: '🇺🇸' },
    { id: 'houston',       label: 'Houston',       flag: '🇺🇸' },
    { id: 'taipei',        label: 'Taipei',        flag: '🇹🇼' },
    { id: 'beijing',       label: 'Beijing',       flag: '🇨🇳' },
    { id: 'san_francisco', label: 'San Francisco', flag: '🇺🇸' },
    { id: 'dallas',        label: 'Dallas',        flag: '🇺🇸' },
    { id: 'wellington',    label: 'Wellington',    flag: '🇳🇿' },
    { id: 'chongqing',     label: 'Chongqing',     flag: '🇨🇳' },
    { id: 'wuhan',         label: 'Wuhan',         flag: '🇨🇳' },
    { id: 'ankara',        label: 'Ankara',        flag: '🇹🇷' },
    { id: 'moscow',        label: 'Moscou',        flag: '🇷🇺' },
    { id: 'lucknow',       label: 'Lucknow',       flag: '🇮🇳' },
    { id: 'istanbul',      label: 'Istanbul',      flag: '🇹🇷' },
    { id: 'warsaw',        label: 'Varsovie',      flag: '🇵🇱' },
    { id: 'milan',         label: 'Milan',         flag: '🇮🇹' },
    { id: 'helsinki',      label: 'Helsinki',      flag: '🇫🇮' },
    { id: 'karachi',       label: 'Karachi',       flag: '🇵🇰' },
    { id: 'cape_town',     label: 'Cape Town',     flag: '🇿🇦' },
    { id: 'jeddah',        label: 'Jeddah',        flag: '🇸🇦' },
    { id: 'shenzhen',      label: 'Shenzhen',      flag: '🇨🇳' },
    { id: 'busan',         label: 'Busan',         flag: '🇰🇷' },
    { id: 'qingdao',       label: 'Qingdao',       flag: '🇨🇳' },
    { id: 'kuala_lumpur',  label: 'Kuala Lumpur',  flag: '🇲🇾' },
    { id: 'tel_aviv',      label: 'Tel Aviv',      flag: '🇮🇱' },
    { id: 'manila',        label: 'Manila',        flag: '🇵🇭' },
    { id: 'munich',        label: 'Munich',        flag: '🇩🇪' },
  ];

  const [analyses, setAnalyses]     = React.useState([]);
  const [loading, setLoading]       = React.useState(true);
  const [triggering, setTriggering] = React.useState(false);
  const [expanded, setExpanded]     = React.useState({});
  const [cityStats, setCityStats]   = React.useState({});
  const [activeSignals, setActiveSignals] = React.useState({});
  const [showAllCities, setShowAllCities] = React.useState(false);

  const fetchAnalyses = React.useCallback(() => {
    fetch(`${SB_URL}/rest/v1/strategie_analyses?order=created_at.desc&limit=30&select=id,date,nb_signaux,nb_villes,nb_resolus,nb_gagnes,taux_global,analyse_text,created_at`, {
      headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
    })
      .then(r => r.json())
      .then(data => { setAnalyses(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const fetchCityStats = React.useCallback(() => {
    Promise.all(VILLES.map(v =>
      fetch(`${SB_URL}/rest/v1/${v.id}_tracking?select=yes_price_au_signal,resultat&limit=500`, {
        headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
      }).then(r => r.json()).then(rows => {
        const data = Array.isArray(rows) ? rows : [];
        const resolved = data.filter(t => t.resultat);
        const won  = resolved.filter(t => t.resultat === 'GAGNANT').length;
        const lost = resolved.filter(t => t.resultat === 'PERDANT').length;
        const pending = data.length - resolved.length;
        const taux = resolved.length > 0 ? Math.round(won / resolved.length * 100) : null;
        return { id: v.id, total: data.length, won, lost, pending, taux };
      }).catch(() => ({ id: v.id, total: 0, won: 0, lost: 0, pending: 0, taux: null }))
    )).then(results => {
      const map = {};
      results.forEach(r => { map[r.id] = r; });
      setCityStats(map);
    });
  }, []);

  const fetchActiveSignals = React.useCallback(() => {
    Promise.all(VILLES.map(v =>
      fetch(`${SB_URL}/rest/v1/${v.id}_tracking?select=yes_price_au_signal&resultat=is.null&limit=10`, {
        headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
      }).then(r => r.json()).then(rows => ({
        id: v.id, count: Array.isArray(rows) ? rows.length : 0
      })).catch(() => ({ id: v.id, count: 0 }))
    )).then(results => {
      const map = {};
      results.forEach(r => { map[r.id] = r.count; });
      setActiveSignals(map);
    });
  }, []);

  React.useEffect(() => {
    fetchAnalyses();
    fetchCityStats();
    fetchActiveSignals();
    const id = setInterval(() => {
      fetchAnalyses();
      fetchCityStats();
      fetchActiveSignals();
    }, 2 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchAnalyses, fetchCityStats, fetchActiveSignals]);

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
    bilan:  { icon: '📊', color: '#3b82f6', bg: 'rgba(59,130,246,.08)' },
    reco:   { icon: '💡', color: '#f59e0b', bg: 'rgba(245,158,11,.08)' },
    route:  { icon: '🚀', color: '#10b981', bg: 'rgba(16,185,129,.08)' },
    risk:   { icon: '⚠️', color: '#ef4444', bg: 'rgba(239,68,68,.08)' },
    other:  { icon: '📋', color: 'var(--text-3)', bg: 'var(--fill)' },
  };

  const getSectionMeta = (title) => {
    const t = (title || '').toUpperCase();
    if (t.includes('BILAN') || t.includes('PERFORMANCE') || t.includes('RÉSULTAT')) return SECTION_META.bilan;
    if (t.includes('RECOMM') || t.includes('CONSEIL') || t.includes('ACTION') || t.includes('OPPORTUN')) return SECTION_META.reco;
    if (t.includes('FEUILLE') || t.includes('ROUTE') || t.includes('PRIORIT') || t.includes('STRATÉG')) return SECTION_META.route;
    if (t.includes('RISQUE') || t.includes('ATTENTION') || t.includes('ÉVITER')) return SECTION_META.risk;
    return SECTION_META.other;
  };

  // ─── totaux globaux ────────────────────────────────────────
  const allStats      = Object.values(cityStats);
  const totalSignaux  = allStats.reduce((s, c) => s + c.total, 0);
  const totalGagnes   = allStats.reduce((s, c) => s + c.won, 0);
  const totalPerdus   = allStats.reduce((s, c) => s + c.lost, 0);
  const totalPending  = allStats.reduce((s, c) => s + c.pending, 0);
  const totalResolved = totalGagnes + totalPerdus;
  const tauxGlobal    = totalResolved > 0 ? Math.round(totalGagnes / totalResolved * 100) : null;
  const totalActifs   = Object.values(activeSignals).reduce((s, c) => s + c, 0);

  const latest  = analyses[0];
  const history = analyses.slice(1);

  // Courbe progression
  const progression = [...analyses].reverse().filter(a => a.taux_global != null);

  // Villes triées : avec données en premier (par taux desc), puis sans
  const villesSorted = [...VILLES].sort((a, b) => {
    const sa = cityStats[a.id], sb = cityStats[b.id];
    const ta = sa?.taux ?? -1, tb = sb?.taux ?? -1;
    if (ta !== tb) return tb - ta;
    return (sb?.total ?? 0) - (sa?.total ?? 0);
  });
  const villesAvecData  = villesSorted.filter(v => (cityStats[v.id]?.total ?? 0) > 0);
  const villesSansData  = villesSorted.filter(v => (cityStats[v.id]?.total ?? 0) === 0);
  const villesDisplay   = showAllCities ? villesSorted : villesAvecData;

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>

      {/* ── Hero ── */}
      <div style={{
        borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)', overflow: 'hidden',
        background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
        padding: '24px 24px 20px', position: 'relative',
      }}>
        {/* Glow */}
        <div style={{
          position: 'absolute', top: -40, right: -40, width: 200, height: 200,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(139,92,246,.3) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <button onClick={onBack} className="tap" style={{
          border: 'none', background: 'rgba(255,255,255,.1)', borderRadius: 999,
          width: 32, height: 32, display: 'grid', placeItems: 'center',
          cursor: 'pointer', color: '#fff', marginBottom: 18,
        }}>
          <Icon name="chevron-left" size={17} stroke={2.4} />
        </button>

        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ fontSize: 28 }}>🧠</span>
              <div>
                <h1 style={{ margin: 0, fontSize: 22, fontWeight: 900, color: '#fff', letterSpacing: '-.02em' }}>
                  Mistral Stratège
                </h1>
                <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,.5)' }}>
                  Analyse IA cross-ville · Railway 24/7 · toutes les 15 min
                </p>
              </div>
            </div>

            {/* KPIs hero */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
              {tauxGlobal !== null && (
                <div style={{
                  background: tauxGlobal >= 70 ? 'rgba(52,199,89,.2)' : 'rgba(255,149,0,.2)',
                  border: `1px solid ${tauxGlobal >= 70 ? 'rgba(52,199,89,.4)' : 'rgba(255,149,0,.4)'}`,
                  borderRadius: 10, padding: '8px 14px', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 22, fontWeight: 900, color: tauxGlobal >= 70 ? '#34C759' : '#FF9500', lineHeight: 1 }}>
                    {tauxGlobal}%
                  </div>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,.5)', marginTop: 2 }}>Win rate global</div>
                </div>
              )}
              <div style={{ background: 'rgba(255,255,255,.08)', borderRadius: 10, padding: '8px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', lineHeight: 1 }}>{totalSignaux}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,.5)', marginTop: 2 }}>Signaux totaux</div>
              </div>
              {totalActifs > 0 && (
                <div style={{
                  background: 'rgba(255,69,58,.2)', border: '1px solid rgba(255,69,58,.4)',
                  borderRadius: 10, padding: '8px 14px', textAlign: 'center',
                  animation: 'pulse 2s infinite',
                }}>
                  <div style={{ fontSize: 22, fontWeight: 900, color: '#FF453A', lineHeight: 1 }}>{totalActifs}</div>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,.5)', marginTop: 2 }}>Signaux actifs</div>
                </div>
              )}
              <div style={{ background: 'rgba(255,255,255,.08)', borderRadius: 10, padding: '8px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', lineHeight: 1 }}>{VILLES.length}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,.5)', marginTop: 2 }}>Villes</div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
            <button onClick={triggerAnalyse} disabled={triggering} className="tap" style={{
              border: 'none',
              background: triggering ? 'rgba(139,92,246,.3)' : 'linear-gradient(135deg, #7c3aed, #a855f7)',
              color: '#fff', borderRadius: 10, padding: '10px 16px',
              fontSize: 13, fontWeight: 700, cursor: triggering ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap',
              boxShadow: triggering ? 'none' : '0 4px 14px rgba(139,92,246,.4)',
            }}>
              <span style={{ fontSize: 15 }}>{triggering ? '⏳' : '⚡'}</span>
              {triggering ? 'Analyse en cours…' : 'Analyser maintenant'}
            </button>
            <button onClick={() => { fetchAnalyses(); fetchCityStats(); fetchActiveSignals(); }} className="tap" style={{
              border: '1px solid rgba(255,255,255,.15)', background: 'rgba(255,255,255,.06)',
              color: 'rgba(255,255,255,.7)', borderRadius: 10, padding: '8px 14px',
              fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Icon name="refresh" size={13} stroke={2} />
              Rafraîchir
            </button>
            <div style={{
              background: 'rgba(52,199,89,.12)', border: '1px solid rgba(52,199,89,.3)',
              borderRadius: 10, padding: '7px 12px',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#34C759', boxShadow: '0 0 6px #34C759' }} />
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#34C759' }}>Railway actif</div>
                {latest && <div style={{ fontSize: 10, color: 'rgba(255,255,255,.4)' }}>
                  {latest.date}
                </div>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Progression Win Rate ── */}
      {progression.length >= 2 && (
        <div style={{
          borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)',
          background: 'var(--bg-elev)', border: '1px solid var(--separator)', padding: '16px 20px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 700 }}>📈 Progression du win rate</span>
            {(() => {
              const delta = (progression.at(-1).taux_global - progression[0].taux_global).toFixed(1);
              const up = delta >= 0;
              return (
                <span style={{ fontSize: 13, fontWeight: 700, color: up ? 'var(--green)' : 'var(--red)' }}>
                  {up ? '↗' : '↘'} {up ? '+' : ''}{delta}%
                </span>
              );
            })()}
          </div>
          {(() => {
            const n = progression.length;
            const tauxMax = Math.max(...progression.map(a => a.taux_global), 100);
            const range   = tauxMax - 0 || 1;
            const W = n * 40;
            const pts = progression.map((a, i) => ({
              x: n === 1 ? W / 2 : i * 40 + 20,
              y: 52 - ((a.taux_global) / range) * 46,
              taux: a.taux_global,
              up: !progression[i - 1] || a.taux_global >= progression[i - 1].taux_global,
            }));
            const lineStr = pts.map(p => `${p.x},${p.y}`).join(' ');
            const areaStr = `${pts[0].x},55 ${lineStr} ${pts.at(-1).x},55`;
            return (
              <div style={{ position: 'relative' }}>
                <svg width="100%" height="60" viewBox={`0 0 ${W} 60`} preserveAspectRatio="none" style={{ display: 'block', overflow: 'visible' }}>
                  <defs>
                    <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--green)" stopOpacity=".25" />
                      <stop offset="100%" stopColor="var(--green)" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <polygon points={areaStr} fill="url(#pg)" />
                  <polyline points={lineStr} fill="none" stroke="var(--green)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  {pts.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="4" fill={p.up ? 'var(--green)' : 'var(--red)'} />)}
                </svg>
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none' }}>
                  {pts.map((p, i) => (
                    <div key={i} style={{
                      position: 'absolute',
                      left: n === 1 ? '50%' : `${(i / (n - 1)) * 100}%`,
                      top: Math.max(0, p.y - 17) + 'px',
                      transform: 'translateX(-50%)',
                      fontSize: 10.5, fontWeight: 800,
                      color: p.up ? 'var(--green)' : 'var(--red)',
                    }}>{p.taux}%</div>
                  ))}
                </div>
              </div>
            );
          })()}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{progression[0]?.date?.slice(0, 10)}</span>
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{progression.at(-1)?.date?.slice(0, 10)}</span>
          </div>
        </div>
      )}

      {/* ── Dernière analyse Mistral ── */}
      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-3)', padding: 40, fontSize: 14 }}>Chargement…</div>
      ) : !latest ? (
        <div style={{
          borderRadius: 'var(--r-card)', padding: 32, textAlign: 'center',
          background: 'var(--bg-elev)', border: '1px solid var(--separator)', marginBottom: 'var(--gap)',
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🧠</div>
          <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 8 }}>Aucune analyse disponible</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.6, marginBottom: 20 }}>
            Clique <strong>⚡ Analyser maintenant</strong> en haut — résultat dans ~15 min.
          </div>
        </div>
      ) : (
        <>
          {/* Header analyse */}
          <div style={{
            borderRadius: 'var(--r-card) var(--r-card) 0 0',
            background: 'linear-gradient(135deg, rgba(139,92,246,.12), rgba(168,85,247,.06))',
            border: '1px solid rgba(139,92,246,.2)',
            borderBottom: 'none',
            padding: '14px 20px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16 }}>🧠</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--text)' }}>Dernière analyse Mistral</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{latest.date}</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {latest.nb_signaux != null && (
                <span style={{ fontSize: 11, background: 'rgba(139,92,246,.15)', color: '#a855f7',
                  padding: '3px 10px', borderRadius: 999, fontWeight: 700 }}>
                  {latest.nb_signaux} signaux
                </span>
              )}
              {latest.taux_global != null && (
                <span style={{
                  fontSize: 11, fontWeight: 800, padding: '3px 10px', borderRadius: 999,
                  background: latest.taux_global >= 70 ? 'rgba(52,199,89,.15)' : 'rgba(255,149,0,.15)',
                  color: latest.taux_global >= 70 ? 'var(--green)' : 'var(--orange)',
                }}>
                  {latest.taux_global}% win
                </span>
              )}
            </div>
          </div>

          {/* Sections analyse */}
          {parseSections(latest.analyse_text).map((s, i, arr) => {
            const meta = getSectionMeta(s.title);
            const isLast = i === arr.length - 1;
            return (
              <div key={i} style={{
                background: 'var(--bg-elev)',
                border: '1px solid rgba(139,92,246,.15)',
                borderTop: i === 0 ? '1px solid rgba(139,92,246,.15)' : '1px solid var(--separator)',
                borderRadius: isLast ? '0 0 var(--r-card) var(--r-card)' : 0,
                marginBottom: isLast ? 'var(--gap)' : 0,
                overflow: 'hidden',
              }}>
                {s.title && (
                  <div style={{
                    padding: '9px 18px',
                    background: meta.bg,
                    borderBottom: `1px solid color-mix(in oklab, ${meta.color} 15%, transparent)`,
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}>
                    <span style={{ fontSize: 15 }}>{meta.icon}</span>
                    <span style={{ fontSize: 11.5, fontWeight: 800, color: meta.color,
                      textTransform: 'uppercase', letterSpacing: '.07em' }}>
                      {s.title.replace(/^\d+\.\s*/, '')}
                    </span>
                  </div>
                )}
                <div style={{
                  padding: '14px 20px', fontSize: 13.5, color: 'var(--text)',
                  lineHeight: 1.8, whiteSpace: 'pre-wrap',
                }}>
                  {s.body.trim()}
                </div>
              </div>
            );
          })}

          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px',
            borderRadius: 'var(--r-md)', background: 'var(--fill)',
            fontSize: 11.5, color: 'var(--text-3)', marginBottom: 'var(--gap)',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--green)', flexShrink: 0 }} />
            Analyse auto quotidienne · <strong style={{ color: 'var(--text-2)' }}>⚡ Analyser maintenant</strong> → résultat dans ~15 min
          </div>
        </>
      )}

      {/* ── Performance villes ── */}
      <div style={{
        borderRadius: 'var(--r-card)', marginBottom: 'var(--gap)',
        background: 'var(--bg-elev)', border: '1px solid var(--separator)', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '13px 20px', background: 'var(--fill)',
          borderBottom: '1px solid var(--separator)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 15 }}>🌍</span>
            <span style={{ fontSize: 13.5, fontWeight: 700 }}>Performance des bots météo</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {totalActifs > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, color: '#FF453A',
                background: 'rgba(255,69,58,.12)', padding: '3px 8px', borderRadius: 999,
              }}>
                🔴 {totalActifs} actifs
              </span>
            )}
            {tauxGlobal !== null && (
              <span style={{
                fontSize: 14, fontWeight: 800,
                color: tauxGlobal >= 70 ? 'var(--green)' : tauxGlobal >= 50 ? 'var(--orange)' : 'var(--red)',
              }}>
                {tauxGlobal}% global
              </span>
            )}
          </div>
        </div>

        {/* Stats globales */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderBottom: '1px solid var(--separator)' }}>
          {[
            { label: 'Signaux', val: totalSignaux, color: 'var(--text)' },
            { label: 'Gagnés', val: totalGagnes, color: 'var(--green)' },
            { label: 'Perdus', val: totalPerdus, color: 'var(--red)' },
            { label: 'En cours', val: totalPending, color: 'var(--orange)' },
          ].map((s, i) => (
            <div key={i} style={{
              padding: '12px 8px', textAlign: 'center',
              borderRight: i < 3 ? '1px solid var(--separator)' : 'none',
            }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.val}</div>
              <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Grille villes — 2 colonnes */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
          {villesDisplay.map((v, i) => {
            const s     = cityStats[v.id];
            const taux  = s?.taux ?? null;
            const actif = (activeSignals[v.id] || 0) > 0;
            const color = taux === null ? 'var(--text-3)'
              : taux >= 70 ? 'var(--green)'
              : taux >= 50 ? 'var(--orange)'
              : 'var(--red)';
            const isRight   = i % 2 === 1;
            const isLastRow = i >= villesDisplay.length - (villesDisplay.length % 2 === 0 ? 2 : 1);

            return (
              <div key={v.id} style={{
                padding: '11px 14px',
                borderRight: !isRight ? '1px solid var(--separator)' : 'none',
                borderBottom: !isLastRow ? '1px solid var(--separator)' : 'none',
                display: 'flex', alignItems: 'center', gap: 10,
                background: actif ? 'rgba(255,69,58,.03)' : 'transparent',
              }}>
                <span style={{ fontSize: 18, flexShrink: 0 }}>{v.flag}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {v.label}
                    </span>
                    {actif && (
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: '#FF453A', boxShadow: '0 0 5px #FF453A',
                        flexShrink: 0,
                      }} />
                    )}
                  </div>
                  <div style={{ height: 4, borderRadius: 999, background: 'var(--fill)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${taux ?? 0}%`, borderRadius: 999,
                      background: color, transition: 'width .6s ease',
                    }} />
                  </div>
                </div>
                <div style={{ flexShrink: 0, width: 36, textAlign: 'right' }}>
                  {taux !== null ? (
                    <span style={{ fontSize: 13.5, fontWeight: 800, color }}>{taux}%</span>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--text-3)' }}>—</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Toggle afficher toutes les villes */}
        <button onClick={() => setShowAllCities(v => !v)} className="tap" style={{
          width: '100%', border: 'none', background: 'var(--fill)',
          borderTop: '1px solid var(--separator)',
          padding: '11px 20px', cursor: 'pointer',
          fontSize: 12, color: 'var(--text-3)', fontWeight: 600,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          <Icon name={showAllCities ? 'chevron-up' : 'chevron-down'} size={13} stroke={2.2} />
          {showAllCities
            ? 'Masquer les villes sans données'
            : `Afficher toutes les villes (${villesSansData.length} sans données)`
          }
        </button>
      </div>

      {/* ── Historique analyses ── */}
      {history.length > 0 && (
        <div style={{
          borderRadius: 'var(--r-card)', overflow: 'hidden',
          background: 'var(--bg-elev)', border: '1px solid var(--separator)',
          marginBottom: 'var(--gap)',
        }}>
          <div style={{
            padding: '13px 20px', background: 'var(--fill)',
            borderBottom: '1px solid var(--separator)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 13.5, fontWeight: 700 }}>📅 Analyses précédentes</span>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{history.length} entrées</span>
          </div>
          {history.map((a, i) => (
            <div key={a.id} style={{ borderBottom: i < history.length - 1 ? '1px solid var(--separator)' : 'none' }}>
              <button onClick={() => setExpanded(e => ({ ...e, [a.id]: !e[a.id] }))}
                className="tap" style={{
                  width: '100%', border: 'none', background: 'transparent',
                  cursor: 'pointer', padding: '11px 18px',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center', textAlign: 'left',
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{a.date}</span>
                  {a.nb_signaux != null && (
                    <span style={{ fontSize: 10.5, color: 'var(--text-3)', background: 'var(--fill)',
                      padding: '2px 7px', borderRadius: 999 }}>
                      {a.nb_signaux} signaux
                    </span>
                  )}
                  {a.taux_global != null && (() => {
                    const idx = history.indexOf(a);
                    const prev = history[idx + 1];
                    const up = !prev?.taux_global || a.taux_global >= prev.taux_global;
                    return (
                      <span style={{ fontSize: 11, fontWeight: 700, color: up ? 'var(--green)' : 'var(--red)' }}>
                        {up ? '↗' : '↘'} {a.taux_global}%
                      </span>
                    );
                  })()}
                </div>
                <Icon name={expanded[a.id] ? 'chevron-up' : 'chevron-down'} size={14} stroke={2.2}
                  style={{ color: 'var(--text-3)', flexShrink: 0 }} />
              </button>
              {expanded[a.id] && (
                <div style={{
                  padding: '14px 18px 18px', fontSize: 13, color: 'var(--text)',
                  lineHeight: 1.75, whiteSpace: 'pre-wrap',
                  borderTop: '1px solid var(--separator)',
                  background: 'color-mix(in oklab,var(--fill) 50%,transparent)',
                }}>
                  {a.analyse_text}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

window.StratègePage = StratègePage;
