// ============================================================
// page_analyse.jsx — Agent d'analyse Polymarket via Mistral AI
// ============================================================
function AnalysePage() {
  const { Card, SectionTitle, Button, Icon, Segmented, Stat } = window;

  const CATEGORIES = [
    { value: 'tout',      label: 'Tout' },
    { value: 'politique', label: 'Politique' },
    { value: 'crypto',    label: 'Crypto' },
    { value: 'finance',   label: 'Finance' },
    { value: 'sport',     label: 'Sport' },
  ];
  const VOLUMES = [
    { value: 1000,  label: '$1k+' },
    { value: 5000,  label: '$5k+' },
    { value: 10000, label: '$10k+' },
    { value: 50000, label: '$50k+' },
  ];
  const CONFIDENCE_COLOR = {
    'Élevée': 'var(--green)',
    'Moyenne': 'var(--orange)',
    'Faible': 'var(--text-3)',
  };

  const [category,   setCategory]   = React.useState('tout');
  const [minVolume,  setMinVolume]   = React.useState(5000);
  const [loading,    setLoading]     = React.useState(false);
  const [result,     setResult]      = React.useState(null);
  const [history,    setHistory]     = React.useState([]);
  const [error,      setError]       = React.useState(null);
  const [copied,     setCopied]      = React.useState(false);
  const [showHist,   setShowHist]    = React.useState(false);

  // Charge l'historique au montage
  React.useEffect(() => {
    fetch('http://localhost:5000/api/analyse/history')
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setHistory(data); })
      .catch(() => {});
  }, []);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch('http://localhost:5000/api/analyse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, min_volume: minVolume }),
      });
      const data = await r.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
      setHistory(h => [{ time: new Date().toISOString(), ...data }, ...h.slice(0, 19)]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const copyStrategy = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const fmtTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div>
      <SectionTitle title="Analyse Polymarket"
        sub="Agent Mistral — analyse les marchés et propose des stratégies" />

      {/* Filtres */}
      <Card style={{ marginBottom: 'var(--gap)', display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 7 }}>CATÉGORIE</div>
          <Segmented options={CATEGORIES} value={category} onChange={setCategory} size="sm" />
        </div>
        <div style={{ minWidth: 200 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 7 }}>VOLUME MINIMUM</div>
          <Segmented options={VOLUMES} value={minVolume} onChange={setMinVolume} size="sm" />
        </div>
        <div style={{ alignSelf: 'flex-end' }}>
          <Button variant="primary" icon={loading ? null : 'chart'} onClick={runAnalysis}>
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,.3)',
                  borderTopColor: '#fff', borderRadius: '50%',
                  animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
                Analyse en cours…
              </span>
            ) : 'Analyser maintenant'}
          </Button>
        </div>
      </Card>

      {/* Erreur */}
      {error && (
        <Card style={{ marginBottom: 'var(--gap)', background: 'color-mix(in oklab, var(--red) 10%, transparent)',
          border: '1px solid color-mix(in oklab, var(--red) 25%, transparent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--red)' }}>
            <Icon name="x" size={18} stroke={2.2} />
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Erreur d'analyse</div>
              <div style={{ fontSize: 13, marginTop: 2, opacity: 0.85 }}>{error}</div>
              {error.includes('MISTRAL_API_KEY') && (
                <div style={{ fontSize: 12, marginTop: 6, opacity: 0.7 }}>
                  → Ajoute <code style={{ background: 'var(--fill)', padding: '1px 6px', borderRadius: 4 }}>
                  MISTRAL_API_KEY=ta_cle</code> dans <code>bot/.env</code>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Résultats */}
      {result && (
        <div style={{ animation: 'slideIn .3s cubic-bezier(.22,.7,.3,1)' }}>
          {/* Résumé */}
          <Card style={{ marginBottom: 'var(--gap)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 8 }}>RÉSUMÉ DU MARCHÉ</div>
                <p style={{ margin: 0, fontSize: 15, lineHeight: 1.6, color: 'var(--text)' }}>{result.summary}</p>
              </div>
              <div style={{ display: 'flex', gap: 20, flexShrink: 0 }}>
                <Stat label="Marchés analysés" value={result.markets_analysed || 0} />
                <Stat label="Opportunités" value={result.opportunities?.length || 0} accent="var(--accent)" />
              </div>
            </div>
          </Card>

          {/* Opportunités */}
          {result.opportunities?.length > 0 && (
            <div style={{ marginBottom: 'var(--gap)' }}>
              <div style={{ fontSize: 13.5, fontWeight: 700, letterSpacing: '-.01em', marginBottom: 10 }}>
                Opportunités identifiées
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {result.opportunities.map((opp, i) => (
                  <Card key={i} style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                    {/* Badge recommandation */}
                    <div style={{ flexShrink: 0, minWidth: 48, textAlign: 'center', paddingTop: 2 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#fff', padding: '3px 10px',
                        borderRadius: 'var(--r-pill)', display: 'inline-block',
                        background: opp.recommendation === 'YES' ? 'var(--green)' : 'var(--red)' }}>
                        {opp.recommendation}
                      </div>
                      <div style={{ fontSize: 19, fontWeight: 700, marginTop: 6, color: opp.recommendation === 'YES' ? 'var(--green)' : 'var(--red)' }}>
                        {(opp.yes_price * 100).toFixed(0)}¢
                      </div>
                    </div>
                    {/* Contenu */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 650, marginBottom: 4,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {opp.title}
                      </div>
                      <p style={{ margin: '0 0 8px', fontSize: 13.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                        {opp.reasoning}
                      </p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 12, fontWeight: 600,
                          color: CONFIDENCE_COLOR[opp.confidence] || 'var(--text-3)',
                          display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ width: 6, height: 6, borderRadius: 999,
                            background: CONFIDENCE_COLOR[opp.confidence] || 'var(--text-3)' }} />
                          Confiance {opp.confidence}
                        </span>
                        <span style={{ fontSize: 11.5, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
                          {opp.condition_id?.slice(0, 14)}…
                        </span>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Suggestion de stratégie */}
          {result.strategy_suggestion && (
            <Card style={{ marginBottom: 'var(--gap)',
              background: 'color-mix(in oklab, var(--accent) 8%, var(--bg-elev))',
              border: '1px solid color-mix(in oklab, var(--accent) 20%, transparent)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>
                    💡 STRATÉGIE SUGGÉRÉE
                  </div>
                  <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.6, fontStyle: 'italic' }}>
                    "{result.strategy_suggestion}"
                  </p>
                </div>
                <button onClick={() => copyStrategy(result.strategy_suggestion)} className="tap"
                  style={{ border: 'none', cursor: 'pointer', flexShrink: 0,
                    background: copied ? 'var(--green)' : 'var(--accent)',
                    color: '#fff', borderRadius: 'var(--r-md)', padding: '8px 14px',
                    fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center',
                    gap: 6, transition: 'background .2s' }}>
                  <Icon name={copied ? 'check' : 'link'} size={15} stroke={2.2} />
                  {copied ? 'Copié !' : 'Copier'}
                </button>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Historique */}
      {history.length > 0 && (
        <div>
          <button onClick={() => setShowHist(!showHist)} className="tap"
            style={{ border: 'none', background: 'transparent', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
              fontSize: 14, fontWeight: 600, color: 'var(--text-2)', marginBottom: 10 }}>
            <Icon name={showHist ? 'chevdown' : 'chevron'} size={16} stroke={2} />
            Historique des analyses ({history.length})
          </button>
          {showHist && (
            <Card pad={false}>
              {history.map((h, i) => (
                <div key={i} style={{ padding: '12px var(--pad)',
                  borderBottom: i < history.length - 1 ? '1px solid var(--separator)' : 'none',
                  display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500,
                    flexShrink: 0, minWidth: 90 }}>{fmtTime(h.time)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      marginBottom: 3 }}>{h.summary || 'Analyse sans résumé'}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                      {h.opportunities?.length || 0} opportunité(s) · {h.category} · ${(h.min_volume || 0).toLocaleString()}+ vol.
                    </div>
                  </div>
                  <button onClick={() => setResult(h)} className="tap"
                    style={{ border: 'none', background: 'var(--fill)', cursor: 'pointer',
                      borderRadius: 8, padding: '4px 10px', fontSize: 12,
                      color: 'var(--text-2)', fontWeight: 500, flexShrink: 0 }}>
                    Voir
                  </button>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <Card style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-3)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6, color: 'var(--text-2)' }}>
            Lance une analyse
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.6, maxWidth: 380, margin: '0 auto' }}>
            Mistral va analyser les marchés Polymarket en temps réel et identifier
            les meilleures opportunités selon tes filtres.
          </div>
        </Card>
      )}
    </div>
  );
}
window.AnalysePage = AnalysePage;
