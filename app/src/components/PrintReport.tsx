// A plain report that only shows when printing (see @media print in styles.css).
import type { AssessResponse, ModuleOutput } from '../api';
import type { FormState } from '../form';
import { flow, linkLabel, litres, locationClass, num, pct, range, statusLabel } from '../format';
import { vulnerabilityQuestions } from '../questions';
import { dipQuestions, textQuestions } from '../questionExtras';

function answerList(form: FormState): [string, string][] {
  const out: [string, string][] = [];
  for (const q of vulnerabilityQuestions) {
    const v = form.answers[q.id];
    if (v == null || v === '') continue;
    out.push([q.label, q.kind === 'choice' ? q.options.find(([k]) => k === v)?.[1] ?? v
      : q.kind === 'multi' ? v.split(',').map((x) => q.options.find(([k]) => k === x)?.[1] ?? x).join(', ') : `${v} ${q.unit}`]);
  }
  for (const q of textQuestions) if (form.answers[q.key]) out.push([q.label, form.answers[q.key]]);
  for (const q of dipQuestions) if (form.answers[q.key]) out.push([q.label, `${form.answers[q.key]} ${q.unit}`]);
  return out;
}

function Head<R>({ m, n }: { m: ModuleOutput<R>; n: number }) {
  return (
    <>
      <h2>
        {n}. {m.title} <span className="p-status">({statusLabel[m.status]}, {m.confidence.toLowerCase()} evidence)</span>
      </h2>
      {m.validation && <p className="p-caution">{m.validation}</p>}
    </>
  );
}

function List({ items }: { items: string[] }) {
  return items.length ? <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul> : null;
}

