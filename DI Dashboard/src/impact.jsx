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
const shortChange = (c) =>
  c.direction === "dry_to_flowing"
    ? "Flows"
    : c.direction === "still_dry"
      ? "Dry"
      : (c.mid > 0 ? "+" : "") + fmt(c.mid, 1);

// One row per spring: name on the left, then earlier value (hollow) to later value (filled), with the monsoon
// flow (square) on the same row line. Bars show the range given; the change is on the right.
export function Dumbbell({ rows, earlier = "Before DI", later = "After DI" }) {
  const [ref, W] = useChartWidth();
  if (!rows.length) return <div ref={ref} />;
  const narrow = W < 560,
    tiny = W < 400,
    hasMonsoon = rows.some((r) => r.monsoon_after),
    rowH = 40,
    T = narrow ? (hasMonsoon ? 62 : 44) : 34,
    LW = Math.min(narrow ? 100 : 150, Math.max(70, 8 + 7.5 * Math.max(...rows.map((r) => r.name.length)))),
    RW = tiny ? 50 : narrow ? 118 : 150,
    H = T + rows.length * rowH + 28;
  const top =
    Math.max(1, ...rows.flatMap((r) => [r.before.high, r.after.high, r.monsoon_after?.high || 0])) * 1.08;
  const x0 = LW + 12,
    x1 = W - RW,
    x = (n) => x0 + (n / top) * (x1 - x0);
  const ticks = (tiny ? [0, 1] : narrow ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).map((f) => top * f),
    last = ticks.length - 1;
  const legend = [
    ["hollow", earlier],
    ["filled", later],
    ...(hasMonsoon ? [["square", "Monsoon flow, after DI"]] : []),
  ];
  let lx = x0;
  return (
    <div className="chart" ref={ref}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={earlier + " and " + later + " spring flow, litres per minute"}
      >
        <g className="axis">
          {legend.map(([kind, label], k) => {
            const lxNow = narrow ? 6 : lx,
              ly = narrow ? 10 + k * 17 : 10;
            if (!narrow) lx += 34 + label.length * 6.6;
            return (
              <g key={kind}>
                {kind === "square" ? (
                  <rect
                    x={lxNow - 5}
                    y={ly - 5}
                    width="10"
                    height="10"
                    fill="white"
                    stroke="var(--teal)"
                    strokeWidth="2"
                  />
                ) : (
                  <circle
                    cx={lxNow}
                    cy={ly}
                    r="5"
                    fill={kind === "filled" ? "var(--accent)" : "white"}
                    stroke={kind === "filled" ? "none" : "var(--muted)"}
                    strokeWidth="2"
                  />
                )}
                <text x={lxNow + 11} y={ly + 4}>
                  {label}
                </text>
              </g>
            );
          })}
        </g>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={T - 4} y2={H - 24} className="chart-grid" />
            <text
              x={x(t)}
              y={H - 8}
              textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}
              className="axis"
            >
              {fmt(t, 1)}
              {i === last ? " L/min" : ""}
            </text>
          </g>
        ))}
        {rows.map((r, i) => {
          const y = T + i * rowH + rowH / 2,
            b = r.before,
            a = r.after,
            m = r.monsoon_after;
          return (
            <g key={r.key || i}>
              <line x1={x0} x2={x1} y1={y} y2={y} className="chart-grid" />
              <text x={LW} y={y + 4} textAnchor="end" className="chart-label dumbbell-name">
                {r.name}
              </text>
              <text
                x={W - 2}
                y={y + 4}
                textAnchor="end"
                className={(narrow ? "axis" : "chart-label") + " dumbbell-change " + tone(r.change.direction)}
              >
                {tiny ? shortChange(r.change) : changeText(r.change)}
              </text>
              <rect
                x={x(b.low) - 1}
                width={Math.max(2, x(b.high) - x(b.low) + 2)}
                y={y - 3}
                height="6"
                rx="3"
                fill="var(--line)"
              >
                <title>
                  {b.record_label}: {range(b)} L/min · {b.basis_label}
                </title>
              </rect>
              <rect
                x={x(a.low) - 1}
                width={Math.max(2, x(a.high) - x(a.low) + 2)}
                y={y - 3}
                height="6"
                rx="3"
                fill="var(--accent)"
                opacity=".25"
              >
                <title>
                  {a.record_label}: {range(a)} L/min · {a.basis_label}
                </title>
              </rect>
              {m && (
                <line
                  x1={x(a.mid)}
                  x2={x(m.mid)}
                  y1={y}
                  y2={y}
                  stroke="var(--teal)"
                  strokeWidth="1.5"
                  opacity=".45"
                />
              )}
              <line x1={x(b.mid)} x2={x(a.mid)} y1={y} y2={y} stroke="var(--muted)" strokeWidth="2" />
              <circle cx={x(b.mid)} cy={y} r="6" fill="white" stroke="var(--muted)" strokeWidth="2">
                <title>
                  {b.record_label}: {range(b)} L/min
                </title>
              </circle>
              <circle cx={x(a.mid)} cy={y} r="6" fill="var(--accent)">
                <title>
                  {a.record_label}: {range(a)} L/min
                </title>
              </circle>
              {m && (
                <rect
                  x={x(m.mid) - 5}
                  y={y - 5}
                  width="10"
                  height="10"
                  fill="white"
                  stroke="var(--teal)"
                  strokeWidth="2"
                >
                  <title>Monsoon flow after DI: {range(m)} L/min</title>
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
  const numeric = rowsFrom(state, (i) =>
    i.spring_before_after?.kind === "numeric" ? i.spring_before_after : null,
  );
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
        <Empty title="No numbers before DI yet">
          Record a visit marked “Before DI”, or add recalled flows.
        </Empty>
      )}
      {numeric.length > 0 && (
        <p className="caption">
          Before DI: earlier RDI reports, or the lowest record so far. After DI: the October 2026 field forms.
          Values agreed by the team; hover a point to see the source.
        </p>
      )}
      {reported.length > 0 && (
        <div className="reported-list">
          <h3>Where only the direction is known</h3>
          {reported.map(({ a, s }) => (
            <a key={s.id} href={"#/tracking?site=" + s.id} className="reported-row">
              <strong>{s.name}</strong>
              <Tag tone={tone(a.impact.spring_before_after.direction)}>
                {reportedText[a.impact.spring_before_after.direction] ||
                  a.impact.spring_before_after.direction}
              </Tag>
            </a>
          ))}
          <p className="caption">
            From the field form question “Flow now compared with 10–20 years ago”. No number is invented.
          </p>
        </div>
      )}
      {none.length > 0 && (
        <p className="caption">
          No spring flow before or after DI yet: {none.map(({ s }) => s.name).join(", ")}.
        </p>
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
            After-DI dry-season flow compared with after-DI monsoon flow. Much of this rise is the rain season
            itself, so read it as how much the spring responds to rain. New visits will become the latest
            reading.
          </p>
        </>
      ) : (
        <Empty title="Two flow records are needed">Each spring needs at least two flow records.</Empty>
      )}
    </Panel>
  );
}

const statusTone = (v) =>
  v === "working" ? "positive" : ["broken", "no_water", "defunct"].includes(v) ? "warning" : "";

// One row per handpump: condition before DI, condition now, and what else people or the team noted.
export function PumpBeforeAfter({ rows }) {
  if (!rows.length)
    return <Empty title="No DI handpump linked yet">Add the handpump in the site details.</Empty>;
  return (
    <table className="pump-table">
      <thead>
        <tr>
          <th>Handpump</th>
          <th>Before DI</th>
          <th>After DI</th>
          <th>Remarks</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => (
          <tr key={(p.site || "") + p.name + i}>
            <td>
              <strong>{p.name}</strong>
              {p.site && <span>{p.site}</span>}
            </td>
            <td data-label="Before DI">
              <Tag tone={statusTone(p.before)}>{p.before ? pumpText[p.before] || p.before : "Not known"}</Tag>
            </td>
            <td data-label="After DI">
              <Tag tone={statusTone(p.after)}>{p.after ? pumpText[p.after] || p.after : "Not checked"}</Tag>
            </td>
            <td data-label="Remarks">{p.remarks || p.before_note || "–"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PortfolioPumps({ state }) {
  const rows = state.assessment.sites.flatMap((a) =>
    a.impact.handpumps_before_after.map((p) => ({
      ...p,
      site: state.sites.find((s) => s.id === a.site_id)?.name,
    })),
  );
  const p = state.assessment.portfolio.impact;
  return (
    <Panel
      title="Handpumps: before vs after DI"
      sub={`${p.pumps_restored} of ${p.pumps} DI handpumps were defunct before DI and work now.`}
    >
      <PumpBeforeAfter rows={rows} />
    </Panel>
  );
}

const areaText = {
  access: "Water at home",
  quality: "Water quality",
  vegetation: "Vegetation and farming",
  livelihoods: "Farming and income",
  upkeep: "Upkeep",
  hygiene: "Hygiene",
  sanitation: "Toilets",
  education: "School",
  equity: "Who benefits",
};
const assetText = {
  spring: "Spring",
  handpump: "Handpump",
  village: "Village",
};

// What people told us changed for them, from the community interaction part of the field forms.
export function BeyondWater({ impact }) {
  const { story, changes } = impact.beyond_water || {};
  if (!story && !changes?.length)
    return (
      <Empty title="Nothing recorded yet">Ask people what has changed for them on the next visit.</Empty>
    );
  return (
    <>
      {story && <blockquote className="beyond-story">{story}</blockquote>}
      {changes?.length > 0 && (
        <table className="pump-table beyond-table">
          <thead>
            <tr>
              <th>What changed</th>
              <th>Before DI</th>
              <th>Now</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c, i) => (
              <tr key={i}>
                <td>
                  <strong>{areaText[c.area] || c.area}</strong>
                  <span>{assetText[c.asset] || "Village"}</span>
                </td>
                <td data-label="Before DI">{c.before}</td>
                <td data-label="Now">
                  <Tag
                    tone={c.direction === "better" ? "positive" : c.direction === "worse" ? "warning" : ""}
                  >
                    {{
                      better: "Better",
                      worse: "Needs attention",
                      same: "No change",
                      unclear: "Unclear",
                    }[c.direction] || c.direction}
                  </Tag>{" "}
                  {c.after}
                  {c.caveat && <small>{c.caveat}</small>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="caption">From what people told us on the October 2026 field visit.</p>
    </>
  );
}

export function PortfolioBeyondWater({ state }) {
  const rows = state.assessment.sites
    .map((a) => ({ a, s: state.sites.find((s) => s.id === a.site_id) }))
    .filter(({ a }) => a.impact.beyond_water?.story);
  if (!rows.length) return null;
  return (
    <Panel title="Impact beyond water" sub="What people told us on the field visit.">
      <div className="beyond-grid">
        {rows.map(({ a, s }) => (
          <a key={s.id} href={"#/tracking?site=" + s.id + "&asset=village"} className="beyond-card">
            <strong>{s.name}</strong>
            <span>{s.village}</span>
            <p>{a.impact.beyond_water.story}</p>
          </a>
        ))}
      </div>
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
      <Dumbbell
        rows={[{ name: r.metric === "lean_flow_lpm" ? "Dry season" : "On the day", role: impact.role, ...r }]}
      />
      <dl className="facts">
        {[
          ["Before DI", range(r.before) + " L/min · " + r.before.basis_label],
          [
            "After DI",
            range(r.after) +
              " L/min · " +
              r.after.basis_label +
              (r.after.date ? " · " + date(r.after.date) : ""),
          ],
          ...(r.monsoon_after ? [["Monsoon flow after DI", range(r.monsoon_after) + " L/min"]] : []),
          [
            "Change",
            changeText(r.change) +
              (r.change.low === r.change.high
                ? ""
                : " · range " + fmt(r.change.low, 1) + " to " + fmt(r.change.high, 1) + " L/min"),
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
      <Dumbbell
        rows={[{ name: "Spring flow", ...r }]}
        earlier={r.before.record_label}
        later={r.after.record_label}
      />
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

const span = (r, d = 1) => fmt(r[1], d) + " (range " + fmt(r[0], d) + "–" + fmt(r[2], d) + ")";

export function RainInfo({ impact }) {
  const w = impact.di_water;
  if (!w.annual_rain_mm)
    return <Empty title="No rainfall value">Annual rain at the spring is not recorded.</Empty>;
  return (
    <>
      <dl className="facts">
        {[
          ["Yearly rain", fmt(w.annual_rain_mm) + " mm · " + w.annual_rain_source],
          ...(w.rain_chirps_mm
            ? [["Satellite estimate (CHIRPS)", fmt(w.rain_chirps_mm) + " mm, for comparison"]]
            : []),
          ...(w.monsoon_share_pct
            ? [["Falls in the monsoon (Jun–Sep)", fmt(w.monsoon_share_pct) + "%"]]
            : []),
          ...(w.dry_season_mm ? [["Dry-season rain", fmt(w.dry_season_mm) + " mm (CHIRPS)"]] : []),
          [
            "Winter snow at the spring's height",
            fmt(w.snow_mm) + " mm water equivalent; half counted as melting into the gutters",
          ],
          ["Rain used for DI", fmt(w.rain_used_mm) + " mm a year"],
        ].map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="caption">
        Same source order as the planner: IMD rain gauges first, satellite only when gauges are missing.
      </p>
    </>
  );
}

// Rain on the roof, collected, injected, and the part that may reach the spring (planner Module C).
export function WaterSteps({ w }) {
  const steps = [
    ["Rain on the DI roofs", w.collected_m3 / w.collection, "roof area × rain used"],
    ["Rain collected", w.collected_m3, "× " + w.collection + " (gutter, pipe, splash losses)"],
    ["Injected into the aquifer", w.volume_m3, "× " + w.injection + " (first flush, overflow, clogging)"],
    [
      "May reach the spring",
      w.reaching_m3[1],
      "range " + fmt(w.reaching_m3[0]) + "–" + fmt(w.reaching_m3[2]) + " m³",
    ],
  ];
  return (
    <div className="water-steps">
      {steps.map(([label, value, note], i) => (
        <div key={label} className={i === 3 ? "final" : ""}>
          <span>{label}</span>
          <strong>
            {fmt(value)}
            <small> m³/yr</small>
          </strong>
          <p>{note}</p>
        </div>
      ))}
    </div>
  );
}

export function DIWater({ impact }) {
  const w = impact.di_water;
  if (!w.available) return <Empty title="No DI water estimate">{w.reason}</Empty>;
  const rows = w.rows.filter((r) => r.volume_m3 != null);
  return (
    <>
      <WaterSteps w={w} />
      <table className="pump-table water-rows">
        <thead>
          <tr>
            <th>Handpump</th>
            <th>Collected</th>
            <th>Injected</th>
            <th>Where it sits</th>
            <th>May reach spring</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                <strong>{r.name}</strong>
                <span>
                  {fmt(r.roof_area_m2)} m² roof
                  {!r.online && " · DI line " + r.di_status + ", not injecting now"}
                </span>
              </td>
              <td data-label="Collected">{fmt(r.collected_m3)} m³</td>
              <td data-label="Injected">{fmt(r.volume_m3)} m³</td>
              <td data-label="Where it sits">
                {r.location_label}, share {fmt((100 * r.share[0]) / r.depth_factor)}–
                {fmt((100 * r.share[2]) / r.depth_factor)}%
                <small>
                  Injected at {fmt(r.depth_m)} m depth{r.depth_given ? "" : " (assumed)"}, {r.depth_words}: ×{" "}
                  {r.depth_factor}
                </small>
              </td>
              <td data-label="May reach spring">
                <strong>{fmt(r.reaching_m3[1])} m³</strong>
                <small>
                  range {fmt(r.reaching_m3[0])}–{fmt(r.reaching_m3[2])}
                </small>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="facts">
        {[
          ["Added spring flow, spread over the year", span(w.added_lpm_year, 2) + " L/min"],
          ["Best case, all in the " + w.lean_months + " lean months", span(w.added_lpm_lean, 2) + " L/min"],
          ...(w.offline.length
            ? [
                [
                  "Not injecting now",
                  w.offline.join(", ") +
                    " (DI line disconnected). Now: about " +
                    fmt(w.reaching_now_m3[1]) +
                    " m³ a year may reach the spring.",
                ],
              ]
            : []),
          [
            "Share of the dry-season gain DI could explain",
            w.share_of_gain_pct == null
              ? "Not available (needs a dry-season gain)"
              : "About " + w.share_of_gain_pct + "% (best-case lean-season flow ÷ the gain)",
          ],
        ].map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="caption">
        Same method and defaults as the spring planner's DI impact section. The share reaching the spring is
        the planner's judgement range until monitoring shows the real link.
        {rows.some((r) => r.location_class === "in_catchment") &&
          " The planner's recharge zones are not run for these sites yet, so the 'in the catchment' share is used."}
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
        <span>Handpumps restored after DI</span>
        <strong>
          {p.pumps_restored + p.pumps_improved}
          <small> / {p.pumps} DI handpumps</small>
        </strong>
        <p>{p.pumps_not_working} not working now</p>
      </div>
      <div>
        <span>Dry-season spring flow up after DI</span>
        <strong>
          {p.spring_numeric_up + p.spring_reported_up}
          <small> / {p.spring_numeric + p.spring_reported} springs with flow data</small>
        </strong>
        <p>
          {p.spring_no_data} of {p.di_sites} DI springs have no flow data yet
        </p>
      </div>
      <div>
        <span>DI water injected into the ground</span>
        <strong>
          {fmt(p.di_volume_m3)}
          <small> m³ a year</small>
        </strong>
        <p>
          From {fmt(p.di_collected_m3)} m³ of roof rain collected at {p.di_sites_with_volume} sites
        </p>
      </div>
      <div>
        <span>DI water fed into the springs (approx.)</span>
        <strong>
          {fmt(p.di_reaching_now_m3[1])}
          <small> m³ a year</small>
        </strong>
        <p>
          Range {fmt(p.di_reaching_now_m3[0])}–{fmt(p.di_reaching_now_m3[2])}.
          {p.di_offline.length > 0 &&
            " About " +
              fmt(p.di_reaching_m3[1]) +
              " once " +
              p.di_offline.join(" and ") +
              " are reconnected."}
        </p>
      </div>
    </div>
  );
}
