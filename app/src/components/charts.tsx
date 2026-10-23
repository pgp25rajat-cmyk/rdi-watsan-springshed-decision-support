// Small hand-drawn SVG/HTML charts (no chart library).
import type { FlowPath } from '../api';
import { MONTHS, classColor, num } from '../format';

export function Gauge({ score, label }: { score: number; label: string }) {
  const cx = 110, cy = 112, r = 88;
  const t = Math.max(0, Math.min(100, score)) / 100;
  const at = (v: number) => {
    const a = Math.PI * (1 - v);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  };
  const [x0, y0] = at(0);
  const [x1, y1] = at(1);
  const [xs, ys] = at(t);
  const color = classColor(label);
  const tick = (v: number) => {
    const a = Math.PI * (1 - v);
    return { x1: cx + (r - 14) * Math.cos(a), y1: cy - (r - 14) * Math.sin(a), x2: cx + (r + 14) * Math.cos(a), y2: cy - (r + 14) * Math.sin(a) };
  };
  return (
    <svg className="gauge" viewBox="0 0 220 128" role="img" aria-label={`Score ${score} of 100, ${label}`}>
      <defs>
        <linearGradient id="gauge-track" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="var(--risk-low)" />
          <stop offset="0.5" stopColor="var(--risk-med)" />
          <stop offset="1" stopColor="var(--risk-high)" />
        </linearGradient>
      </defs>
      <path d={`M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`} fill="none" stroke="url(#gauge-track)" strokeOpacity="0.22" strokeWidth="18" strokeLinecap="round" />
      {t > 0 && <path d={`M ${x0} ${y0} A ${r} ${r} 0 0 1 ${xs} ${ys}`} fill="none" stroke={color} strokeWidth="18" strokeLinecap="round" />}
      <line {...tick(t)} stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
      <text x={cx} y={cy - 22} textAnchor="middle" className="gauge-score" fill="var(--ink)">{Math.round(score)}</text>
      <text x={cx} y={cy - 2} textAnchor="middle" className="gauge-sub" fill="var(--ink-3)">of 100</text>
      <text x={x0} y={cy + 15} textAnchor="middle" className="gauge-end" fill="var(--ink-3)">0</text>
      <text x={x1} y={cy + 15} textAnchor="middle" className="gauge-end" fill="var(--ink-3)">100</text>
    </svg>
  );
}

const COVER_COLORS: Record<string, string> = {
  'tree cover': '#2d6a4f', forest: '#2d6a4f', cropland: '#d4a72c', grassland: '#9cc97e', shrubland: '#6f9a55',
  'built-up': '#b5524a', 'bare ground': '#a8a092', bare: '#a8a092', water: '#3a86c8', snow: '#c9d6df',
};
const FALLBACK = ['#5b7f95', '#8d6e97', '#c27c4e', '#7c8d4c', '#9aa1a9'];

export function StackedBar({ shares }: { shares: Record<string, number> }) {
  const entries = Object.entries(shares).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  const color = (k: string, i: number) => COVER_COLORS[k.toLowerCase()] ?? FALLBACK[i % FALLBACK.length];
  return (
    <div className="stacked">
      <div className="stacked-bar" role="img" aria-label={entries.map(([k, v]) => `${k} ${Math.round(v)}%`).join(', ')}>
        {entries.map(([k, v], i) => (
          <span key={k} style={{ flexGrow: v / total, background: color(k, i) }} title={`${k}: ${Math.round(v)}%`} />
        ))}
      </div>
      <ul className="stacked-legend">
        {entries.map(([k, v], i) => (
          <li key={k}><i style={{ background: color(k, i) }} />{k} <b>{Math.round(v)}%</b></li>
        ))}
      </ul>
    </div>
  );
}

