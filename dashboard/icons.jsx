// ============================================================
// icons.jsx — minimal SF-style line icons (stroke-based)
// ============================================================
function Icon({ name, size = 22, stroke = 1.8, style, fill }) {
  const p = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round',
    strokeLinejoin: 'round', style, 'aria-hidden': true };
  switch (name) {
    case 'grid': return (<svg {...p}><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></svg>);
    case 'wallet': return (<svg {...p}><rect x="3" y="6" width="18" height="13" rx="3.5"/><path d="M3 9.5h18"/><circle cx="16.5" cy="13" r="1.1" fill="currentColor" stroke="none"/></svg>);
    case 'clock': return (<svg {...p}><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>);
    case 'chart': return (<svg {...p}><path d="M4 19V5"/><path d="M4 19h16"/><path d="M7.5 15l3.2-4 2.6 2.4L18 8"/></svg>);
    case 'sliders': return (<svg {...p}><path d="M5 7h7M16 7h3"/><path d="M5 12h3M12 12h7"/><path d="M5 17h9M18 17h1"/><circle cx="14" cy="7" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="16" cy="17" r="2"/></svg>);
    case 'plus': return (<svg {...p}><path d="M12 5v14M5 12h14"/></svg>);
    case 'chevron': return (<svg {...p}><path d="M9 5l7 7-7 7"/></svg>);
    case 'chevron-right': return (<svg {...p}><path d="M9 5l7 7-7 7"/></svg>);
    case 'chevron-left': return (<svg {...p}><path d="M15 5l-7 7 7 7"/></svg>);
    case 'chevron-down': return (<svg {...p}><path d="M5 9l7 7 7-7"/></svg>);
    case 'calendar-days': return (<svg {...p}><rect x="3" y="4" width="18" height="17" rx="3"/><path d="M3 9h18"/><path d="M8 2v4M16 2v4"/><circle cx="8" cy="14" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="14" r="1" fill="currentColor" stroke="none"/><circle cx="16" cy="14" r="1" fill="currentColor" stroke="none"/></svg>);
    case 'chevdown': return (<svg {...p}><path d="M5 9l7 7 7-7"/></svg>);
    case 'play': return (<svg {...p}><path d="M7 5.5l11 6.5-11 6.5z" fill="currentColor" stroke="none"/></svg>);
    case 'pause': return (<svg {...p}><rect x="6.5" y="5.5" width="3.4" height="13" rx="1.3" fill="currentColor" stroke="none"/><rect x="14.1" y="5.5" width="3.4" height="13" rx="1.3" fill="currentColor" stroke="none"/></svg>);
    case 'up': return (<svg {...p}><path d="M6 15l6-6 6 6"/></svg>);
    case 'down': return (<svg {...p}><path d="M6 9l6 6 6-6"/></svg>);
    case 'arrowupright': return (<svg {...p}><path d="M7 17L17 7M9 7h8v8"/></svg>);
    case 'search': return (<svg {...p}><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-3.5-3.5"/></svg>);
    case 'bell': return (<svg {...p}><path d="M18 9a6 6 0 1 0-12 0c0 5-2 6.5-2 6.5h16S18 14 18 9z"/><path d="M10 19a2.5 2.5 0 0 0 4 0"/></svg>);
    case 'x': return (<svg {...p}><path d="M6 6l12 12M18 6L6 18"/></svg>);
    case 'dot': return (<svg {...p}><circle cx="12" cy="12" r="5" fill="currentColor" stroke="none"/></svg>);
    case 'shield': return (<svg {...p}><path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/></svg>);
    case 'bolt': return (<svg {...p}><path d="M13 3L5 13h6l-1 8 8-10h-6z" fill="currentColor" stroke="none"/></svg>);
    case 'gear': return (<svg {...p}><circle cx="12" cy="12" r="3.2"/><path d="M12 3v2.5M12 18.5V21M21 12h-2.5M5.5 12H3M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8M18.4 18.4l-1.8-1.8M7.4 7.4L5.6 5.6"/></svg>);
    case 'coins': return (<svg {...p}><ellipse cx="12" cy="6.5" rx="7" ry="3"/><path d="M5 6.5v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/><path d="M5 11.5c0 1.7 3.1 3 7 3s7-1.3 7-3"/></svg>);
    case 'pulse': return (<svg {...p}><path d="M3 12h4l2.5-6 4 13 2.5-7H21"/></svg>);
    case 'link': return (<svg {...p}><path d="M9 12h6"/><path d="M10 8H7a4 4 0 0 0 0 8h3"/><path d="M14 8h3a4 4 0 0 1 0 8h-3"/></svg>);
    case 'check': return (<svg {...p}><path d="M5 12.5l4.5 4.5L19 7"/></svg>);
    case 'pencil': return (<svg {...p}><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>);
    default: return null;
  }
}
window.Icon = Icon;
