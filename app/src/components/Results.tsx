import type { ReactNode } from 'react';
import type { AResult, AssessResponse, BResult, CResult, Feature, Indicator, ModuleOutput, RechargeZone } from '../api';
import { MONTHS, ZONE_RANK_COLORS, classColor, flow, litres, linkLabel, locationClass, num, pct, range, scoreColor, statusLabel } from '../format';
import { CrossSection, Gauge, MonthlyBars, RangeStrip, StackedBar } from './charts';
import type { Tab } from './MapView';

type Props = {
  result: AssessResponse;
  tab: Tab;
  setTab: (t: Tab) => void;
  stale: boolean;
  onFocus: (lat: number, lon: number, zoom?: number) => void;
  onAddSite: () => void;
};

const TABS: { id: Tab; label: string; key: 'A' | 'B' | 'C' }[] = [
  { id: 'A', label: 'Vulnerability', key: 'A' },
  { id: 'B', label: 'Springshed', key: 'B' },
  { id: 'C', label: 'DI impact', key: 'C' },
];

export default function Results({ result, tab, setTab, stale, onFocus, onAddSite }: Props) {
  return (
    <div className="results">
      <div className="results-head">
        <div>
          <h2 className="results-title">{result.spring.name}</h2>
          <p className="muted small">
            {result.spring.latitude.toFixed(5)}, {result.spring.longitude.toFixed(5)} · {num(result.spring.elevation_m)} m ·
            {' '}{new Date(result.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
          </p>
        </div>
      </div>
      {stale && <p className="msg msg-info">You changed the inputs since this result. Press <b>Assess this spring</b> again to update it.</p>}
      <div className="tabs" role="tablist" aria-label="Results">
        {TABS.map((t) => {
          const m = result[t.key];
          return (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`}
              className={`tab${tab === t.id ? ' on' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
              {m.status === 'provisional' && <span className="dot dot-amber" title="Provisional" />}
              {(m.status === 'unavailable' || m.status === 'failed') && <span className="dot dot-grey" title={statusLabel[m.status]} />}
            </button>
          );
        })}
      </div>
      <div className="tab-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'A' && <ModuleFrame m={result.A}>{(r) => <VulnerabilityTab m={result.A} r={r} />}</ModuleFrame>}
        {tab === 'B' && <ModuleFrame m={result.B}>{(r) => <SpringshedTab m={result.B} r={r} onFocus={onFocus} />}</ModuleFrame>}
        {tab === 'C' && <ModuleFrame m={result.C}>{(r) => <DiTab m={result.C} r={r} onAddSite={onAddSite} />}</ModuleFrame>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ shared pieces
function ModuleFrame<R>({ m, children }: { m: ModuleOutput<R>; children: (r: R) => ReactNode }) {
  const broken = m.status === 'unavailable' || m.status === 'failed' || m.result == null;
  return (
    <div className="module">
      <div className="module-head">
        <h3>{m.title}</h3>
        <span className={`badge badge-${m.status}`}>{statusLabel[m.status]}</span>
        {!broken && <span className="badge badge-conf" title="How complete the inputs were. It does not say the answer is right.">Evidence: {m.confidence}</span>}
      </div>
      {m.status === 'provisional' && !broken && (
        <p className="msg msg-amber small">Provisional: a first answer. Some inputs or checks are still missing.</p>
      )}
      {broken ? (
        <div className="unavailable">
          <p className="unavailable-title">{m.status === 'failed' ? 'This part could not run.' : 'This part has no answer for this spring yet.'}</p>
          {m.rationale.length > 0 && <ul>{m.rationale.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          {m.warnings.length > 0 && <ul className="warn-list">{m.warnings.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          {m.missing_inputs.length > 0 && <MissingList m={m} />}
        </div>
      ) : children(m.result as R)}
    </div>
  );
}

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="block">
      <h4>{title}</h4>
      <ul className="bullets">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </section>
  );
}

/** The module's answer in everyday words, shown first. */
function Plain({ items, title = 'In simple words' }: { items?: string[]; title?: string }) {
  if (!items?.length) return null;
  return (
    <section className="plain">
      <h4>{title}</h4>
      {items.map((x, i) => <p key={i}>{x}</p>)}
    </section>
  );
}

function Warnings({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <details className="warnings block">
      <summary>Notes and warnings ({items.length})</summary>
      <ul className="warn-list">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </details>
  );
}

function MissingList<R>({ m }: { m: ModuleOutput<R> }) {
  const items = [...m.missing_inputs].sort((a, b) => Number(a.id !== 'flow_vs_past') - Number(b.id !== 'flow_vs_past') || (b.weight ?? 0) - (a.weight ?? 0)).slice(0, 5);
  if (!items.length) return null;
  return (
    <section className="block">
      <h4>What would improve this answer</h4>
      <ul className="improve">
        {items.map((x) => (
          <li key={x.id}>
            <b>{x.indicator}</b>{x.weight ? <span className="muted"> · worth {num(x.weight)}% of the score</span> : null}
            <div>{x.needs}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Stat({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string }) {
  return (
    <div className="stat" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ A
function VulnerabilityTab({ m, r }: { m: ModuleOutput<AResult>; r: AResult }) {
  const groups = new Map<string, Indicator[]>();
  for (const i of r.indicators) groups.set(i.group, [...(groups.get(i.group) ?? []), i]);
  return (
    <>
      <div className="hero">
        <Gauge score={r.score} label={r.class} />
        <div className="hero-text">
          <div className="hero-class" style={{ color: classColor(r.class) }}>{r.class} {r.kind === 'exposure score' ? 'exposure' : 'vulnerability'}</div>
          <p className="small">
            {r.kind === 'exposure score'
              ? 'This is an exposure score: it is built only from the maps (rain, slope, land use) because no field answers were given. It says how exposed the place is, not how the spring itself is doing.'
              : 'Higher = more at risk of drying up or getting dirty. It combines your field answers with what the maps say about the place.'}
          </p>
          <div className="meta-row">
            <span><b>{m.confidence}</b> evidence</span>
            <span><b>{num(r.coverage_pct)}%</b> of the score has data</span>
          </div>
          <div className="coverage" aria-hidden="true"><span style={{ width: `${Math.min(100, r.coverage_pct)}%` }} /></div>
        </div>
      </div>
      <Plain title="Why this score" items={m.summary} />
      <Bullets title="Biggest contributors" items={m.rationale.slice(m.summary?.length ?? 0)} />
      <section className="block">
        <h4>What makes up the score</h4>
        <p className="hint">Each bar is how worrying that sign is (0–100). Points = its share of the final score.</p>
        {[...groups.entries()].map(([g, list]) => (
          <div className="ind-group" key={g}>
            <div className="ind-group-head">
              <span>{g}</span>
              <span className="muted">{num(list.reduce((s, i) => s + i.points, 0), 1)} pts</span>
            </div>
            {list.map((i) => (
              <div className="ind" key={i.id} title={i.why}>
                <div className="ind-top">
                  <span className="ind-name">{i.indicator}</span>
                  <span className="ind-pts">+{num(i.points, 1)}</span>
                </div>
                <div className="ind-bar-row">
                  <div className="ind-bar"><span style={{ width: `${i.score}%`, background: scoreColor(i.score) }} /></div>
                  <span className="ind-val">{i.value}</span>
                </div>
                <div className="ind-why">{i.why}{i.comparison ? <span className="muted"> · {i.comparison}</span> : null}</div>
              </div>
            ))}
          </div>
        ))}
      </section>
      {(r.context.length > 0 || r.nearest_dataset_spring) && (
        <section className="block">
          <h4>About the place</h4>
          <ul className="bullets muted-bullets">
            {r.nearest_dataset_spring && (
              <li>Nearest spring in the dataset: {r.nearest_dataset_spring.spring_name} ({r.nearest_dataset_spring.record_id}), {num(r.nearest_dataset_spring.distance_m)} m away</li>
            )}
            {r.elevation_gap_m != null && Math.abs(r.elevation_gap_m) >= 1 && <li>Your elevation and the map elevation differ by {num(Math.abs(r.elevation_gap_m))} m</li>}
            {r.context.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </section>
      )}
      <Warnings items={m.warnings} />
      <MissingList m={m} />
    </>
  );
}

// ------------------------------------------------------------------ B
function SpringshedTab({ m, r, onFocus }: { m: ModuleOutput<BResult>; r: BResult; onFocus: Props['onFocus'] }) {
  const zones = r.recharge_zones;
  const onSlope = zones.filter((z) => z.link.kind === 'Surface slope').length;
  return (
    <>
      <p className="msg msg-caution">Candidate zones from maps: places to inspect, not sites ready for works. Walk them with a geologist before spending money.</p>
      <Plain title="How this area was mapped" items={m.summary} />
      <div className="stats">
        <Stat label="Recharge area needed" accent="var(--green)"
          value={<>{num(r.target_area_ha.mid, 1)} <small>ha</small></>}
          sub={r.target_area_ha.kind === 'default'
            ? <><b className="flag-default">Default size</b>: no flow reading was given</>
            : `Could be ${num(r.target_area_ha.low, 1)} – ${num(r.target_area_ha.high, 1)} ha`} />
        <Stat label="Catchment to the ridge" accent="var(--water)"
          value={r.surface_catchment.geojson || r.surface_catchment.area_ha ? <>{num(r.surface_catchment.area_ha, 1)} <small>ha</small></> : '–'}
          sub={r.outlet_catchment
            ? `The valley above the spring. ${num(r.outlet_catchment.area_ha, 1)} ha runs off straight to the outlet`
            : 'The valley above the spring'} />
        <Stat label="Top recharge zones" accent="var(--earth)"
          value={<>{zones.length}</>}
          sub={zones.length === 0 ? 'None found' : onSlope === zones.length ? 'All on the spring slope'
            : onSlope === 0 ? 'All beyond the spring slope' : `${onSlope} on the spring slope, ${zones.length - onSlope} beyond`} />
      </div>
      {r.streams_block_zones === false && <p className="small"><b>Streams:</b> not treated as barriers (your choice), so zones may cross a stream.</p>}

      <section className="block">
        <h4>Best candidate places to recharge this spring</h4>
        <p className="hint">Ranked by how well the ground soaks up rain, how surely its water reaches the spring, and how close it is. Click a zone to see it on the map.</p>
        {zones.length > 0 ? (
          <ol className="zone-list">
            {zones.map((z) => <ZoneCard key={z.id} z={z} onFocus={onFocus} />)}
          </ol>
        ) : <p className="hint">No zone was found. {r.search.searched}</p>}
        <p className="hint">{r.search.searched}</p>
        {r.search.checks.length > 0 && (
          <details className="checks">
            <summary>How to check the zones in the field</summary>
            <ul>{r.search.checks.map((x) => <li key={x}>{x}</li>)}</ul>
          </details>
        )}
      </section>

      {r.geology && (
        <p className="small">
          <b>Rock at the spring:</b> {r.geology.unit} ({r.geology.rock_class.toLowerCase()})
          {r.geology.nearest_fault_m != null && <>. Nearest mapped fault: {num(r.geology.nearest_fault_m)} m ({r.geology.nearest_fault_name})</>}.
        </p>
      )}

      {r.factors.length > 0 && (
        <section className="block">
          <h4>What the recharge map looks at</h4>
          <ul className="factors">
            {r.factors.map((f) => (
              <li key={f.id}>
                <div className="factor-top"><span>{f.name}</span><b>{num(f.weight_pct)}%</b></div>
                <div className="factor-bar"><span style={{ width: `${f.weight_pct}%` }} /></div>
                <div className="hint">{f.how}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Bullets title="How the zones were found" items={m.rationale} />
      <MissingList m={m} />
      <Warnings items={m.warnings} />
    </>
  );
}

/** Middle of a polygon's outline, for flying the map to it. */
function middleOf(f: Feature | null): [number, number] | null {
  let w = Infinity, so = Infinity, e = -Infinity, n = -Infinity;
  const add = (c: any) => {
    if (typeof c[0] === 'number') { w = Math.min(w, c[0]); e = Math.max(e, c[0]); so = Math.min(so, c[1]); n = Math.max(n, c[1]); }
    else for (const x of c) add(x);
  };
  if (f?.geometry?.coordinates) add(f.geometry.coordinates);
  return Number.isFinite(w) ? [(so + n) / 2, (w + e) / 2] : null;
}

function ZoneCard({ z, onFocus }: { z: RechargeZone; onFocus: Props['onFocus'] }) {
  const mid = middleOf(z.geojson);
  const linked = z.link.kind !== 'Surface slope';
  return (
    <li>
      <button type="button" className="zone-card" style={{ borderLeftColor: ZONE_RANK_COLORS[z.rank - 1] }}
        onClick={() => mid && onFocus(mid[0], mid[1], 15)} disabled={!mid}>
        <span className="zone-card-top">
          <span className="zone-id">{z.id}</span>
          <span className={`zone-link${linked ? ' linked' : ''}`}>{linkLabel[z.link.kind]}</span>
          <span className="muted small">{num(z.area_ha, 1)} ha · {z.distance_m < 60 ? 'at the spring' : `${num(z.distance_m)} m away`} · {num(z.height_above_spring_m.mean)} m above</span>
        </span>
        <span className="small">{z.why}</span>
        <StackedBar shares={z.land_cover_pct} />
        <dl className="facts">
          <div><dt>Recharge potential</dt><dd>{Math.round(z.mean_potential * 100)}%</dd></div>
          <div><dt>Mean slope</dt><dd>{num(z.mean_slope_deg)}°</dd></div>
          {z.soil && <div><dt>Soil (top 30 cm)</dt><dd>{z.soil.class.split(' (')[0]}</dd></div>}
          {z.soil_depth_cm != null && <div><dt>Soil depth</dt><dd>{z.soil_depth_cm >= 200 ? '200 cm or more' : `about ${num(z.soil_depth_cm)} cm`}</dd></div>}
          <div><dt>Inside the catchment</dt><dd>{z.in_catchment_pct}%</dd></div>
          {linked && <div className="wide"><dt>Link to the spring</dt><dd>{z.link.name}</dd></div>}
          {z.rock_unit && <div className="wide"><dt>Rock</dt><dd>{z.rock_unit}</dd></div>}
        </dl>
      </button>
    </li>
  );
}

// ------------------------------------------------------------------ C
function days(d: number) {
  return d < 1 ? 'under a day' : d < 60 ? `${num(d)} days` : d < 730 ? `${num(d / 30.4)} months` : `${num(d / 365)} years`;
}

function oneRoofM3(r: CResult): number | null {
  const get = (id: string) => {
    const a = r.assumptions.find((x) => x.id === id);
    return a && typeof a.value === 'number' ? a.value : null;
  };
  const c = get('collection_coefficient');
  const e = get('injection_efficiency');
  if (c == null || e == null || !r.rain.annual_mm) return null;
  return (100 * r.rain.annual_mm) / 1000 * c * e;
}

/** The key answer: how much of the injected water is expected to reach the spring. */
function Takeaway({ r }: { r: CResult }) {
  const t = r.totals;
  const into = t.volume_m3_per_year;
  if (!t.reaching_m3_per_year || !into) return null;
  const share = (v: number) => Math.round((100 * v) / into);
  const exact = (100 * t.reaching_m3_per_year.mid) / into;
  const mid = Math.round(exact);
  const verdict = mid >= 30 ? 'Likely to recharge the spring, if the handpump is connected to it.'
    : mid >= 10 ? 'Some of the water may recharge the spring; most of it is expected to go elsewhere.'
      : 'Little of this water is expected to reach the spring. Consider a site inside a top recharge zone (R1-R3).';
  return (
    <section className={`takeaway ${mid >= 30 ? 'takeaway-good' : mid >= 10 ? 'takeaway-mid' : 'takeaway-low'}`}>
      <div className="takeaway-num">{exact > 0 && exact < 1 ? '<1' : mid}<small>%</small></div>
      <div>
        <h4>of the water injected may reach the spring</h4>
        <p>About {num(t.reaching_m3_per_year.mid)} of {num(into)} m³ a year (range {share(t.reaching_m3_per_year.low)}–{share(t.reaching_m3_per_year.high)}%; 0 if the handpump is not connected). {verdict}</p>
      </div>
    </section>
  );
}

function DiTab({ m, r, onAddSite }: { m: ModuleOutput<CResult>; r: CResult; onAddSite: () => void }) {
  const t = r.totals;
  const roof = oneRoofM3(r);
  if (r.sites.length === 0) {
    return (
      <>
        <div className="empty-di">
          <svg className="empty-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5C9 7 5.5 10.6 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10.6 15 7 12 2.5Z" fill="currentColor" /></svg>
          <h4>No DI sites yet</h4>
          <p>Add the defunct handpumps you plan to use on the map, then press <b>Assess this spring</b> again to see how much water they could add.</p>
          <button type="button" className="btn btn-primary" onClick={onAddSite}>+ Add DI site on the map</button>
        </div>
        {(roof != null || r.roofs_for_10pct != null) && (
          <section className="block">
            <h4>What one roof could do</h4>
            <ul className="bullets">
              {roof != null && <li>One 100 m² roof in {num(r.rain.annual_mm)} mm of rain could put about <b>{num(roof)} m³</b> ({litres(roof)}) a year into the ground.</li>}
              {r.roofs_for_10pct != null && <li>About <b>{num(r.roofs_for_10pct)}</b> roofs of 100 m² inside a recharge zone on the spring slope could add 10% to the dry-season flow, if 60% of their water reaches the spring and all of it comes out in the dry months.</li>}
            </ul>
          </section>
        )}
        <Bullets title="Notes" items={m.rationale} />
        <Warnings items={m.warnings} />
      </>
    );
  }
  const maxLean = Math.max(t.added_flow_lpm_lean.high, 0.01);
  return (
    <>
      <Takeaway r={r} />
      <Plain title="Where the water goes" items={m.summary} />
      {r.safety && !r.safety.ready && (
        <section className="safety safety-stop">
          <h4>Not ready for DI yet</h4>
          <ul className="safety-list">{r.safety.actions.map((a) => <li key={a}>{a}</li>)}</ul>
        </section>
      )}
      <div className="stats">
        <Stat label="Water put into the ground" accent="var(--water)"
          value={<>{num(t.volume_m3_per_year)} <small>m³/year</small></>} sub={litres(t.volume_m3_per_year)} />
        {t.reaching_m3_per_year && (
          <Stat label="Of that, reaching the spring" accent="var(--green)"
            value={<>{num(t.reaching_m3_per_year.mid)} <small>m³/year</small></>}
            sub={`Range ${num(t.reaching_m3_per_year.low)} – ${num(t.reaching_m3_per_year.high)} m³; 0 if not connected`} />
        )}
        <Stat label="Dry-season water equivalent" accent="var(--green)"
          value={<>{flow(t.added_flow_lpm_lean.mid)} <small>L/min</small></>}
          sub={<>Range {range(t.added_flow_lpm_lean)} L/min; 0 if not connected<RangeStrip {...t.added_flow_lpm_lean} max={maxLean * 1.1} /></>} />
        {t.pct_of_lean_flow && (
          <Stat label="Share of today's dry-season flow" accent="var(--green)"
            value={<>+{flow(t.pct_of_lean_flow.mid)}<small>%</small></>}
            sub={`${range(t.pct_of_lean_flow)}% of ${flow(t.lean_flow_lpm)} L/min`} />
        )}
        {r.roofs_for_10pct != null && (
          <Stat label="Roofs for +10% flow" accent="var(--earth)" value={num(r.roofs_for_10pct)} sub="100 m² roofs in a zone on the spring slope, if the assumptions hold" />
        )}
      </div>
      <p className="hint">These are planning scenarios: the water the sites could add if the assumed share reaches the spring and all of it comes out in the dry months. Only monitoring can show the real gain, which could be zero.</p>
      {!t.pct_of_lean_flow && <p className="hint">Add the lean-season flow in step 2 to see this as a share of today's flow.</p>}

      <section className="block">
        <h4>Each DI site</h4>
        <ol className="site-cards">
          {r.sites.map((s, i) => {
            const lc = locationClass[s.location_class];
            return (
              <li key={s.id} className="site-card" style={{ borderLeftColor: lc.color }}>
                <div className="site-card-head">
                  <span className="site-num sm" style={{ background: lc.color }}>{i + 1}</span>
                  <b>{s.name}</b>
                  <span className="badge" style={{ background: lc.color }}>{lc.label}</span>
                </div>
                <p className="small site-note">{s.location_note}</p>
                <dl className="site-facts">
                  <div><dt>Injected / year</dt><dd>{num(s.volume_m3_per_year)} m³{s.runoff_m3_per_year != null && <span className="muted"> of {num(s.runoff_m3_per_year)} m³ roof runoff</span>}</dd></div>
                  <div><dt>Assumed to reach spring</dt><dd>{s.reaching_m3_per_year ? `${num(s.reaching_m3_per_year.mid)} m³ (` : ''}{pct(s.share_reaching_spring.mid)}{s.reaching_m3_per_year ? ')' : ''} <span className="muted">({pct(s.share_reaching_spring.low)}–{pct(s.share_reaching_spring.high)}; 0 if not connected)</span></dd></div>
                  {s.depth_m != null && <div><dt>Handpump depth</dt><dd>{num(s.depth_m)} m{s.depth_given === false ? <span className="muted"> (assumed)</span> : null}{s.flow_path ? <span className="muted"> · injects {Math.abs(s.flow_path.injection_elevation_m - s.flow_path.spring_elevation_m)} m {s.flow_path.injection_elevation_m >= s.flow_path.spring_elevation_m ? 'above' : 'below'} the spring</span> : null}</dd></div>}
                  {s.flow_path && <div><dt>Hydraulic gradient</dt><dd>{s.flow_path.hydraulic_gradient.toFixed(2)} <span className="muted">({num(s.flow_path.length_m)} m path)</span></dd></div>}
                  <div><dt>Dry-season equivalent</dt><dd>{flow(s.added_flow_lpm_lean.mid)} L/min <span className="muted">({range(s.added_flow_lpm_lean)})</span></dd></div>
                  <div><dt>Storage rise (illustration)</dt><dd>{range(s.water_level_rise_m, (n) => n.toFixed(2))} m</dd></div>
                  <div><dt>Travel time (rough)</dt><dd>{s.travel_time_days ? `${days(s.travel_time_days.low)} – ${days(s.travel_time_days.high)}` : '–'}</dd></div>
                  <div><dt>Roof · distance</dt><dd>{num(s.roof_area_m2)} m² · {num(s.distance_to_spring_m)} m{s.height_above_spring_m != null ? `, ${s.height_above_spring_m >= 0 ? `${num(s.height_above_spring_m)} m above` : `${num(-s.height_above_spring_m)} m below`}` : ''}</dd></div>
                </dl>
                {s.flow_path && s.flow_path.profile.length > 1 && (
                  <details className="xsec-box" open={i === 0}>
                    <summary>How the water would travel to the spring (cross-section)</summary>
                    <CrossSection path={s.flow_path} name={s.name} />
                    <p className="hint">Ground along the straight line from the handpump to the spring (heights stretched to be readable). The dashed blue arrow is the assumed path of the injected water; {s.flow_path.gradient_basis}.
                      {s.flow_path.valley_between_m ? ` The ground dips about ${s.flow_path.valley_between_m} m below the spring on the way, so some water may come out in that valley first.` : ''}</p>
                  </details>
                )}
                {s.flags.length > 0 && <ul className="flags">{s.flags.map((f, k) => <li key={k}>{f}</li>)}</ul>}
              </li>
            );
          })}
        </ol>
      </section>

      {(r.rain.monthly_mm || r.monthly_injection_m3) && (
        <section className="block">
          <h4>Through the year</h4>
          <p className="hint">Most water goes in during the monsoon (June–September). It comes out slowly over the following months.</p>
          <div className="monthly-pair">
            {r.rain.monthly_mm && <MonthlyBars title="Rain" unit="mm" values={r.rain.monthly_mm} color="#7fb3d8" />}
            {r.monthly_injection_m3 && <MonthlyBars title="Water put into the ground, all sites" unit="m³" values={r.monthly_injection_m3} color="#0b6e8a" />}
          </div>
          <p className="hint">Rain: {num(r.rain.annual_mm)} mm a year ({r.rain.source}).{r.rain.snow_mm ? ` Snow: about ${num(r.rain.snow_mm)} mm of water a winter (ERA5); ${num(r.rain.snow_used_mm ?? 0)} mm counted as melting off the roofs in January–March.` : ''}</p>
          <details className="table-view">
            <summary>Show as a table</summary>
            <div className="table-wrap">
              <table className="table compact">
                <thead><tr><th>Month</th>{MONTHS.map((mo) => <th key={mo} className="num">{mo}</th>)}</tr></thead>
                <tbody>
                  {r.rain.monthly_mm && <tr><td>Rain (mm)</td>{r.rain.monthly_mm.map((v, i) => <td key={i} className="num">{num(v)}</td>)}</tr>}
                  {r.monthly_injection_m3 && <tr><td>Into ground (m³)</td>{r.monthly_injection_m3.map((v, i) => <td key={i} className="num">{num(v, 1)}</td>)}</tr>}
                </tbody>
              </table>
            </div>
          </details>
        </section>
      )}

      <Bullets title="What this means" items={m.rationale} />
      <Bullets title="How to check if it works" items={r.monitoring_plan} />
      <Bullets title="For comparison" items={r.benchmarks} />
      {r.assumptions.length > 0 && (
        <section className="block">
          <h4>Assumptions used</h4>
          <ul className="bullets assumption-list">
            {r.assumptions.map((a) => (
              <li key={a.id}>
                <b>{a.label}:</b> {typeof a.value === 'number' ? (a.unit === 'share' ? pct(a.value) : num(a.value, 2)) : a.value} {a.unit === 'share' ? '' : a.unit}
                <div className="hint">{a.note}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Warnings items={m.warnings} />
    </>
  );
}

// ------------------------------------------------------------------ before the first result
export function HowItWorks({ demo, onExample }: { demo: boolean; onExample: () => void }) {
  return (
    <div className="how">
      <h2>How it works</h2>
      <p>Tell the tool about one spring. In about half a minute you get three answers, drawn on the map.</p>
      <ol className="how-list">
        <li>
          <span className="how-icon how-a" aria-hidden="true">A</span>
          <div><b>Vulnerability</b><p>A score from 0 to 100: how much at risk the spring is, and why.</p></div>
        </li>
        <li>
          <span className="how-icon how-b" aria-hidden="true">B</span>
          <div><b>Springshed</b><p>The three best places to recharge the spring, on its own slope or beyond the ridge, ranked.</p></div>
        </li>
        <li>
          <span className="how-icon how-c" aria-hidden="true">C</span>
          <div><b>DI impact</b><p>How much extra water rooftop rain put into defunct handpumps could give the spring in the dry months.</p></div>
        </li>
      </ol>
      <p className="hint">Start with step 1 on the left. Field answers and DI sites are optional but make the answer better.</p>
      <button type="button" className="btn" onClick={onExample}>{demo ? 'Fill in the example spring' : 'Try an example spring'}</button>
    </div>
  );
}
