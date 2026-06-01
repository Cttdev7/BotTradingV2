// ============================================================
// app.jsx — shell, navigation, new-bot sheet, tweaks
// ============================================================
const { useState, useEffect, useMemo } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "accent": "#007AFF",
  "density": "comfortable"
}/*EDITMODE-END*/;

// ---- app brand mark ----
function Logo({ size = 30 }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.3, flexShrink: 0,
      background: 'linear-gradient(150deg, var(--accent), color-mix(in oklab, var(--accent) 65%, #000))',
      display: 'grid', placeItems: 'center', boxShadow: '0 3px 10px color-mix(in oklab, var(--accent) 45%, transparent)' }}>
      <window.Icon name="pulse" size={size * 0.62} stroke={2.6} style={{ color: '#fff' }} />
    </div>
  );
}

function NavItem({ icon, label, active, onClick, badge }) {
  return (
    <button onClick={onClick} className="tap" style={{ display: 'flex', alignItems: 'center', gap: 11,
      width: '100%', border: 'none', cursor: 'pointer', textAlign: 'left', padding: '9px 11px',
      borderRadius: 'var(--r-md)', fontSize: 14.5, fontWeight: 550,
      background: active ? 'var(--accent)' : 'transparent',
      color: active ? '#fff' : 'var(--text-2)' }}>
      <window.Icon name={icon} size={20} stroke={active ? 2.2 : 1.9} />
      <span style={{ flex: 1 }}>{label}</span>
      {badge != null && <span className="num" style={{ fontSize: 12, fontWeight: 600,
        color: active ? 'rgba(255,255,255,.85)' : 'var(--text-3)' }}>{badge}</span>}
    </button>
  );
}

