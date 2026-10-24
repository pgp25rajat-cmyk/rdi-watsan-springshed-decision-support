import React, { useId } from "react";
export const areas = {
  access: "Collecting water",
  hygiene: "Hygiene",
  sanitation: "Toilets",
  education: "School",
  livelihoods: "Farming and income",
  equity: "Who benefits",
  vegetation: "Vegetation",
  quality: "Water quality",
  upkeep: "Maintenance",
};
export const seasons = {
  dry: "Dry season",
  monsoon: "Monsoon",
  post_monsoon: "After the monsoon",
  winter: "Winter",
  unknown: "Not sure",
};
export const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const fmt = (x, d = 0) =>
  x == null ? "—" : Number(x).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
export const date = (x) =>
  x
    ? new Date(x + "T12:00:00").toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Date not added";
export const visitDate = (v) =>
  v?.visit_date_end && v.visit_date_end !== v.visit_date
    ? date(v.visit_date) + " – " + date(v.visit_date_end)
    : date(v?.visit_date);
export function active(visits) {
  const done = visits.filter((v) => v.status === "submitted"),
    replaced = new Set(done.map((v) => v.supersedes));
  return done.filter((v) => !replaced.has(v.id)).sort((a, b) => a.visit_date.localeCompare(b.visit_date));
}
export function Icon({ name, size = 18 }) {
  const shapes = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <path d="M3 14h7v7H3zM14 14h7v7h-7z" />
      </>
    ),
    site: (
      <>
        <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15" />
      </>
    ),
    water: (
      <>
        <path d="M12 2C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-13Z" />
        <path d="M8 15a4 4 0 0 0 4 4" />
      </>
    ),
    visit: (
      <>
        <rect x="4" y="5" width="16" height="16" rx="2" />
        <path d="M8 2v6M16 2v6M4 11h16m-11 5 2 2 4-4" />
      </>
    ),
    track: (
      <>
        <path d="M4 20V4M4 20h17M7 15l4-5 4 2 6-7" />
      </>
    ),
    people: (
      <>
        <circle cx="9" cy="7" r="3" />
        <path d="M3 21v-4a6 6 0 0 1 12 0v4M16 4a3 3 0 0 1 0 6M21 21v-4a5 5 0 0 0-4-5" />
      </>
    ),
    plus: <path d="M12 4v16M4 12h16" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    back: <path d="M20 12H4m6-6-6 6 6 6" />,
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    close: <path d="m5 5 14 14M19 5 5 19" />,
    check: <path d="m4 12 5 5L20 6" />,
    file: (
      <>
        <path d="M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h6" />
      </>
    ),
    rain: (
      <>
        <path d="M5 14a5 5 0 1 1 2-9 6 6 0 0 1 11 2 4 4 0 0 1 1 8M7 17l-2 4M13 17l-2 4M19 17l-2 4" />
      </>
    ),
    flow: (
      <>
        <path d="M3 7c4-4 6 4 10 0s6 0 8 0M3 12c4-4 6 4 10 0s6 0 8 0M3 17c4-4 6 4 10 0s6 0 8 0" />
      </>
    ),
    leaf: (
      <>
        <path d="M20 3C9 2 3 8 5 15s15 6 15-12Z" />
        <path d="M4 21 16 8" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9 8a3 3 0 0 1 6 1c0 2-3 2-3 5M12 17h.01" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {shapes[name] || shapes.file}
    </svg>
  );
}
export function Mark() {
  return (
    <svg width="34" height="34" viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path
        d="m4 20 11-14 8 10 5-7 8 11M4 27c7-6 11 6 18 0s11-3 14-1M4 34c7-6 11 6 18 0s11-3 14-1"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}
export function Button({ children, href, primary = false, ...props }) {
  return href ? (
    <a className={"button " + (primary ? "primary" : "")} href={href} {...props}>
      {children}
    </a>
  ) : (
    <button className={"button " + (primary ? "primary" : "")} {...props}>
      {children}
    </button>
  );
}
export function Header({ title, sub, action }) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {action}
    </header>
  );
}
export function Panel({ title, sub, action, children, className = "" }) {
  return (
    <section className={"panel " + className}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {sub && <p>{sub}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Field({ label, required = false, hint, children, wide = false }) {
  const id = useId();
  return (
    <div className={"field " + (wide ? "wide" : "")}>
      <label htmlFor={id}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {React.cloneElement(children, { id, required, "aria-describedby": hint ? id + "-hint" : undefined })}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function Tag({ children, tone = "" }) {
  return <span className={"tag " + tone}>{children}</span>;
}
export function Empty({ title, children, action }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function FileLinks({ files }) {
  return (
    <div className="file-links">
      {files.map((f) => (
        <a key={f.id} href={"/api/v2/attachments/" + f.id} target="_blank" rel="noreferrer">
          <Icon name="file" size={16} />
          {f.name}
          <Icon name="arrow" size={14} />
        </a>
      ))}
    </div>
  );
}
export function PillChoice({ value, onChange, options, label }) {
  return (
    <div className="choice-group" role="group" aria-label={label}>
      {Object.entries(options).map(([k, v]) => (
        <button
          type="button"
          key={k}
          aria-pressed={value === k}
          className={value === k ? "chosen" : ""}
          onClick={() => onChange(k)}
        >
          {v}
        </button>
      ))}
    </div>
  );
}
