// ============================================================
// page_settings.jsx — bot configuration (iOS settings style)
// ============================================================
function SettingsPage({ bot, onToggle, onBack }) {
  const { fmtUSD, Card, BotGlyph, MarketChip, StatusPill, Toggle, Group, Row,
    Segmented, Button, Icon } = window;

  const [cfg, setCfg] = React.useState({
    capital: bot.capital || 10000,
    maxPos: bot.market === 'polymarket' ? 8 : 5,
    riskPer: 2,
    stopLoss: 8,
    takeProfit: 16,
    leverage: bot.market === 'stocks' ? 1 : 2,
    mode: 'auto',
    reinvest: true,
    notifyTrade: true,
    notifyDrawdown: true,
    paperMode: bot.status !== 'running',
  });
  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));

  const SliderRow = ({ label, k, min, max, step = 1, unit = '', fmt }) => (
    <div style={{ padding: '12px var(--pad)', borderBottom: '1px solid var(--separator)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 9 }}>
        <span style={{ fontSize: 15, fontWeight: 500 }}>{label}</span>
        <span className="num" style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)' }}>
          {fmt ? fmt(cfg[k]) : cfg[k] + unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={cfg[k]}
        onChange={(e) => set(k, Number(e.target.value))}
        style={{ width: '100%', accentColor: 'var(--accent)', height: 4 }} />
    </div>
  );

  return (
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 'var(--gap)' }}>
        <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)',
          width: 38, height: 38, borderRadius: 11, cursor: 'pointer', display: 'grid', placeItems: 'center',
          color: 'var(--accent)', transform: 'scaleX(-1)' }}><Icon name="chevron" size={20} stroke={2.4} /></button>
        <BotGlyph bot={bot} size={46} />
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.02em' }}>Réglages</h2>
          <div style={{ color: 'var(--text-3)', fontSize: 13.5, marginTop: 2 }}>{bot.name}</div>
        </div>
        <Button variant="primary" icon="check">Enregistrer</Button>
      </div>

      <Group header="Exécution">
        <div style={{ padding: '12px var(--pad)', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid var(--separator)' }}>
          <div><div style={{ fontSize: 15, fontWeight: 500 }}>Bot actif</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1 }}>Démarre / met en pause l'exécution</div></div>
          <Toggle on={bot.status === 'running'} onChange={() => onToggle(bot.id)} />
        </div>
        <div style={{ padding: '12px var(--pad)', borderBottom: '1px solid var(--separator)' }}>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 9 }}>Mode</div>
          <Segmented value={cfg.mode} onChange={(v) => set('mode', v)} options={[
            { value: 'auto', label: 'Automatique' }, { value: 'signal', label: 'Signal only' }, { value: 'manual', label: 'Manuel' }]} />
        </div>
        <div style={{ padding: '12px var(--pad)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div><div style={{ fontSize: 15, fontWeight: 500 }}>Mode papier (simulation)</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1 }}>Aucun ordre réel n'est envoyé</div></div>
          <Toggle on={cfg.paperMode} onChange={(v) => set('paperMode', v)} color="var(--orange)" />
        </div>
      </Group>

      <Group header="Capital & dimensionnement">
        <SliderRow label="Capital alloué" k="capital" min={1000} max={100000} step={500} fmt={(v) => fmtUSD(v)} />
        <SliderRow label="Risque par position" k="riskPer" min={0.5} max={10} step={0.5} unit="%" />
        <SliderRow label="Positions simultanées max" k="maxPos" min={1} max={20} />
        {bot.market !== 'polymarket' && <SliderRow label="Levier" k="leverage" min={1} max={5} unit="×" />}
        <div style={{ padding: '12px var(--pad)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div><div style={{ fontSize: 15, fontWeight: 500 }}>Réinvestir les gains</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1 }}>Capitalisation automatique</div></div>
          <Toggle on={cfg.reinvest} onChange={(v) => set('reinvest', v)} />
        </div>
      </Group>

      <Group header="Gestion du risque" footer="Le bot se met en pause automatiquement si la perte journalière dépasse la limite de drawdown.">
        <SliderRow label="Stop-loss" k="stopLoss" min={1} max={30} unit="%" />
        <SliderRow label="Take-profit" k="takeProfit" min={2} max={60} unit="%" />
      </Group>

      <Group header="Connexions">
        <Row icon="link" iconBg="var(--accent)" label={bot.venue.split(' · ')[0]} sub="Clé API connectée"
          trailing={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 13, color: 'var(--green)', fontWeight: 600 }}><Icon name="check" size={16} stroke={2.6} />Connecté</span>} />
        <Row icon="coins" iconBg="var(--orange)" label="Webhook signaux" sub="TradingView · personnalisé"
          last value="Configurer" onClick={() => {}} trailing={<Icon name="chevron" size={18} style={{ color: 'var(--text-3)', marginLeft: 6 }} />} />
      </Group>

      <Group header="Notifications">
        <div style={{ padding: '12px var(--pad)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--separator)' }}>
          <span style={{ fontSize: 15, fontWeight: 500 }}>À chaque trade</span>
          <Toggle on={cfg.notifyTrade} onChange={(v) => set('notifyTrade', v)} />
        </div>
        <div style={{ padding: '12px var(--pad)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 15, fontWeight: 500 }}>Alerte drawdown</span>
          <Toggle on={cfg.notifyDrawdown} onChange={(v) => set('notifyDrawdown', v)} />
        </div>
      </Group>

      <Group>
        <Row icon="x" iconBg="var(--red)" label={<span style={{ color: 'var(--red)' }}>Supprimer le bot</span>}
          sub="Action irréversible" last onClick={() => {}} />
      </Group>
    </div>
  );
}
window.SettingsPage = SettingsPage;
