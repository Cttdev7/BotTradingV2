// ============================================================
// ui.jsx — shared iOS-style primitives
// ============================================================

// Card surface
function Card({ children, style, pad = true, onClick, hover }) {
  return (
    <div onClick={onClick} className={onClick ? 'tap' : ''} style={{
      background: 'var(--bg-elev)', borderRadius: 'var(--r-card)',
      boxShadow: 'var(--shadow-card)', padding: pad ? 'var(--pad)' : 0,
      cursor: onClick ? 'pointer' : 'default', ...style,
    }}>{children}</div>
  );
}

// Section header (large iOS title + optional trailing)
function SectionTitle({ title, sub, trailing }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
      gap: 12, marginBottom: 14 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.02em' }}>{title}</h2>
        {sub && <p style={{ margin: '3px 0 0', color: 'var(--text-3)', fontSize: 13.5 }}>{sub}</p>}
      </div>
      {trailing}
    </div>
  );
}

// Bot glyph badge (colored rounded square)
function BotGlyph({ bot, size = 40 }) {
  const m = window.MARKETS[bot.market];
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.28, flexShrink: 0,
      display: 'grid', placeItems: 'center', fontSize: size * 0.46, fontWeight: 600,
      color: '#fff', background: `linear-gradient(160deg, ${m.tint}, color-mix(in oklab, ${m.tint} 72%, #000))`,
      boxShadow: `0 4px 12px color-mix(in oklab, ${m.tint} 40%, transparent)` }}>
      {bot.glyph}
    </div>
  );
}

// Market chip
function MarketChip({ market }) {
  const m = window.MARKETS[market];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5,
      fontWeight: 600, color: m.color, background: `color-mix(in oklab, ${m.tint} 14%, transparent)`,
      padding: '3px 9px', borderRadius: 999 }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: m.color }} />{m.label}
    </span>
  );
}

// Status pill
function StatusPill({ status }) {
  const running = status === 'running';
  const c = running ? 'var(--green)' : 'var(--text-3)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12,
      fontWeight: 600, color: c }}>
      <span style={{ position: 'relative', width: 8, height: 8 }}>
        <span style={{ position: 'absolute', inset: 0, borderRadius: 999, background: c }} />
        {running && <span style={{ position: 'absolute', inset: -3, borderRadius: 999,
          background: c, opacity: .35, animation: 'pingPulse 1.8s ease-out infinite' }} />}
      </span>
      {running ? 'Actif' : 'En pause'}
    </span>
  );
}

// iOS toggle
function Toggle({ on, onChange, color = 'var(--green)' }) {
  return (
    <button onClick={(e) => { e.stopPropagation(); onChange(!on); }} style={{
      width: 51, height: 31, borderRadius: 999, border: 'none', padding: 0, cursor: 'pointer',
      background: on ? color : 'var(--fill-2)', position: 'relative', transition: 'background .2s',
      flexShrink: 0 }}>
      <span style={{ position: 'absolute', top: 2, left: on ? 22 : 2, width: 27, height: 27,
        borderRadius: 999, background: '#fff', boxShadow: '0 2px 6px rgba(0,0,0,.25)',
        transition: 'left .22s cubic-bezier(.3,.7,.4,1)' }} />
    </button>
  );
}

// Segmented control
function Segmented({ options, value, onChange, size = 'md' }) {
  const idx = Math.max(0, options.findIndex((o) => (o.value ?? o) === value));
  const n = options.length;
  const pad = size === 'sm' ? '5px 0' : '7px 0';
  const fs = size === 'sm' ? 12.5 : 13.5;
  return (
    <div style={{ position: 'relative', display: 'flex', padding: 2, borderRadius: 'var(--r-sm)',
      background: 'var(--fill)', userSelect: 'none' }}>
      <div style={{ position: 'absolute', top: 2, bottom: 2, left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
        width: `calc((100% - 4px) / ${n})`, background: 'var(--bg-elev)', borderRadius: 'calc(var(--r-sm) - 2px)',
        boxShadow: '0 1px 3px rgba(0,0,0,.12)', transition: 'left .2s cubic-bezier(.3,.7,.4,1)' }} />
      {options.map((o) => {
        const v = o.value ?? o, l = o.label ?? o;
        return (
          <button key={v} onClick={() => onChange(v)} style={{ position: 'relative', zIndex: 1,
            flex: 1, border: 'none', background: 'transparent', padding: pad, fontSize: fs,
            fontWeight: 600, cursor: 'pointer', color: v === value ? 'var(--text)' : 'var(--text-3)',
            transition: 'color .2s' }}>{l}</button>
        );
      })}
    </div>
  );
}

