import { useMemo, useState } from 'react';
import type { DatasetSpring, DiAssumptions, DiSite } from '../api';
import { DEFAULT_ASSUMPTIONS } from '../api';
import type { FormState } from '../form';
import { locationWarning, newSiteId, parseNumber, springPoint } from '../form';
import { num } from '../format';
import { vulnerabilityQuestions, type Question } from '../questions';
import { dipQuestions, questionGroups, textQuestions } from '../questionExtras';
import type { Placing } from './MapView';

type SetForm = (fn: (f: FormState) => FormState) => void;

type Props = {
  form: FormState;
  setForm: SetForm;
  springs: DatasetSpring[];
  placing: Placing;
  setPlacing: (p: Placing) => void;
  onPickSpring: (s: DatasetSpring) => void;
  onFocusPoint: () => void;
};

export default function Form(props: Props) {
  return (
    <div className="form">
      <SpringStep {...props} />
      <FieldStep form={props.form} setForm={props.setForm} />
      <DiStep {...props} />
    </div>
  );
}

function StepHead({ n, title, done, hint }: { n: number; title: string; done?: boolean; hint?: string }) {
  return (
    <div className="step-head">
      <span className={`step-num${done ? ' done' : ''}`} aria-hidden="true">{done ? '✓' : n}</span>
      <div>
        <h2>{title}</h2>
        {hint && <p className="hint">{hint}</p>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 1. spring
function SpringStep({ form, setForm, springs, placing, setPlacing, onPickSpring, onFocusPoint }: Props) {
  const [query, setQuery] = useState('');
  const [geoMsg, setGeoMsg] = useState('');
  const point = springPoint(form);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const scored: [number, DatasetSpring][] = [];
    for (const s of springs) {
      const name = s.name.toLowerCase();
      const hay = `${name} ${s.village} ${s.district} ${s.id}`.toLowerCase();
      if (!hay.includes(q)) continue;
      scored.push([name.startsWith(q) ? 0 : name.includes(q) ? 1 : 2, s]);
    }
    return scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name)).slice(0, 7).map((x) => x[1]);
  }, [query, springs]);

  const set = (k: keyof FormState['spring'], v: string) =>
    setForm((f) => ({ ...f, spring: { ...f.spring, [k]: v, ...(k === 'lat' || k === 'lon' ? { datasetId: undefined } : {}) } }));

  const useMyLocation = () => {
    if (!navigator.geolocation) { setGeoMsg('This browser cannot read your location.'); return; }
    setGeoMsg('Reading your location…');
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setForm((f) => ({ ...f, spring: { ...f.spring, lat: p.coords.latitude.toFixed(6), lon: p.coords.longitude.toFixed(6), datasetId: undefined } }));
        setGeoMsg(`Done (accurate to about ${Math.round(p.coords.accuracy)} m).`);
        setTimeout(onFocusPoint, 50);
      },
      () => setGeoMsg('Could not read your location. Allow location access, or type the numbers.'),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const warn = locationWarning(point);
  return (
    <section className="step" aria-labelledby="step1">
      <StepHead n={1} title="Spring" done={!!point} hint="Find it in the list, click the map, or type its position." />
      <div className="field">
        <label htmlFor="spring-search">Search springs in the dataset</label>
        <input id="spring-search" type="search" placeholder={springs.length ? `Name, village or district (${num(springs.length)} spring${springs.length === 1 ? "" : "s"})` : 'Spring list not loaded'}
          value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" disabled={!springs.length} />
        {query.trim().length >= 2 && (
          <ul className="matches" role="listbox" aria-label="Matching springs">
            {matches.length === 0 && <li className="muted">No spring matches “{query}”.</li>}
            {matches.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => { onPickSpring(s); setQuery(''); }}>
                  <strong>{s.name}</strong>
                  <span>{[s.village, s.district].filter(Boolean).join(', ')}{s.elevation_m != null ? ` · ${num(s.elevation_m)} m` : ''}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="row-buttons">
        <button type="button" className={`btn${placing === 'spring' ? ' btn-active' : ''}`} onClick={() => setPlacing(placing === 'spring' ? 'none' : 'spring')}>
          {placing === 'spring' ? 'Click the map…' : point ? 'Move on the map' : 'Pick on the map'}
        </button>
        <button type="button" className="btn" onClick={useMyLocation}>Use my location</button>
      </div>
      {geoMsg && <p className="hint">{geoMsg}</p>}
      <div className="grid2">
        <div className="field">
          <label htmlFor="lat">Latitude</label>
          <input id="lat" inputMode="decimal" placeholder="e.g. 29.91903" value={form.spring.lat} onChange={(e) => set('lat', e.target.value)} onBlur={onFocusPoint} />
        </div>
        <div className="field">
          <label htmlFor="lon">Longitude</label>
          <input id="lon" inputMode="decimal" placeholder="e.g. 78.55647" value={form.spring.lon} onChange={(e) => set('lon', e.target.value)} onBlur={onFocusPoint} />
        </div>
      </div>
      {(form.spring.lat || form.spring.lon) && !point && <p className="msg msg-warn">Enter both numbers in decimal degrees, like 29.91903 and 78.55647.</p>}
      {warn && <p className="msg msg-warn">{warn}</p>}
      <div className="field">
        <label htmlFor="spring-name">Spring name</label>
        <input id="spring-name" placeholder="e.g. Nauli Dhara" value={form.spring.name} onChange={(e) => set('name', e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="elev">Elevation <span className="muted">(optional, metres)</span></label>
        <input id="elev" inputMode="decimal" placeholder="Leave blank to use the map elevation" value={form.spring.elevation} onChange={(e) => set('elevation', e.target.value)} />
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ 2. field observations
function FieldStep({ form, setForm }: { form: FormState; setForm: SetForm }) {
  const byId = useMemo(() => new Map(vulnerabilityQuestions.map((q) => [q.id, q])), []);
  const setAnswer = (id: string, v: string) => setForm((f) => ({ ...f, answers: { ...f.answers, [id]: v } }));
  const answered = (ids: string[]) => ids.filter((id) => (form.answers[id] ?? '') !== '').length;
  const geoIds = [...textQuestions.map((q) => q.key), ...dipQuestions.map((q) => q.key)];
  const total = answered([...vulnerabilityQuestions.map((q) => q.id), ...geoIds]);
  return (
    <section className="step" aria-labelledby="step2">
      <StepHead n={2} title="Field observations" done={total > 0}
        hint="All optional. Each answer makes the result more certain. Skip anything you do not know." />
      {questionGroups.map((g) => (
        <details className="group" key={g.title}>
          <summary>
            <span className="group-title">{g.title}</span>
            <span className="group-count">{answered(g.ids)} of {g.ids.length}</span>
            <span className="group-hint">{g.hint}</span>
          </summary>
          <div className="group-body">
            {g.ids.map((id) => {
              const q = byId.get(id);
              return q ? <QuestionInput key={id} q={q} value={form.answers[id] ?? ''} onChange={(v) => setAnswer(id, v)} /> : null;
            })}
          </div>
        </details>
      ))}
      <details className="group">
        <summary>
          <span className="group-title">Geology</span>
          <span className="group-count">{answered(geoIds)} of {geoIds.length}</span>
          <span className="group-hint">Rock at the spring; helps draw the springshed</span>
        </summary>
        <div className="group-body">
          {textQuestions.map((q) => (
            <div className="field" key={q.key}>
              <label htmlFor={`q-${q.key}`}>{q.label}</label>
              <input id={`q-${q.key}`} placeholder={q.placeholder} value={form.answers[q.key] ?? ''} onChange={(e) => setAnswer(q.key, e.target.value)} />
            </div>
          ))}
          {dipQuestions.map((q) => {
            const v = form.answers[q.key] ?? '';
            const n = parseNumber(v);
            const bad = v !== '' && (n == null || n < q.min || n > q.max);
            return (
              <div className="field" key={q.key}>
                <label htmlFor={`q-${q.key}`}>{q.label}</label>
                <div className="with-unit">
                  <input id={`q-${q.key}`} inputMode="decimal" value={v} onChange={(e) => setAnswer(q.key, e.target.value)} aria-describedby={`h-${q.key}`} />
                  <span>{q.unit}</span>
                </div>
                <p className="hint" id={`h-${q.key}`}>{q.help}</p>
                {bad && <p className="msg msg-warn">Use a number from {q.min} to {q.max}.</p>}
              </div>
            );
          })}
          <label className="check">
            <input type="checkbox" checked={form.answers.streams_block_zones !== 'no'}
              onChange={(e) => setAnswer('streams_block_zones', e.target.checked ? '' : 'no')} />
            Streams stop a recharge zone
          </label>
          <p className="hint">On by default: a stream usually drains the water before it reaches the spring. Turn it off where
            the rock carries water under the stream (for example along a fault).</p>
        </div>
      </details>
    </section>
  );
}

function QuestionInput({ q, value, onChange }: { q: Question; value: string; onChange: (v: string) => void }) {
  if (q.kind === 'multi') {
    const picked = value ? value.split(',') : [];
    const toggle = (v: string) => {
      let next = picked.includes(v) ? picked.filter((x) => x !== v) : [...picked, v];
      if (v === 'none' && next.includes('none')) next = ['none'];
      else next = next.filter((x) => x !== 'none' || v === 'none');
      onChange(q.options.map(([o]) => o).filter((o) => next.includes(o)).join(','));
    };
    return (
      <fieldset className="field choice">
        <legend>{q.label}</legend>
        <div className="chips">
          {q.options.map(([v, label]) => (
            <label key={v} className={`chip${picked.includes(v) ? ' on' : ''}`}>
              <input type="checkbox" value={v} checked={picked.includes(v)} onChange={() => toggle(v)} />
              {label}
            </label>
          ))}
          {value !== '' && <button type="button" className="chip-clear" onClick={() => onChange('')}>Clear</button>}
        </div>
      </fieldset>
    );
  }
  if (q.kind === 'choice') {
    return (
      <fieldset className="field choice">
        <legend>{q.label}</legend>
        <div className="chips">
          {q.options.map(([v, label]) => (
            <label key={v} className={`chip${value === v ? ' on' : ''}`}>
              <input type="radio" name={q.id} value={v} checked={value === v} onChange={() => onChange(v)} />
              {label}
            </label>
          ))}
          {value !== '' && <button type="button" className="chip-clear" onClick={() => onChange('')}>Clear</button>}
        </div>
      </fieldset>
    );
  }
  const n = parseNumber(value);
  const bad = value !== '' && (n == null || n < 0);
  return (
    <div className="field">
      <label htmlFor={`q-${q.id}`}>{q.label}</label>
      <div className="with-unit">
        <input id={`q-${q.id}`} inputMode={q.integer ? 'numeric' : 'decimal'} value={value} onChange={(e) => onChange(e.target.value)} />
        <span>{q.unit}</span>
      </div>
      {q.help && <p className="hint">{q.help}</p>}
      {bad && <p className="msg msg-warn">Use a number of 0 or more.</p>}
    </div>
  );
}

// ------------------------------------------------------------------ 3. DI plan
function DiStep({ form, setForm, placing, setPlacing }: Props) {
  const point = springPoint(form);
  const updateSite = (id: string, patch: Partial<DiSite>) =>
    setForm((f) => ({ ...f, sites: f.sites.map((s) => (s.id === id ? { ...s, ...patch } : s)) }));
  const removeSite = (id: string) => setForm((f) => ({ ...f, sites: f.sites.filter((s) => s.id !== id) }));
  const setA = (patch: Partial<DiAssumptions>) => setForm((f) => ({ ...f, assumptions: { ...f.assumptions, ...patch } }));
  const a = form.assumptions;
  const [typed, setTyped] = useState({ lat: '', lon: '' });
  const typedLat = parseNumber(typed.lat), typedLon = parseNumber(typed.lon);
  const typedOk = typedLat != null && typedLon != null && Math.abs(typedLat) <= 90 && Math.abs(typedLon) <= 180;
  const addTyped = () => {
    if (!typedOk) return;
    setForm((f) => ({ ...f, sites: [...f.sites, { id: newSiteId(), name: '', latitude: +typedLat!.toFixed(6), longitude: +typedLon!.toFixed(6),
      roof_area_m2: 100, first_flush: true, filter: true }] }));
    setTyped({ lat: '', lon: '' });
  };
  return (
    <section className="step" aria-labelledby="step3">
      <StepHead n={3} title="DI plan (optional)" done={form.sites.length > 0}
        hint="DI = a defunct handpump used to put rooftop rainwater into the ground. Add the ones you plan to use." />
      <button type="button" className={`btn btn-wide${placing === 'site' ? ' btn-active' : ''}`} disabled={!point}
        onClick={() => setPlacing(placing === 'site' ? 'none' : 'site')}>
        {placing === 'site' ? 'Click on the map to place it…' : '+ Add DI site on the map'}
      </button>
      {!point && <p className="hint">Choose the spring first.</p>}
      {point && (
        <div className="typed-site">
          <p className="hint">Or type the handpump's position:</p>
          <div className="grid2">
            <div className="field">
              <label htmlFor="site-lat">Latitude</label>
              <input id="site-lat" inputMode="decimal" placeholder="e.g. 30.17339" value={typed.lat} onChange={(e) => setTyped({ ...typed, lat: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="site-lon">Longitude</label>
              <input id="site-lon" inputMode="decimal" placeholder="e.g. 78.31285" value={typed.lon} onChange={(e) => setTyped({ ...typed, lon: e.target.value })} />
            </div>
          </div>
          {(typed.lat || typed.lon) && !typedOk && <p className="msg msg-warn">Enter both numbers in decimal degrees.</p>}
          <button type="button" className="btn btn-small" disabled={!typedOk} onClick={addTyped}>+ Add DI site at this position</button>
        </div>
      )}
      {form.sites.length > 0 && (
        <ol className="sites">
          {form.sites.map((s, i) => (
            <li key={s.id} className="site">
              <div className="site-top">
                <span className="site-num" aria-hidden="true">{i + 1}</span>
                <label className="sr-only" htmlFor={`sn-${s.id}`}>Name of DI site {i + 1}</label>
                <input id={`sn-${s.id}`} placeholder={`DI site ${i + 1}`} value={s.name ?? ''} onChange={(e) => updateSite(s.id, { name: e.target.value })} />
                <button type="button" className="btn btn-small btn-ghost" onClick={() => removeSite(s.id)} aria-label={`Remove DI site ${i + 1}`}>Remove</button>
              </div>
              <div className="site-grid">
                <label className="inline-field">
                  <span>Roof area</span>
                  <span className="with-unit small">
                    <input inputMode="numeric" value={String(s.roof_area_m2)}
                      onChange={(e) => { const n = parseNumber(e.target.value); updateSite(s.id, { roof_area_m2: n != null && n >= 0 ? n : 0 }); }} />
                    <span>m²</span>
                  </span>
                </label>
                <label className="inline-field">
                  <span>Handpump depth</span>
                  <span className="with-unit small">
                    <input inputMode="numeric" placeholder="70" value={s.depth_m != null ? String(s.depth_m) : ''}
                      onChange={(e) => { const n = parseNumber(e.target.value); updateSite(s.id, { depth_m: n != null && n > 0 ? n : null }); }} />
                    <span>m</span>
                  </span>
                </label>
                <label className="inline-field">
                  <span>Water level below ground</span>
                  <span className="with-unit small">
                    <input inputMode="decimal" placeholder="optional" value={s.water_level_m != null ? String(s.water_level_m) : ''}
                      onChange={(e) => { const n = parseNumber(e.target.value); updateSite(s.id, { water_level_m: n != null && n >= 0 ? n : null }); }} />
                    <span>m</span>
                  </span>
                </label>
                <label className="check"><input type="checkbox" checked={s.first_flush} onChange={(e) => updateSite(s.id, { first_flush: e.target.checked })} /> First-flush diverter</label>
                <label className="check"><input type="checkbox" checked={s.filter} onChange={(e) => updateSite(s.id, { filter: e.target.checked })} /> Filter</label>
              </div>
              <SitePosition site={s} onMove={(lat, lon) => updateSite(s.id, { latitude: lat, longitude: lon })} />
              <p className="hint">Depth: most handpumps are 50-80 m; 70 m is used if left blank. Water level: how far down the water stands in the handpump, if known. Type a new position or drag the marker to move it.</p>
            </li>
          ))}
        </ol>
      )}

      <details className="group">
        <summary>
          <span className="group-title">Assumptions</span>
          <span className="group-hint">The numbers behind the water estimate. The defaults are fine for most sites.</span>
        </summary>
        <div className="group-body">
          <fieldset className="field">
            <legend>Yearly rain</legend>
            <label className="check"><input type="radio" name="rain" checked={a.annual_rain_mm == null} onChange={() => setA({ annual_rain_mm: null })} /> Read it from the rainfall maps</label>
            <label className="check">
              <input type="radio" name="rain" checked={a.annual_rain_mm != null} onChange={() => setA({ annual_rain_mm: 1600 })} /> I know it:
              <span className="with-unit small">
                <input aria-label="Yearly rain in mm" inputMode="numeric" disabled={a.annual_rain_mm == null} value={a.annual_rain_mm ?? ''}
                  onChange={(e) => { const n = parseNumber(e.target.value); setA({ annual_rain_mm: n != null && n >= 0 ? n : 0 }); }} />
                <span>mm</span>
              </span>
            </label>
          </fieldset>
          <Slider label="Roof water that reaches the handpump" help="Some rain splashes off or leaks from gutters." min={0.6} max={0.95} step={0.05}
            value={a.collection_coefficient} fmt={(v) => `${Math.round(v * 100)}%`} onChange={(v) => setA({ collection_coefficient: v })} />
          <Slider label="Water that goes into the ground" help="What is left after the first flush and overflow in heavy storms." min={0.6} max={0.95} step={0.05}
            value={a.injection_efficiency} fmt={(v) => `${Math.round(v * 100)}%`} onChange={(v) => setA({ injection_efficiency: v })} />
          <Slider label="Spread of the water mound around the handpump" help="Used only for the water-level rise. Smaller = higher rise." min={20} max={150} step={5}
            value={a.radius_of_influence_m} fmt={(v) => `${v} m`} onChange={(v) => setA({ radius_of_influence_m: v })} />
          <button type="button" className="btn btn-small btn-ghost" onClick={() => setA({ ...DEFAULT_ASSUMPTIONS })}>Reset to defaults</button>
        </div>
      </details>
    </section>
  );
}

/** Editable latitude and longitude of a DI site; a change is kept once both numbers are valid. */
function SitePosition({ site, onMove }: { site: DiSite; onMove: (lat: number, lon: number) => void }) {
  const [lat, setLat] = useState(site.latitude.toFixed(6));
  const [lon, setLon] = useState(site.longitude.toFixed(6));
  const [seen, setSeen] = useState(`${site.latitude},${site.longitude}`);
  if (seen !== `${site.latitude},${site.longitude}`) {  // moved on the map
    setSeen(`${site.latitude},${site.longitude}`);
    setLat(site.latitude.toFixed(6));
    setLon(site.longitude.toFixed(6));
  }
  const commit = (la: string, lo: string) => {
    const a = parseNumber(la), b = parseNumber(lo);
    if (a != null && b != null && Math.abs(a) <= 90 && Math.abs(b) <= 180 && (a !== site.latitude || b !== site.longitude)) onMove(a, b);
  };
  return (
    <div className="site-pos">
      <label className="inline-field"><span>Lat</span>
        <input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} onBlur={() => commit(lat, lon)} aria-label="DI site latitude" />
      </label>
      <label className="inline-field"><span>Long</span>
        <input inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} onBlur={() => commit(lat, lon)} aria-label="DI site longitude" />
      </label>
    </div>
  );
}

function Slider({ label, help, min, max, step, value, fmt, onChange }: {
  label: string; help: string; min: number; max: number; step: number; value: number; fmt: (v: number) => string; onChange: (v: number) => void;
}) {
  const id = `sl-${label.replace(/\W+/g, '-').toLowerCase()}`;
  return (
    <div className="field slider">
      <div className="slider-head">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{fmt(value)}</output>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <p className="hint">{help}</p>
    </div>
  );
}
