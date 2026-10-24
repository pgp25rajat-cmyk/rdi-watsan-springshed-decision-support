import React, { useRef, useState, useLayoutEffect } from "react";
import { Icon, fmt, date, visitDate, Empty, Tag } from "./shared.jsx";

function DesktopWaterPath() {
  return (
    <svg
      viewBox="0 0 760 205"
      className="water-path"
      role="img"
      aria-label="Rainwater passes from roof through filter into the handpump borehole. A possible underground connection to the spring needs checking."
    >
      <path d="M0 111 155 95 360 136 550 146 760 183V205H0Z" fill="var(--raised)" />
      <path d="M15 112 155 98 360 139 550 149 745 181" fill="none" stroke="var(--line)" strokeWidth="2" />
      <g stroke="var(--ink)" fill="none" strokeWidth="2">
        <path d="m60 69 48-32 48 32M72 66v39h71V66M86 105V81h22v24M118 76h12v13h-12" />
        <path d="M155 70h30v41h18M199 100h24v28h-24zM211 128v22h79M290 89v101M281 101h18v27h-18M290 94l27-15M296 108h28v14h12" />
        <path d="M527 147v17h-20v8M506 173h29M503 179h42M501 185h57" />
      </g>
      <g stroke="var(--accent)" fill="none" strokeWidth="2">
        <path d="M140 24l-4 9M163 23l-4 9M186 24l-4 9M185 81v19M211 133v17h79v34" />
        <path d="m289 171-5-7m5 7 5-7" />
        <path d="M305 181c92 19 140-20 202-10" strokeDasharray="5 5" />
        <path d="M504 169l9 3-8 5" />
      </g>
      <g fill="var(--ink)" fontFamily="var(--font)" fontSize="13">
        <text x="74" y="128">
          Roof
        </text>
        <text x="188" y="89">
          Filter
        </text>
        <text x="267" y="65">
          Handpump
        </text>
        <text x="509" y="137">
          Spring
        </text>
        <text x="340" y="199" fill="var(--muted)" fontSize="12">
          Underground link needs checking
        </text>
        <text x="45" y="17" fill="var(--muted)" fontSize="12">
          Rainfall also recharges the ground naturally
        </text>
      </g>
      <g stroke="var(--muted)" strokeWidth="1.5">
        <path d="M24 55v42M40 65v35" />
        <path d="m20 89 4 8 4-8M36 92l4 8 4-8" />
      </g>
      <g stroke="var(--ink)" fill="none" strokeWidth="2">
        <circle cx="671" cy="103" r="8" />
        <path d="M671 111v30m-14-18h28m-14 18-12 29m12-29 12 29M650 173h48" />
      </g>
      <text x="633" y="191" fontFamily="var(--font)" fontSize="13" fill="var(--ink)">
        Village use
      </text>
      <path d="M556 164h70" stroke="var(--accent)" strokeWidth="2" />
      <path d="m619 159 8 5-8 5" fill="none" stroke="var(--accent)" strokeWidth="2" />
    </svg>
  );
}

