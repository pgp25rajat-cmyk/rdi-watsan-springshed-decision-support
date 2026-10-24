import React, { useState, useEffect } from "react";
import { Panel, Empty, Tag, Icon, visitDate } from "./shared.jsx";
import { ChoiceSelect } from "./controls.jsx";
import { handpumpGroups, pumpPhotos, sitePumps } from "./photos.js";

// A photo saved with the site wins; otherwise the field photo of its selected DI handpump.
const fieldPhoto = (s) => sitePumps(s).flatMap((p) => pumpPhotos(p.name))[0];
export const photoUrl = (s) =>
  s.photo_url || (s.photo_id ? "/api/v2/attachments/" + s.photo_id : null) || fieldPhoto(s)?.url || null;
export function SitePhoto({ site, large = false, photo }) {
  const field = !site.photo_url && !site.photo_id ? photo || fieldPhoto(site) : null,
    url = field ? field.url : photoUrl(site),
    caption = field ? field.caption : site.photo_caption;
  return url ? (
    <figure className={"site-photo " + (large ? "large" : "")}>
      <img src={url} alt={caption || site.name + " site photograph"} loading="lazy" />
      {large && (
        <figcaption>
          {caption}
          {site.photo_id && (
            <a href={"/api/v2/attachments/" + site.photo_id} target="_blank" rel="noreferrer">
              Open original <Icon name="arrow" size={13} />
            </a>
          )}
        </figcaption>
      )}
    </figure>
  ) : (
    <div className="photo-empty">
      <Icon name="site" size={26} />
      <span>No site photo yet</span>
      <span>Edit site details to add a photo</span>
    </div>
  );
}

const BASIS = {
  measured: "Measured",
  estimate: "Estimate",
  report: "Report",
  recall: "People's recall",
  agreed: "Team value",
  observed: "Seen on the visit",
  not_measured: "Not measured",
};

