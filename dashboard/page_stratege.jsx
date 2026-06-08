// ============================================================
// page_stratege.jsx — Analyse Mistral cross-ville
// ============================================================
function StratègePage({ onBack }) {
  const { Card, Button, Icon } = window;
  const SB_URL = 'https://obqkqhlqlowxrxbyvktl.supabase.co';
  const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728';

  const [analyses, setAnalyses] = React.useState([]);
  const [loading, setLoading]   = React.useState(true);
  const [triggering, setTriggering] = React.useState(false);
  const [expanded, setExpanded] = React.useState({});

  const fetchAnalyses = React.useCallback(() => {
    setLoading(true);
    fetch(`${SB_URL}/rest/v1/strategie_analyses?order=created_at.desc&limit=20`, {
      headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` }
    })
      .then(r => r.json())
      .then(data => { setAnalyses(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    fetchAnalyses();
    const id = setInterval(fetchAnalyses, 2 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchAnalyses]);

  const triggerAnalyse = () => {
    setTriggering(true);
    fetch(`${SB_URL}/rest/v1/strategie_config?id=eq.main`, {
      method: 'PATCH',
      headers: {
        apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`,
        'Content-Type': 'application/json', Prefer: 'return=minimal'
      },
      body: JSON.stringify({ trigger: true })
    })
      .then(() => {
        setTimeout(() => {
          setTriggering(false);
          fetchAnalyses();
        }, 3000);
      })
      .catch(() => setTriggering(false));
  };

  const latest = analyses[0];
  const history = analyses.slice(1);

  // Parse les sections de l'analyse (1. BILAN / 2. RECO / 3. FEUILLE)
  const parseSections = (text) => {
    if (!text) return [{ title: '', body: text }];
    const sections = [];
    const lines = text.split('\n');
    let current = null;
    for (const line of lines) {
      const match = line.match(/^#+\s*(.+)|^\d\.\s+\*\*(.+?)\*\*|^\*\*(\d\..+?)\*\*/);
      if (match) {
        if (current) sections.push(current);
        current = { title: (match[1] || match[2] || match[3] || '').replace(/\*/g, ''), body: '' };
      } else if (current) {
        current.body += (current.body ? '\n' : '') + line;
      } else {
        sections.push({ title: '', body: line });
      }
    }
    if (current) sections.push(current);
    return sections.filter(s => s.title || s.body.trim());
  };

  const sectionIcon = (title) => {
    const t = (title || '').toUpperCase();
    if (t.includes('BILAN') || t.includes('PERFORMANCE')) return '📊';
    if (t.includes('RECOMM') || t.includes('CONSEIL')) return '💡';
    if (t.includes('FEUILLE') || t.includes('ROUTE') || t.includes('ACTION')) return '🚀';
    return '📋';
  };

  return (
    <div style={{ maxWidth: 780, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)',
          borderRadius: 999, width: 34, height: 34, display: 'grid', placeItems: 'center',
          cursor: 'pointer', color: 'var(--text-2)', flexShrink: 0 }}>
          <Icon name="chevron-left" size={18} stroke={2.2} />
        </button>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: '-.02em' }}>
            🧠 Mistral Stratège
          </h1>
          <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 2 }}>
            Analyse cross-ville · Rapport de performance · Recommandations
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={fetchAnalyses} className="tap" style={{ border: 'none', background: 'var(--fill)',
            borderRadius: 999, width: 34, height: 34, display: 'grid', placeItems: 'center',
            cursor: 'pointer', color: 'var(--text-2)' }}>
            <Icon name="refresh" size={16} stroke={2} />
          </button>
          <button onClick={triggerAnalyse} disabled={triggering} className="tap" style={{
            border: 'none', cursor: triggering ? 'default' : 'pointer',
            background: triggering ? 'var(--fill)' : 'var(--accent)',
            color: triggering ? 'var(--text-3)' : '#fff',
            borderRadius: 'var(--r-md)', padding: '8px 16px',
            fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6,
            transition: 'background .2s' }}>
            <Icon name={triggering ? 'clock' : 'sparkles'} size={15} stroke={2} />
            {triggering ? 'En cours… (~15 min)' : 'Analyser maintenant'}
          </button>
        </div>
      </div>

      {/* Dernière analyse */}
      {loading ? (
        <Card style={{ padding: 32, textAlign: 'center', color: 'var(--text-3)' }}>
          Chargement…
        </Card>
      ) : !latest ? (
        <Card style={{ padding: 32, textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>Aucune analyse disponible</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 20 }}>
            La première analyse se génère automatiquement à 18h,<br/>ou clique "Analyser maintenant" (résultat dans ~15 min).
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-3)', background: 'var(--fill)',
            borderRadius: 'var(--r-md)', padding: '10px 16px', display: 'inline-block' }}>
            ⚠️ Assure-toi que <strong>MISTRAL_API_KEY</strong> est configurée dans Railway
          </div>
        </Card>
      ) : (
        <>
          {/* Carte analyse principale */}
          <Card style={{ marginBottom: 'var(--gap)', padding: 0, overflow: 'hidden',
            border: '1px solid color-mix(in oklab,var(--accent) 25%,var(--separator))' }}>
            <div style={{ padding: '14px 20px', background: 'color-mix(in oklab,var(--accent) 8%,var(--bg-elev))',
              borderBottom: '1px solid var(--separator)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 16 }}>🧠</span>
                <span style={{ fontSize: 14, fontWeight: 700 }}>Dernière analyse</span>
                <span style={{ fontSize: 11.5, color: 'var(--text-3)' }}>· {latest.date}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--text-3)',
                  background: 'var(--fill)', padding: '3px 8px', borderRadius: 999 }}>
                  {latest.nb_signaux} signaux
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-3)',
                  background: 'var(--fill)', padding: '3px 8px', borderRadius: 999 }}>
                  {latest.nb_villes} villes
                </span>
              </div>
            </div>
            {parseSections(latest.analyse_text).map((s, i) => (
              <div key={i} style={{ padding: '16px 20px',
                borderBottom: i < parseSections(latest.analyse_text).length - 1 ? '1px solid var(--separator)' : 'none' }}>
                {s.title && (
                  <div style={{ fontSize: 12.5, fontWeight: 800, color: 'var(--accent)',
                    textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 8, display: 'flex', gap: 6 }}>
                    <span>{sectionIcon(s.title)}</span>
                    <span>{s.title}</span>
                  </div>
                )}
                <div style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.65,
                  whiteSpace: 'pre-wrap' }}>
                  {s.body.trim()}
                </div>
              </div>
            ))}
          </Card>

          {/* Historique analyses */}
          {history.length > 0 && (
            <Card style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '13px 20px', background: 'var(--fill)',
                borderBottom: '1px solid var(--separator)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 700 }}>📅 Historique analyses</span>
                <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{history.length} précédentes</span>
              </div>
              {history.map((a, i) => (
                <div key={a.id} style={{ borderBottom: i < history.length - 1 ? '1px solid var(--separator)' : 'none' }}>
                  <button onClick={() => setExpanded(e => ({ ...e, [a.id]: !e[a.id] }))}
                    className="tap" style={{ width: '100%', border: 'none', background: 'transparent',
                      cursor: 'pointer', padding: '12px 20px', display: 'flex',
                      justifyContent: 'space-between', alignItems: 'center', textAlign: 'left' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text)' }}>{a.date}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-3)',
                        background: 'var(--fill)', padding: '2px 7px', borderRadius: 999 }}>
                        {a.nb_signaux} signaux · {a.nb_villes} villes
                      </span>
                    </div>
                    <Icon name={expanded[a.id] ? 'chevron-up' : 'chevron-down'} size={14} stroke={2}
                      style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                  </button>
                  {expanded[a.id] && (
                    <div style={{ padding: '0 20px 16px', fontSize: 13, color: 'var(--text)',
                      lineHeight: 1.65, whiteSpace: 'pre-wrap', borderTop: '1px solid var(--separator)',
                      paddingTop: 14, background: 'color-mix(in oklab,var(--fill) 40%,transparent)' }}>
                      {a.analyse_text}
                    </div>
                  )}
                </div>
              ))}
            </Card>
          )}
        </>
      )}

      {/* Info Railway */}
      <div style={{ marginTop: 'var(--gap)', padding: '12px 16px', borderRadius: 'var(--r-md)',
        background: 'var(--fill)', fontSize: 12, color: 'var(--text-3)',
        display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--green)', flexShrink: 0 }} />
        Analyse auto quotidienne à <strong style={{ color: 'var(--text-2)' }}>18h Paris</strong> · Bot Railway actif · "Analyser maintenant" : résultat dans ~15 min
      </div>
    </div>
  );
}

window.StratègePage = StratègePage;