export function WaterPath() {
  return (
    <>
      <DesktopWaterPath />
      <div
        className="mobile-water-path"
        role="img"
        aria-label="Rainwater from the roof passes through maintained filters to the DI handpump. A possible spring link must be checked."
      >
        {[
          ["rain", "Rain on the roof", "Rain also recharges the ground naturally."],
          ["water", "First flush and filter", "Divert the first runoff; keep filters maintained."],
          ["site", "DI handpump", "The pipe takes collected water into the borehole."],
          ["flow", "Possible link to the spring", "The underground connection needs checking."],
          ["people", "Village water", "Follow availability and changes in daily life."],
        ].map(([icon, title, note]) => (
          <div key={title}>
            <Icon name={icon} size={23} />
            <div>
              <strong>{title}</strong>
              <span>{note}</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
function useChartWidth() {
  const ref = useRef(),
    [width, setWidth] = useState(500);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(260, Math.round(entries[0].contentRect.width))),
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

export function Journey({ compact = false }) {
  const stages = [
    ["site", "Set up the site", "Once", "Add the spring, handpump, GPS and water history."],
    [
      "visit",
      "Record a visit",
      "Short term · 0–12 months",
      "Check the pump and DI pipe. Record spring flow.",
    ],
    ["water", "Check the dry season", "Medium term · 1–3 years", "See whether water lasts when rain stops."],
    [
      "people",
      "Look for wider changes",
      "Long term · 3+ years",
      "Follow farming, hygiene, toilets, school and access.",
    ],
  ];
  return (
    <div className={"journey " + (compact ? "compact" : "")}>
      {stages.map(([icon, title, when, body], i) => (
        <section className="journey-stage" key={title}>
          <div className="journey-symbol">
            <Icon name={icon} size={compact ? 24 : 38} />
            {i < 3 && <span className="journey-arrow">→</span>}
          </div>
          <span className="when">{when}</span>
          <h3>{title}</h3>
          {!compact && <p>{body}</p>}
        </section>
      ))}
    </div>
  );
}

export function FlowChart({ visits, metric = "spring" }) {
  const [chartRef, W] = useChartWidth();
  const points = visits.filter((v) => v[metric]?.flow_lpm != null);
  if (!points.length)
    return (
      <div ref={chartRef}>
        <Empty title="No flow readings yet">
          Record the next visit to start the chart. Missing readings stay blank.
        </Empty>
      </div>
    );
  const H = 235,
    L = 46,
    R = 30,
    T = 32,
    B = 52;
  let min = Math.min(...points.map((v) => Date.parse(v.visit_date))),
    max = Math.max(...points.map((v) => Date.parse(v.visit_date_end || v.visit_date)));
  if (max - min < 86400000 * 30) {
    const mid = (min + max) / 2;
    min = mid - 86400000 * 30;
    max = mid + 86400000 * 30;
  }
  const top = Math.max(1, ...points.map((v) => v[metric].flow_lpm)) * 1.2;
  const x = (d) => L + ((Date.parse(d) - min) / (max - min)) * (W - L - R),
    y = (n) => H - B - (n / top) * (H - T - B);
  return (
    <div className="chart" ref={chartRef}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Flow readings on visit dates, in litres per minute"
      >
        <text x="8" y="16" className="axis">
          L/min
        </text>
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <line x1={L} x2={W - R} y1={y((top * i) / 3)} y2={y((top * i) / 3)} className="chart-grid" />
            <text x={L - 10} y={y((top * i) / 3) + 4} textAnchor="end" className="axis">
              {fmt((top * i) / 3, 1)}
            </text>
          </g>
        ))}
        {[0, 1, 2].map((i) => (
          <text key={i} x={L + ((W - L - R) * i) / 2} y={H - 12} textAnchor="middle" className="axis">
            {new Date(min + ((max - min) * i) / 2).toLocaleDateString("en-GB", {
              month: "short",
              year: "2-digit",
            })}
          </text>
        ))}
        {points.map((v) => (
          <g key={v.id}>
            <circle
              cx={x(v.visit_date)}
              cy={y(v[metric].flow_lpm)}
              r="5"
              fill={v.entry_method === "source_review" ? "white" : "var(--accent)"}
              stroke="var(--accent)"
              strokeWidth="2"
            >
              <title>
                {visitDate(v)}: {fmt(v[metric].flow_lpm, 2)} L/min
              </title>
            </circle>
            <text
              x={Math.min(W - R - 5, Math.max(L + 12, x(v.visit_date)))}
              y={y(v[metric].flow_lpm) - 13}
              textAnchor={
                x(v.visit_date) < L + 30 ? "start" : x(v.visit_date) > W - R - 30 ? "end" : "middle"
              }
              className="chart-label"
            >
              {fmt(v[metric].flow_lpm, 1)}
            </text>
          </g>
        ))}
      </svg>
      <p className="caption">
        Each dot is a recorded value. Hollow dots are transcribed source summaries; solid dots are portal
        measurements. Date ranges stay in the visit record. Flow between visits is unknown.
      </p>
    </div>
  );
}

export function RainChart({ weather }) {
  const [chartRef, W] = useChartWidth();
  if (!weather?.dates?.length) return null;
  const totals = new Map();
  weather.dates.forEach((d, i) => {
    const month = d.slice(0, 7);
    if (!totals.has(month)) totals.set(month, { sum: 0, known: 0, total: 0 });
    const r = totals.get(month);
    r.total++;
    if (weather.rain_mm[i] != null) {
      r.sum += weather.rain_mm[i];
      r.known++;
    }
  });
  const data = [...totals.entries()].slice(-6);
  const max = Math.max(1, ...data.map(([, v]) => v.sum)) * 1.2,
    H = 210,
    L = 42,
    B = 40,
    T = 20,
    R = 15;
  return (
    <div className="chart rain-chart" ref={chartRef}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Monthly available rainfall estimates in millimetres"
      >
        <text x="5" y="13" className="axis">
          mm
        </text>
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <line
              x1={L}
              x2={W - R}
              y1={H - B - ((H - T - B) * i) / 2}
              y2={H - B - ((H - T - B) * i) / 2}
              className="chart-grid"
            />
            <text x={L - 10} y={H - B - ((H - T - B) * i) / 2 + 4} textAnchor="end" className="axis">
              {fmt((max * i) / 2)}
            </text>
          </g>
        ))}
        {data.map(([month, v], i) => {
          const slot = (W - L - R) / data.length,
            height = (v.sum / max) * (H - T - B);
          return (
            <g key={month}>
              <rect
                x={L + slot * i + slot * 0.2}
                width={slot * 0.6}
                y={H - B - height}
                height={height}
                fill="var(--accent)"
                opacity={v.known === v.total ? 1 : 0.4}
              >
                <title>
                  {month}: {fmt(v.sum, 1)} mm; {v.known} available days
                </title>
              </rect>
              <text x={L + slot * (i + 0.5)} y={H - 12} textAnchor="middle" className="axis">
                {new Date(month + "-15T12:00:00").toLocaleDateString("en-GB", {
                  month: "short",
                  year: "2-digit",
                })}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="caption">
        Open-Meteo / ERA5 · area estimate, about 25 km grid · through {date(weather.dates.at(-1))}. First and
        last months may be partial.
      </p>
    </div>
  );
}

export function VisitStrip({ visits, onOpen }) {
  if (!visits.length)
    return (
      <Empty title="The visit history starts here">
        Save a visit after entering your field notes. Each visit will appear on this timeline.
      </Empty>
    );
  const sorted = [...visits].sort((a, b) => a.visit_date.localeCompare(b.visit_date));
  return (
    <div className="visit-strip">
      <div className="visit-line" />
      {sorted.map((v) => (
        <button key={v.id} className="visit-point" onClick={() => onOpen(v)}>
          <span className="visit-node">
            <Icon name="visit" size={20} />
          </span>
          <time>{visitDate(v)}</time>
          <strong>
            {v.spring?.flow_lpm == null
              ? v.spring?.reported_range
                ? v.spring.reported_range.join("–") + " L/min (estimate)"
                : "Flow not measured"
              : fmt(v.spring.flow_lpm, 1) + " L/min"}
          </strong>
          <span>
            {v.pump.status === "working"
              ? "Pump working"
              : v.pump.status === "broken"
                ? "Pump broken"
                : v.pump.status === "no_water"
                  ? "Pump has no water"
                  : "Pump not checked"}
          </span>
          {v.changes.length > 0 && (
            <Tag>
              {v.changes.length} {v.changes.length === 1 ? "change" : "changes"} noted
            </Tag>
          )}
        </button>
      ))}
    </div>
  );
}