export function PhotoStrip({ photos }) {
  const [open, setOpen] = useState(null);
  if (!photos.length) return <Empty title="No field photos yet">Photos are added by DI handpump.</Empty>;
  return (
    <>
      <div className="photo-strip">
        {photos.map((p, i) => (
          <button key={p.src} onClick={() => setOpen(i)} aria-label={"Open photo: " + p.caption}>
            <img src={p.url} alt={p.caption} loading="lazy" />
            <span>{p.caption}</span>
          </button>
        ))}
      </div>
      {open != null && (
        <div
          className="photo-view"
          role="dialog"
          aria-label={photos[open].caption}
          onClick={() => setOpen(null)}
        >
          <figure onClick={(e) => e.stopPropagation()}>
            <img src={photos[open].url} alt={photos[open].caption} />
            <figcaption>
              {photos[open].caption}
              <button onClick={() => setOpen(null)}>Close</button>
            </figcaption>
          </figure>
        </div>
      )}
    </>
  );
}
function readable(e) {
  const v = e.value;
  if (v == null) return "Not recorded";
  if (Array.isArray(v)) return v.every((x) => typeof x === "number") ? v.join(", ") : JSON.stringify(v);
  if (typeof v === "object") {
    if (v.before) return v.before + " → " + v.after;
    return Object.entries(v)
      .filter(([k]) => !["readings", "flow_m3_s"].includes(k))
      .map(([k, x]) => k.replaceAll("_", " ") + ": " + (typeof x === "object" ? JSON.stringify(x) : x))
      .join(" · ");
  }
  return String(v);
}
export function EvidenceRows({ state, siteId, siteIds, otherPumps = [], visitId, onOpen, asset, all = false }) {
  const [visible, setVisible] = useState(12);
  useEffect(() => setVisible(12), [siteId, siteIds?.join(), visitId, asset]);
  // Handpump records start with the handpump's name; hide those of another handpump at the same spring.
  const otherPump = (e) => otherPumps.some((n) => (e.field || "").startsWith(n + " · "));
  const rows = (state.evidence_records || []).filter(
    (e) =>
      (!siteId || e.site_id === siteId) &&
      (!siteIds || siteIds.includes(e.site_id)) &&
      !otherPump(e) &&
      (!visitId || e.visit_id === visitId) &&
      (!asset || asset === "all" || e.asset === asset),
  );
  if (!rows.length)
    return (
      <Empty title="No source records yet">
        A saved visit keeps its entered values and supporting files. The initial field records include
        page-level references.
      </Empty>
    );
  return (
    <div className="evidence-list">
      {rows.slice(0, all ? rows.length : visible).map((e) => {
        const file = state.attachments.find((a) => a.id === e.attachment_id),
          visit = state.visits.find((v) => v.id === e.visit_id);
        return (
          <article key={e.id}>
            <div className="evidence-heading">
              <div>
                <strong>{e.field.replaceAll("_", " ")}</strong>
                <span>
                  {{
                    spring: "Spring",
                    handpump: "Handpump",
                    di: "DI line",
                    village: "Village",
                    site: "Site",
                  }[e.asset] || e.asset}{" "}
                  · {state.sites.find((s) => s.id === e.site_id)?.name}
                </span>
              </div>
              <Tag tone={e.review_status === "team_review_needed" ? "warning" : ""}>
                {e.review_status === "team_review_needed"
                  ? "Check source"
                  : e.basis === "portal_entry"
                    ? "Portal entry"
                    : BASIS[e.basis] || "Source record"}
              </Tag>
            </div>
            <p className="evidence-value">{readable(e)}</p>
            {e.source_excerpt && <p className="caption">{e.source_excerpt}</p>}
            <div className="evidence-links">
              {file && (
                <a
                  href={"/api/v2/attachments/" + file.id + (e.page ? "#page=" + e.page : "")}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Icon name="file" size={14} />
                  {file.name}
                  {e.page ? " · page " + e.page : ""}
                </a>
              )}
              {visit && onOpen && (
                <button type="button" onClick={() => onOpen(visit)}>
                  Open visit · {visitDate(visit)}
                </button>
              )}
            </div>
          </article>
        );
      })}
      {!all && rows.length > visible && (
        <div className="evidence-more">
          <span>
            {visible} of {rows.length} records shown
          </span>
          <button type="button" className="button" onClick={() => setVisible((n) => n + 12)}>
            Show more records
          </button>
        </div>
      )}
    </div>
  );
}
export function Sources({ state, onOpen }) {
  const groups = handpumpGroups(state.sites),
    [pump, setPump] = useState("all"),
    [asset, setAsset] = useState("all"),
    group = groups.find((g) => g.name === pump);
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Source records</h1>
          <p>See the value, where it came from, and what still needs checking.</p>
        </div>
      </header>
      <div className="source-controls">
        <label>
          DI handpump
          <ChoiceSelect aria-label="Source handpump" value={pump} onChange={(e) => setPump(e.target.value)}>
            <option value="all">All DI handpumps</option>
            {groups.map((g) => (
              <option key={g.name} value={g.name}>
                {g.name} ·{" "}
                {[...g.sites]
                  .sort((x, y) => x.name.localeCompare(y.name))
                  .map((s) => s.name)
                  .join(", ")}
              </option>
            ))}
          </ChoiceSelect>
        </label>
        <label>
          Related to
          <ChoiceSelect aria-label="Source asset" value={asset} onChange={(e) => setAsset(e.target.value)}>
            {[
              ["all", "All records"],
              ["spring", "Spring"],
              ["handpump", "Handpump"],
              ["di", "DI line"],
              ["village", "Village"],
              ["site", "Site and photos"],
            ].map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </ChoiceSelect>
        </label>
      </div>
      <Panel title="Every value and where it came from" sub="Reports, field forms, team values and visits.">
        <EvidenceRows
          state={state}
          siteIds={group ? group.sites.map((s) => s.id) : null}
          otherPumps={group ? groups.filter((g) => g !== group).map((g) => g.name) : []}
          asset={asset}
          onOpen={onOpen}
        />
      </Panel>
    </>
  );
}
