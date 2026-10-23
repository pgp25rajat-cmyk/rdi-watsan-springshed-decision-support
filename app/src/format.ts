import type { DiSiteResult, Range, Status } from './api';

/** Indian digit grouping (1,08,800), as the team writes numbers. */
export function num(n: number | null | undefined, digits = 0): string {
  if (n == null || !Number.isFinite(n)) return '–';
  return n.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

/** Rounds to a sensible number of significant figures for small flows. */
export function flow(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '–';
  const a = Math.abs(n);
  if (a === 0) return '0';
  if (a < 0.01) return '<0.01';
  if (a < 1) return n.toFixed(2);
  if (a < 10) return n.toFixed(1);
  return num(n, 0);
}

export function range(r: Range | { low: number; high: number } | null | undefined, f: (n: number) => string = flow): string {
  if (!r) return '–';
  return `${f(r.low)} – ${f(r.high)}`;
}

export const pct = (share: number) => `${Math.round(share * 100)}%`;

export const classColor = (c: string | undefined) =>
  c === 'High' ? 'var(--risk-high)' : c === 'Medium' ? 'var(--risk-med)' : c === 'Low' ? 'var(--risk-low)' : 'var(--ink-3)';

export function scoreColor(score: number) {
  if (score >= 65) return 'var(--risk-high)';
  if (score >= 35) return 'var(--risk-med)';
  return 'var(--risk-low)';
}

export const statusLabel: Record<Status, string> = {
  complete: 'Complete',
  provisional: 'Provisional',
  unavailable: 'Not available',
  failed: 'Could not run',
};

export const locationClass: Record<DiSiteResult['location_class'], { label: string; color: string }> = {
  in_zone_slope: { label: 'In a recharge zone on the spring slope', color: '#1f7a45' },
  in_zone_linked: { label: 'In a recharge zone linked by a fault or rock tilt', color: '#7aa83b' },
  in_zone_crack: { label: 'In a recharge zone linked by a crack', color: '#8e5bb5' },
  in_catchment: { label: 'In surface catchment', color: '#2f74b5' },
  outside: { label: 'Outside the recharge zones', color: '#7b818a' },
  below_spring: { label: 'Below the spring', color: '#c0392b' },
};

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function litres(m3: number) {
  const l = m3 * 1000;
  if (l >= 1e5) return `${num(l / 1e5, 1)} lakh litres`;
  return `${num(l)} litres`;
}

// Recharge zone colours by rank (R1 strongest) and what links each zone to the spring
export const ZONE_RANK_COLORS = ['#1f7a45', '#3f9d55', '#86c06c'] as const;
export const linkLabel: Record<string, string> = {
  'Surface slope': 'On the spring slope',
  'GSI fault': 'Linked by a fault',
  'Rock layers (up-dip)': 'Linked by rock tilt',
  'DEM lineament': 'Linked by a crack',
  'Mapped lineament': 'Linked by a mapped fracture',
};
