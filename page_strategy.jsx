// ============================================================
// page_strategy.jsx — éditeur de stratégie (prompt) du bot
// ============================================================
function StrategyPage({ bot, onBack }) {
  const { Card, SectionTitle, BotGlyph, Button, Icon } = window;
  const [prompt, setPrompt] = React.useState('');
  const [name, setName] = React.useState(bot ? bot.name : 'Polymarket Edge');
  const [enabled, setEnabled] = React.useState(false);
  const [status, setStatus] = React.useState(null); // 'saving' | 'saved' | 'error'
  const [connected, setConnected] = React.useState(null); // null=loading, true, false

  // Charge la stratégie sauvegardée depuis le backend
  React.useEffect(() => {
    fetch('http://localhost:5000/api/strategy')
      .then((r) => r.json())
      .then((d) => {
        if (d.prompt !== undefined) setPrompt(d.prompt);
        if (d.name)    setName(d.name);
        if (d.enabled !== undefined) setEnabled(d.enabled);
      })
      .catch(() => {}); // pas de backend lancé, ok

    fetch('http://localhost:5000/api/status')
      .then((r) => r.json())
      .then((d) => setConnected(d.connected))
      .catch(() => setConnected(false));
  }, []);

  const save = () => {
    setStatus('saving');
    fetch('http://localhost:5000/api/strategy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, name, enabled }),
    })
      .then((r) => r.json())
      .then(() => setStatus('saved'))
      .catch(() => setStatus('error'));
  };

  const examples = [
    'Achète YES quand la probabilité est < 40% et que le volume dépasse 10 000 USDC.',
    'Mise sur NO pour les marchés électoraux quand le candidat sortant est favori à > 70%.',
    'Arbitrage : achète le côté sous-évalué quand YES + NO != 1.00 avec un écart > 3%.',
  ];

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      {onBack && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 'var(--gap)' }}>
          <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)',
            width: 38, height: 38, borderRadius: 11, cursor: 'pointer', display: 'grid', placeItems: 'center',
            color: 'var(--accent)', transform: 'scaleX(-1)' }}><Icon name="chevron" size={20} stroke={2.4} /></button>
          {bot && <BotGlyph bot={bot} size={38} />}
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.02em' }}>Stratégie</h2>
        </div>
      )}

      {!onBack && <SectionTitle title="Stratégie" sub="Décris ce que ton bot doit faire en langage naturel" />}

      {/* Statut connexion */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--gap)',
        fontSize: 13, fontWeight: 500,
        color: connected === null ? 'var(--text-3)' : connected ? 'var(--green)' : 'var(--orange)' }}>
        <span style={{ width: 7, height: 7, borderRadius: 999, flexShrink: 0,
          background: connected === null ? 'var(--text-3)' : connected ? 'var(--green)' : 'var(--orange)' }} />
        {connected === null ? 'Vérification de la connexion…' :
         connected ? 'Bot connecté à Polymarket' :
         'Backend non lancé — lance python bot/server.py'}
      </div>

      {/* Nom du bot */}
      <Card style={{ marginBottom: 'var(--gap)' }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 8 }}>NOM DU BOT</div>
        <input value={name} onChange={(e) => setName(e.target.value)}
          placeholder="ex. Polymarket Edge"
          style={{ width: '100%', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-md)',
            padding: '11px 14px', fontSize: 15, color: 'var(--text)', outline: 'none', fontFamily: 'inherit' }} />
      </Card>

      {/* Zone prompt */}
      <Card style={{ marginBottom: 'var(--gap)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>STRATÉGIE (PROMPT)</div>
          <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{prompt.length} caractères</span>
        </div>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
          placeholder="Décris en détail la stratégie du bot : quand acheter, quand vendre, quel montant, quels types de marchés cibler, quels critères de risque..."
          rows={8}
          style={{ width: '100%', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-md)',
            padding: '12px 14px', fontSize: 14.5, color: 'var(--text)', outline: 'none',
            fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.6 }} />

        {/* Exemples */}
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 600, marginBottom: 8 }}>EXEMPLES</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {examples.map((ex, i) => (
              <button key={i} onClick={() => setPrompt(ex)} className="tap"
                style={{ textAlign: 'left', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-sm)',
                  padding: '9px 12px', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer', lineHeight: 1.5 }}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Bouton activer */}
      <Card style={{ marginBottom: 'var(--gap)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500 }}>Activer le bot</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 2 }}>
            Le bot utilisera ce prompt pour prendre ses décisions
          </div>
        </div>
        <window.Toggle on={enabled} onChange={setEnabled} />
      </Card>

      {/* Sauvegarder */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <Button variant="primary" icon="check" onClick={save}>
          {status === 'saving' ? 'Sauvegarde…' : 'Sauvegarder'}
        </Button>
        {status === 'saved' && (
          <span style={{ fontSize: 13.5, color: 'var(--green)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5 }}>
            <Icon name="check" size={16} stroke={2.4} />Sauvegardé
          </span>
        )}
        {status === 'error' && (
          <span style={{ fontSize: 13.5, color: 'var(--red)', fontWeight: 500 }}>
            Erreur — le backend est-il lancé ?
          </span>
        )}
      </div>
    </div>
  );
}
window.StrategyPage = StrategyPage;