export default function PrintReport({ result, form, demo }: { result: AssessResponse | null; form: FormState; demo: boolean }) {
  if (!result) {
    return (
      <div className="print-report">
        <h1>Spring Health &amp; Recharge Planner</h1>
        <p>No assessment has been run yet. Choose a spring and press “Assess this spring”, then print again.</p>
      </div>
    );
  }
  const A = result.A.result;
  const B = result.B.result;
  const C = result.C.result;
  const answers = answerList(form);
  return (
    <div className="print-report">
      <header className="p-header">
        <h1>Spring report: {result.spring.name}</h1>
        <p>
          Spring Health &amp; Recharge Planner · {new Date(result.created_at).toLocaleString('en-IN', { dateStyle: 'long', timeStyle: 'short' })}
          {' '}· run {result.run_id} · map set: {result.map_set}
        </p>
        {demo && <p className="p-demo">DEMO DATA: the tool server was not running. These numbers are illustrative only.</p>}
      </header>

      <section>
        <h2>The spring</h2>
        <table className="p-table">
          <tbody>
            <tr><th>Position</th><td>{result.spring.latitude.toFixed(5)} N, {result.spring.longitude.toFixed(5)} E</td></tr>
            <tr><th>Elevation</th><td>{num(result.spring.elevation_m)} m</td></tr>
            {answers.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}
            {form.sites.length > 0 && <tr><th>DI sites planned</th><td>{form.sites.length}</td></tr>}
          </tbody>
        </table>
      </section>

      <section>
        <Head m={result.A} n={1} />
        {A ? (
          <>
            <p className="p-key">Score <b>{A.score} of 100</b>: <b>{A.class}</b> {A.kind}. {num(A.coverage_pct)}% of the score has data.</p>
            <List items={result.A.rationale} />
            <table className="p-table p-small">
              <thead><tr><th>Group</th><th>Sign</th><th>Value</th><th className="num">0-100</th><th className="num">Points</th></tr></thead>
              <tbody>
                {A.indicators.map((i) => (
                  <tr key={i.id}><td>{i.group}</td><td>{i.indicator}</td><td>{i.value}</td><td className="num">{num(i.score)}</td><td className="num">{num(i.points, 1)}</td></tr>
                ))}
              </tbody>
            </table>
            {result.A.missing_inputs.length > 0 && (
              <p><b>To improve this answer:</b> {result.A.missing_inputs.slice(0, 5).map((x) => x.needs).join(' ')}</p>
            )}
          </>
        ) : <List items={[...result.A.rationale, ...result.A.warnings]} />}
      </section>

      <section>
        <Head m={result.B} n={2} />
        {B ? (
          <>
            <p className="p-key">
              Recharge area this flow needs: about <b>{num(B.target_area_ha.mid, 1)} ha</b> (range {num(B.target_area_ha.low, 1)}–{num(B.target_area_ha.high, 1)} ha)
              {B.target_area_ha.kind === 'default' ? ', a default size: no flow reading was given' : ''}.
              Catchment to the ridge {num(B.surface_catchment.area_ha, 1)} ha
              {B.outlet_catchment ? ` (${num(B.outlet_catchment.area_ha, 1)} ha runs off straight to the outlet)` : ''}.
            </p>
            {B.recharge_zones.length > 0 && (
              <>
                <p><b>Top candidate recharge zones</b> (best first; places to inspect)</p>
                <ol>{B.recharge_zones.map((z) => <li key={z.id}>{z.id} ({linkLabel[z.link.kind].toLowerCase()}): {z.why}</li>)}</ol>
              </>
            )}
            <List items={[...(result.B.summary ?? []), ...result.B.rationale]} />
            <p className="p-caution">A first estimate from maps. Walk the zones with a geologist before spending money.</p>
          </>
        ) : <List items={[...result.B.rationale, ...result.B.warnings]} />}
      </section>

      <section>
        <Head m={result.C} n={3} />
        {C && C.sites.length > 0 ? (
          <>
            <p className="p-key">
              Water put into the ground: <b>{num(C.totals.volume_m3_per_year)} m³ a year</b> ({litres(C.totals.volume_m3_per_year)}).
              {C.totals.reaching_m3_per_year ? <> Of that, about <b>{num(C.totals.reaching_m3_per_year.mid)} m³</b> may reach the spring (range {num(C.totals.reaching_m3_per_year.low)}–{num(C.totals.reaching_m3_per_year.high)}).</> : null}
              Dry-season water equivalent <b>{flow(C.totals.added_flow_lpm_lean.mid)} L/min</b> (range {range(C.totals.added_flow_lpm_lean)}; 0 if not connected)
              {C.totals.pct_of_lean_flow ? <>, about <b>+{flow(C.totals.pct_of_lean_flow.mid)}%</b> of today's {flow(C.totals.lean_flow_lpm)} L/min</> : null}.
              {C.roofs_for_10pct != null && <> About {num(C.roofs_for_10pct)} roofs of 100 m² in a recharge zone on the spring slope could add 10%, if the assumptions hold.</>}
            </p>
            {C.safety && (
              <>
                <p><b>{C.safety.ready ? 'Before any injection' : 'Not ready for DI yet'}</b></p>
                <List items={C.safety.actions} />
              </>
            )}
            <table className="p-table p-small">
              <thead><tr><th>Site</th><th>Where</th><th className="num">Depth m</th><th className="num">m³/year</th><th className="num">Assumed to reach spring</th><th className="num">Dry-season equivalent L/min</th><th className="num">Storage rise m (illustration)</th></tr></thead>
              <tbody>
                {C.sites.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name} ({num(s.roof_area_m2)} m²)</td>
                    <td>{locationClass[s.location_class].label}</td>
                    <td className="num">{s.depth_m != null ? num(s.depth_m) : '–'}</td>
                    <td className="num">{num(s.volume_m3_per_year)}</td>
                    <td className="num">{s.reaching_m3_per_year ? `${num(s.reaching_m3_per_year.mid)} m³, ` : ''}{pct(s.share_reaching_spring.low)}–{pct(s.share_reaching_spring.high)}</td>
                    <td className="num">{flow(s.added_flow_lpm_lean.mid)} ({range(s.added_flow_lpm_lean)})</td>
                    <td className="num">{range(s.water_level_rise_m, (n) => n.toFixed(2))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <List items={[...(result.C.summary ?? []), ...result.C.rationale]} />
            <p><b>How to check if it works</b></p>
            <List items={C.monitoring_plan} />
          </>
        ) : (
          <List items={[...result.C.rationale, ...(C?.roofs_for_10pct != null ? [`About ${num(C.roofs_for_10pct)} roofs of 100 m² in a recharge zone on the spring slope could add 10% to the dry-season flow, if the assumptions hold.`] : [])]} />
        )}
      </section>

      {[result.A, result.B, result.C].some((m) => m.warnings.length) && (
        <section>
          <h2>Notes and warnings</h2>
          <List items={[...result.A.warnings, ...result.B.warnings, ...result.C.warnings].filter((w, i, all) => all.indexOf(w) === i)} />
        </section>
      )}
    </div>
  );
}
