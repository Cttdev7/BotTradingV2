// ============================================================
// charts.jsx — SVG charts (sparkline, area, donut, bars)
// Responsive via viewBox + non-scaling strokes.
// ============================================================

// --- Sparkline (inline mini trend) ---
function Sparkline({ data, w = 88, h = 30, color, up }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const c = color || (up ? 'var(--green)' : 'var(--red)');
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - 3 - ((v - min) / rng) * (h - 6);
    return [x, y];
  });
  const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', overflow: 'visible' }}>
      <path d={d} fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// --- Area chart (interactive) ---
function AreaChart({ data, height = 220, color = 'var(--accent)', showAxis = true, currency = true }) {
  const W = 760, H = height;
  const padB = showAxis ? 22 : 6, padT = 10;
  const ref = React.useRef(null);
  const [hover, setHover] = React.useState(null); // index
  if (!data || data.length < 2) return null;

  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const X = (i) => (i / (data.length - 1)) * W;
  const Y = (v) => padT + (1 - (v - min) / rng) * (H - padT - padB);

  const line = data.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' ');
  const area = `${line} L ${W} ${H - padB} L 0 ${H - padB} Z`;
  const up = data[data.length - 1] >= data[0];
  const stroke = color === 'auto' ? (up ? 'var(--green)' : 'var(--red)') : color;
  const gid = React.useId();

  const onMove = (e) => {
    const r = ref.current.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    let i = Math.round((x / W) * (data.length - 1));
    i = Math.max(0, Math.min(data.length - 1, i));
    setHover(i);
  };
  const hv = hover != null ? data[hover] : null;
  const fmtV = (v) => currency ? '$' + Math.round(v).toLocaleString('en-US') : v.toFixed(1);

  return (
    <div style={{ position: 'relative' }}>
      <svg ref={ref} width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
           onMouseMove={onMove} onMouseLeave={() => setHover(null)}
           style={{ display: 'block', cursor: 'crosshair', overflow: 'visible' }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.5].map((f) => (
          <line key={f} x1="0" x2={W} y1={Y(min + rng * f)} y2={Y(min + rng * f)}
                stroke="var(--separator)" strokeWidth="1" vectorEffect="non-scaling-stroke" strokeDasharray="2 4" />
        ))}
        <path d={area} fill={`url(#${gid})`} />
        <path d={line} fill="none" stroke={stroke} strokeWidth="2.4"
              strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {hover != null && (
          <>
            <line x1={X(hover)} x2={X(hover)} y1={padT} y2={H - padB}
                  stroke="var(--text-3)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
            <circle cx={X(hover)} cy={Y(hv)} r="4" fill={stroke}
                    stroke="var(--bg-elev)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </>
        )}
      </svg>
      {hover != null && (
        <div className="num" style={{
          position: 'absolute', top: 0,
          left: `calc(${(X(hover) / W) * 100}% )`, transform: 'translateX(-50%)',
          background: 'var(--text)', color: 'var(--bg-elev)', padding: '4px 9px',
          borderRadius: 8, fontSize: 12, fontWeight: 600, pointerEvents: 'none',
          whiteSpace: 'nowrap', boxShadow: 'var(--shadow-pop)',
        }}>{fmtV(hv)}</div>
      )}
    </div>
  );
}

// --- Donut (allocation) ---
function Donut({ items, size = 168, thickness = 26, centerLabel, centerSub }) {
  const total = items.reduce((s, it) => s + it.value, 0) || 1;
  const r = (size - thickness) / 2;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {items.map((it, i) => {
          const frac = it.value / total;
          const dash = frac * circ;
          const el = (
            <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={it.color}
                    strokeWidth={thickness} strokeDasharray={`${dash} ${circ - dash}`}
                    strokeDashoffset={-acc * circ} strokeLinecap="butt" />
          );
          acc += frac;
          return el;
        })}
      </svg>
      {centerLabel != null && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
          <div className="num" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-.01em' }}>{centerLabel}</div>
          {centerSub && <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 2 }}>{centerSub}</div>}
        </div>
      )}
    </div>
  );
}

// --- Horizontal bar meter ---
function Meter({ value, max = 100, color = 'var(--accent)', h = 7 }) {
  return (
    <div style={{ background: 'var(--fill)', borderRadius: 999, height: h, overflow: 'hidden', width: '100%' }}>
      <div style={{ width: `${Math.min(100, (value / max) * 100)}%`, height: '100%',
        background: color, borderRadius: 999 }} />
    </div>
  );
}

Object.assign(window, { Sparkline, AreaChart, Donut, Meter });