// Stat tile
function Stat({ label, value, sub, accent, big }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500, marginBottom: 5 }}>{label}</div>
      <div className="num" style={{ fontSize: big ? 26 : 19, fontWeight: 700, letterSpacing: '-.02em',
        color: accent || 'var(--text)' }}>{value}</div>
      {sub && <div className="num" style={{ fontSize: 12.5, marginTop: 3, color: 'var(--text-3)' }}>{sub}</div>}
    </div>
  );
}

// Grouped list (iOS settings) container + row
function Group({ header, footer, children }) {
  return (
    <div style={{ marginBottom: 'var(--gap)' }}>
      {header && <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-3)',
        textTransform: 'uppercase', letterSpacing: '.04em', padding: '0 4px 7px' }}>{header}</div>}
      <div style={{ background: 'var(--bg-elev)', borderRadius: 'var(--r-card)', overflow: 'hidden',
        boxShadow: 'var(--shadow-card)' }}>{children}</div>
      {footer && <div style={{ fontSize: 12, color: 'var(--text-3)', padding: '8px 4px 0', lineHeight: 1.45 }}>{footer}</div>}
    </div>
  );
}

function Row({ icon, iconBg, label, sub, value, trailing, onClick, last }) {
  return (
    <div onClick={onClick} className={onClick ? 'tap' : ''} style={{ display: 'flex', alignItems: 'center',
      gap: 13, padding: '0 var(--pad)', minHeight: 'var(--row-h)', cursor: onClick ? 'pointer' : 'default',
      borderBottom: last ? 'none' : '1px solid var(--separator)' }}>
      {icon && (
        <div style={{ width: 30, height: 30, borderRadius: 8, background: iconBg || 'var(--accent)',
          color: '#fff', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
          <window.Icon name={icon} size={18} stroke={2} />
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0, padding: '9px 0' }}>
        <div style={{ fontSize: 15, fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 1 }}>{sub}</div>}
      </div>
      {value != null && <div className="num" style={{ fontSize: 14.5, color: 'var(--text-3)' }}>{value}</div>}
      {trailing}
    </div>
  );
}

// Delta text (+x% green / -x% red) with optional arrow
function Delta({ pct, abs, size = 14, showArrow }) {
  const v = pct != null ? pct : abs;
  const pos = v >= 0;
  const c = v === 0 ? 'var(--text-3)' : pos ? 'var(--green)' : 'var(--red)';
  return (
    <span className="num" style={{ color: c, fontWeight: 600, fontSize: size,
      display: 'inline-flex', alignItems: 'center', gap: 2 }}>
      {showArrow && v !== 0 && <window.Icon name={pos ? 'up' : 'down'} size={size + 2} stroke={2.4} />}
      {pct != null ? window.fmtPct(pct) : window.fmtSigned(abs)}
    </span>
  );
}

// Plain icon button
function IconButton({ icon, onClick, label, active }) {
  return (
    <button onClick={onClick} aria-label={label} className="tap" style={{ width: 38, height: 38,
      borderRadius: 11, border: 'none', cursor: 'pointer', display: 'grid', placeItems: 'center',
      background: active ? 'var(--accent)' : 'var(--fill)', color: active ? '#fff' : 'var(--text-2)' }}>
      <window.Icon name={icon} size={20} />
    </button>
  );
}

// Primary button
function Button({ children, onClick, variant = 'primary', icon, size = 'md', full }) {
  const styles = {
    primary: { background: 'var(--accent)', color: '#fff' },
    secondary: { background: 'var(--fill)', color: 'var(--text)' },
    danger: { background: 'color-mix(in oklab, var(--red) 14%, transparent)', color: 'var(--red)' },
    ghost: { background: 'transparent', color: 'var(--accent)' },
  }[variant];
  return (
    <button onClick={onClick} className="tap" style={{ ...styles, border: 'none', cursor: 'pointer',
      borderRadius: 'var(--r-md)', padding: size === 'sm' ? '8px 14px' : '11px 18px',
      fontSize: size === 'sm' ? 13.5 : 15, fontWeight: 600, display: 'inline-flex',
      alignItems: 'center', justifyContent: 'center', gap: 7, width: full ? '100%' : 'auto' }}>
      {icon && <window.Icon name={icon} size={18} stroke={2.2} />}{children}
    </button>
  );
}

Object.assign(window, {
  Card, SectionTitle, BotGlyph, MarketChip, StatusPill, Toggle, Segmented,
  Stat, Group, Row, Delta, IconButton, Button,
});
