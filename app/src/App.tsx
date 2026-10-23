import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AssessRequest, AssessResponse, DatasetSpring, ExistingDiSite, Health } from './api';
import { assess, getExistingDiSites, getHealth, getSprings } from './api';
import { DEMO_SPRING, MOCK_HEALTH, demoDiSites, mockAssess, mockSprings } from './mock';
import { emptyForm, loadForm, newSiteId, saveForm, springPoint, toRequest, type FormState } from './form';
import Form from './components/Form';
import MapView, { type Focus, type Placing, type Tab } from './components/MapView';
import Results, { HowItWorks } from './components/Results';
import PrintReport from './components/PrintReport';

type Mode = 'checking' | 'live' | 'demo' | 'unavailable';
const ALLOW_DEMO = import.meta.env.VITE_ALLOW_DEMO !== 'false';
// Elevation tiles for the 3D map: the tool serves them from its own map files; the demo uses a public copy.
const LIVE_TERRAIN = '/api/terrain/{z}/{x}/{y}.png?v=2'; // v: bump when the tiles change, so browsers drop old copies
const DEMO_TERRAIN = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';

// DI sites further than this from the spring are treated as left over from another spring.
const MAX_SITE_DISTANCE_M = 3000;
function distanceM(lat1: number, lon1: number, lat2: number, lon2: number) {
  const k = Math.PI / 180;
  const dy = (lat2 - lat1) * 111_132;
  const dx = (lon2 - lon1) * 111_320 * Math.cos(((lat1 + lat2) / 2) * k);
  return Math.hypot(dx, dy);
}

const STEPS = ['Scoring vulnerability', 'Mapping the springshed', 'Estimating DI impact'];

