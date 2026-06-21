// page_calendar.jsx — PNL Calendar (ProfitWeather V2)
(function () {
  const { useState, useEffect, useMemo } = React;

  const DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
  const MONTH_NAMES = ['Janvier','Février','Mars','Avril','Mai','Juin',
    'Juillet','Août','Septembre','Octobre','Novembre','Décembre'];

  const SB_URL = window.SB_URL;
  const SB_KEY = window.SB_KEY;
  // Doit rester aligné avec PERF_RESET_DATE dans bot/loop_v2.py et bot/server.py —
  // sinon le calendrier remonte aussi les trades d'avant le reset des stats.
  const PERF_RESET_DATE = '2026-06-17T15:34:00';

  async function loadFromSupabase() {
    const r = await fetch(
      `${SB_URL}/rest/v1/trade_history?bot_id=eq.polyedge2&time=gte.${PERF_RESET_DATE}&order=time.asc&limit=500`,
      { headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}` } }
    );
    if (!r.ok) throw new Error(`${r.status}`);
    const rows = await r.json();
    const days = {};
    for (const t of rows) {
      const ts  = t.time || '';
      const day = ts.slice(0, 10);
      if (!day) continue;
      if (!days[day]) days[day] = { pnl: 0, wins: 0, losses: 0, open: 0, trades: 0 };
      days[day].trades++;
      const pnl = t.pnl != null ? parseFloat(t.pnl) : null;
      if (pnl === null)      { days[day].open++;   }
      else if (pnl > 0)  { days[day].wins++;   days[day].pnl += pnl; }
      else if (pnl < 0)  { days[day].losses++; days[day].pnl += pnl; }
    }
    for (const d of Object.values(days)) d.pnl = Math.round(d.pnl * 100) / 100;
    return days;
  }

  function CalendarPage({ onBack }) {
    const now = new Date();
    const [year,  setYear]   = useState(now.getFullYear());
    const [month, setMonth]  = useState(now.getMonth());
    const [allData, setAllData] = useState({});
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState(false);

    useEffect(() => {
      loadFromSupabase()
        .then(d => { setAllData(d || {}); setLoading(false); })
        .catch(() => { setError(true); setLoading(false); });
    }, []);

    const prevMonth = () => {
      if (month === 0) { setYear(y => y - 1); setMonth(11); }
      else setMonth(m => m - 1);
    };
    const nextMonth = () => {
      const n = new Date();
      if (year === n.getFullYear() && month === n.getMonth()) return;
      if (month === 11) { setYear(y => y + 1); setMonth(0); }
      else setMonth(m => m + 1);
    };
    const isCurrentMonth = year === now.getFullYear() && month === now.getMonth();

    // Filter data for selected month
    const monthData = useMemo(() => {
      const prefix = `${year}-${String(month + 1).padStart(2, '0')}`;
      const result = {};
      Object.entries(allData).forEach(([day, stats]) => {
        if (day.startsWith(prefix)) result[day] = stats;
      });
      return result;
    }, [allData, year, month]);

    // Monthly aggregates
    const stats = useMemo(() => {
      let totalPnl = 0, wins = 0, losses = 0, winAmt = 0, lossAmt = 0;
      Object.values(monthData).forEach(d => {
        totalPnl += d.pnl;
        if (d.pnl > 0)      { wins++;   winAmt  += d.pnl; }
        else if (d.pnl < 0) { losses++; lossAmt += Math.abs(d.pnl); }
      });
      return {
        totalPnl: Math.round(totalPnl * 100) / 100,
        wins, losses,
        winAmt:  Math.round(winAmt  * 100) / 100,
        lossAmt: Math.round(lossAmt * 100) / 100,
      };
    }, [monthData]);

    // Streaks (positive PNL days)
    const { currentStreak, bestStreak } = useMemo(() => {
      const sorted = Object.entries(monthData).sort(([a],[b]) => a < b ? -1 : 1);
      let best = 0, run = 0;
      sorted.forEach(([, d]) => {
        if (d.pnl > 0) { run++; best = Math.max(best, run); }
        else run = 0;
      });
      let cur = 0;
      for (let i = sorted.length - 1; i >= 0; i--) {
        if (sorted[i][1].pnl > 0) cur++;
        else break;
      }
      return { currentStreak: cur, bestStreak: best };
    }, [monthData]);

    // Calendar grid cells
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    let firstDow = new Date(year, month, 1).getDay();
    firstDow = firstDow === 0 ? 6 : firstDow - 1; // Mon=0
    const cells = [...Array(firstDow).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];

    const totalTradeDays = stats.wins + stats.losses;
    const winPct = totalTradeDays > 0 ? (stats.wins / totalTradeDays) * 100 : 0;

    return (
      <div style={{ padding: 'var(--gap)', maxWidth: 620, margin: '0 auto' }}>

        {/* ── Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
          {onBack && (
            <button onClick={onBack} className="tap" style={{ border: 'none', background: 'var(--fill)',
              width: 34, height: 34, borderRadius: 999, cursor: 'pointer',
              display: 'grid', placeItems: 'center', flexShrink: 0, color: 'var(--text-2)' }}>
              <window.Icon name="chevron-left" size={18} stroke={2.3} />
            </button>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <window.Icon name="calendar-days" size={20} stroke={2.2} />
            <div>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.02em' }}>PNL Calendar</h1>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 1 }}>ProfitWeather V2</div>
            </div>
          </div>
        </div>

        {/* ── Month navigation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 14, padding: '12px 16px', background: 'var(--bg-elev)',
          borderRadius: 'var(--r-card)', border: '1px solid var(--separator)' }}>
          <button onClick={prevMonth} className="tap" style={{ border: 'none', background: 'var(--fill)',
            width: 32, height: 32, borderRadius: 999, cursor: 'pointer',
            display: 'grid', placeItems: 'center', color: 'var(--text-2)' }}>
            <window.Icon name="chevron-left" size={16} stroke={2.2} />
          </button>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.01em' }}>
            {MONTH_NAMES[month]} {year}
          </span>
          <button onClick={nextMonth} className="tap" style={{ border: 'none',
            background: isCurrentMonth ? 'transparent' : 'var(--fill)',
            width: 32, height: 32, borderRadius: 999, cursor: isCurrentMonth ? 'default' : 'pointer',
            display: 'grid', placeItems: 'center',
            color: isCurrentMonth ? 'var(--text-3)' : 'var(--text-2)', opacity: isCurrentMonth ? 0.35 : 1 }}>
            <window.Icon name="chevron-right" size={16} stroke={2.2} />
          </button>
        </div>

        {/* ── Stats bar */}
        <div style={{ background: 'var(--bg-elev)', borderRadius: 'var(--r-card)',
          border: '1px solid var(--separator)', padding: '18px 20px', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14 }}>
            <span className="num" style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.03em',
              color: stats.totalPnl >= 0 ? '#0dbda8' : '#ff6b8a' }}>
              {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnl.toFixed(2)} USDC
            </span>
            {totalTradeDays > 0 && (
              <span style={{ fontSize: 13, color: 'var(--text-3)', fontWeight: 600 }}>
                {totalTradeDays} jour{totalTradeDays > 1 ? 's' : ''} tradés
              </span>
            )}
          </div>

          {totalTradeDays > 0 && (
            <div style={{ borderRadius: 99, overflow: 'hidden', height: 7,
              background: 'var(--fill)', marginBottom: 14, display: 'flex' }}>
              <div style={{ width: `${winPct}%`, background: '#0dbda8', transition: 'width .45s ease' }} />
              <div style={{ flex: 1, background: '#ff6b8a' }} />
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 10.5, fontWeight: 700, color: '#0dbda8',
                textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>
                Jours gagnants
              </div>
              <div className="num" style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)' }}>
                {stats.wins}
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginLeft: 6 }}>
                  +{stats.winAmt.toFixed(2)} $
                </span>
              </div>
            </div>
            <div style={{ width: 1, background: 'var(--separator)', margin: '0 18px' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 10.5, fontWeight: 700, color: '#ff6b8a',
                textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>
                Jours perdants
              </div>
              <div className="num" style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)' }}>
                {stats.losses}
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginLeft: 6 }}>
                  -{stats.lossAmt.toFixed(2)} $
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Calendar grid */}
        <div style={{ background: 'var(--bg-elev)', borderRadius: 'var(--r-card)',
          border: '1px solid var(--separator)', padding: 14, marginBottom: 14 }}>
          {/* Day-of-week headers */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 6 }}>
            {DAY_LABELS.map(d => (
              <div key={d} style={{ textAlign: 'center', fontSize: 10.5, fontWeight: 700,
                color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.05em', padding: '2px 0' }}>
                {d}
              </div>
            ))}
          </div>
          {/* Cells */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
            {cells.map((day, i) => {
              if (!day) return <div key={`blank-${i}`} />;
              const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
              const d   = monthData[key];
              const pnl = d ? d.pnl : null;
              const isToday = year === now.getFullYear() && month === now.getMonth() && day === now.getDate();
              const isFuture = new Date(year, month, day) > now;

              let bg = 'var(--fill)';
              let pnlColor = 'var(--text-3)';
              if (!isFuture && pnl !== null && pnl > 0) { bg = 'color-mix(in oklab,#0dbda8 16%,transparent)'; pnlColor = '#0dbda8'; }
              if (!isFuture && pnl !== null && pnl < 0) { bg = 'color-mix(in oklab,#ff6b8a 15%,transparent)'; pnlColor = '#ff6b8a'; }

              return (
                <div key={key} style={{ background: bg, borderRadius: 10,
                  padding: '7px 3px 6px', textAlign: 'center', minHeight: 56,
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  justifyContent: 'space-between',
                  border: isToday ? '1.5px solid var(--accent)' : '1.5px solid transparent',
                  opacity: isFuture ? 0.35 : 1 }}>
                  <span style={{ fontSize: 13, fontWeight: isToday ? 800 : 600,
                    color: isToday ? 'var(--accent)' : 'var(--text)' }}>{day}</span>
                  {!isFuture && pnl !== null ? (
                    <span className="num" style={{ fontSize: 10, fontWeight: 700, color: pnlColor, marginTop: 3, lineHeight: 1.1 }}>
                      {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}
                    </span>
                  ) : !isFuture && d && d.open > 0 ? (
                    <span style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 4 }}>…</span>
                  ) : (
                    <span style={{ height: 14 }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Streaks */}
        <div style={{ background: 'var(--bg-elev)', borderRadius: 'var(--r-card)',
          border: '1px solid var(--separator)', padding: '14px 20px',
          display: 'flex', alignItems: 'center' }}>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-3)',
              textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>
              Série positive actuelle
            </div>
            <div className="num" style={{ fontSize: 26, fontWeight: 800,
              color: currentStreak > 0 ? '#0dbda8' : 'var(--text-2)' }}>
              {currentStreak}
              <span style={{ fontSize: 13, marginLeft: 4, fontWeight: 600, color: 'var(--text-3)' }}>j</span>
            </div>
          </div>
          <div style={{ width: 1, background: 'var(--separator)', alignSelf: 'stretch', margin: '0 16px' }} />
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-3)',
              textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>
              Meilleure série ce mois
            </div>
            <div className="num" style={{ fontSize: 26, fontWeight: 800,
              color: bestStreak > 0 ? '#0dbda8' : 'var(--text-2)' }}>
              {bestStreak}
              <span style={{ fontSize: 13, marginLeft: 4, fontWeight: 600, color: 'var(--text-3)' }}>j</span>
            </div>
          </div>
        </div>

        {/* ── Error / empty states */}
        {!loading && error && (
          <div style={{ marginTop: 14, padding: '12px 16px', borderRadius: 'var(--r-card)',
            background: 'color-mix(in oklab,var(--orange) 10%,transparent)',
            border: '1px solid color-mix(in oklab,var(--orange) 25%,transparent)',
            fontSize: 13, color: 'var(--text-2)' }}>
            Impossible de charger les données — vérifie la connexion Supabase.
          </div>
        )}
        {!loading && !error && Object.keys(allData).length === 0 && (
          <div style={{ marginTop: 14, padding: '12px 16px', borderRadius: 'var(--r-card)',
            background: 'var(--fill)', fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
            Aucun trade trouvé dans <code>trade_history</code> pour polyedge2.
          </div>
        )}
      </div>
    );
  }

  window.CalendarPage = CalendarPage;
})();
