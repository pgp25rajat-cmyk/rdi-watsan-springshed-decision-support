import React from "react";
import { Panel, Empty, Tag, fmt, date } from "./shared.jsx";
import { useChartWidth } from "./graphics.jsx";

export const directionText = {
  increase: "Increase",
  likely_increase: "Likely increase (ranges overlap)",
  decrease: "Decrease",
  likely_decrease: "Likely decrease (ranges overlap)",
  no_clear_change: "No clear change",
  no_change: "No change",
  dry_to_flowing: "Dry → flowing",
  still_dry: "Still dry",
  same: "About the same",
};
const reportedText = {
  increase: "People say the spring gives more water now",
  same: "People say the flow is about the same",
  decrease: "People say the spring gives less water now",
};
const pumpText = {
  defunct: "Defunct",
  no_water: "No water",
  no_water_dry_season: "No water in dry season",
  poor_quality: "Working, poor water",
  working: "Working",
  broken: "Broken",
};
const outcomeText = {
  restored: "Restored",
  improved: "Improved",
  not_working_now: "Not working now",
  no_change: "No change",
  unknown: "Before-DI condition not known",
};
const tone = (d) =>
  ["increase", "likely_increase", "dry_to_flowing", "restored", "improved"].includes(d)
    ? "positive"
    : ["decrease", "likely_decrease", "not_working_now", "still_dry"].includes(d)
      ? "warning"
      : "";
const range = (p) => (p.low === p.high ? fmt(p.low, 1) : fmt(p.low, 1) + "–" + fmt(p.high, 1));
export const changeText = (c) =>
  c.direction === "dry_to_flowing" || c.direction === "still_dry"
    ? directionText[c.direction]
    : (c.mid > 0 ? "+" : "") +
      fmt(c.mid, 1) +
      " L/min" +
      (c.percent != null ? " (" + (c.percent > 0 ? "+" : "") + fmt(c.percent) + "%)" : "");

