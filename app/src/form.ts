// Form state (as typed by the user), conversion to the API request, and remembering it in the browser.
import type { AssessRequest, DiAssumptions, DiSite, FieldAnswers } from './api';
import { DEFAULT_ASSUMPTIONS } from './api';
import { vulnerabilityQuestions } from './questions';
import { dipQuestions, textQuestions } from './questionExtras';

export type FormState = {
  spring: { name: string; lat: string; lon: string; elevation: string; datasetId?: string };
  answers: Record<string, string>; // every field answer as typed; '' = not answered
  sites: DiSite[];
  assumptions: DiAssumptions;
};

export const emptyForm = (): FormState => ({
  spring: { name: '', lat: '', lon: '', elevation: '' },
  answers: {},
  sites: [],
  assumptions: { ...DEFAULT_ASSUMPTIONS },
});

export function parseNumber(s: string | undefined): number | null {
  if (s == null) return null;
  const t = String(s).trim().replace(',', '.');
  if (t === '') return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

export function springPoint(form: FormState): { lat: number; lon: number } | null {
  const lat = parseNumber(form.spring.lat);
  const lon = parseNumber(form.spring.lon);
  if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return { lat, lon };
}

/** A short warning when the point is far outside Uttarakhand (the maps only cover the state). */
export function locationWarning(p: { lat: number; lon: number } | null): string | null {
  if (!p) return null;
  if (p.lat < 28.6 || p.lat > 31.6 || p.lon < 77.4 || p.lon > 81.2) return 'This point is outside Uttarakhand. The maps used by the tool may not cover it.';
  return null;
}

export function answeredCount(form: FormState): number {
  return Object.values(form.answers).filter((v) => v !== '' && v != null).length;
}

export function toRequest(form: FormState): AssessRequest | null {
  const p = springPoint(form);
  if (!p) return null;
  const field: FieldAnswers = {};
  const f = field as Record<string, string | number | boolean>;
  for (const q of vulnerabilityQuestions) {
    const raw = form.answers[q.id];
    if (raw == null || raw === '') continue;
    if (q.kind === 'number') {
      const n = parseNumber(raw);
      if (n != null && n >= 0) f[q.id] = q.integer ? Math.round(n) : n;
    } else if (q.kind === 'multi') {
      const picked = raw.split(',').filter((v) => q.options.some(([o]) => o === v));
      if (picked.length) (f as Record<string, unknown>)[q.id] = picked;
    } else if (q.options.some(([v]) => v === raw)) f[q.id] = raw;
  }
  for (const q of dipQuestions) {
    const n = parseNumber(form.answers[q.key]);
    if (n != null && n >= q.min && n <= q.max) f[q.key] = n;
  }
  for (const q of textQuestions) {
    const t = (form.answers[q.key] || '').trim();
    if (t) f[q.key] = t;
  }
  if (form.answers.streams_block_zones === 'no') f.streams_block_zones = false;
  const elevation = parseNumber(form.spring.elevation);
  return {
    spring: { name: form.spring.name.trim() || undefined, latitude: p.lat, longitude: p.lon, elevation_m: elevation },
    field,
    di: { sites: form.sites, assumptions: { ...form.assumptions } },
  };
}

const KEY = 'spring-planner.form.v1';

export function loadForm(): FormState {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return emptyForm();
    const saved = JSON.parse(raw) as Partial<FormState>;
    const base = emptyForm();
    return {
      spring: { ...base.spring, ...(saved.spring ?? {}) },
      answers: { ...(saved.answers ?? {}) },
      sites: Array.isArray(saved.sites) ? saved.sites.filter((s) => Number.isFinite(s?.latitude) && Number.isFinite(s?.longitude)) : [],
      assumptions: { ...base.assumptions, ...(saved.assumptions ?? {}) },
    };
  } catch {
    return emptyForm();
  }
}

export function saveForm(form: FormState) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(form));
  } catch {
    /* storage blocked: the form still works, it is just not remembered */
  }
}

let counter = 0;
export const newSiteId = () => `di-${Date.now().toString(36)}-${(counter++).toString(36)}`;