export default function App() {
  const [mode, setMode] = useState<Mode>('checking');
  const [health, setHealth] = useState<Health | null>(null);
  const [springs, setSprings] = useState<DatasetSpring[]>([]);
  const [springsError, setSpringsError] = useState('');
  const [existingDi, setExistingDi] = useState<ExistingDiSite[]>([]);
  const [form, setFormState] = useState<FormState>(loadForm);
  const [placing, setPlacing] = useState<Placing>('none');
  const [result, setResult] = useState<AssessResponse | null>(null);
  const [resultKey, setResultKey] = useState('');
  const [tab, setTab] = useState<Tab>('A');
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const [resultRequest, setResultRequest] = useState<AssessRequest | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const focusN = useRef(0);
  const mapRef = useRef<HTMLDivElement>(null);

  const setForm = useCallback((fn: (f: FormState) => FormState) => setFormState((f) => fn(f)), []);
  useEffect(() => saveForm(form), [form]);

  const connect = useCallback(async () => {
    setMode('checking');
    try {
      const h = await getHealth();
      if (!h.ok) throw new Error('not ok');
      setHealth(h);
      setMode('live');
      try {
        setSprings(await getSprings());
        setSpringsError('');
        setExistingDi(await getExistingDiSites().catch(() => []));
      } catch (e) {
        setSprings([]);
        setSpringsError('The spring list could not be loaded. You can still click the map or type the position.');
      }
    } catch {
      setHealth(MOCK_HEALTH);
      setMode(ALLOW_DEMO ? 'demo' : 'unavailable');
      setSprings(ALLOW_DEMO ? mockSprings() : []);
      setSpringsError('');
    }
  }, []);
  useEffect(() => { void connect(); }, [connect]);

  const point = springPoint(form);
  const flyTo = useCallback((lat: number, lon: number, zoom = 15) => {
    focusN.current += 1;
    setFocus({ lat, lon, zoom, n: focusN.current });
  }, []);

  const pickSpring = useCallback((s: DatasetSpring) => {
    setForm((f) => ({
      ...f,
      spring: {
        name: s.name, lat: String(s.latitude), lon: String(s.longitude),
        elevation: s.elevation_m != null ? String(Math.round(s.elevation_m)) : '', datasetId: s.id,
      },
    }));
    setPlacing('none');
    flyTo(s.latitude, s.longitude, 15);
  }, [flyTo, setForm]);

  // DI sites belong to one spring: when the spring moves far away (another spring picked, or a new point),
  // sites left from the earlier spring are dropped so they are not assessed against the wrong spring.
  const [siteNotice, setSiteNotice] = useState('');
  useEffect(() => {
    if (!point) return;
    const far = form.sites.filter((s) => distanceM(point.lat, point.lon, s.latitude, s.longitude) > MAX_SITE_DISTANCE_M);
    if (!far.length) return;
    setForm((f) => ({ ...f, sites: f.sites.filter((s) => !far.some((x) => x.id === s.id)) }));
    setSiteNotice(`${far.length} DI ${far.length === 1 ? 'site' : 'sites'} from the earlier spring ${far.length === 1 ? 'was' : 'were'} removed: `
      + `${far.length === 1 ? 'it was' : 'they were'} more than ${MAX_SITE_DISTANCE_M / 1000} km from this spring. Add this spring's own handpumps on the map.`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [point?.lat, point?.lon]);

  // A WATSAN DI handpump clicked on the map joins the DI plan with its known depth and roof
  const useExistingDi = useCallback((d: ExistingDiSite) => {
    setForm((f) => (f.sites.some((s) => s.name === d.name && s.latitude === d.latitude && s.longitude === d.longitude) ? f : {
      ...f,
      sites: [...f.sites, { id: newSiteId(), name: d.name, latitude: d.latitude, longitude: d.longitude, roof_area_m2: d.roof_area_m2 ?? 100,
        first_flush: true, filter: true, depth_m: d.depth_m ?? undefined }],
    }));
  }, [setForm]);

  const effectivePlacing: Placing = placing !== 'none' ? placing : point ? 'none' : 'spring';

  const onPlace = useCallback((lat: number, lon: number) => {
    if (effectivePlacing === 'site') {
      setForm((f) => ({
        ...f,
        sites: [...f.sites, { id: newSiteId(), name: '', latitude: +lat.toFixed(6), longitude: +lon.toFixed(6), roof_area_m2: 100, first_flush: true, filter: true }],
      }));
    } else if (effectivePlacing === 'spring') {
      setForm((f) => ({ ...f, spring: { ...f.spring, lat: lat.toFixed(6), lon: lon.toFixed(6), datasetId: undefined } }));
    }
    setPlacing('none');
  }, [effectivePlacing, setForm]);

  const loadExample = () => {
    setForm(() => ({
      ...emptyForm(),
      spring: { name: DEMO_SPRING.name, lat: String(DEMO_SPRING.latitude), lon: String(DEMO_SPRING.longitude), elevation: String(DEMO_SPRING.elevation_m) },
      // Balench as recorded on the field form (18 Oct 2026)
      answers: { flow_vs_past: 'more', lean_flow_lpm: '1', monsoon_flow_lpm: '3', low_flow_months: '3', dry_months: '0' },
      sites: demoDiSites(),
    }));
    flyTo(DEMO_SPRING.latitude, DEMO_SPRING.longitude, 16);
  };

  const request = useMemo(() => toRequest(form), [form]);
  const requestKey = request ? JSON.stringify(request) : '';
  const stale = !!result && requestKey !== resultKey;

  // progress text while waiting
  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed((Date.now() - t0) / 1000), 250);
    return () => window.clearInterval(id);
  }, [running]);
  const step = mode === 'demo' ? Math.min(2, Math.floor(elapsed / 0.8)) : elapsed < 4 ? 0 : elapsed < 15 ? 1 : 2;

  const run = async () => {
    if (!request || running || (mode !== 'live' && mode !== 'demo')) return;
    setRunning(true);
    setError('');
    setPlacing('none');
    try {
      const r = mode === 'live'
        ? await assess(request)
        : await new Promise<AssessResponse>((ok) => setTimeout(() => ok(mockAssess(request)), 2400));
      setResult(r);
      setResultRequest(request);
      setResultKey(JSON.stringify(request));
      setTab('A');
      if (window.innerWidth < 900) setTimeout(() => mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const addSiteFromResults = () => {
    setPlacing('site');
    mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const demo = mode === 'demo';
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M16 3C12 9 7 13.5 7 19a9 9 0 0 0 18 0c0-5.5-5-10-9-16Z" fill="var(--water)" />
            <path d="M10.5 21.5c2.5-1.2 4.5-1.2 7 0s4.3 1.1 4.8.6" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <h1>Spring Health &amp; Recharge Planner</h1>
        </div>
        <div className="top-actions">
          <StatusPill mode={mode} health={health} />
          <button type="button" className="btn btn-light" disabled={!result}
            // the full report (maps, cross-sections, tables) is built by the tool; the demo only has the short printout
            onClick={() => (result && !demo ? window.open(`/api/report/${encodeURIComponent(result.run_id)}`, '_blank', 'noopener') : window.print())}
            title={result ? 'Open the full report with maps, to save as PDF' : 'Run an assessment first'}>
            Download report
          </button>
        </div>
      </header>
      {demo && (
        <div className="demo-banner" role="status">
          <span><b>Demo data:</b> the tool server is not running. Results below are made-up examples to show how the page works.</span>
          <button type="button" className="btn btn-small" onClick={() => void connect()}>Try again</button>
        </div>
      )}
      {mode === 'unavailable' && (
        <div className="demo-banner" role="alert">
          <span>The assessment service is unavailable or still starting. Please reconnect before assessing a spring.</span>
          <button type="button" className="btn btn-small" onClick={() => void connect()}>Reconnect</button>
        </div>
      )}
      {result?.persistence?.durable === false && (
        <div className="demo-banner" role="alert">
          <span>This assessment has not been saved to the pilot archive. Download a copy before leaving this page.</span>
          <button type="button" className="btn btn-small" onClick={() => {
            const url = URL.createObjectURL(new Blob([JSON.stringify({ request: resultRequest, result }, null, 2)], { type: 'application/json' }));
            const link = document.createElement('a'); link.href = url; link.download = `${result.run_id}.json`; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }}>Download assessment</button>
        </div>
      )}

      <div className="layout">
        <aside className="panel" aria-label="Inputs">
          <div className="panel-scroll">
            {springsError && <p className="msg msg-warn">{springsError}</p>}
            {siteNotice && <p className="msg msg-info" role="status">{siteNotice} <button type="button" className="link-btn" onClick={() => setSiteNotice('')}>OK</button></p>}
            <Form form={form} setForm={setForm} springs={springs} placing={placing} setPlacing={(p) => { setPlacing(p); if (p === 'site' && result) setTab('C'); }}
              onPickSpring={pickSpring} onFocusPoint={() => { const p = springPoint(form); if (p) flyTo(p.lat, p.lon, 15); }} />
            <button type="button" className="btn btn-ghost btn-small reset" onClick={() => { setForm(() => emptyForm()); setResult(null); }}>
              Clear the form
            </button>
          </div>
          <div className="panel-foot">
            {running ? (
              <div className="progress" role="status" aria-live="polite">
                <ol>
                  {STEPS.map((s, i) => (
                    <li key={s} className={i < step ? 'done' : i === step ? 'now' : ''}>
                      <span className="tick" aria-hidden="true">{i < step ? '✓' : ''}</span>{s}
                    </li>
                  ))}
                </ol>
                <p className="hint">{Math.floor(elapsed)} s · {mode !== 'live' ? 'Demo data' : elapsed < 20 ? 'The first run after starting the tool can take up to a minute while the maps load.' : 'Still loading the map layers (only the first run after starting the tool). The steps above are a rough guide, not exact progress.'}</p>
              </div>
            ) : error ? (
              <p className="msg msg-error">Something went wrong: {error}</p>
            ) : null}
            <button type="button" className="btn btn-primary btn-big" onClick={run} disabled={!request || running || mode === 'checking' || mode === 'unavailable'}>
              {running ? <><span className="spinner" aria-hidden="true" /> Working…</> : result && !stale ? 'Assess again' : 'Assess this spring'}
            </button>
            {!request && <p className="hint center">Choose a spring location first.</p>}
          </div>
        </aside>

        <main className="main">
          <div className="map-area" ref={mapRef}>
            <MapView springs={springs} existingDi={existingDi} onUseExistingDi={useExistingDi} point={point} springName={form.spring.name} result={result} tab={tab} sites={form.sites}
              placing={effectivePlacing} canCancel={placing !== 'none'} focus={focus} onPlace={onPlace}
              terrainUrl={demo ? DEMO_TERRAIN : LIVE_TERRAIN}
              onCancelPlacing={() => setPlacing('none')}
              onSiteMove={(id, lat, lon) => setForm((f) => ({ ...f, sites: f.sites.map((s) => (s.id === id ? { ...s, latitude: +lat.toFixed(6), longitude: +lon.toFixed(6) } : s)) }))}
              onUseSpring={pickSpring} />
          </div>
          <div className="results-area">
            {result ? (
              <Results result={result} tab={tab} setTab={setTab} stale={stale} onFocus={flyTo} onAddSite={addSiteFromResults} />
            ) : (
              <HowItWorks demo={demo} onExample={loadExample} />
            )}
          </div>
        </main>
      </div>
      <PrintReport result={result} form={form} demo={demo} />
    </div>
  );
}

function StatusPill({ mode, health }: { mode: Mode; health: Health | null }) {
  if (mode === 'checking') return <span className="pill pill-grey">Connecting…</span>;
  if (mode === 'unavailable') return <span className="pill pill-amber">Service unavailable</span>;
  if (mode === 'demo') return <span className="pill pill-amber" title="The tool server did not answer at /api/health">Demo data</span>;
  return (
    <span className="pill pill-green" title={health?.map_set ? `Map set approved by ${health.map_set.approved_by} on ${health.map_set.approved_at}` : 'No approved map set'}>
      <span className="pill-dot" aria-hidden="true" />Server connected
      {health?.map_set && <span className="pill-extra">Maps {health.map_set.snapshot_id}</span>}
      {health?.offline && <span className="pill-extra">offline</span>}
    </span>
  );
}