// One row per spring: earlier value (hollow) to later value (filled). Bars show the range given.
export function Dumbbell({ rows, earlier = "Before DI", later = "After DI" }) {
  const [ref, W] = useChartWidth();
  if (!rows.length) return <div ref={ref} />;
  const rowH = 58,
    T = W < 500 ? 58 : 26,
    L = 8,
    R = 16,
    H = T + rows.length * rowH + 30;
  const top = Math.max(1, ...rows.flatMap((r) => [r.before.high, r.after.high, r.monsoon_after?.high || 0])) * 1.12;
  const hasMonsoon = rows.some((r) => r.monsoon_after);
  const x = (n) => L + (n / top) * (W - L - R);
  const ticks = (W < 500 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).map((f) => top * f),
    last = ticks.length - 1,
    narrow = W < 500,
    legendX = narrow ? L + 6 : L + 40 + earlier.length * 7;
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={earlier + " and " + later + " spring flow, litres per minute"}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={T - 6} y2={H - 26} className="chart-grid" />
            <text x={x(t)} y={H - 10} textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"} className="axis">
              {fmt(t, 1)}
              {i === last ? " L/min" : ""}
            </text>
          </g>
        ))}
        <g className="axis">
          <circle cx={L + 6} cy={10} r="5" fill="white" stroke="var(--muted)" strokeWidth="2" />
          <text x={L + 16} y={14}>
            {earlier}
          </text>
          <circle cx={legendX} cy={narrow ? 26 : 10} r="5" fill="var(--accent)" />
          <text x={legendX + 10} y={narrow ? 30 : 14}>
            {later}
          </text>
          {hasMonsoon && (
            <>
              <rect x={narrow ? L + 1 : legendX + 30 + later.length * 7} y={narrow ? 37 : 5} width="10" height="10" fill="white" stroke="var(--teal)" strokeWidth="2" transform="" />
              <text x={narrow ? L + 16 : legendX + 46 + later.length * 7} y={narrow ? 46 : 14}>
                Monsoon flow, after DI
              </text>
            </>
          )}
        </g>
        {rows.map((r, i) => {
          const y = T + i * rowH + 34,
            b = r.before,
            a = r.after;
          return (
            <g key={r.key || i}>
              <text x={L} y={y - 18} className="chart-label dumbbell-name">
                {r.name}
              </text>
              <text x={W - R} y={y - 18} textAnchor="end" className={"chart-label dumbbell-change " + tone(r.change.direction)}>
                {changeText(r.change)}
              </text>
              <rect x={x(b.low) - 1} width={Math.max(2, x(b.high) - x(b.low) + 2)} y={y - 9} height="6" rx="3" fill="var(--line)">
                <title>
                  {b.record_label}: {range(b)} L/min · {b.basis_label}
                </title>
              </rect>
              <rect x={x(a.low) - 1} width={Math.max(2, x(a.high) - x(a.low) + 2)} y={y + 3} height="6" rx="3" fill="var(--accent)" opacity=".35">
                <title>
                  {a.record_label}: {range(a)} L/min · {a.basis_label}
                </title>
              </rect>
              <line x1={x(b.mid)} x2={x(a.mid)} y1={y} y2={y} stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="3 3" />
              <circle cx={x(b.mid)} cy={y} r="6" fill="white" stroke="var(--muted)" strokeWidth="2" />
              <circle cx={x(a.mid)} cy={y} r="6" fill="var(--accent)" />
              {r.monsoon_after && (
                <rect x={x(r.monsoon_after.mid) - 5} y={y - 5} width="10" height="10" fill="white" stroke="var(--teal)" strokeWidth="2">
                  <title>Monsoon flow after DI: {range(r.monsoon_after)} L/min</title>
                </rect>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function rowsFrom(state, pick) {
  return state.assessment.sites
    .map((a) => {
      const s = state.sites.find((x) => x.id === a.site_id),
        r = pick(a.impact);
      return r && r.before ? { key: s.id, name: s.name, role: a.impact.role, ...r } : null;
    })
    .filter(Boolean);
}

export function PortfolioBeforeAfter({ state }) {
  const numeric = rowsFrom(state, (i) => (i.spring_before_after?.kind === "numeric" ? i.spring_before_after : null));
  const reported = state.assessment.sites
    .map((a) => ({ a, s: state.sites.find((x) => x.id === a.site_id) }))
    .filter(({ a }) => a.impact.spring_before_after?.kind === "reported");
  const none = state.assessment.sites
    .map((a) => ({ a, s: state.sites.find((x) => x.id === a.site_id) }))
    .filter(({ a }) => !a.impact.spring_before_after);
  return (
    <Panel
      title="Dry-season spring flow: before vs after DI"
      sub="The main impact result. Dry-season flow, as DI should matter most when rain stops. Squares show monsoon flow after DI."
    >
      {numeric.length ? (
        <Dumbbell rows={numeric} />
      ) : (
        <Empty title="No numbers before DI yet">Record a visit marked “Before DI”, or add recalled flows.</Empty>
      )}
      {numeric.length > 0 && (
        <p className="caption">
          Before DI: earlier RDI reports, or the lowest record so far. After DI: the October 2026 field forms. Values
          agreed by the team; hover a point to see the source.
        </p>
      )}
      {reported.length > 0 && (
        <div className="reported-list">
          <h3>Where only the direction is known</h3>
          {reported.map(({ a, s }) => (
            <a key={s.id} href={"#/tracking?site=" + s.id} className="reported-row">
              <strong>{s.name}</strong>
              <Tag tone={tone(a.impact.spring_before_after.direction)}>
                {reportedText[a.impact.spring_before_after.direction] || a.impact.spring_before_after.direction}
              </Tag>
            </a>
          ))}
          <p className="caption">From the field form question “Flow now compared with 10–20 years ago”. No number is invented.</p>
        </div>
      )}
      {none.length > 0 && (
        <p className="caption">No spring flow before or after DI yet: {none.map(({ s }) => s.name).join(", ")}.</p>
      )}
    </Panel>
  );
}

export function PortfolioLastTwo({ state }) {
  const rows = rowsFrom(state, (i) => i.last_two);
  return (
    <Panel
      title="Spring flow: last two readings"
      sub="Readings in order: before-DI dry, after-DI dry, then after-DI monsoon (latest). The last two are compared."
    >
      {rows.length ? (
        <>
          <Dumbbell rows={rows} earlier="After DI · dry season" later="After DI · monsoon (latest)" />
          <p className="caption">
            After-DI dry-season flow compared with after-DI monsoon flow. Much of this rise is the rain season itself, so
            read it as how much the spring responds to rain. New visits will become the latest reading.
          </p>
        </>
      ) : (
        <Empty title="Two flow records are needed">Each spring needs at least two flow records.</Empty>
      )}
    </Panel>
  );
}

export function PumpBeforeAfter({ rows, compact = false }) {
  if (!rows.length) return <Empty title="No DI handpump linked yet">Add the handpump in the site details.</Empty>;
  return (
    <div className="pump-ba">
      {rows.map((p, i) => (
        <div key={(p.site || "") + p.name + i} className="pump-ba-row">
          <div>
            <strong>{p.name}</strong>
            {p.site && <span>{p.site}</span>}
          </div>
          <div className="pump-ba-states">
            <Tag>{p.before ? pumpText[p.before] || p.before : "Not known"}</Tag>
            <span aria-hidden="true">→</span>
            <Tag tone={p.after === "broken" ? "warning" : ""}>{p.after ? pumpText[p.after] || p.after : "Not checked"}</Tag>
          </div>
          <Tag tone={tone(p.outcome)}>{outcomeText[p.outcome]}</Tag>
          {!compact && p.before_note && <p className="caption">{p.before_note}</p>}
        </div>
      ))}
    </div>
  );
}

export function PortfolioPumps({ state }) {
  const rows = state.assessment.sites.flatMap((a) =>
    a.impact.handpumps_before_after.map((p) => ({ ...p, site: state.sites.find((s) => s.id === a.site_id)?.name })),
  );
  const p = state.assessment.portfolio.impact;
  return (
    <Panel
      title="Handpumps: before vs after DI"
      sub={`${p.pumps_restored} of ${p.pumps} DI handpumps were defunct before DI and work now.`}
    >
      <PumpBeforeAfter rows={rows} compact />
      <p className="caption">Agreed by the team (2026-10-24). The Kaddukhal field form had recorded the pump as broken.</p>
    </Panel>
  );
}

export function SiteBeforeAfter({ impact }) {
  const r = impact.spring_before_after;
  if (!r)
    return (
      <Empty title="No before/after spring record">
        Ask how the spring was before DI on the next visit, or record a visit marked “Before DI”.
      </Empty>
    );
  if (r.kind === "reported")
    return (
      <div className="ba-reported">
        <Tag tone={tone(r.direction)}>{reportedText[r.direction] || r.direction}</Tag>
        <p>{r.note}</p>
        <p className="caption">
          {r.evidence_label}. No flow number before DI, so the change cannot be put in L/min.
        </p>
      </div>
    );
  return (
    <>
      <Dumbbell rows={[{ name: r.metric_label, role: impact.role, ...r }]} />
      <dl className="facts">
        {[
          ["Before DI", range(r.before) + " L/min · " + r.before.basis_label],
          ["After DI", range(r.after) + " L/min · " + r.after.basis_label + (r.after.date ? " · " + date(r.after.date) : "")],
          ...(r.monsoon_after ? [["Monsoon flow after DI", range(r.monsoon_after) + " L/min"]] : []),
          [
            "Change",
            changeText(r.change) +
              (r.change.low === r.change.high ? "" : " · range " + fmt(r.change.low, 1) + " to " + fmt(r.change.high, 1) + " L/min"),
          ],
          ["Result", directionText[r.change.direction]],
        ].map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {r.after.note && <p className="caption">{r.after.note}</p>}
    </>
  );
}

export function SiteLastTwo({ impact }) {
  const r = impact.last_two;
  if (!r) return <Empty title="Two flow records are needed">The next visit will give a second record.</Empty>;
  return (
    <>
      <Dumbbell rows={[{ name: "Spring flow", ...r }]} earlier={r.before.record_label} later={r.after.record_label} />
      {r.sequence?.length > 2 && (
        <p className="caption">
          All readings: {r.sequence.map((p) => p.record_label + " " + range(p)).join(" → ")} L/min
        </p>
      )}
      <dl className="facts">
        {[
          [r.before.record_label, range(r.before) + " L/min · " + r.before.basis_label],
          [r.after.record_label, range(r.after) + " L/min · " + r.after.basis_label],
          ["Change", changeText(r.change) + " · " + directionText[r.change.direction]],
        ].map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {r.cautions.map((c) => (
        <p key={c} className="notice">
          {c}
        </p>
      ))}
    </>
  );
}

export function DIWater({ impact }) {
  const w = impact.di_water;
  if (!w.available) return <Empty title="No DI water estimate">{w.reason}</Empty>;
  return (
    <>
      <div className="roof-figure">
        <strong>{fmt(w.volume_m3)}</strong>
        <span>m³ a year can go into the ground</span>
      </div>
      <div className="method-readings">
        {w.rows.map((r) => (
          <div key={r.name}>
            <span>{r.name}</span>
            <strong>{r.roof_area_m2 == null ? "Roof not recorded" : fmt(r.roof_area_m2) + " m² roof"}</strong>
            <span>{r.volume_m3 == null ? "—" : fmt(r.volume_m3) + " m³/yr"}</span>
          </div>
        ))}
      </div>
      <p className="formula small-formula">
        roof × {fmt(w.annual_rain_mm)} mm × {w.collection} × {w.injection} ÷ 1000
      </p>
      <dl className="facts">
        {[
          ["As a steady flow", fmt(w.steady_lpm, 2) + " L/min, all year"],
          ["Best case, lean season", fmt(w.lean_lpm, 2) + " L/min, if it all came out in the 5 dry months"],
          [
            "Share of the spring gain DI could explain",
            w.share_of_gain_pct == null
              ? "Not available (needs a measured or recalled gain)"
              : "At most " + w.share_of_gain_pct + "% of the " + w.gain_metric.toLowerCase() + " gain",
          ],
        ].map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="caption">
        Rain: {w.annual_rain_source || "annual rain at the spring"}. 0.8 roof collection and 0.85 injection are the
        planner's defaults. This assumes every litre reaches this spring, so it is an upper limit.
        {w.missing_roofs?.length ? " No roof area for: " + w.missing_roofs.join(", ") + "." : ""}
      </p>
    </>
  );
}

export function ImpactSummary({ state }) {
  const p = state.assessment.portfolio.impact;
  return (
    <div className="progress-grid">
      <div>
        <span>Dry-season spring flow up after DI</span>
        <strong>
          {p.spring_numeric_up + p.spring_reported_up}
          <small> / {p.spring_numeric + p.spring_reported} springs with flow data</small>
        </strong>
        <p>{p.spring_no_data} of {p.di_sites} DI springs have no flow data yet</p>
      </div>
      <div>
        <span>Handpumps restored after DI</span>
        <strong>
          {p.pumps_restored + p.pumps_improved}
          <small> / {p.pumps} DI handpumps</small>
        </strong>
        <p>{p.pumps_not_working} not working now</p>
      </div>
      <div>
        <span>DI water into the ground</span>
        <strong>
          {fmt(p.di_volume_m3)}
          <small> m³ a year</small>
        </strong>
        <p>Upper estimate for {p.di_sites_with_volume} sites with a roof area</p>
      </div>
      <div>
        <span>Springs with readings after DI</span>
        <strong>{p.last_two}</strong>
        <p>Dry-season vs monsoon in “last two readings”</p>
      </div>
    </div>
  );
}
