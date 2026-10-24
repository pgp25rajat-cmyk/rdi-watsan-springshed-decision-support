import React, { useState } from "react";
import {
  Header,
  Panel,
  Button,
  Icon,
  Empty,
  Tag,
  FileLinks,
  fmt,
  date,
  visitDate,
  active,
  areas,
  seasons,
} from "./shared.jsx";
import { FlowChart, VisitStrip } from "./graphics.jsx";
import { ChoiceSelect } from "./controls.jsx";
import { SiteMap } from "./maps.jsx";
import { SitePhoto, PhotoStrip, EvidenceRows } from "./evidence.jsx";
import { handpumpGroups, pumpPhotos, sitePhotos } from "./photos.js";
import {
  ImpactSummary,
  PortfolioBeforeAfter,
  PortfolioLastTwo,
  PortfolioPumps,
  SiteBeforeAfter,
  SiteLastTwo,
  PumpBeforeAfter,
  DIWater,
  BeyondWater,
  PortfolioBeyondWater,
  RainInfo,
} from "./impact.jsx";

const pumpLabels = {
  working: "Working",
  no_water: "No water",
  broken: "Broken",
  not_checked: "Not checked",
};
const diLabels = {
  connected: "Connected",
  broken: "Broken",
  blocked: "Blocked",
  disconnected: "Disconnected",
  not_checked: "Not checked",
};
const directionLabels = {
  better: "Better",
  same: "About the same",
  worse: "Worse",
  unclear: "Not clear yet",
};
const warning = (s) => (["broken", "blocked", "disconnected", "no_water"].includes(s) ? "warning" : "");
const assessment = (state, id) => state.assessment.sites.find((a) => a.site_id === id);
const shownFlow = (a) =>
  a.current_flow != null
    ? fmt(a.current_flow, 1) + " L/min"
    : a.spring?.reported_range
      ? a.spring.reported_range.join("–") + " L/min (estimate)"
      : "Not measured";