function NewBotSheet({ onClose, onCreate }) {
  const { Segmented, Button, MARKETS, fmtUSD } = window;
  const [name, setName] = useState('');
  const [market, setMarket] = useState('crypto');
  const [strategy, setStrategy] = useState('momentum');
  const [capital, setCapital] = useState(15000);
  const strategies = {
    crypto: [['momentum', 'Momentum'], ['grid', 'Grille'], ['arb', 'Arbitrage']],
    stocks: [['meanrev', 'Mean reversion'], ['earnings', 'Earnings drift'], ['momentum', 'Momentum']],
    polymarket: [['edge', 'Arbitrage de probabilités'], ['news', 'News-driven']],
  };
  const stratLabel = (strategies[market].find((s) => s[0] === strategy) || strategies[market][0]);

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, animation: 'fade .2s' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-elev)', borderRadius: 22,
        width: 'min(440px, 100%)', padding: 26, boxShadow: 'var(--shadow-pop)', animation: 'sheetUp .28s cubic-bezier(.22,.7,.3,1)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: '-.02em' }}>Nouveau bot</h2>
          <button onClick={onClose} className="tap" style={{ border: 'none', background: 'var(--fill)', width: 32, height: 32,
            borderRadius: 999, cursor: 'pointer', display: 'grid', placeItems: 'center', color: 'var(--text-2)' }}>
            <window.Icon name="x" size={18} stroke={2.4} /></button>
        </div>

        <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>NOM</label>
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Momentum BTC"
          style={{ width: '100%', margin: '6px 0 18px', border: 'none', background: 'var(--fill)', borderRadius: 'var(--r-md)',
            padding: '12px 14px', fontSize: 15, color: 'var(--text)', outline: 'none', fontFamily: 'inherit' }} />

        <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>MARCHÉ</label>
        <div style={{ margin: '6px 0 18px' }}>
          <Segmented value={market} onChange={(v) => { setMarket(v); setStrategy(({crypto:'momentum',stocks:'meanrev',polymarket:'edge'})[v]); }}
            options={[{ value: 'crypto', label: 'Crypto' }, { value: 'stocks', label: 'Actions' }, { value: 'polymarket', label: 'Polymarket' }]} />
        </div>

        <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>STRATÉGIE</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '8px 0 18px' }}>
          {strategies[market].map(([v, l]) => (
            <button key={v} onClick={() => setStrategy(v)} className="tap" style={{ border: 'none', cursor: 'pointer',
              padding: '8px 13px', borderRadius: 999, fontSize: 13.5, fontWeight: 600,
              background: strategy === v ? 'var(--accent)' : 'var(--fill)', color: strategy === v ? '#fff' : 'var(--text-2)' }}>{l}</button>
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)' }}>CAPITAL ALLOUÉ</label>
          <span className="num" style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent)' }}>{fmtUSD(capital)}</span>
        </div>
        <input type="range" min={1000} max={100000} step={500} value={capital} onChange={(e) => setCapital(Number(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--accent)', marginBottom: 24 }} />

        <Button full variant="primary" onClick={() => onCreate({ name: name.trim() || stratLabel[1], market, strategy, capital })}>
          Créer le bot
        </Button>
      </div>
    </div>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [bots, setBots] = useState(window.BOTS.map((b) => ({ ...b })));
  const [nav, setNav] = useState({ page: 'dashboard', botId: null });
  const [sheet, setSheet] = useState(false);
  const [renaming, setRenaming] = useState(null);

  // apply theme tokens
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', t.theme);
    document.documentElement.setAttribute('data-density', t.density);
    document.documentElement.style.setProperty('--accent', t.accent);
  }, [t.theme, t.density, t.accent]);

  const go = (page, botId = null) => { setNav({ page, botId }); window.scrollTo?.(0, 0);
    document.querySelector('.main')?.scrollTo(0, 0); };
  const toggleBot = (id) => setBots((bs) => bs.map((b) => b.id === id
    ? { ...b, status: b.status === 'running' ? 'paused' : 'running' } : b));
  const renameBot = (id, newName) => {
    const name = (newName || '').trim();
    if (name) setBots((bs) => bs.map((b) => b.id === id ? { ...b, name } : b));
  };
  const createBot = (d) => {
    const glyphs = { crypto: '◎', stocks: '◆', polymarket: '◑' };
    const nb = {
      id: 'bot' + Date.now(), name: d.name, market: d.market, glyph: glyphs[d.market],
      strategy: d.strategy, venue: 'À configurer', status: 'paused', capital: d.capital,
      allocPct: 0, pnlDayPct: 0, pnlDayAbs: 0, pnlTotalPct: 0, pnlTotalAbs: 0,
      winRate: 0, sharpe: 0, maxDD: 0, trades: 0, openPos: 0,
      series: window.makeSeries(Date.now(), 90, 0.001, 0.01, d.capital),
    };
    setBots((bs) => [...bs, nb]); setSheet(false); go('settings', nb.id);
  };

  const bot = bots.find((b) => b.id === nav.botId);
  const active = bots.filter((b) => b.status === 'running').length;
  const portfolio = useMemo(() => window.computePortfolio(bots), [bots]);

  let content;
  if (nav.page === 'dashboard') content = <window.DashboardPage bots={bots} portfolio={portfolio} onToggle={toggleBot} onOpen={(id) => go('bot', id)} onNewBot={() => setSheet(true)} />;
  else if (nav.page === 'portfolio') content = <window.PortfolioPage bots={bots} portfolio={portfolio} onOpen={(id) => go('bot', id)} />;
  else if (nav.page === 'history') content = <window.HistoryPage bots={bots} />;
  else if (nav.page === 'bot' && bot) content = <window.BotPage bot={bot} onToggle={toggleBot} onBack={() => go('dashboard')} onSettings={() => go('settings', bot.id)} onRename={renameBot} />;
  else if (nav.page === 'settings' && bot) content = <window.SettingsPage bot={bot} onToggle={toggleBot} onBack={() => go('bot', bot.id)} />;
  else content = <window.DashboardPage bots={bots} onToggle={toggleBot} onOpen={(id) => go('bot', id)} onNewBot={() => setSheet(true)} />;

  const mainNav = [
    { page: 'dashboard', icon: 'grid', label: 'Bots', badge: bots.length },
    { page: 'portfolio', icon: 'wallet', label: 'Portefeuille' },
    { page: 'history', icon: 'clock', label: 'Historique' },
  ];
  const navActive = (p) => nav.page === p || (p === 'dashboard' && (nav.page === 'bot' || nav.page === 'settings'));

  return (
    <div className="app">
      {/* sidebar */}
      <aside className="sidebar" style={{ background: 'var(--bg)', borderRight: '1px solid var(--separator)',
        display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ padding: '22px 16px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Logo /><div><div style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>TradingBot</div>
            <div style={{ fontSize: 11.5, color: 'var(--green)', fontWeight: 600 }}>{active} actifs</div></div>
        </div>
        <nav style={{ padding: '4px 12px', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {mainNav.map((n) => <NavItem key={n.page} {...n} active={navActive(n.page)} onClick={() => go(n.page)} />)}
        </nav>
        <div style={{ padding: '18px 18px 8px', fontSize: 11.5, fontWeight: 600, color: 'var(--text-3)',
          textTransform: 'uppercase', letterSpacing: '.05em' }}>Bots</div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {bots.map((b) => {
            const sel = nav.botId === b.id;
            const isRenaming = renaming?.id === b.id;
            return (
              <div key={b.id} className="bot-item"
                style={{ borderRadius: 'var(--r-md)', background: sel ? 'var(--fill)' : 'transparent' }}>
                {isRenaming ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 9px' }}>
                    <window.BotGlyph bot={b} size={26} />
                    <input autoFocus value={renaming.name}
                      onChange={(e) => setRenaming((r) => ({ ...r, name: e.target.value }))}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { renameBot(b.id, renaming.name); setRenaming(null); }
                        if (e.key === 'Escape') setRenaming(null);
                      }}
                      onBlur={() => { renameBot(b.id, renaming.name); setRenaming(null); }}
                      style={{ flex: 1, minWidth: 0, background: 'transparent', border: 'none',
                        outline: 'none', fontSize: 13.5, fontWeight: 550, color: 'var(--text)',
                        fontFamily: 'inherit' }} />
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <button onClick={() => go('bot', b.id)} className="tap"
                      style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10,
                        border: 'none', cursor: 'pointer', textAlign: 'left', padding: '7px 9px',
                        borderRadius: 'var(--r-md)', background: 'transparent', minWidth: 0 }}>
                      <window.BotGlyph bot={b} size={26} />
                      <span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 550, color: 'var(--text)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
                      <span style={{ width: 7, height: 7, borderRadius: 999, flexShrink: 0,
                        background: b.status === 'running' ? 'var(--green)' : 'var(--text-3)' }} />
                    </button>
                    <button className="bot-edit-btn" onClick={(e) => { e.stopPropagation(); setRenaming({ id: b.id, name: b.name }); }}
                      style={{ border: 'none', background: 'transparent', cursor: 'pointer',
                        padding: '0 6px 0 0', color: 'var(--text-3)', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                      <window.Icon name="pencil" size={14} stroke={1.8} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div style={{ padding: 12, borderTop: '1px solid var(--separator)' }}>
          <window.Button full icon="plus" onClick={() => setSheet(true)}>Nouveau bot</window.Button>
        </div>
      </aside>

      {/* main */}
      <div className="main">
        <div className="mobile-top">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Logo size={26} /><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>TradingBot</span>
          </div>
          <window.IconButton icon="plus" onClick={() => setSheet(true)} label="Nouveau bot" />
        </div>
        <div className="main-inner">
          <div key={nav.page + (nav.botId || '')} className="page-enter">{content}</div>
        </div>
      </div>

      {/* mobile tab bar */}
      <nav className="tabbar">
        {mainNav.map((n) => {
          const a = navActive(n.page);
          return (
            <button key={n.page} onClick={() => go(n.page)} style={{ flex: 1, border: 'none', background: 'transparent',
              cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, padding: '4px 0',
              color: a ? 'var(--accent)' : 'var(--text-3)' }}>
              <window.Icon name={n.icon} size={24} stroke={a ? 2.3 : 1.9} />
              <span style={{ fontSize: 10.5, fontWeight: 600 }}>{n.label}</span>
            </button>
          );
        })}
      </nav>

      {sheet && <NewBotSheet onClose={() => setSheet(false)} onCreate={createBot} />}

      {/* Tweaks */}
      <TweaksPanel title="Tweaks">
        <TweakSection label="Apparence" />
        <TweakRadio label="Thème" value={t.theme} options={[{ value: 'light', label: 'Clair' }, { value: 'dark', label: 'Sombre' }]} onChange={(v) => setTweak('theme', v)} />
        <TweakColor label="Accent" value={t.accent} options={['#007AFF', '#30D158', '#5E5CE6', '#FF9500', '#FF375F']} onChange={(v) => setTweak('accent', v)} />
        <TweakRadio label="Densité" value={t.density} options={[{ value: 'compact', label: 'Compact' }, { value: 'comfortable', label: 'Normal' }, { value: 'spacious', label: 'Aéré' }]} onChange={(v) => setTweak('density', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