/** One series of 12 monthly bars. Two of these stacked share the month axis (no dual axis). */
export function MonthlyBars({ values, unit, color, title }: { values: number[]; unit: string; color: string; title: string }) {
  const W = 360, H = 112, left = 34, bottom = 18, top = 10;
  const max = Math.max(...values, 1);
  const nice = niceMax(max);
  const bw = (W - left - 4) / 12;
  const y = (v: number) => top + (H - top - bottom) * (1 - v / nice);
  const peak = values.indexOf(Math.max(...values));
  return (
    <figure className="monthly">
      <figcaption>{title} <span className="muted">({unit})</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${values.map((v, i) => `${MONTHS[i]} ${num(v)}`).join(', ')}`}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={left} x2={W} y1={y(nice * f)} y2={y(nice * f)} stroke="var(--line)" strokeWidth="1" />
            <text x={left - 5} y={y(nice * f) + 3.5} textAnchor="end" className="axis">{num(nice * f)}</text>
          </g>
        ))}
        {values.map((v, i) => {
          const x = left + 2 + i * bw;
          const h = Math.max(0, y(0) - y(v));
          return (
            <g key={i} className="bar">
              <rect x={x} y={top} width={bw} height={H - top - bottom} fill="transparent">
                <title>{`${MONTHS[i]}: ${num(v, 1)} ${unit}`}</title>
              </rect>
              <path d={roundedTop(x + bw * 0.18, y(0), bw * 0.64, h, 3)} fill={color} pointerEvents="none" />
              {i === peak && v > 0 && <text x={x + bw / 2} y={y(v) - 3} textAnchor="middle" className="axis strong">{num(v)}</text>}
              <text x={x + bw / 2} y={H - 5} textAnchor="middle" className="axis">{MONTHS[i][0]}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

function roundedTop(x: number, base: number, w: number, h: number, r: number) {
  if (h <= 0) return '';
  const rr = Math.min(r, h, w / 2);
  return `M ${x} ${base} V ${base - h + rr} Q ${x} ${base - h} ${x + rr} ${base - h} H ${x + w - rr} Q ${x + w} ${base - h} ${x + w} ${base - h + rr} V ${base} Z`;
}

function niceMax(v: number) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

/** Low–mid–high range on a 0..max scale. */
export function RangeStrip({ low, mid, high, max }: { low: number; mid: number; high: number; max: number }) {
  const s = (v: number) => `${Math.max(0, Math.min(100, (v / (max || 1)) * 100))}%`;
  return (
    <div className="range-strip" aria-hidden="true">
      <span className="range-band" style={{ left: s(low), width: `calc(${s(high)} - ${s(low)})` }} />
      <span className="range-mid" style={{ left: s(mid) }} />
    </div>
  );
}

/** Cross-section from a DI handpump to the spring, like the "groundwater flow path" figure of the SRHU reports:
 *  the ground along the straight line, the borehole down to the injection point, the spring outlet level and the
 *  assumed path of the injected water. Not to scale sideways vs up (heights are stretched to be readable). */
export function CrossSection({ path, name }: { path: FlowPath; name: string }) {
  const W = 600, H = 250, L = 56, R = 18, T = 26, B = 34;
  const pts = path.profile;
  const len = Math.max(path.length_m, 1);
  const head = path.head_at_handpump_m;
  const zs = [...pts.map((p) => p[1]), path.injection_elevation_m, path.spring_elevation_m, ...(head != null ? [head] : [])];
  const lo = Math.min(...zs), hi = Math.max(...zs);
  const pad = Math.max(8, (hi - lo) * 0.08);
  const z0 = lo - pad, z1 = hi + pad;
  const x = (d: number) => L + ((W - L - R) * d) / len;
  const y = (z: number) => T + ((H - T - B) * (z1 - z)) / (z1 - z0);
  const ground = pts.map(([d, z]) => `${x(d).toFixed(1)},${y(z).toFixed(1)}`).join(' ');
  const fill = `${x(0)},${y(z0)} ${ground} ${x(len)},${y(z0)}`;
  const hx = x(0), injY = y(path.injection_elevation_m), gY = y(path.ground_at_handpump_m);
  const sx = x(len), sY = y(path.spring_elevation_m);
  const above = path.injection_elevation_m >= path.spring_elevation_m;
  // the water's assumed route: from the injection point, curving towards the outlet
  const midX = (hx + sx) / 2, midY = Math.max(injY, sY) + (above ? 0 : 6);
  const route = `M ${hx + 4} ${injY} Q ${midX} ${midY} ${sx - 9} ${sY + 2}`;
  const step = niceStep((z1 - z0) / 4);
  const ticks: number[] = [];
  for (let v = Math.ceil(z0 / step) * step; v <= z1; v += step) ticks.push(v);
  const id = `arrow-${name.replace(/\W+/g, '')}`;
  return (
    <svg className="xsec" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Cross-section from ${name} to the spring: ${num(path.length_m)} m apart, injection at ${num(path.injection_elevation_m)} m, spring at ${num(path.spring_elevation_m)} m above sea level`}>
      <defs>
        <marker id={id} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#0b5fa5" />
        </marker>
      </defs>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
          <text x={L - 6} y={y(v) + 4} textAnchor="end" className="xsec-tick">{num(v)}</text>
        </g>
      ))}
      <polygon points={fill} fill="#d9c7a3" opacity="0.55" />
      <polyline points={ground} fill="none" stroke="#8a6d3b" strokeWidth="2" />
      <line x1={L} x2={W - R} y1={sY} y2={sY} stroke="#0b6e8a" strokeWidth="1.2" strokeDasharray="5 4" />
      <text x={W - R - 2} y={sY - 5} textAnchor="end" className="xsec-note">spring outlet level</text>
      {head != null && <line x1={hx} y1={y(head)} x2={sx} y2={sY} stroke="#2b7bbd" strokeWidth="1.5" strokeDasharray="2 3" />}
      <line x1={hx} x2={hx} y1={gY} y2={injY} stroke="#44535a" strokeWidth="3" />
      <path d={route} fill="none" stroke="#0b5fa5" strokeWidth="2.5" strokeDasharray="7 4" markerEnd={`url(#${id})`} />
      <circle cx={hx} cy={injY} r="5.5" fill="#0b5fa5" stroke="#fff" strokeWidth="1.5" />
      <rect x={hx - 6} y={gY - 12} width="12" height="12" rx="2" fill="#44535a" />
      <text x={hx + 10} y={gY - 4} className="xsec-label">{name}</text>
      <text x={hx + 10} y={injY + 16} className="xsec-note">injected at {num(path.depth_m)} m depth ({num(path.injection_elevation_m)} m)</text>
      <circle cx={sx} cy={sY} r="6" fill="#0b6e8a" stroke="#fff" strokeWidth="1.5" />
      <text x={sx - 10} y={sY + 18} textAnchor="end" className="xsec-label">Spring ({num(path.spring_elevation_m)} m)</text>
      <text x={L} y={H - 10} className="xsec-tick">0 m</text>
      <text x={W - R} y={H - 10} textAnchor="end" className="xsec-tick">{num(path.length_m)} m along the line</text>
      <text x={8} y={T - 10} className="xsec-tick">m above sea level</text>
    </svg>
  );
}

function niceStep(raw: number) {
  const p = 10 ** Math.floor(Math.log10(Math.max(raw, 1e-6)));
  const n = raw / p;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * p;
}
