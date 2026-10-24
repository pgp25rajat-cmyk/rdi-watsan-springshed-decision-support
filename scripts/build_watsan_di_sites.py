"""Build the WATSAN DI sites data file used by the DI impact dashboard.

One place for the springs where RDI/WATSAN has done DI (direct injection) recharge, their handpumps, and every
flow or condition value we hold for them, labelled as before or after DI.

Inputs (all already in the repository):
  data/02_processed/field_visit/field_visit_springs_v1.csv      October 2026 field visit, springs
  data/02_processed/field_visit/field_visit_di_sites_v1.csv     October 2026 field visit, DI handpumps
  data/01_staged/field_visit/csv/field_visit_discharge_readings_2026-10.csv   bucket readings
  data/01_staged/literature/csv/literature_spring_values_long_v1.csv          WATSAN Spring Assessment Report
                                                                              (SRC-003) and SRHU reports (SRC-027/028)
  data/02_processed/spring_master/spring_master_v1.csv          coordinates, DEM elevation, CHIRPS annual rain

Outputs: data/02_processed/watsan_di/
  watsan_di_sites_v1.csv         one row per spring site (8 DI sites + Paniyar Dhar as a no-DI comparison)
  watsan_di_handpumps_v1.csv     one row per DI handpump
  watsan_di_observations_v1.csv  one row per value: site, asset, before/after DI, record, value range, basis, source
  watsan_di_sites_v1.xlsx        the three tables plus a README sheet

Rules
- Field form values are primary (as for the planner). WATSAN report values are kept as an earlier, undated record.
- Kokhliyal (Bhawani Khala) is a Himmotthan site with no DI, so it is left out.
- "Before DI" values come only from what people recalled on the field visit; no WATSAN before-DI measurement exists.
  They are labelled basis = recall. Where the recall gives only a direction (more / same), no number is invented.
- Paniyar Dhar has no DI. It is kept as a comparison spring next to Balench, the same way the field form named it.
- DI installation year is left blank unless a source states it (Uniyal Gaon: "installed last year" on 20 Oct 2026).

Usage: python scripts/build_watsan_di_sites.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELD = ROOT / "data/02_processed/field_visit"
READINGS = ROOT / "data/01_staged/field_visit/csv/field_visit_discharge_readings_2026-10.csv"
LITERATURE = ROOT / "data/01_staged/literature/csv/literature_spring_values_long_v1.csv"
MASTER = ROOT / "data/02_processed/spring_master/spring_master_v1.csv"
OUT = ROOT / "data/02_processed/watsan_di"

REPORT = "WATSAN Spring Assessment Report (SRC-003), summary table; date and method not stated"
FORM = "Field form, DOCC/WATSAN field visit, October 2026"

# site_id, spring record, field spring id, role, handpump ids (primary first)
SITES = [
    ("WDI-01", "RDI-SPR-0001", "FV26-BAL", "DI site", ["FV26-DI-ARK1", "FV26-DI-ARK2"]),
    ("WDI-02", "RDI-SPR-0002", "FV26-CHO", "DI site", ["FV26-DI-CHP1"]),
    ("WDI-03", "RDI-SPR-0003", "FV26-GAN", "DI site", ["FV26-DI-UNI"]),
    ("WDI-04", "RDI-SPR-0004", "FV26-MAL", "DI site", ["FV26-DI-GUN"]),
    ("WDI-05", "RDI-SPR-0005", "FV26-NIM", "DI site", ["FV26-DI-CHP2"]),
    ("WDI-06", "RDI-SPR-0006", "FV26-PAN", "Comparison spring (no DI)", []),
    ("WDI-07", "RDI-SPR-0007", "FV26-RAS", "DI site", ["FV26-DI-KAN"]),
    ("WDI-08", "RDI-SPR-0008", None, "DI site", ["FV26-DI-KUN"]),
    ("WDI-09", "RDI-SPR-0009", None, "DI site", ["SRC028-DI-DUN"]),
]

# Handpumps not visited: from the SRHU reports.
REPORT_HANDPUMPS = [
    {
        "handpump_id": "SRC028-DI-DUN",
        "name": "Dungsi (Domsi)",
        "latitude": 30.481472,
        "longitude": 78.236694,
        "link_status": "Reported by the SRHU Dungsi & Makhdet report (SRC-028); not visited",
        "source": "SRHU Dungsi & Makhdet hydrogeology report (SRC-028); handpump printed as 30°28'53.3\"N 78°14'12.1\"E",
    }
]

# Field-form text -> dashboard status codes.
PUMP_AFTER = {
    "FV26-DI-ARK1": ("working", "Pump condition not ticked; delivery test 6-7 strokes for 1-2 L shows it gives water"),
    "FV26-DI-ARK2": ("not_checked", "Pump condition not recorded"),
    "FV26-DI-GUN": ("working", ""),
    "FV26-DI-CHP1": ("working", ""),
    "FV26-DI-CHP2": ("not_checked", "Pump condition not recorded; people said it has water in the dry season now"),
    "FV26-DI-KAN": ("working", ""),
    "FV26-DI-UNI": ("broken", "Possible vehicle damage (not confirmed)"),
    "FV26-DI-KUN": ("working", "Water tapped directly from the handpump"),
}
DI_AFTER = {
    "FV26-DI-ARK1": "broken",
    "FV26-DI-ARK2": "connected",
    "FV26-DI-GUN": "connected",
    "FV26-DI-CHP1": "connected",
    "FV26-DI-CHP2": "disconnected",
    "FV26-DI-KAN": "connected",
    "FV26-DI-UNI": "not_checked",
    "FV26-DI-KUN": "connected",
}
SAFETY = {"Working": "ok", "OK": "ok", "Not working": "needs_work", "Dirty/blocked": "needs_work"}

# What people said about the time before DI (field visit recall). Codes: defunct, no_water_dry_season,
# poor_quality, working.  Text is kept as said.
PUMP_BEFORE = {
    "FV26-DI-ARK1": ("defunct", "Handpump was defunct before DI, now has water in the dry season (Balench form)"),
    "FV26-DI-CHP2": ("defunct", "Handpump was defunct, with red/brown high-iron water, before DI"),
    "FV26-DI-GUN": ("poor_quality", "Handpump gave less water and had high iron before DI; flow has increased"),
    "FV26-DI-KAN": ("no_water_dry_season", "Handpump has water in the dry season now (implies it did not before)"),
    "FV26-DI-KUN": ("defunct", "DI was fitted on a previously defunct handpump"),
}

# Condition after DI from what people said, where the form's pump box was left blank.
PUMP_AFTER_RECALL = {"FV26-DI-CHP2": ("working", "People said the handpump has water in the dry season now")}

# Spring before/after DI from recall. (metric, before low-high, after low-high, note)
SPRING_RECALL = {
    "FV26-BAL": [
        (
            "lean_flow_lpm",
            (1, 2),
            (2, 3),
            "Guide: lean flow 1-2 L/min before DI, 2-3 L/min now. The form's lean-flow box says about 1 L/min, "
            "so the gain is uncertain.",
        )
    ],
    "FV26-PAN": [
        (
            "lean_flow_lpm",
            (0, 0),
            (0, 0),
            "No DI. People said the flow has stayed similar: it dries every summer.",
        )
    ],
}
# Direction of change people reported (after DI, compared with earlier years).
DIRECTION = {"More": "increase", "Same": "same", "Less": "decrease", "Dries at times": "same"}

# The report puts Malani at Chopdiyal Gaon and Nimbujhard at Gunogi; the field GPS puts them the other way round.
REPORT_NOTE = {
    "RDI-SPR-0004": "The report places Malani at Chopdiyal Gaon (field GPS: Gunogi), so its row may belong to Nimbujhard.",
    "RDI-SPR-0005": "The report places Nimbujhard at Gunogi (field GPS: Chopriyal), so its row may belong to Malani.",
}

# Changes people described on the field visit, as (asset, area, direction, earlier, now, note). Wording kept close
# to the form; "earlier" is the time before DI unless the note says otherwise.
CHANGES = {
    "WDI-01": [("handpump", "access", "better", "Arakot handpump was defunct",
                "Handpump has water in the dry season; water decent, slight iron", "")],
    "WDI-02": [("village", "access", "better", "Severe water crisis; people walked 2-3 km downhill for water",
                "Water available in the village; vegetation and farming",
                "Himmotthan solar pumping from the spring is a separate scheme and explains much of this.")],
    "WDI-03": [("village", "access", "same", "Naula is the only source when JJM does not supply",
                "No impact from DI seen", "Geologist found no link between the DI handpump and the naula.")],
    "WDI-04": [("handpump", "access", "better", "Handpump gave less water", "Handpump flow has increased", ""),
               ("handpump", "quality", "unclear", "High iron in handpump water", "Iron is still the main concern", "")],
    "WDI-05": [("handpump", "quality", "better", "Handpump water very bad (red/brown), handpump defunct",
                "Handpump has water in the dry season", "DI line is now disconnected (house construction)."),
               ("spring", "access", "better", "Lower spring flow", "Discharge has improved", "")],
    "WDI-06": [("village", "access", "same", "Dries in lean months; people fetch water from Balench",
                "Still dries every summer", "No DI here: comparison spring.")],
    "WDI-07": [("handpump", "access", "better", "Handpump had no water in the dry season",
                "Has water in the dry season; very good quality, travellers drink and wash", ""),
               ("spring", "access", "better", "Lower spring flow", "Flow has increased", "")],
    "WDI-08": [("handpump", "access", "better", "Handpump defunct", "Handpump working; water tapped directly", "")],
}

INSTALL = {"FV26-DI-UNI": (2025, "Installed last year for the school (field visit, 20 Oct 2026)")}
VISIT_DATE_OVERRIDE = {"FV26-DI-KUN": "2026-10-21"}


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(text):
    try:
        return float(str(text).split()[0].replace(",", ""))
    except (ValueError, IndexError):
        return None


def roof(text, handpump_id):
    """Roof area in m2. Arakot 1 and 2 share one 300 m2 figure on the form, split evenly."""
    value = num(text)
    if value is not None and handpump_id in ("FV26-DI-ARK1", "FV26-DI-ARK2"):
        return value / 2, "Form gives 300 m2 for Arakot 1 and 2 together; split evenly"
    return value, ("Form value unclear" if text and "unclear" in text else "")


def range_text(low, high):
    if low is None:
        return ""
    return f"{low:g}" if high in (None, low) else f"{low:g}-{high:g}"


def parse_range(text):
    """'1.5–2' -> (1.5, 2); '~16' -> (16, 16)."""
    text = (text or "").replace("~", "").replace("–", "-").strip()
    if not text:
        return None, None
    parts = [num(p) for p in text.split("-")]
    if len(parts) == 2 and None not in parts:
        return parts[0], parts[1]
    return parts[0], parts[0]


def main():
    springs = {r["field_site_id"]: r for r in read(FIELD / "field_visit_springs_v1.csv")}
    pumps = {r["di_site_id"]: r for r in read(FIELD / "field_visit_di_sites_v1.csv")}
    readings = {}
    for r in read(READINGS):
        readings.setdefault(r["field_site_id"], []).append(r)
    lit = {}
    for r in read(LITERATURE):
        lit.setdefault(r["record_id"], {})[r["field"]] = r
    master = {r["record_id"]: r for r in read(MASTER)}

    site_rows, pump_rows, obs = [], [], []

    def add(site_id, asset, asset_id, record, period, date, metric, low=None, high=None, text="", basis="", source="",
            note="", area="", direction=""):
        obs.append(
            {
                "obs_id": f"OBS-{len(obs) + 1:03d}",
                "site_id": site_id,
                "asset": asset,
                "asset_id": asset_id,
                "record": record,
                "period": period,
                "date": date,
                "metric": metric,
                "value_low": "" if low is None else round(low, 2),
                "value_high": "" if high is None else round(high, 2),
                "value_text": text,
                "basis": basis,
                "source": source,
                "note": note,
                "change_area": area,
                "change_direction": direction,
            }
        )

    for site_id, record_id, field_id, role, handpump_ids in SITES:
        m = master[record_id]
        L = lit.get(record_id, {})
        f = springs.get(field_id, {})
        get = lambda k: (L.get(k) or {}).get("value_as_printed", "")
        visit_date = f.get("visit_date", "")
        site_rows.append(
            {
                "site_id": site_id,
                "spring_record_id": record_id,
                "field_site_id": field_id or "",
                "role": role,
                "spring_name": f.get("spring_name") or m["spring_name"].replace(" Spring", ""),
                "other_names": f.get("other_names", ""),
                "village": f.get("village") or get("village") or get("source_area_name"),
                "district": f.get("district") or "Tehri Garhwal",
                "latitude": m["latitude"],
                "longitude": m["longitude"],
                "elevation_m": m["elevation_m"],
                "annual_rain_mm": m["rainfall_mean_annual_mm"],
                "annual_rain_source": "CHIRPS 2018-2025 mean at the spring (as the planner)",
                "households": f.get("households", ""),
                "people": f.get("people", ""),
                "handpump_ids": ";".join(handpump_ids),
                "di_link_status": f.get("di_link_status")
                or (pumps.get(handpump_ids[0], {}).get("link_basis", "") if handpump_ids else "")
                or "Reported by the SRHU report (SRC-028); not visited",
                "report_catchment_ha": get("catchment_area_ha_source_value"),
                "visit_date": visit_date,
                "water_before": f.get("before_after_di_recall", ""),
                "community_notes": f.get("community_notes", ""),
                "top_concerns": f.get("top_concerns", ""),
                "other_works": f.get("recharge_works_uphill", ""),
                "notes": f.get("notes", ""),
            }
        )

        # Spring: WATSAN report (after DI, undated)
        low, high = parse_range(get("discharge_lpm_source_value"))
        if low is not None:
            add(site_id, "spring", record_id, "watsan_report", "after_di", "", "flow_lpm", low, high,
                get("discharge_lpm_source_value"), "report", REPORT,
                " ".join(x for x in ("Report says DI was fitted at nearby handpumps; season of the reading is not stated.",
                                     REPORT_NOTE.get(record_id, "")) if x))

        # Spring: field visit flow today
        if f:
            status = f["flow_today_status"]
            if status == "measured":
                rows = readings.get(field_id, [])
                rates = [60 * float(r["litres"]) / float(r["seconds"]) for r in rows]
                mean = sum(rates) / len(rates)
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "flow_lpm", mean, mean,
                    "; ".join(f"{r['litres']} L in {r['seconds']} s" for r in rows), "measured", FORM,
                    "Mean of 3 bucket-and-stopwatch readings, whole flow caught at the outlet pipe.")
            elif status == "estimate":
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "flow_lpm",
                    num(f["flow_today_lpm_low"]), num(f["flow_today_lpm_high"]), f["flow_today_text"], "estimate", FORM,
                    "Estimated by looking at the source, not timed.")
            else:
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "flow_lpm",
                    text=f["flow_today_text"], basis="not_measured", source=FORM)
            for metric, key in (("lean_flow_lpm", "lean"), ("monsoon_flow_lpm", "monsoon")):
                lo, hi = num(f.get(f"{key}_flow_lpm_low")), num(f.get(f"{key}_flow_lpm_high"))
                if lo is not None and field_id not in SPRING_RECALL:
                    add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, metric, lo, hi,
                        range_text(lo, hi) + " L/min", "recall", FORM, "Typical flow people gave for this season now.")
            direction = DIRECTION.get(f.get("flow_vs_10_20_years", ""))
            if direction:
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "reported_change",
                    text=direction, basis="recall", source=FORM,
                    note=f"Flow compared with 10-20 years ago: {f['flow_vs_10_20_years']}. "
                    + (f.get("community_notes") or ""))
            for metric, before, after, note in SPRING_RECALL.get(field_id, []):
                add(site_id, "spring", record_id, "before_di_recall", "before_di", "", metric, *before,
                    range_text(*before) + " L/min", "recall", FORM + " (recalled on " + visit_date + ")", note)
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, metric, *after,
                    range_text(*after) + " L/min", "recall", FORM, note)

        # Handpumps
        for i, hp_id in enumerate(handpump_ids):
            p = pumps.get(hp_id)
            if p is None:
                rp = next(x for x in REPORT_HANDPUMPS if x["handpump_id"] == hp_id)
                pump_rows.append({"handpump_id": hp_id, "site_id": site_id, "primary": "yes" if i == 0 else "no",
                                  "name": rp["name"], "latitude": rp["latitude"], "longitude": rp["longitude"],
                                  "link_status": rp["link_status"], "source": rp["source"]})
                continue
            area, area_note = roof(p["roof_area_m2"], hp_id)
            year, year_note = INSTALL.get(hp_id, ("", ""))
            hp_date = VISIT_DATE_OVERRIDE.get(hp_id, visit_date)
            pump_rows.append(
                {
                    "handpump_id": hp_id,
                    "site_id": site_id,
                    "primary": "yes" if i == 0 else "no",
                    "name": p["name"],
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "elevation_m": p["elevation_m"],
                    "height_above_spring_m": p["height_above_spring_dem_m"],
                    "distance_to_spring_m": p["distance_to_spring_m"],
                    "bore_depth_m": p["bore_depth_m"],
                    "roof_area_m2": "" if area is None else area,
                    "roof_note": area_note,
                    "roof_material": p["roof_material"],
                    "di_install_year": year,
                    "di_install_note": year_note,
                    "first_flush": SAFETY.get(p["first_flush"], "not_checked"),
                    "filter": SAFETY.get(p["filter"], "not_checked"),
                    "gutter_pipe": p["gutter_pipe"],
                    "pump_status": PUMP_AFTER.get(hp_id, ("not_checked", ""))[0],
                    "di_status": DI_AFTER.get(hp_id, "not_checked"),
                    "pump_yield_text": p["pump_yield_text"],
                    "visit_date": hp_date,
                    "link_status": p["link_status"],
                    "source": FORM,
                    "notes": "; ".join(x for x in (PUMP_AFTER.get(hp_id, ("", ""))[1], p["di_status"], p["notes"]) if x),
                }
            )
            if hp_id in PUMP_BEFORE:
                code, said = PUMP_BEFORE[hp_id]
                add(site_id, "handpump", hp_id, "before_di_recall", "before_di", "", "pump_status", text=code,
                    basis="recall", source=FORM + " (recalled on " + hp_date + ")", note=said)
            pump_status = PUMP_AFTER.get(hp_id, ("not_checked", ""))[0]
            add(site_id, "handpump", hp_id, "field_visit_2026_10", "after_di", hp_date, "pump_status", text=pump_status,
                basis="observed", source=FORM, note=PUMP_AFTER.get(hp_id, ("", ""))[1])
            if hp_id in PUMP_AFTER_RECALL:
                code, said = PUMP_AFTER_RECALL[hp_id]
                add(site_id, "handpump", hp_id, "field_visit_2026_10", "after_di", hp_date, "pump_status", text=code,
                    basis="recall", source=FORM, note=said)
            if p["pump_yield_text"]:
                add(site_id, "handpump", hp_id, "field_visit_2026_10", "after_di", hp_date, "pump_yield",
                    text=p["pump_yield_text"], basis="observed", source=FORM,
                    note="Strokes per litre; not convertible to L/min without timing.")
            if i == 0:
                hp_report = parse_range(get("handpump_discharge_lpm_source_value"))
                if hp_report[0] is not None:
                    add(site_id, "handpump", hp_id, "watsan_report", "after_di", "", "flow_lpm", *hp_report,
                        get("handpump_discharge_lpm_source_value"), "report", REPORT,
                        "Report's 'nearby DI handpump at higher elevation'; date and method not stated.")

        for asset, area, direction, earlier, now, note in CHANGES.get(site_id, []):
            asset_id = record_id if asset == "spring" else (handpump_ids[0] if asset == "handpump" else site_id)
            date = VISIT_DATE_OVERRIDE.get(asset_id, visit_date) if asset == "handpump" else visit_date
            add(site_id, asset, asset_id, "field_visit_2026_10", "after_di", date, "village_change", text=now,
                basis="recall", source=FORM, note=(earlier + (" | " + note if note else "")), area=area,
                direction=direction)

    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "watsan_di_sites_v1.csv": site_rows,
        "watsan_di_handpumps_v1.csv": pump_rows,
        "watsan_di_observations_v1.csv": obs,
    }
    for name, rows in tables.items():
        fields = []
        for r in rows:
            fields += [k for k in r if k not in fields]
        with open(OUT / name, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    write_workbook(tables)
    print(f"{len(site_rows)} sites, {len(pump_rows)} handpumps, {len(obs)} observations -> {OUT.relative_to(ROOT)}")


README = [
    ("What this is", "Springs where RDI/WATSAN has done DI recharge, their handpumps, and every flow or condition value "
     "we hold for them. Used by the DI impact dashboard (DI Dashboard/). Built by scripts/build_watsan_di_sites.py."),
    ("Sites", "8 DI springs from the WATSAN Spring Assessment Report and the SRHU reports, plus Paniyar Dhar (no DI) as a "
     "comparison spring next to Balench. Kokhliyal is a Himmotthan site without DI, so it is not included."),
    ("period", "before_di = how things were before DI (recall only; no measured before-DI flow exists). "
     "after_di = any record taken after DI was fitted."),
    ("record", "before_di_recall = what people said on the field visit about the time before DI; "
     "watsan_report = WATSAN Spring Assessment Report values (undated, after DI); "
     "field_visit_2026_10 = DOCC/WATSAN field visit, 18-21 Oct 2026."),
    ("basis", "measured = bucket and stopwatch; estimate = judged by eye; report = value printed in a report, method "
     "not stated; recall = what people said; observed = condition seen on the visit."),
    ("village_change", "A change people described: value_text = now, note = earlier (then | any caveat), with "
     "change_area and change_direction."),
    ("Ranges", "value_low and value_high keep the range as given. Nothing is replaced by a midpoint here."),
    ("Not included", "Photos, scanned forms and people's names."),
]


def write_workbook(tables):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl not installed: workbook skipped")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    for row in README:
        ws.append(row)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 120
    for name, rows in tables.items():
        sheet = wb.create_sheet(name.replace("watsan_di_", "").replace("_v1.csv", ""))
        fields = []
        for r in rows:
            fields += [k for k in r if k not in fields]
        sheet.append(fields)
        for c in sheet[1]:
            c.font = Font(bold=True)
        for r in rows:
            sheet.append([r.get(k, "") for k in fields])
        sheet.freeze_panes = "A2"
    wb.save(OUT / "watsan_di_sites_v1.xlsx")


if __name__ == "__main__":
    main()
