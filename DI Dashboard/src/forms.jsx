import React, { useRef, useState } from "react";
import { api, attach } from "./api.js";
import { ChoiceSelect, DatePicker } from "./controls.jsx";
import { LocationPicker } from "./maps.jsx";
import {
  Header,
  Panel,
  Field,
  Button,
  Icon,
  Tag,
  PillChoice,
  areas,
  seasons,
  today,
  fmt,
} from "./shared.jsx";
import { handpumpGroups, sitePumps } from "./photos.js";

const SPRING_FIELDS = ["spring_name", "gps_later", "latitude", "longitude", "link_basis"];
const emptySpring = () => ({
  spring_name: "",
  gps_later: false,
  latitude: "",
  longitude: "",
  link_basis: "",
});

// The handpump and its site come first; then one or more springs. Each spring is saved as its own site record
// that shares the handpump details, so every spring keeps its own visits and results.
export function SiteForm({ site, onSaved }) {
  const [data, setData] = useState(() => ({
    ...{
      village: "",
      district: "",
      handpump_name: "",
      pump_gps_later: true,
      pump_latitude: "",
      pump_longitude: "",
      roof_area_m2: "",
      collection_factor: "",
      di_year: "",
      households: "",
      water_before: "",
      collection_before: "",
      supply: "",
      other_works: "",
      additional_handpumps: [],
    },
    ...site,
  }));
  const [springs, setSprings] = useState(() =>
    site ? [Object.fromEntries(SPRING_FIELDS.map((k) => [k, site[k] ?? ""]))] : [emptySpring()],
  );
  const pumps = data.additional_handpumps || [];
  const setPump = (i, k, v) =>
    set(
      "additional_handpumps",
      pumps.map((p, j) => (j === i ? { ...p, [k]: v } : p)),
    );
  const setSpring = (i, patch) => setSprings((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [photo, setPhoto] = useState(null);
  // Ids of springs already saved, so a retry after an error updates them instead of adding duplicates.
  const savedIds = useRef(site ? [site.id] : []);
  const set = (k, v) => setData((d) => ({ ...d, [k]: v }));
  const input = (k, props = {}) => (
    <input value={data[k] ?? ""} onChange={(e) => set(k, e.target.value)} {...props} />
  );
  const springInput = (i, k, props = {}) => (
    <input value={springs[i][k] ?? ""} onChange={(e) => setSpring(i, { [k]: e.target.value })} {...props} />
  );
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    let i = 0;
    try {
      for (; i < springs.length; i++) {
        const id = savedIds.current[i];
        const s = await api("sites" + (id ? "/" + id : ""), {
          ...data,
          ...springs[i],
          name: springs[i].spring_name,
        });
        savedIds.current[i] = s.id;
      }
      if (photo) await attach(photo, savedIds.current[0], null, { kind: "site_photo", asset: "handpump" });
      await onSaved(savedIds.current[0]);
    } catch (e) {
      setError((springs.length > 1 && i < springs.length ? "Spring " + (i + 1) + ": " : "") + e.message);
      setBusy(false);
    }
  }
  return (
    <>
      <Header
        title={site ? "Site details" : "Add a site"}
        sub="A DI handpump and the springs it feeds. Add this once; update it when something changes."
      />
      <div className="setup-layout">
        <form onSubmit={save}>
          <p className="form-note">Fields marked * are needed.</p>
          <Panel title="Handpump and site">
            <div className="form-grid">
              <Field
                label="Handpump name or landmark"
                required
                wide
                hint="Use a name that the next visitor can recognise."
              >
                {input("handpump_name", { placeholder: "e.g. Arakot 1, or handpump near the school" })}
              </Field>
              <Field label="Village" required>
                {input("village")}
              </Field>
              <Field label="District" required>
                {input("district")}
              </Field>
            </div>
          </Panel>
          <Panel
            title="Handpump location"
            sub="The handpump has its own position. It is never placed at a spring by default."
          >
            <div className="form-grid">
              <div className="wide">
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={data.pump_gps_later}
                    onChange={(e) => set("pump_gps_later", e.target.checked)}
                  />
                  I will add handpump GPS later
                </label>
              </div>
              {!data.pump_gps_later && (
                <>
                  <Field label="Handpump latitude" required>
                    {input("pump_latitude", { type: "number", step: "any", min: -90, max: 90 })}
                  </Field>
                  <Field label="Handpump longitude" required>
                    {input("pump_longitude", { type: "number", step: "any", min: -180, max: 180 })}
                  </Field>
                </>
              )}
              <div className="wide">
                <LocationPicker
                  title="Handpump"
                  latitude={data.pump_latitude}
                  longitude={data.pump_longitude}
                  onPick={(lat, lon) =>
                    setData((d) => ({
                      ...d,
                      pump_gps_later: false,
                      pump_latitude: lat.toFixed(6),
                      pump_longitude: lon.toFixed(6),
                    }))
                  }
                />
              </div>
            </div>
          </Panel>
          <Panel title="Handpump details" sub="Leave a box blank if it is not known yet.">
            <div className="form-grid">
              <Field label="Year DI was installed">
                {input("di_year", { type: "number", min: 1900, max: new Date().getFullYear(), step: 1 })}
              </Field>
              <Field label="Connected roof area (m²)">
                {input("roof_area_m2", { type: "number", min: 0, step: "any" })}
              </Field>
              <Field
                label="Collection factor (0–1)"
                hint="A stated assumption for the roof-water estimate. Leave blank if unknown."
              >
                {input("collection_factor", {
                  type: "number",
                  min: 0,
                  max: 1,
                  step: "any",
                  placeholder: "e.g. 0.8, if justified",
                })}
              </Field>
              <Field label="Handpump photo" hint="JPG, PNG or WebP, up to 25 MB.">
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp"
                  onChange={(e) => setPhoto(e.target.files[0] || null)}
                />
              </Field>
              {photo && <p className="caption wide">{photo.name} will be saved with this site.</p>}
            </div>
            <details className="optional-section extra-pumps">
              <summary>
                Other DI handpumps feeding the same spring <span>Optional</span>
              </summary>
              <p className="caption">
                For example Arakot 1 and Arakot 2 both feed Balench. Each keeps its own checks.
              </p>
              {pumps.map((p, i) => (
                <div className="form-grid extra-pump" key={i}>
                  <Field label="Handpump name" required>
                    <input value={p.name ?? ""} onChange={(e) => setPump(i, "name", e.target.value)} />
                  </Field>
                  <Field label="Roof area (m²)">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={p.roof_area_m2 ?? ""}
                      onChange={(e) => setPump(i, "roof_area_m2", e.target.value)}
                    />
                  </Field>
                  <Field label="Latitude">
                    <input
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                      value={p.latitude ?? ""}
                      onChange={(e) => setPump(i, "latitude", e.target.value)}
                    />
                  </Field>
                  <Field label="Longitude">
                    <input
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                      value={p.longitude ?? ""}
                      onChange={(e) => setPump(i, "longitude", e.target.value)}
                    />
                  </Field>
                  <Field label="Year DI was installed">
                    <input
                      type="number"
                      min="1900"
                      max={new Date().getFullYear()}
                      step="1"
                      value={p.di_year ?? ""}
                      onChange={(e) => setPump(i, "di_year", e.target.value)}
                    />
                  </Field>
                  <div className="field">
                    <button
                      type="button"
                      className="button"
                      onClick={() =>
                        set(
                          "additional_handpumps",
                          pumps.filter((_, j) => j !== i),
                        )
                      }
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
              <Button type="button" onClick={() => set("additional_handpumps", [...pumps, { name: "" }])}>
                <Icon name="plus" size={15} />
                Add another handpump
              </Button>
            </details>
            {data.location_notes && <p className="notice">{data.location_notes}</p>}
          </Panel>
          {springs.map((sp, i) => (
            <Panel
              key={i}
              title={springs.length > 1 ? "Spring " + (i + 1) : "Spring"}
              sub="A spring this handpump feeds. It gets its own record, visits and results."
              action={
                i > 0 &&
                !savedIds.current[i] && (
                  <button
                    type="button"
                    className="remove"
                    onClick={() => setSprings((all) => all.filter((_, j) => j !== i))}
                  >
                    Remove this spring
                  </button>
                )
              }
            >
              <div className="form-grid">
                <Field label="Spring name" required>
                  {springInput(i, "spring_name", { placeholder: "Local name of the spring" })}
                </Field>
                <Field label="How was this spring linked to the handpump?" required>
                  <ChoiceSelect
                    value={sp.link_basis ?? ""}
                    onChange={(e) => setSpring(i, { link_basis: e.target.value })}
                  >
                    <option value="">Choose one</option>
                    <option value="reported">WATSAN or local people explained the link</option>
                    <option value="field_checked">The link was checked in the field</option>
                    <option value="unknown">The link still needs checking</option>
                  </ChoiceSelect>
                </Field>
                <div className="wide">
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={!!sp.gps_later}
                      onChange={(e) => setSpring(i, { gps_later: e.target.checked })}
                    />
                    I will add spring GPS later
                  </label>
                </div>
                {!sp.gps_later && (
                  <>
                    <Field label="Spring latitude" required hint="Decimal degrees, from GPS.">
                      {springInput(i, "latitude", { type: "number", step: "any", min: -90, max: 90 })}
                    </Field>
                    <Field label="Spring longitude" required>
                      {springInput(i, "longitude", { type: "number", step: "any", min: -180, max: 180 })}
                    </Field>
                  </>
                )}
                <div className="wide">
                  <LocationPicker
                    title={"Spring" + (springs.length > 1 ? " " + (i + 1) : "")}
                    latitude={sp.latitude}
                    longitude={sp.longitude}
                    otherPoint={
                      data.pump_latitude !== "" && data.pump_latitude != null
                        ? {
                            id: site?.id || "",
                            name: data.handpump_name || "Handpump",
                            latitude: data.pump_latitude,
                            longitude: data.pump_longitude,
                          }
                        : null
                    }
                    onPick={(lat, lon) =>
                      setSpring(i, { gps_later: false, latitude: lat.toFixed(6), longitude: lon.toFixed(6) })
                    }
                  />
                </div>
              </div>
            </Panel>
          ))}
          {!site && (
            <div className="add-spring">
              <Button type="button" onClick={() => setSprings((all) => [...all, emptySpring()])}>
                <Icon name="plus" size={15} />
                Add another spring
              </Button>
            </div>
          )}
          <details className="optional-section">
            <summary>
              Village water history <span>Record once</span>
            </summary>
            <div className="form-grid">
              <Field label="Households using this water">
                {input("households", { type: "number", min: 0, step: 1 })}
              </Field>
              <Field label="How does water reach the village?">
                <ChoiceSelect value={data.supply ?? ""} onChange={(e) => set("supply", e.target.value)}>
                  <option value="">Not recorded yet</option>
                  <option>Collected at the spring</option>
                  <option>Piped to the village</option>
                  <option>Solar pumping and pipes</option>
                  <option>Handpump and spring</option>
                  <option>Other arrangement</option>
                </ChoiceSelect>
              </Field>
              <Field label="Water problems before the work" wide>
                <textarea
                  rows="3"
                  value={data.water_before ?? ""}
                  onChange={(e) => set("water_before", e.target.value)}
                  placeholder="Seasonal shortages, a dry handpump, poor water quality…"
                />
              </Field>
              <Field label="Earlier effort to collect water" wide>
                <textarea
                  rows="3"
                  value={data.collection_before ?? ""}
                  onChange={(e) => set("collection_before", e.target.value)}
                  placeholder="A short account is enough; exact minutes are not required."
                />
              </Field>
              <Field label="Other work at the site" wide>
                <textarea
                  rows="3"
                  value={data.other_works ?? ""}
                  onChange={(e) => set("other_works", e.target.value)}
                  placeholder="Solar pumping, storage, new pipes, recharge work…"
                />
              </Field>
            </div>
          </details>
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          <div className="form-actions">
            <Button href={site ? "#/sites/" + site.id : "#/sites"}>Cancel</Button>
            <Button primary disabled={busy} type="submit">
              {busy
                ? "Saving…"
                : springs.length > 1
                  ? "Save site and " + springs.length + " springs"
                  : "Save site"}
              <Icon name="check" size={16} />
            </Button>
          </div>
        </form>
        <aside className="setup-help">
          <Icon name="site" size={32} />
          <h2>A place you can return to</h2>
          <p>
            Use local names and landmarks. A clear site record helps everyone measure at the same place next
            time.
          </p>
          <div className="setup-example">
            <span>Site details</span>
            <strong>DI handpump → springs</strong>
            <span>Visit 1 → Visit 2 → Visit 3</span>
            <p>The setup stays separate from the visit notes.</p>
          </div>
          <p>
            Only GPS and date ranges are sent to Open-Meteo for rainfall. Names, notes and files stay in this
            database.
          </p>
        </aside>
      </div>
    </>
  );
}

const emptySpringCheck = () => ({
  status: "",
  point: "",
  capture: "",
  readings: [
    { litres: "", seconds: "" },
    { litres: "", seconds: "" },
    { litres: "", seconds: "" },
  ],
});
const sameName = (a, b) =>
  String(a || "")
    .trim()
    .toLowerCase() ===
  String(b || "")
    .trim()
    .toLowerCase();
const emptyVisit = (site) => ({
  site_id: site || "",
  visit_date: today(),
  visitor: "",
  season: "",
  spring: emptySpringCheck(),
  pump: { status: "", measure: false },
  di: { status: "" },
  safety: { filter: "not_checked", first_flush: "not_checked", overflow: "not_checked" },
  tests: [],
  change_status: "",
  changes: [],
  other_work: "",
  notes: "",
});
function Readings({ rows, onChange, label }) {
  return (
    <div className="reading-table">
      <div>
        <span>Reading</span>
        <span>Litres</span>
        <span>Seconds</span>
        <span>L/min</span>
      </div>
      {[0, 1, 2].map((i) => {
        const r = rows?.[i] || {};
        return (
          <div key={i}>
            <span>{i + 1}</span>
            <input
              aria-label={label + " reading " + (i + 1) + " litres"}
              type="number"
              required
              min="0.001"
              step="any"
              value={r.litres ?? ""}
              onChange={(e) => {
                const a = [...(rows || [{}, {}, {}])];
                a[i] = { ...r, litres: e.target.value };
                onChange(a);
              }}
            />
            <input
              aria-label={label + " reading " + (i + 1) + " seconds"}
              type="number"
              required
              min="0.001"
              step="any"
              value={r.seconds ?? ""}
              onChange={(e) => {
                const a = [...(rows || [{}, {}, {}])];
                a[i] = { ...r, seconds: e.target.value };
                onChange(a);
              }}
            />
            <strong>{r.litres && r.seconds ? fmt((r.litres * 60) / r.seconds, 1) : "—"}</strong>
          </div>
        );
      })}
      <p className="field-help">Keep all three readings. The app calculates the average.</p>
    </div>
  );
}

export function VisitForm({ state, onSaved, onDraftSaved, draft, correction, siteId }) {
  const [data, setData] = useState(() =>
    draft
      ? structuredClone(draft)
      : correction
        ? {
            ...structuredClone(correction),
            id: undefined,
            supersedes: correction.id,
            correction_reason: "",
            ...(correction.date_accuracy ? { visit_date: "" } : {}),
          }
        : emptyVisit(siteId),
  );
  // The visit starts at a DI handpump, then the springs it feeds that were visited. Each spring is saved as its
  // own visit record carrying the same handpump check. A draft or correction is one spring and stays fixed.
  const fixed = Boolean(draft || correction),
    groups = handpumpGroups(state.sites);
  const [pumpName, setPumpName] = useState(() => {
    const s = state.sites.find((x) => x.id === data.site_id);
    return s ? data.pump_asset_name || s.handpump_name || sitePumps(s)[0]?.name || "" : "";
  });
  const [chosen, setChosen] = useState(() => (data.site_id ? [data.site_id] : []));
  const [springs, setSprings] = useState(() => (data.site_id ? { [data.site_id]: data.spring } : {}));
  const savedIds = useRef(fixed && data.id ? { [data.site_id]: data.id } : {});
  const group = groups.find((g) => sameName(g.name, pumpName)),
    springSites = chosen.map((id) => state.sites.find((s) => s.id === id)).filter(Boolean);
  const springOf = (id) => springs[id] || emptySpringCheck();
  const setSpringPart = (id, k, v) => {
    setSprings((all) => ({ ...all, [id]: { ...(all[id] || emptySpringCheck()), [k]: v } }));
    key.current = crypto.randomUUID();
    setSavedMessage("");
  };
  function pickPump(name) {
    const g = groups.find((x) => sameName(x.name, name));
    setPumpName(name);
    setChosen(g && g.sites.length === 1 ? [g.sites[0].id] : []);
    set("site_id", g?.sites[0]?.id || "");
  }
  const toggleSpring = (id, on) =>
    setChosen((c) => {
      const next = on ? [...c, id] : c.filter((x) => x !== id);
      // Keep the order the springs are listed in for this handpump.
      return (group?.sites || []).map((s) => s.id).filter((x) => next.includes(x));
    });
  const [step, setStep] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [savedMessage, setSavedMessage] = useState(""),
    [files, setFiles] = useState([]);
  const form = useRef(),
    key = useRef(crypto.randomUUID());
  const set = (k, v) => {
    setData((d) => ({ ...d, [k]: v }));
    key.current = crypto.randomUUID();
    setSavedMessage("");
  };
  const setPart = (part, k, v) => setData((d) => ({ ...d, [part]: { ...d[part], [k]: v } }));
  const site = springSites[0];
  const input = (k, props = {}) =>
    props.type === "date" ? (
      <DatePicker value={data[k] ?? ""} onChange={(e) => set(k, e.target.value)} max={today()} />
    ) : (
      <input value={data[k] ?? ""} onChange={(e) => set(k, e.target.value)} {...props} />
    );
  function validateStep() {
    if (!form.current.reportValidity()) return false;
    if (!pumpName) {
      setError("Choose the handpump you checked.");
      return false;
    }
    if (!springSites.length) {
      setError("Tick at least one spring you visited.");
      return false;
    }
    if (springSites.some((s) => !s.setup_complete)) {
      setError("Finish the site details before recording a visit.");
      return false;
    }
    if (step === 1 && (!data.pump.status || !data.di.status)) {
      setError("Choose the handpump and DI pipe conditions.");
      return false;
    }
    if (step === 2 && springSites.some((s) => !springOf(s.id).status)) {
      setError("Choose whether the flow was measured at each spring.");
      return false;
    }
    return true;
  }
  function next() {
    setError("");
    if (validateStep()) {
      setStep((s) => s + 1);
      window.scrollTo(0, 0);
    }
  }
  async function save(submit) {
    setError("");
    if (submit && !form.current.reportValidity()) return;
    if (files.some((f) => f.size > 25 * 1024 * 1024)) {
      setError("Choose files up to 25 MB each. The visit can still be saved as a draft.");
      return;
    }
    if (!springSites.length) {
      setError("Choose the handpump and tick at least one spring you visited.");
      return;
    }
    setBusy(true);
    let current;
    try {
      for (const [i, s] of springSites.entries()) {
        current = s;
        const pump = sitePumps(s).find((p) => sameName(p.name, pumpName));
        let body = {
          ...data,
          id: savedIds.current[s.id],
          site_id: s.id,
          spring: springOf(s.id),
          pump_asset_name: pump?.name || "",
        };
        if (i === 0 && files.length) {
          const d = await api("visits", { ...body, submit: false });
          body = { ...body, id: d.id };
          savedIds.current[s.id] = d.id;
          for (const f of files) await attach(f, d.site_id, d.id);
          setFiles([]);
        }
        const result = await api(
          "visits",
          { ...body, submit },
          submit ? key.current + ":" + s.id : undefined,
        );
        savedIds.current[s.id] = result.id;
      }
      if (submit) await onSaved(springSites[0].id);
      else {
        setSavedMessage(
          (springSites.length > 1 ? springSites.length + " drafts" : "Draft") +
            " saved in the database. You can continue from the dashboard.",
        );
        await onDraftSaved();
      }
    } catch (e) {
      setError((springSites.length > 1 && current ? current.name + ": " : "") + e.message);
    } finally {
      setBusy(false);
    }
  }
  function changeRow(index, k, v) {
    const rows = [...data.changes];
    rows[index] = { ...rows[index], [k]: v };
    set("changes", rows);
  }
  const testRow = (i, k, v) => {
    const rows = [...data.tests];
    rows[i] = { ...rows[i], [k]: v };
    set("tests", rows);
  };
  return (
    <>
      <Header
        title={correction ? "Correct a visit" : "Record a visit"}
        sub="Start with the handpump you checked, then each spring you visited."
      />
      <div className="wizard">
        <div className="wizard-steps" aria-label="Visit steps">
          {[
            ["visit", "Visit details"],
            ["site", "Handpump and DI"],
            ["water", "Springs"],
            ["people", "Changes and notes"],
          ].map(([icon, label], i) => (
            <div key={label} className={step === i ? "current" : step > i ? "done" : ""}>
              <Icon name={step > i ? "check" : icon} size={18} />
              <span>{label}</span>
            </div>
          ))}
        </div>
        <form
          ref={form}
          onSubmit={(e) => {
            e.preventDefault();
            step < 3 ? next() : save(true);
          }}
        >
          <div className="visit-heading">
            <span>
              {pumpName
                ? pumpName + (springSites.length ? " · " + springSites.map((s) => s.name).join(", ") : "")
                : "Choose a handpump"}
            </span>
            <span>Fields marked * are needed.</span>
          </div>
          {step === 0 && correction?.date_accuracy && (
            <p className="notice">
              The source uses a visit date range. Enter the confirmed visit day before saving this correction.
            </p>
          )}
          {step === 0 && (
            <Panel title="About this visit" sub="Site history and setup details are kept on the site page.">
              <div className="form-grid">
                <Field label="Which DI handpump did you check?" required wide>
                  <ChoiceSelect disabled={fixed} value={pumpName} onChange={(e) => pickPump(e.target.value)}>
                    <option value="">Choose a handpump</option>
                    {groups.map((g) => (
                      <option key={g.name} value={g.name}>
                        {g.name} · {g.sites[0].village}
                      </option>
                    ))}
                  </ChoiceSelect>
                </Field>
                {group && (
                  <div className="field wide">
                    <span className="field-label">
                      Which springs did you visit? <span className="required">*</span>
                    </span>
                    <div className="spring-ticks">
                      {[...group.sites]
                        .sort((a, b) => a.name.localeCompare(b.name))
                        .map((s) => (
                          <label className="check-label" key={s.id}>
                            <input
                              type="checkbox"
                              disabled={fixed}
                              checked={chosen.includes(s.id)}
                              onChange={(e) => toggleSpring(s.id, e.target.checked)}
                            />
                            {s.spring_name || s.name}
                          </label>
                        ))}
                    </div>
                    <small>Springs this handpump feeds. Each one gets its own flow reading.</small>
                  </div>
                )}
                {site && !site.setup_complete && (
                  <div className="notice wide">
                    This site needs its one-time details first.{" "}
                    <a href={"#/sites/" + site.id + "/edit"}>Finish site details →</a>
                  </div>
                )}
                <Field label="Visit date" required>
                  {input("visit_date", { type: "date", max: today() })}
                </Field>
                <Field label="Who visited?" required>
                  {input("visitor", { placeholder: "Name or team" })}
                </Field>
                <Field label="Season" required wide>
                  <ChoiceSelect value={data.season} onChange={(e) => set("season", e.target.value)}>
                    <option value="">Choose one</option>
                    {Object.entries(seasons).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </ChoiceSelect>
                </Field>
                <Field
                  label="Before or after DI?"
                  hint="Used for the before/after impact result. 'Work it out' uses the DI year on the site; with no year, the visit counts as after DI."
                >
                  <ChoiceSelect value={data.period || ""} onChange={(e) => set("period", e.target.value)}>
                    <option value="">Work it out from the DI year</option>
                    <option value="before_di">Before DI was fitted</option>
                    <option value="after_di">After DI was fitted</option>
                  </ChoiceSelect>
                </Field>
              </div>
              <div className="site-note">
                <Icon name="site" />
                <p>
                  Need to change the roof area, households or water history?{" "}
                  <a href={"#/sites/" + (site?.id || "") + "/edit"}>Edit site details.</a>
                </p>
              </div>
            </Panel>
          )}
          {step === 1 && (
            <>
              <Panel title="Handpump and DI pipe">
                <div className="field">
                  <span className="field-label">
                    Handpump condition <span className="required">*</span>
                  </span>
                  <PillChoice
                    label="Handpump condition"
                    value={data.pump.status}
                    onChange={(v) =>
                      setData((d) => ({
                        ...d,
                        pump: { ...d.pump, status: v, measure: v === "working" && d.pump.measure },
                      }))
                    }
                    options={{
                      working: "Working",
                      no_water: "No water",
                      broken: "Broken",
                      not_checked: "Not checked",
                    }}
                  />
                </div>
                <div className="field">
                  <span className="field-label">
                    Roof-to-handpump pipe <span className="required">*</span>
                  </span>
                  <PillChoice
                    label="DI pipe condition"
                    value={data.di.status}
                    onChange={(v) => setPart("di", "status", v)}
                    options={{
                      connected: "Connected",
                      broken: "Broken",
                      blocked: "Blocked",
                      disconnected: "Disconnected",
                      not_checked: "Not checked",
                    }}
                  />
                </div>
                {data.pump.status === "working" && (
                  <details className="inline-details">
                    <summary>
                      Handpump delivery test <span>Optional</span>
                    </summary>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={Boolean(data.pump.measure)}
                        onChange={(e) => setPart("pump", "measure", e.target.checked)}
                      />
                      We measured the handpump delivery
                    </label>
                    {data.pump.measure && (
                      <>
                        <Readings
                          label="Pump"
                          rows={data.pump.readings}
                          onChange={(v) => setPart("pump", "readings", v)}
                        />
                        <Field label="How was the pump test done?" required>
                          <input
                            value={data.pump.procedure || ""}
                            onChange={(e) => setPart("pump", "procedure", e.target.value)}
                            placeholder="Pumping rhythm, time and other conditions"
                          />
                        </Field>
                      </>
                    )}
                  </details>
                )}
                <details className="inline-details">
                  <summary>
                    Filter, first flush and overflow <span>Optional check</span>
                  </summary>
                  <div className="form-grid">
                    {[
                      ["filter", "Filter"],
                      ["first_flush", "First flush"],
                      ["overflow", "Overflow"],
                    ].map(([k, label]) => (
                      <Field key={k} label={label}>
                        <ChoiceSelect
                          value={data.safety?.[k] || "not_checked"}
                          onChange={(e) => setPart("safety", k, e.target.value)}
                        >
                          <option value="not_checked">Not checked</option>
                          <option value="ok">Looks okay</option>
                          <option value="needs_work">Needs work</option>
                          <option value="missing">Missing</option>
                        </ChoiceSelect>
                      </Field>
                    ))}
                  </div>
                </details>
              </Panel>
              <details className="optional-section">
                <summary>
                  Water test results <span>Only if tested</span>
                </summary>
                {data.tests.map((t, i) => (
                  <div className="repeat-block" key={i}>
                    <div className="repeat-head">
                      <strong>Water test {i + 1}</strong>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          set(
                            "tests",
                            data.tests.filter((_, j) => i !== j),
                          )
                        }
                      >
                        Remove
                      </button>
                    </div>
                    <div className="form-grid">
                      <Field label="Parameter" required>
                        <ChoiceSelect
                          value={t.parameter}
                          onChange={(e) => testRow(i, "parameter", e.target.value)}
                        >
                          {["Iron", "pH", "Turbidity", "E. coli", "TDS"].map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </ChoiceSelect>
                      </Field>
                      <Field
                        label={
                          "Result (" +
                          { Iron: "mg/L", pH: "pH", Turbidity: "NTU", "E. coli": "CFU/100 mL", TDS: "mg/L" }[
                            t.parameter
                          ] +
                          ")"
                        }
                        required
                      >
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={t.value}
                          onChange={(e) => testRow(i, "value", e.target.value)}
                        />
                      </Field>
                      <Field label="Kit or lab" required>
                        <input value={t.method} onChange={(e) => testRow(i, "method", e.target.value)} />
                      </Field>
                      <Field label="Sample taken from" required>
                        <ChoiceSelect
                          value={t.sample_point}
                          onChange={(e) => testRow(i, "sample_point", e.target.value)}
                        >
                          <option value="">Choose one</option>
                          <option>Spring</option>
                          <option>Handpump</option>
                          <option>DI inlet water</option>
                        </ChoiceSelect>
                      </Field>
                    </div>
                  </div>
                ))}
                <Button
                  type="button"
                  onClick={() =>
                    set("tests", [
                      ...data.tests,
                      { parameter: "Iron", value: "", method: "", sample_point: "" },
                    ])
                  }
                >
                  <Icon name="plus" size={16} />
                  Add test result
                </Button>
                <p className="field-help">A few tests do not establish that the water is safe to drink.</p>
              </details>
            </>
          )}
          {step === 2 && (
            <>
              {springSites.map((s) => (
                <Panel
                  key={s.id}
                  title={"Spring flow: " + (s.spring_name || s.name)}
                  sub="Use the same outlet or collection point each time."
                >
                  <div className="field">
                    <span className="field-label">
                      Was the flow measured? <span className="required">*</span>
                    </span>
                    <PillChoice
                      label={"Spring flow status, " + s.name}
                      value={springOf(s.id).status}
                      onChange={(v) => setSpringPart(s.id, "status", v)}
                      options={{
                        measured: "Measured",
                        dry: "No water flowing",
                        not_measured: "Not measured",
                      }}
                    />
                  </div>
                  {springOf(s.id).status === "measured" && (
                    <>
                      <Readings
                        label={"Spring " + s.name}
                        rows={springOf(s.id).readings}
                        onChange={(v) => setSpringPart(s.id, "readings", v)}
                      />
                      <div className="form-grid">
                        <Field
                          label="Measurement point"
                          required
                          hint="A pipe, outlet or landmark you can find again."
                        >
                          <input
                            value={springOf(s.id).point || ""}
                            onChange={(e) => setSpringPart(s.id, "point", e.target.value)}
                          />
                        </Field>
                        <Field label="Did you catch the whole flow?" required>
                          <ChoiceSelect
                            value={springOf(s.id).capture || ""}
                            onChange={(e) => setSpringPart(s.id, "capture", e.target.value)}
                          >
                            <option value="">Choose one</option>
                            <option value="full">Yes, the whole flow</option>
                            <option value="partial">Only part of the flow</option>
                          </ChoiceSelect>
                        </Field>
                      </div>
                    </>
                  )}
                  {springOf(s.id).status === "not_measured" && (
                    <Field label="Why was it not measured?" required>
                      <ChoiceSelect
                        value={springOf(s.id).reason || ""}
                        onChange={(e) => setSpringPart(s.id, "reason", e.target.value)}
                      >
                        <option value="">Choose one</option>
                        <option>Could not reach the outlet</option>
                        <option>Could not collect the flow</option>
                        <option>No container or timing equipment</option>
                        <option>Other reason — see notes</option>
                      </ChoiceSelect>
                    </Field>
                  )}
                  {springOf(s.id).status === "dry" && (
                    <p className="field-help">
                      The visit will record zero flow, rather than a missing reading.
                    </p>
                  )}
                </Panel>
              ))}
            </>
          )}
          {step === 3 && (
            <>
              <Panel
                title="Changes people noticed"
                sub="A short account is enough. Exact numbers are only needed if you have them."
              >
                <Field label="Were any changes discussed or seen?" required>
                  <ChoiceSelect
                    value={data.change_status}
                    onChange={(e) => set("change_status", e.target.value)}
                  >
                    <option value="">Choose one</option>
                    <option value="none">No change noticed</option>
                    <option value="some">Some changes were noticed</option>
                    <option value="not_discussed">Not discussed on this visit</option>
                  </ChoiceSelect>
                </Field>
                {data.change_status === "some" && (
                  <>
                    {data.changes.map((c, i) => (
                      <div className="repeat-block" key={i}>
                        <div className="repeat-head">
                          <strong>Change {i + 1}</strong>
                          <button
                            type="button"
                            className="text-button"
                            onClick={() =>
                              set(
                                "changes",
                                data.changes.filter((_, j) => i !== j),
                              )
                            }
                          >
                            Remove
                          </button>
                        </div>
                        <div className="form-grid">
                          <Field label="Related to" required>
                            <ChoiceSelect
                              value={c.asset || "village"}
                              onChange={(e) => changeRow(i, "asset", e.target.value)}
                            >
                              <option value="spring">Spring</option>
                              <option value="handpump">Handpump</option>
                              <option value="village">Village life</option>
                            </ChoiceSelect>
                          </Field>
                          <Field label="What changed?" required>
                            <ChoiceSelect
                              value={c.area}
                              onChange={(e) => changeRow(i, "area", e.target.value)}
                            >
                              {Object.entries(areas).map(([k, v]) => (
                                <option key={k} value={k}>
                                  {v}
                                </option>
                              ))}
                            </ChoiceSelect>
                          </Field>
                          <Field label="How did it change?" required>
                            <ChoiceSelect
                              value={c.direction}
                              onChange={(e) => changeRow(i, "direction", e.target.value)}
                            >
                              <option value="unclear">Not clear yet</option>
                              <option value="better">Better</option>
                              <option value="same">About the same</option>
                              <option value="worse">Worse</option>
                            </ChoiceSelect>
                          </Field>
                          <Field label="Earlier situation" required>
                            <textarea
                              rows="3"
                              value={c.before}
                              onChange={(e) => changeRow(i, "before", e.target.value)}
                            />
                          </Field>
                          <Field label="Situation now" required>
                            <textarea
                              rows="3"
                              value={c.after}
                              onChange={(e) => changeRow(i, "after", e.target.value)}
                              placeholder="New crops, more reliable water, easier cleaning…"
                            />
                          </Field>
                          <Field label="How do you know?" required>
                            <ChoiceSelect
                              value={c.basis}
                              onChange={(e) => changeRow(i, "basis", e.target.value)}
                            >
                              <option value="people_said">People told us</option>
                              <option value="seen">We saw it during the visit</option>
                            </ChoiceSelect>
                          </Field>
                          {c.basis === "people_said" && (
                            <Field label="Who told you?" required>
                              <input
                                value={c.who}
                                onChange={(e) => changeRow(i, "who", e.target.value)}
                                placeholder="Person or group"
                              />
                            </Field>
                          )}
                        </div>
                      </div>
                    ))}
                    <Button
                      type="button"
                      onClick={() =>
                        set("changes", [
                          ...data.changes,
                          {
                            asset: "village",
                            area: "access",
                            direction: "unclear",
                            before: "",
                            after: "",
                            basis: "people_said",
                            who: "",
                          },
                        ])
                      }
                    >
                      <Icon name="plus" size={16} />
                      Add a change
                    </Button>
                  </>
                )}
              </Panel>
              <Panel title="Anything else to note?">
                <div className="form-grid">
                  <Field label="Repairs or other work since the last visit" wide>
                    <textarea
                      rows="3"
                      value={data.other_work || ""}
                      onChange={(e) => set("other_work", e.target.value)}
                      placeholder="Broken pipes, new connections, solar pumping, construction…"
                    />
                  </Field>
                  <Field label="Other notes" wide>
                    <textarea
                      rows="3"
                      value={data.notes || ""}
                      onChange={(e) => set("notes", e.target.value)}
                      placeholder="Recent rain, access problems, questions for the next visit…"
                    />
                  </Field>
                  {data.supersedes && (
                    <Field label="Why are you correcting this visit?" required wide>
                      <textarea
                        value={data.correction_reason || ""}
                        onChange={(e) => set("correction_reason", e.target.value)}
                        rows="2"
                      />
                    </Field>
                  )}
                  <Field
                    label="Photos or notes"
                    hint="Optional supporting files, up to 25 MB each. The app does not read their contents."
                    wide
                  >
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.docx,.txt"
                      onChange={(e) => setFiles([...e.target.files])}
                    />
                  </Field>
                  {files.length > 0 && (
                    <p className="field-help wide">{files.length} file(s) ready to attach.</p>
                  )}
                </div>
              </Panel>
              <div className="save-note">
                <Icon name="check" />
                <p>
                  This visit will be saved in the database. Rainfall will be matched automatically when GPS is
                  available.
                </p>
              </div>
            </>
          )}
          {error && (
            <p className="error-box" role="alert">
              {error}
            </p>
          )}
          {savedMessage && (
            <p className="saved-box" role="status">
              {savedMessage}
            </p>
          )}
          <div className="wizard-actions">
            <div>
              {step > 0 ? (
                <Button
                  type="button"
                  onClick={() => {
                    setError("");
                    setStep((s) => s - 1);
                    window.scrollTo(0, 0);
                  }}
                >
                  <Icon name="back" size={16} />
                  Back
                </Button>
              ) : (
                <Button href="#/sites">Cancel</Button>
              )}
            </div>
            <div>
              <Button type="button" disabled={busy || !springSites.length} onClick={() => save(false)}>
                Save draft
              </Button>
              <Button type="submit" primary disabled={busy}>
                {busy
                  ? "Saving…"
                  : step < 3
                    ? "Continue"
                    : springSites.length > 1
                      ? "Save " + springSites.length + " spring visits"
                      : "Save visit"}
                <Icon name={step < 3 ? "arrow" : "check"} size={16} />
              </Button>
            </div>
          </div>
        </form>
      </div>
    </>
  );
}