function Changes({ changes }) {
  if (!changes.length)
    return (
      <Empty title="No changes recorded for this area">
        Add a dated account when a change is seen or discussed. No change and not discussed are recorded
        separately.
      </Empty>
    );
  return (
    <div className="changes-list">
      {[...changes].reverse().map((c, i) => (
        <article key={i}>
          <div className="change-heading">
            <div>
              <Icon name={c.area === "livelihoods" ? "leaf" : "people"} size={17} />
              <strong>{areas[c.area] || c.area}</strong>
            </div>
            <Tag tone={c.direction === "worse" ? "warning" : c.direction === "better" ? "positive" : ""}>
              {directionLabels[c.direction]}
            </Tag>
          </div>
          <div className="before-after">
            <div>
              <span>Earlier</span>
              <p>{c.before}</p>
            </div>
            <Icon name="arrow" size={15} />
            <div>
              <span>Now</span>
              <p>{c.after}</p>
            </div>
          </div>
          <p className="caption">
            {date(c.date)} ·{" "}
            {c.asset === "handpump" ? "Handpump · " : c.asset === "spring" ? "Spring · " : ""}
            {c.basis === "seen" ? "Seen during the visit" : "Reported account" + (c.who ? " · " + c.who : "")}
          </p>
        </article>
      ))}
    </div>
  );
}
function VisitList({ visits, onOpen }) {
  return (
    <div className="visit-list">
      {[...visits].reverse().map((v) => (
        <button key={v.id} className="visit-row" onClick={() => onOpen(v)}>
          <Icon name="visit" />
          <div>
            <strong>{visitDate(v)}</strong>
            <span>
              {v.entry_method === "source_review" ? "Field record · source review needed" : v.visitor}
            </span>
          </div>
          <div className="reading-summary">
            <strong>
              {v.spring.flow_lpm == null
                ? v.spring.reported_range
                  ? v.spring.reported_range.join("–") + " L/min (estimate)"
                  : "Not measured"
                : fmt(v.spring.flow_lpm, 1) + " L/min"}
            </strong>
            <span>
              {v.pump_asset_name || "Handpump"} · {pumpLabels[v.pump.status]}
            </span>
          </div>
          <Icon name="arrow" size={15} />
        </button>
      ))}
    </div>
  );
}
const followItems = [
  ["handpumps", "Handpumps working", "working"],
  ["di_lines", "DI lines connected", "connected"],
  ["filters", "Filters working", "working"],
];
function Progress({ state }) {
  const f = state.assessment.portfolio.follow_up,
    [open, setOpen] = useState(null);
  const shown =
    open &&
    (open === "other"
      ? { title: "Other work", ...f.other }
      : { title: followItems.find((x) => x[0] === open)[1], ...f[open] });
  return (
    <>
      <div className="progress-grid follow-grid">
        {followItems.map(([key, label, word]) => {
          const c = f[key];
          return (
            <div key={key}>
              <span>{label}</span>
              <button
                className="follow-number"
                onClick={() => setOpen(key)}
                aria-label={label + ": show sites"}
              >
                <strong>
                  {c.ok}
                  <small> / {c.checked} checked</small>
                </strong>
              </button>
              {c.needs_work.length || c.not_checked ? (
                <button className="follow-alert" onClick={() => setOpen(key)}>
                  {c.needs_work.length > 0 && (
                    <span>
                      {c.needs_work.length} not {word}: {c.needs_work.map((n) => n.handpump).join(", ")}
                    </span>
                  )}
                  {c.not_checked > 0 && <span>{c.not_checked} not checked yet</span>}
                </button>
              ) : (
                <p>All checked ones {word}</p>
              )}
            </div>
          );
        })}
        <div>
          <span>Any other work?</span>
          <button
            className="follow-number"
            onClick={() => setOpen("other")}
            aria-label="Other work: show sites"
          >
            <strong>
              {f.other.count}
              <small> handpumps</small>
            </strong>
          </button>
          {f.other.count ? (
            <button className="follow-alert" onClick={() => setOpen("other")}>
              {f.other.count} handpump{f.other.count === 1 ? "" : "s"} require{f.other.count === 1 ? "s" : ""}{" "}
              additional work. Click to know more.
            </button>
          ) : (
            <p>Nothing else recorded</p>
          )}
        </div>
      </div>
      {shown && (
        <div className="modal-backdrop popup-backdrop" onClick={() => setOpen(null)}>
          <div className="popup" role="dialog" aria-label={shown.title} onClick={(e) => e.stopPropagation()}>
            <div className="drawer-head">
              <h2>{shown.title}</h2>
              <button onClick={() => setOpen(null)} aria-label="Close">
                <Icon name="close" size={16} />
              </button>
            </div>
            {shown.needs_work.length
              ? shown.needs_work.map((n) => (
                  <div key={n.handpump} className="work-row">
                    <Icon name="help" />
                    <div>
                      <strong>{n.handpump}</strong>
                      <p>{n.issue}</p>
                      <p>
                        {n.sites.map((s, i) => (
                          <React.Fragment key={s.id}>
                            {i > 0 && " · "}
                            <a href={"#/sites/" + s.id} onClick={() => setOpen(null)}>
                              {s.name}
                            </a>
                          </React.Fragment>
                        ))}
                      </p>
                    </div>
                  </div>
                ))
              : !shown.not_checked_list?.length && (
                  <Empty title="Nothing to fix">No handpump needs work on this check.</Empty>
                )}
            {shown.not_checked_list?.length > 0 && (
              <>
                <h3 className="popup-sub">Not checked yet</h3>
                {shown.not_checked_list.map((n) => (
                  <div key={n.handpump} className="work-row">
                    <Icon name="help" />
                    <div>
                      <strong>{n.handpump}</strong>
                      <p>
                        {n.sites.map((s, i) => (
                          <React.Fragment key={s.id}>
                            {i > 0 && " · "}
                            <a href={"#/sites/" + s.id} onClick={() => setOpen(null)}>
                              {s.name}
                            </a>
                          </React.Fragment>
                        ))}
                      </p>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
function Compare({ comparison, kind = "spring" }) {
  return comparison ? (
    <>
      <div className="comparison">
        <div>
          <span>{date(comparison.before_date)}</span>
          <strong>
            {fmt(comparison.before_lpm, 1)} <small>L/min</small>
          </strong>
        </div>
        <Icon name="arrow" size={22} />
        <div>
          <span>{date(comparison.after_date)}</span>
          <strong>
            {fmt(comparison.after_lpm, 1)} <small>L/min</small>
          </strong>
        </div>
      </div>
      <p>
        <strong>
          {comparison.difference_lpm > 0 ? "+" : ""}
          {fmt(comparison.difference_lpm, 1)} L/min
        </strong>
        {comparison.percent != null ? " · " + fmt(comparison.percent, 1) + "%" : ""} between matching visits.
      </p>
      <p className="caption">
        Same {kind}, season and measurement procedure. This is observed change; DI's contribution has not been
        isolated.
      </p>
    </>
  ) : (
    <Empty title="A comparable follow-up is needed">
      {kind === "spring"
        ? "Use the same outlet, season and method, and capture the whole flow. Source summaries and date ranges stay visible but do not create a before/after result."
        : "Repeat the same timed pumping procedure at the same handpump and season. A working pump alone does not give a delivery rate or prove restoration."}
    </Empty>
  );
}
// Timed flow readings entered on visits (not the agreed before/after values).
const hasReadings = (visits, metric = "spring") => visits.some((v) => v[metric]?.flow_lpm != null);
function Quality({ visits, onOpen, asset }) {
  const rows = [...visits]
    .reverse()
    .flatMap((v) =>
      v.tests
        .filter(
          (t) => !asset || t.sample_point.toLowerCase().includes(asset === "pump" ? "handpump" : "spring"),
        )
        .map((t) => ({ ...t, visit: v })),
    );
  if (!rows.length) return null;
  return (
    <Panel
      title="Water tests"
      sub="Numeric results stay separate from descriptions of colour, taste or iron."
    >
      {rows.length ? (
        <div className="quality-table">
          {rows.map((t, i) => (
            <button className="quality-row" key={i} onClick={() => onOpen(t.visit)}>
              <div>
                <strong>{t.parameter}</strong>
                <span>{t.sample_point}</span>
              </div>
              <strong>
                {fmt(t.value, 2)} <small>{t.unit}</small>
              </strong>
              <div>
                <span>{visitDate(t.visit)}</span>
                <span>{t.method}</span>
              </div>
              <Icon name="arrow" size={15} />
            </button>
          ))}
        </div>
      ) : (
        <Empty title="No numeric test results entered">
          Reported iron or colour changes remain accounts. They are not converted into lab values.
        </Empty>
      )}
      <p className="caption">
        Compare the same parameter, sample location and method. These results alone do not establish
        drinking-water safety.
      </p>
    </Panel>
  );
}
export function Overview({ state, onOpen }) {
  const p = state.assessment.portfolio,
    drafts = state.visits.filter((v) => v.status === "draft");
  return (
    <>
      <Header
        title="Overview"
        sub="Key metrics and field observations for all the DI sites."
        action={
          <Button primary href="#/sites/new">
            <Icon name="plus" size={16} />
            Add a site
          </Button>
        }
      />
      <ImpactSummary state={state} />
      <PortfolioPumps state={state} />
      <div className="two-col">
        <PortfolioBeforeAfter state={state} />
        <PortfolioLastTwo state={state} />
      </div>
      <PortfolioBeyondWater state={state} />
      <h2 className="section-title">Equipment and follow-up</h2>
      <Progress state={state} />
      <div className={drafts.length ? "overview-map-grid" : ""}>
        <Panel
          title="Springs and linked handpumps"
          sub={`${p.springs_mapped} springs · ${p.handpumps_mapped} DI handpumps. Open a marker to see the site.`}
        >
          <SiteMap sites={state.sites} height={325} />
        </Panel>
        {drafts.length > 0 && (
          <aside>
            <Panel title="Unfinished visits">
              {drafts.map((v) => (
                <a className="draft-row" key={v.id} href={"#/visits/new?draft=" + v.id}>
                  <div>
                    <strong>{state.sites.find((s) => s.id === v.site_id)?.name}</strong>
                    <span>{date(v.visit_date)}</span>
                  </div>
                  <span>Continue →</span>
                </a>
              ))}
            </Panel>
          </aside>
        )}
      </div>
      <div className="data-footer">
        <span />
        <div>
          <a href="/api/v2/export.csv">Download visits</a>
          <a href="/api/v2/backup">Back up database</a>
        </div>
      </div>
    </>
  );
}

export function Sites({ state }) {
  const [q, setQ] = useState(""),
    groups = handpumpGroups(state.sites).filter((g) =>
      [g.name, ...g.sites.flatMap((s) => [s.name, s.village])]
        .join(" ")
        .toLowerCase()
        .includes(q.toLowerCase()),
    );
  return (
    <>
      <Header
        title="Sites"
        sub="Each DI handpump with the springs it feeds."
        action={
          <Button primary href="#/sites/new">
            <Icon name="plus" size={16} />
            Add a site
          </Button>
        }
      />
      <div className="toolbar">
        <input
          className="search"
          aria-label="Find a site"
          placeholder="Find a handpump, spring or village"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span>
          {groups.length} {groups.length === 1 ? "handpump" : "handpumps"}
        </span>
      </div>
      <div className="photo-site-grid">
        {groups.map((g) => {
          const home = g.sites[0],
            photo = pumpPhotos(g.name)[0];
          return (
            <article className="photo-site-card" key={g.name}>
              <a href={"#/sites/" + home.id} aria-label={"Open " + g.name}>
                <SitePhoto site={home} photo={photo} />
              </a>
              <div className="photo-site-content">
                <div className="site-card-head">
                  <div>
                    <a href={"#/sites/" + home.id}>
                      <h2>{g.name}</h2>
                    </a>
                    <p>
                      {home.village} · {home.district || "District to add"}
                    </p>
                  </div>
                  <Icon name="arrow" size={17} />
                </div>
                <div className="pump-springs">
                  <span>{g.sites.length === 1 ? "Spring" : "Springs"}</span>
                  {[...g.sites]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((s) => (
                      <a key={s.id} href={"#/sites/" + s.id}>
                        {s.spring_name || s.name}
                      </a>
                    ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {!groups.length && <Empty title="No matching sites">Try another name or add a site.</Empty>}
    </>
  );
}

function Equipment({ a, onOpen, state }) {
  return (
    <div className="equipment-list">
      {a.equipment.map((p, i) => (
        <article key={i}>
          <div>
            <strong>{p.name}</strong>
            <span>{p.primary ? "Selected handpump" : "Additional linked handpump"}</span>
          </div>
          <div>
            <span>Handpump</span>
            <Tag tone={warning(p.pump_status)}>{pumpLabels[p.pump_status]}</Tag>
          </div>
          <div>
            <span>DI line</span>
            <Tag tone={warning(p.di_status)}>{diLabels[p.di_status]}</Tag>
          </div>
          {p.visit_id && (
            <button
              className="text-link"
              onClick={() => onOpen(state.visits.find((v) => v.id === p.visit_id))}
            >
              Open check <Icon name="arrow" size={14} />
            </button>
          )}
        </article>
      ))}
    </div>
  );
}
export function SiteDetail({ site: s, state, onOpen }) {
  const [tab, setTab] = useState("results"),
    visits = active(state.visits).filter((v) => v.site_id === s.id),
    a = assessment(state, s.id);
  return (
    <>
      <a className="back-link" href="#/sites">
        <Icon name="back" size={15} />
        All sites
      </a>
      <Header
        title={s.name}
        sub={s.village + (s.district ? " · " + s.district : "")}
        action={
          <div className="header-actions">
            <Button href={"#/sites/" + s.id + "/edit"}>Edit details</Button>
            <Button
              primary
              href={s.setup_complete ? "#/visits/new?site=" + s.id : "#/sites/" + s.id + "/edit"}
            >
              {s.setup_complete ? "Record a visit" : "Complete details"}
            </Button>
          </div>
        }
      />
      <div className="site-intro">
        <SitePhoto site={s} large />
        <div className="site-intro-facts">
          <div>
            <span>Spring record</span>
            <strong>{shownFlow(a)}</strong>
          </div>
          <div>
            <span>Selected handpump</span>
            <strong>{s.handpump_name || "Not added"}</strong>
          </div>
          <div>
            <span>Households</span>
            <strong>{s.households ?? "Not recorded"}</strong>
          </div>
          <a href={"#/tracking?site=" + s.id}>
            See it in Track impact <Icon name="arrow" size={15} />
          </a>
        </div>
      </div>
      <div className="tabs">
        {[
          ["results", "Results"],
          ["visits", "Visits"],
          ["details", "Site details"],
          ["sources", "Sources"],
        ].map(([k, label]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "results" && (
        <>
          <div className="two-col">
            <Panel title="Dry-season spring flow: before vs after DI" sub="Before DI compared with after DI.">
              <SiteBeforeAfter impact={a.impact} />
            </Panel>
            <Panel title="Last two readings" sub="After-DI dry flow, then after-DI monsoon flow (latest).">
              <SiteLastTwo impact={a.impact} />
            </Panel>
          </div>
          <div className={hasReadings(visits) ? "two-col" : ""}>
            {hasReadings(visits) && (
              <Panel title="Spring flow at each visit" sub="Timed readings from saved visits.">
                <FlowChart visits={visits} />
                <Compare comparison={a.spring.comparison} />
              </Panel>
            )}
            <Panel title="Handpumps and DI lines" sub="Condition at the latest check.">
              <Equipment a={a} state={state} onOpen={onOpen} />
            </Panel>
          </div>
          <Panel title="Impact beyond water" sub="What people told us changed for them.">
            <BeyondWater impact={a.impact} />
          </Panel>
          <Panel title="Field photos" sub="October 2026 field visit, by linked DI handpump.">
            <PhotoStrip photos={sitePhotos(s)} />
          </Panel>
        </>
      )}
      {tab === "visits" && (
        <>
          <Panel
            title="Visit timeline"
            sub="Date ranges are kept where the individual visit day was not confirmed."
          >
            <VisitStrip visits={visits} onOpen={onOpen} />
          </Panel>
          <Panel title="Saved visits">
            <VisitList visits={visits} onOpen={onOpen} />
          </Panel>
        </>
      )}
      {tab === "details" && (
        <>
          <div className="two-col">
            <Panel title="Locations and relationship">
              <SiteMap sites={[s]} height={300} />
              <dl className="facts">
                {[
                  ["Spring GPS", s.latitude == null ? "Not recorded" : s.latitude + ", " + s.longitude],
                  [
                    "Selected handpump GPS",
                    s.pump_latitude == null ? "Not recorded" : s.pump_latitude + ", " + s.pump_longitude,
                  ],
                  [
                    "Straight-line separation",
                    a.straight_distance_m == null
                      ? "Needs both positions"
                      : fmt(a.straight_distance_m) + " m",
                  ],
                  [
                    "Link basis",
                    {
                      reported: "Reported association",
                      field_checked: "Checked in the field",
                      unknown: "Not established",
                    }[s.link_basis] || "Not recorded",
                  ],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="caption">
                Separation is calculated using great-circle distance. It does not establish underground
                connectivity.
              </p>
            </Panel>
            <Panel title="One-time site history">
              <dl className="facts">
                {[
                  ["Connected roof", s.roof_area_m2 == null ? "Not recorded" : s.roof_area_m2 + " m²"],
                  ["Collection factor", s.collection_factor ?? "Not assumed"],
                  ["DI installation year", s.di_year ?? "Not recorded"],
                  ["Earlier water situation", s.water_before || "Not recorded"],
                  ["Collection effort", s.collection_before || "Not recorded"],
                  ["Other work", s.other_works || "Not recorded"],
                  ["Seasonal account", s.field_history?.seasonal_account || "Not recorded"],
                  ["Source note", s.field_history?.source_spring_note || "Not recorded"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </Panel>
          </div>
        </>
      )}
      {tab === "sources" && (
        <Panel title="Values and their sources">
          <EvidenceRows state={state} siteId={s.id} onOpen={onOpen} />
        </Panel>
      )}
    </>
  );
}

export function Tracking({ state, onOpen }) {
  // Pick a DI handpump; spring results show for each spring it feeds, one after another.
  const groups = handpumpGroups(state.sites),
    query = new URLSearchParams(location.hash.split("?")[1] || ""),
    groupOf = (id) => groups.find((g) => g.sites.some((s) => s.id === id)),
    [selected, setSelected] = useState(
      (
        groups.find((g) => g.name === query.get("pump")) ||
        groupOf(query.get("site")) ||
        groups.find((g) => g.sites.some((s) => assessment(state, s.id)?.visit_count)) ||
        groups[0]
      )?.name,
    ),
    [asset, setAsset] = useState(query.get("asset") || "water");
  const group = groups.find((g) => g.name === selected) || groups[0];
  if (!group)
    return <Empty title="Add a site first">Its spring, handpump and DI checks will appear here.</Empty>;
  const site = group.sites[0],
    a = assessment(state, site.id),
    springs = [...group.sites].sort((x, y) => x.name.localeCompare(y.name)),
    many = springs.length > 1,
    sameName = (x) =>
      x?.replace(/[^a-z0-9]/gi, "").toLowerCase() === group.name.replace(/[^a-z0-9]/gi, "").toLowerCase(),
    visits = active(state.visits).filter((v) => v.site_id === site.id),
    pumpRows = visits.filter((v) => !v.pump_asset_name || sameName(v.pump_asset_name)),
    visitDates = new Set(
      active(state.visits)
        .filter((v) => group.sites.some((s) => s.id === v.site_id))
        .map((v) => v.visit_date || v.id),
    );
  const perSpring = (render) =>
    springs.map((s) => (
      <section key={s.id} className="spring-section">
        {many && <h3 className="spring-heading">Spring: {s.name}</h3>}
        {render(
          s,
          assessment(state, s.id),
          active(state.visits).filter((v) => v.site_id === s.id),
        )}
      </section>
    ));
  return (
    <>
      <Header
        title="Track impact"
        sub="Spring flow, handpumps, water injected and impact beyond water for each DI handpump."
        action={
          <Button primary href={"#/visits/new?site=" + site.id}>
            Record a visit
          </Button>
        }
      />
      <div className="toolbar">
        <label className="inline-label">
          DI handpump
          <ChoiceSelect
            aria-label="DI handpump"
            value={group.name}
            onChange={(e) => setSelected(e.target.value)}
          >
            {groups.map((g) => (
              <option key={g.name} value={g.name}>
                {g.name} · {g.sites.length > 1 ? "Springs" : "Spring"}:{" "}
                {[...g.sites]
                  .sort((x, y) => x.name.localeCompare(y.name))
                  .map((s) => s.name)
                  .join(", ")}
              </option>
            ))}
          </ChoiceSelect>
        </label>
        <span>
          {visitDates.size} saved visits · <a href="#/how">Calculation methods</a>
        </span>
      </div>
      <div className="asset-tabs" role="tablist" aria-label="Impact area">
        {[
          ["water", "Water injected"],
          ["pump", "Handpump performance"],
          ["spring", "Spring performance"],
          ["di", "DI and maintenance"],
          ["village", "Impact beyond water"],
        ].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={id === asset}
            className={asset === id ? "active" : ""}
            onClick={() => setAsset(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {asset === "spring" &&
        perSpring((s, a, visits) => (
          <>
            <div className="two-col">
              <Panel
                title="Dry-season spring flow: before vs after DI"
                sub="Primary result. The square shows monsoon flow after DI."
              >
                <SiteBeforeAfter impact={a.impact} />
              </Panel>
              <Panel title="Last two readings" sub="After-DI dry flow, then after-DI monsoon flow (latest).">
                <SiteLastTwo impact={a.impact} />
              </Panel>
            </div>
            {hasReadings(visits) && (
              <div className="two-col">
                <Panel title="Spring flow at each visit" sub="Timed readings from saved visits.">
                  <FlowChart visits={visits} />
                  {a.spring.reported_range && (
                    <p className="notice">
                      Field-form estimate: {a.spring.reported_range.join("–")} L/min. This range is not
                      replaced by a midpoint.
                    </p>
                  )}
                </Panel>
                <Panel title="Change between matching visits">
                  <Compare comparison={a.spring.comparison} />
                </Panel>
              </div>
            )}
            <Quality visits={visits} asset="spring" onOpen={onOpen} />
          </>
        ))}
      {asset === "pump" && (
        <>
          <Panel title="Before vs after DI" sub="Condition before DI, condition now, and remarks.">
            <PumpBeforeAfter rows={a.impact.handpumps_before_after.filter((p) => sameName(p.name))} />
          </Panel>
          {hasReadings(pumpRows, "pump") && (
            <div className="two-col">
              <Panel title="Handpump delivery" sub={group.name}>
                <FlowChart visits={pumpRows} metric="pump" />
                <p className="caption">
                  Three timed readings and the pumping procedure are required. Strokes per bucket alone cannot
                  give L/min.
                </p>
              </Panel>
              <Panel title="Handpump change">
                <Compare comparison={a.handpump.comparison} kind="handpump" />
                <div className="pump-state">
                  <Tag tone={warning(a.handpump.status)}>{pumpLabels[a.handpump.status]}</Tag>
                  <span>
                    {a.handpump.restored
                      ? "Recovery documented across two visits"
                      : "No before/after recovery established"}
                  </span>
                </div>
              </Panel>
            </div>
          )}
          <Quality visits={visits} asset="pump" onOpen={onOpen} />
        </>
      )}
      {asset === "di" && (
        <>
          <div className="two-col">
            <Panel title="Equipment and recharge connection">
              <Equipment a={a} onOpen={onOpen} state={state} />
            </Panel>
            <Panel title="Maintenance follow-up">
              {a.maintenance.length ? (
                a.maintenance.map((r, i) => (
                  <p key={i} className="notice">
                    {r}
                  </p>
                ))
              ) : (
                <Empty title="No issue has been recorded">
                  Unknown safety checks still need checking. Connected does not mean safe to inject.
                </Empty>
              )}
            </Panel>
          </div>
        </>
      )}
      {asset === "water" && (
        <>
          <Panel title="Rainfall" sub="At the spring, as in the spring planner.">
            <RainInfo impact={a.impact} />
          </Panel>
          {perSpring((s, a) => (
            <Panel
              title="Water injected"
              sub="Rain collected from the DI roofs, injected into the aquifer, and the part that may reach the spring."
            >
              <DIWater impact={a.impact} />
            </Panel>
          ))}
        </>
      )}
      {asset === "village" &&
        perSpring((s, a) => (
          <Panel
            title="Impact beyond water"
            sub="What people told us changed for them, from the community interaction on the field forms."
          >
            <BeyondWater impact={a.impact} />
          </Panel>
        ))}
    </>
  );
}

export function HowItWorks({ state }) {
  const method = state.assessment.methodology,
    [chosen, setChosen] = useState("spring_flow"),
    row = method.indicators.find((x) => x.id === chosen) || method.indicators[0],
    sample = active(state.visits).find((v) => v.spring.readings?.length === 3);
  return (
    <>
      <Header title="How it works" sub="What each result means and how it is worked out." />
      <div className="method-intro">
        <div>
          <h2>Each spring against its own records</h2>
          <p>
            For every DI site the dashboard answers five questions separately: how much roof water goes into
            the ground, whether the handpump works, how the spring flow changed, whether the DI line and
            filter are in order, and what changed for people.
          </p>
          <p>
            They are kept apart, not added into one score, so a gap in one never hides behind another. A
            spring is only compared with its own earlier records, never with other springs.
          </p>
        </div>
        <div className="method-decision">
          <strong>From a visit to a result</strong>
          <ol>
            <li>Record the visit: handpump first, then each spring.</li>
            <li>The dashboard checks units, dates and the three readings.</li>
            <li>It applies the formula below to the readings.</li>
            <li>It shows the result with its source and limits.</li>
          </ol>
        </div>
      </div>
      <Panel
        title="How each value is calculated"
        sub="Pick a result to see its formula, what it needs and what it means."
      >
        <label className="method-selector">
          Result
          <ChoiceSelect
            aria-label="Method indicator"
            value={chosen}
            onChange={(e) => setChosen(e.target.value)}
          >
            {method.indicators.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </ChoiceSelect>
        </label>
        <div className="formula-sheet">
          <div className="formula-title">
            <h3>{row.name}</h3>
            <Tag>
              {row.asset} · {row.unit}
            </Tag>
          </div>
          <p className="formula">{row.formula}</p>
          <dl className="method-facts">
            {[
              ["How the parts combine", row.weights],
              ["Inputs required", row.needs],
              ["When evidence is missing", row.missing],
              ["What the result means", row.interpretation],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Panel>
      <div className="two-col">
        <Panel
          title="A calculation from your field record"
          sub="Original values and the calculated result stay separate."
        >
          {sample ? (
            <>
              <div className="method-readings">
                {sample.spring.readings.map((r, i) => (
                  <div key={i}>
                    <span>Reading {i + 1}</span>
                    <strong>
                      {r.litres} L / {r.seconds} s
                    </strong>
                    <span>{fmt(r.rate_lpm, 2)} L/min</span>
                  </div>
                ))}
              </div>
              <p className="formula small-formula">Mean = {fmt(sample.spring.recalculated_lpm, 2)} L/min</p>
              <p>
                The form/report summary is {fmt(sample.spring.flow_lpm, 1)} L/min. The source summary is
                retained; the calculated mean is shown alongside it.
              </p>
              <p className="caption">
                Each timing contributes one third to the mean. There is no measured before-DI baseline here,
                so a percentage DI gain cannot be calculated.
              </p>
            </>
          ) : (
            <Empty title="Needs a recorded set of three readings">
              The example will use real field readings when available.
            </Empty>
          )}
        </Panel>
        <Panel title="When a comparison is allowed">
          <ol className="method-checks">
            <li>Identify the same spring or the same handpump. A link between the two is not assumed.</li>
            <li>Match season, outlet and method. For pumps, also match the pumping procedure.</li>
            <li>
              Use whole-flow measurements with exact visit dates. Preserve source-only summaries and date
              ranges as reference records.
            </li>
            <li>Calculate the absolute difference and percentage only when the baseline is non-zero.</li>
            <li>Show rainfall, repairs, solar pumping, new pipes and other work beside the change.</li>
          </ol>
          <p className="notice">
            With no matching pair, the dashboard asks for a follow-up visit instead of showing zero change.
          </p>
        </Panel>
      </div>
      <div className="two-col">
        <Panel title="Short, medium and long term">
          <div className="method-timeline">
            <div>
              <span>0–12 months</span>
              <h3>Establish conditions and repeat checks</h3>
              <p>
                Record spring flow, pump function, DI connection, maintenance and water tests. Repeat visits
                every few months where practical.
              </p>
            </div>
            <div>
              <span>1–3 years</span>
              <h3>Compare like seasons</h3>
              <p>
                Follow dry-season reliability, delivery, quality and repairs across repeated visits. Record
                what else changed.
              </p>
            </div>
            <div>
              <span>3+ years</span>
              <h3>Follow sustained village change</h3>
              <p>
                Revisit collection effort, hygiene, toilets, school, crops and income. Keep accounts grounded
                in observations and people’s explanations.
              </p>
            </div>
          </div>
          <p className="caption">
            Time bands guide follow-up; outcomes can appear earlier or later. No fixed lag or guaranteed
            causal loop is assumed.
          </p>
        </Panel>
        <Panel title="What would establish DI’s contribution?">
          <p>
            A before/after difference alone is not enough. Natural rain recharges the aquifer, and other water
            projects or repairs may change availability.
          </p>
          <p>
            Stronger attribution needs repeated records before and after the intervention, verified asset
            connections, and rainfall and season recorded beside each reading. Each spring is judged against
            its own earlier records, not against other springs.
          </p>
          <p className="notice">
            “DI water fed into the springs” is an estimate made with the spring planner’s method, not a
            measurement. The flow changes are what was measured or agreed, with rain and other work shown
            beside them.
          </p>
        </Panel>
      </div>
    </>
  );
}
function visitFiles(state, v) {
  const ids = new Set();
  let current = v;
  while (current && !ids.has(current.id)) {
    ids.add(current.id);
    current = state.visits.find((x) => x.id === current.supersedes);
  }
  return state.attachments.filter((a) => ids.has(a.visit_id) || (v.source_refs || []).includes(a.id));
}

export function VisitDrawer({ visit: v, state, onClose }) {
  const files = visitFiles(state, v);
  return (
    <div className="modal-shade" onClick={onClose}>
      <section
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Visit details"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-head">
          <span>{state.sites.find((s) => s.id === v.site_id)?.name}</span>
          <button className="icon-button" onClick={onClose} aria-label="Close visit">
            <Icon name="close" />
          </button>
        </div>
        <h2>{visitDate(v)}</h2>
        <p className="muted">
          Recorded by {v.visitor} · {seasons[v.season]}
        </p>
        <p className="caption">
          {v.pump_asset_name ? "Handpump in this record: " + v.pump_asset_name : "Selected site handpump"}
        </p>
        {v.entry_method === "source_review" && (
          <p className="notice">
            Transcribed field record. The visit uses a date range and source values need team review.
          </p>
        )}
        <div className="visit-facts">
          <div>
            <span>Spring flow</span>
            <strong>
              {v.spring.flow_lpm == null
                ? v.spring.reported_range
                  ? v.spring.reported_range.join("–") + " L/min (estimate)"
                  : "Not measured"
                : fmt(v.spring.flow_lpm, 2) + " L/min"}
            </strong>
          </div>
          <div>
            <span>Handpump</span>
            <strong>{pumpLabels[v.pump.status]}</strong>
          </div>
          <div>
            <span>DI pipe</span>
            <strong>{diLabels[v.di.status]}</strong>
          </div>
        </div>
        {v.spring.reason && <p>{v.spring.reason}</p>}
        {v.spring.readings?.length > 0 && ["measured", "source_recorded"].includes(v.spring.status) && (
          <div className="readings-review">
            <h3>{v.entry_method === "source_review" ? "Transcribed spring readings" : "Spring readings"}</h3>
            {v.spring.readings.map((r, i) => (
              <p key={i}>
                {r.litres} L / {r.seconds} s = {fmt(r.rate_lpm, 2)} L/min
              </p>
            ))}
            <p className="caption">
              {v.spring.recalculated_lpm != null
                ? "Recalculated mean: " +
                  fmt(v.spring.recalculated_lpm, 2) +
                  " L/min. Source summary: " +
                  fmt(v.spring.flow_lpm, 1) +
                  " L/min. Check any difference."
                : ""}
            </p>
            <p className="caption">
              Point: {v.spring.point} ·{" "}
              {v.spring.capture === "full"
                ? "Whole flow collected"
                : v.spring.capture === "partial"
                  ? "Only part of the flow collected"
                  : "Capture details need source review"}
            </p>
          </div>
        )}
        {v.pump.flow_lpm != null && (
          <div className="readings-review">
            <h3>Handpump delivery</h3>
            <p>{fmt(v.pump.flow_lpm, 2)} L/min</p>
            {v.pump.readings?.map((r, i) => (
              <p key={i}>
                {r.litres} L / {r.seconds} s = {fmt(r.rate_lpm, 2)} L/min
              </p>
            ))}
            <p className="caption">{v.pump.procedure}</p>
          </div>
        )}
        <section className="drawer-notes">
          <h3>Maintenance checks</h3>
          <dl className="facts">
            {[
              ["filter", "Filter"],
              ["first_flush", "First flush"],
              ["overflow", "Overflow"],
            ].map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>
                  {
                    {
                      ok: "Looks okay",
                      needs_work: "Needs work",
                      missing: "Missing",
                      not_checked: "Not checked",
                    }[v.safety?.[key] || "not_checked"]
                  }
                </dd>
              </div>
            ))}
          </dl>
        </section>
        {v.correction_reason && (
          <section className="drawer-notes">
            <h3>Correction note</h3>
            <p>{v.correction_reason}</p>
          </section>
        )}
        {v.tests.length > 0 && (
          <div className="readings-review">
            <h3>Water tests</h3>
            {v.tests.map((t, i) => (
              <p key={i}>
                {t.parameter}: {t.value} {t.unit} · {t.sample_point} · {t.method}
              </p>
            ))}
          </div>
        )}
        <Changes changes={v.changes.map((c) => ({ ...c, date: v.visit_date }))} />
        {v.other_work && (
          <section className="drawer-notes">
            <h3>Other work / repairs</h3>
            <p>{v.other_work}</p>
          </section>
        )}
        {v.notes && (
          <section className="drawer-notes">
            <h3>Notes</h3>
            <p>{v.notes}</p>
          </section>
        )}
        <section className="drawer-notes">
          <h3>Values and sources</h3>
          <EvidenceRows state={state} visitId={v.id} />
        </section>
        <section className="drawer-notes">
          <h3>Supporting files</h3>
          <FileLinks files={files} />
          {files.length > 0 && v.supersedes && (
            <p className="caption">Includes files attached to earlier versions of this visit.</p>
          )}
          {!files.length && <p className="caption">No files attached.</p>}
        </section>
        <Button href={"#/visits/new?correct=" + v.id} onClick={onClose}>
          Correct this visit
        </Button>
        <p className="caption">A correction keeps the earlier visit in the database.</p>
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ report for one DI handpump
// Everything the dashboard holds for one DI handpump on one printable page (Download report > choose a handpump).
// The browser's print window saves it as PDF; it opens by itself when the page is reached with ?print=1.
export function PumpReport({ state, pump }) {
  const groups = handpumpGroups(state.sites),
    group = groups.find((g) => g.name === pump);
  React.useEffect(() => {
    if (!group || !new URLSearchParams(location.hash.split("?")[1] || "").get("print")) return;
    history.replaceState(null, "", "#/report?pump=" + encodeURIComponent(group.name)); // print once, not on every reload
    const id = setTimeout(() => window.print(), 1200); // let the photos and charts draw first
    return () => clearTimeout(id);
  }, [group?.name]);
  if (!group) return <Empty title="Choose a DI handpump">Use Download report at the top of the page.</Empty>;
  const springs = [...group.sites].sort((x, y) => x.name.localeCompare(y.name)),
    first = springs[0],
    a = assessment(state, first.id),
    sameName = (x) =>
      x?.replace(/[^a-z0-9]/gi, "").toLowerCase() === group.name.replace(/[^a-z0-9]/gi, "").toLowerCase(),
    hp = (first.handpumps || []).find((h) => sameName(h.name)) || (first.handpumps || [])[0] || {},
    water = a.impact.di_water?.rows?.find((r) => sameName(r.name)),
    pumpRow = a.impact.handpumps_before_after.filter((p) => sameName(p.name)),
    photos = pumpPhotos(group.name),
    visits = active(state.visits).filter((v) => springs.some((s) => s.id === v.site_id)),
    generated = new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" }),
    range = (r, d = 0) => (r ? r.map((x) => fmt(x, d)).join("–") : "–"),
    word = (x) => (x ? pumpLabels[x] || x.charAt(0).toUpperCase() + x.slice(1).replace(/_/g, " ") : "Not known");
  const facts = [
    ["Springs it feeds", springs.map((s) => s.name + (s.other_names ? " (" + s.other_names + ")" : "")).join(", ")],
    ["Village · district", [first.village, first.district].filter(Boolean).join(" · ")],
    ["Handpump location", hp.latitude != null ? fmt(hp.latitude, 6) + ", " + fmt(hp.longitude, 6) : "Not recorded"],
    ["Handpump height", hp.elevation_m != null ? fmt(hp.elevation_m, 0) + " m" : "Not recorded"],
    [
      "From the spring",
      hp.distance_to_spring_m != null
        ? fmt(hp.distance_to_spring_m, 0) + " m away, " + fmt(hp.height_above_spring_m, 0) + " m above it"
        : "Not recorded",
    ],
    ["Bore depth", hp.bore_depth_m != null ? fmt(hp.bore_depth_m, 0) + " m" : "Not recorded"],
    ["Roof feeding the DI line", hp.roof_area_m2 != null ? fmt(hp.roof_area_m2, 0) + " m²" : "Not recorded"],
    ["DI installed", hp.di_year ? String(Math.round(hp.di_year)) : "Not recorded"],
    ["Handpump now", pumpLabels[hp.pump_status] || "Not checked"],
    ["DI line now", diLabels[hp.di_status] || "Not checked"],
    ["Link to the spring", hp.link_status || first.link_basis || "Not recorded"],
    ["Households using the spring", first.households ?? "Not recorded"],
  ];
  return (
    <div className="pump-report">
      <div className="report-actions">
        <a className="back-link" href={"#/tracking?pump=" + encodeURIComponent(group.name)}>
          <Icon name="back" size={15} />
          Back to Track impact
        </a>
        <Button primary onClick={() => window.print()}>
          Save as PDF
        </Button>
      </div>
      <header className="report-cover">
        <span>WATSAN DI handpump report · RDI</span>
        <h1>{group.name}</h1>
        <p>
          {springs.length > 1 ? "Springs" : "Spring"}: {springs.map((s) => s.name).join(", ")} ·{" "}
          {[first.village, first.district].filter(Boolean).join(", ")}
        </p>
        <small>
          Made on {generated} from the DI dashboard · {visits.length} saved visit records
        </small>
      </header>

      <section className="report-section">
        <h2>1. At a glance</h2>
        <div className="report-kpis">
          <div>
            <span>Handpump</span>
            <strong>
              {pumpRow[0] ? word(pumpRow[0].before) + " → " + word(pumpRow[0].after) : word(hp.pump_status)}
            </strong>
          </div>
          <div>
            <span>DI water injected</span>
            <strong>{water ? fmt(water.volume_m3, 0) + " m³ a year" : "–"}</strong>
          </div>
          <div>
            <span>May reach the spring</span>
            <strong>{water ? fmt(water.reaching_m3[1], 0) + " m³ a year" : "–"}</strong>
            {water && <small>range {range([water.reaching_m3[0], water.reaching_m3[2]])}</small>}
          </div>
          <div>
            <span>Spring flow now</span>
            <strong>{shownFlow(a)}</strong>
          </div>
        </div>
        {first.field_history?.impact_beyond_water && <p className="notice">{first.field_history.impact_beyond_water}</p>}
      </section>

      <section className="report-section">
        <h2>2. Site details</h2>
        <dl className="facts">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        {hp.remarks && <p className="notice">{hp.remarks}</p>}
      </section>

      {photos.length > 0 && (
        <section className="report-section">
          <h2>3. Field photos</h2>
          <div className="report-photos">
            {photos.map((p) => (
              <figure key={p.src}>
                <img src={p.url} alt={p.caption} />
                <figcaption>{p.caption}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      <section className="report-section">
        <h2>{photos.length ? 4 : 3}. Water injected</h2>
        <Panel title="Rainfall" sub="At the spring, as in the spring planner.">
          <RainInfo impact={a.impact} />
        </Panel>
        {springs.map((s) => (
          <Panel key={s.id} title={"Water injected" + (springs.length > 1 ? " · " + s.name : "")}
            sub="Rain collected from the DI roof, injected into the aquifer, and the part that may reach the spring.">
            <DIWater impact={assessment(state, s.id).impact} />
          </Panel>
        ))}
      </section>

      <section className="report-section">
        <h2>{photos.length ? 5 : 4}. Handpump performance</h2>
        <Panel title="Before vs after DI" sub="Condition before DI, condition now, and remarks.">
          <PumpBeforeAfter rows={pumpRow} />
        </Panel>
      </section>

      <section className="report-section">
        <h2>{photos.length ? 6 : 5}. Spring performance</h2>
        {springs.map((s) => {
          const sa = assessment(state, s.id),
            sv = active(state.visits).filter((v) => v.site_id === s.id);
          return (
            <div key={s.id} className="report-spring">
              {springs.length > 1 && <h3 className="spring-heading">Spring: {s.name}</h3>}
              <Panel title="Dry-season spring flow: before vs after DI" sub="The square shows monsoon flow after DI.">
                <SiteBeforeAfter impact={sa.impact} />
              </Panel>
              <Panel title="Last two readings" sub="After-DI dry flow, then after-DI monsoon flow (latest).">
                <SiteLastTwo impact={sa.impact} />
              </Panel>
              {hasReadings(sv) && (
                <Panel title="Spring flow at each visit" sub="Timed readings from saved visits.">
                  <FlowChart visits={sv} />
                </Panel>
              )}
            </div>
          );
        })}
      </section>

      <section className="report-section">
        <h2>{photos.length ? 7 : 6}. DI and maintenance</h2>
        <Panel title="Equipment and recharge connection">
          <Equipment a={a} onOpen={() => {}} state={state} />
        </Panel>
        <Panel title="Maintenance follow-up">
          {a.maintenance.length ? (
            a.maintenance.map((r, i) => (
              <p key={i} className="notice">
                {r}
              </p>
            ))
          ) : (
            <p>No issue has been recorded.</p>
          )}
        </Panel>
      </section>

      <section className="report-section">
        <h2>{photos.length ? 8 : 7}. Impact beyond water</h2>
        {springs.map((s) => (
          <Panel key={s.id} title={springs.length > 1 ? s.name : "What people told us"}
            sub="From the community interaction on the field forms.">
            <BeyondWater impact={assessment(state, s.id).impact} />
          </Panel>
        ))}
      </section>

      <section className="report-section">
        <h2>{photos.length ? 9 : 8}. Source records</h2>
        <EvidenceRows
          state={state}
          siteIds={springs.map((s) => s.id)}
          otherPumps={springs.flatMap((s) => (s.handpumps || []).map((h) => h.name)).filter((n) => !sameName(n))}
          all
        />
      </section>

      <section className="report-section report-method">
        <h2>{photos.length ? 10 : 9}. How these numbers are made</h2>
        <ul>
          <li>Values are ranges where the field records are ranges; change = after − before.</li>
          <li>
            Water injected = roof area × yearly rain × 0.8 (collected) × 0.85 (injected), the spring planner's
            defaults. The part reaching the spring uses the planner's share for where the handpump sits.
          </li>
          <li>
            A before/after difference shows what changed, not how much of it DI caused. Rain, other works and
            reading methods also change flows.
          </li>
          <li>Records are labelled by basis: measured, estimate, report, recall or observed.</li>
        </ul>
      </section>
    </div>
  );
}
