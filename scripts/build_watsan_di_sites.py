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
  watsan_di_sites_v1.csv         one row per spring site (9 DI springs)
  watsan_di_handpumps_v1.csv     one row per DI handpump
  watsan_di_observations_v1.csv  one row per value: site, asset, before/after DI, record, value range, basis, source
  watsan_di_sites_v1.xlsx        the three tables plus a README sheet

Rules
- Field form values are primary (as for the planner). WATSAN report values are kept as an earlier, undated record.
- Kokhliyal (Bhawani Khala) is a Himmotthan site with no DI, so it is left out.
- Spring flow before and after DI (dry season) and after DI (monsoon) are the values Rajat agreed on 2026-10-24 from
  the earlier RDI reports and the field forms (basis = agreed). Every DI handpump was defunct before DI and works now
  (Rajat, 2026-10-24); the Kaddukhal form had recorded it broken.
- Arakot 2 may feed both Balench and Paniyar Dhar (Rajat, 2026-10-24), so it is listed under both sites. Its water is
  counted once in any total.
- DI installation year is left blank unless a source states it (Uniyal Gaon: "installed last year" on 20 Oct 2026).

Usage: python scripts/build_watsan_di_sites.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELD = ROOT / "data/02_processed/field_visit"
READINGS = ROOT / "data/01_staged/field_visit/csv/field_visit_discharge_readings_2026-10.csv"
LITERATURE = ROOT / "data/01_staged/literature/csv/literature_spring_values_long_v1.csv"
MASTER = ROOT / "data/02_processed/spring_master/spring_master_v1.csv"
FEATURES = ROOT / "data/02_processed/spring_features/spring_features_v1.csv"
SECONDARY = ROOT / "data/02_processed/spring_features/spring_secondary_features_v1.csv"
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
    ("WDI-06", "RDI-SPR-0006", "FV26-PAN", "DI site", ["FV26-DI-ARK2"]),
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

# Handpump condition now. Rajat (2026-10-24): every DI handpump was defunct before DI and works now, except
# Kaddukhal, which is broken.
WORKING_NOTE = "Working (Rajat, 2026-10-24)"
PUMP_AFTER = {
    "FV26-DI-ARK1": ("working", "Delivery test 6-7 strokes for 1-2 L"),
    "FV26-DI-ARK2": ("working", "Pump box not ticked on the form; " + WORKING_NOTE),
    "FV26-DI-GUN": ("working", ""),
    "FV26-DI-CHP1": ("working", ""),
    "FV26-DI-CHP2": ("working", "Pump box not ticked on the form; people said it has water in the dry season"),
    "FV26-DI-KAN": ("working", ""),
    "FV26-DI-UNI": ("broken", "Handpump broken, possible vehicle damage (field form; confirmed by Rajat, 2026-10-24)"),
    "FV26-DI-KUN": ("working", "Water tapped directly from the handpump"),
    "SRC028-DI-DUN": ("working", "Not visited; " + WORKING_NOTE),
}
DI_AFTER = {
    "FV26-DI-ARK1": "disconnected",  # roof pipe broken, so no water reaches the handpump (Rajat, 2026-10-24)
    "FV26-DI-ARK2": "connected",
    "FV26-DI-GUN": "connected",
    "FV26-DI-CHP1": "connected",
    "FV26-DI-CHP2": "disconnected",
    "FV26-DI-KAN": "connected",
    "FV26-DI-UNI": "not_checked",
    "FV26-DI-KUN": "connected",
}
SAFETY = {"Working": "ok", "OK": "ok", "Not working": "needs_work", "Dirty/blocked": "needs_work"}

# Before DI every handpump was defunct (Rajat, 2026-10-24). Extra detail people gave on the visit is kept.
BEFORE_NOTE = "All WATSAN DI handpumps were defunct before DI (Rajat, 2026-10-24)"
PUMP_BEFORE_DETAIL = {
    "FV26-DI-ARK1": "Balench form: handpump was defunct before DI, now has water in the dry season",
    "FV26-DI-CHP2": "Defunct, with red/brown high-iron water, before DI",
    "FV26-DI-GUN": "People said it gave less water and had high iron before DI",
    "FV26-DI-KAN": "People said it has water in the dry season now",
    "FV26-DI-KUN": "DI was fitted on a previously defunct handpump",
}

# Spring flow agreed by Rajat (2026-10-24), L/min: (before DI dry season, after DI dry season, after DI monsoon).
# Built from the earlier RDI reports (or the lowest record so far) for before, and the field forms for after.
TEAM_FLOWS = {
    "FV26-BAL": (1.5, 3, 8),
    "FV26-PAN": (0, 0, 4),
    "FV26-CHO": (8, 12, 20),
    "FV26-GAN": (3, 3, 10),
    "FV26-MAL": (7, 10, 17),
    "FV26-NIM": (6, 9, 24),
    "FV26-RAS": (12, 15, 22),
}
TEAM_SOURCE = "Agreed by Rajat (2026-10-24) from the earlier RDI reports (before) and the October 2026 field forms (after)"
HANDPUMP_NAMES = {"FV26-DI-UNI": "Kaddukhal"}

# Remarks shown beside each handpump's before/after status: water quality, breakages, DI line condition.
# From the field forms (DI section and community interaction) and Rajat's corrections (2026-10-24).
REMARKS = {
    "FV26-DI-ARK1": "Has water in the dry season; water decent, slight iron. Rooftop pipe broken, so the DI line is disconnected.",
    "FV26-DI-ARK2": "DI tested on the visit. Link to both springs not verified yet.",
    "FV26-DI-GUN": "Gives more water than before DI. Iron in the water is still a concern.",
    "FV26-DI-CHP1": "DI line, gutter and filter in good order.",
    "FV26-DI-CHP2": "Water quality improved: it was red/brown with high iron before DI (no lab test). "
    "DI line disconnected during house construction; filter blocked.",
    "FV26-DI-KAN": "Water in the dry season, very good quality; travellers drink and wash here. Roadside DI site is dirty.",
    "FV26-DI-UNI": "Handpump broken (possible vehicle damage). First flush not working, filter blocked.",
    "FV26-DI-KUN": "Working again; people tap water directly. Exposed roof pipes at risk from animals and monkeys.",
    "SRC028-DI-DUN": "Not visited; from the SRHU report.",
}

# Other work seen on the visit, beyond the pump, DI line and filter checks.
OTHER_WORK = {
    "FV26-DI-CHP2": "Test the handpump water (quality improved, but no lab test yet)",
    "FV26-DI-GUN": "Test the handpump water for iron",
    "FV26-DI-KAN": "Clean the roadside DI site (litter, dirty inflow)",
    "FV26-DI-KUN": "Protect the exposed roof pipes from animals and monkeys",
}

# Impact beyond water: what people told us in the community interaction part of the field forms, one short
# account per site. Written plainly; any limits stay in the account.
IMPACT_STORY = {
    "WDI-01": "A handpump that had stood defunct now gives water through the dry season, and the spring's dry-season "
    "flow has doubled. The water is decent to drink. Fixing the broken rooftop pipe at Arakot 1 will keep this going.",
    "WDI-02": "Families once walked 2-3 km downhill for water. Today all 28 households (about 200 people) have water "
    "in the village, and it now supports vegetation and farming. People also report more water in springs further "
    "downhill at Silogi. The Himmotthan solar pumping scheme works alongside DI here.",
    "WDI-03": "The naula is the only fallback for 2 households (about 10 people) when the JJM tap fails. People saw no "
    "change from DI, and the school handpump is now broken.",
    "WDI-04": "The Gunogi handpump gives more water than before DI, and the spring's dry-season flow has risen. Iron in "
    "the handpump water is still people's main worry, so a water test is the next step.",
    "WDI-05": "Before DI the handpump water was red-brown and people could not use it. Now it has water through the dry "
    "season, and the spring that about 20 nearby households use flows better. Reconnecting the DI line, cut during "
    "house construction, is the priority.",
    "WDI-06": "The spring still dries in the lean months, and people walk to Balench for water then. It now flows in the "
    "monsoon.",
    "WDI-07": "The Kanatal handpump now has water in the dry season, and it is very good quality: travellers stop to "
    "drink and wash. Nearby houses say the spring flow has gone up. The roadside DI site needs regular cleaning.",
    "WDI-08": "A handpump that was defunct works again, and people tap water from it directly.",
}

# Direction of change people reported (after DI, compared with earlier years).
DIRECTION = {"More": "increase", "Same": "same", "Less": "decrease", "Dries at times": "same"}

# The report printed the wrong villages for these two springs; the values belong to the spring names
# (Rajat, 2026-10-24: Malani is at Gunogi, Nimbujhard at Chopriyal 2).
REPORT_NOTE = {
    "RDI-SPR-0004": "The report prints Chopdiyal Gaon as the village; Malani is at Gunogi (report error, confirmed by Rajat).",
    "RDI-SPR-0005": "The report prints Gunogi as the village; Nimbujhard is at Chopriyal 2 (report error, confirmed by Rajat).",
}

# Changes people described on the field visit, as (asset, area, direction, earlier, now, note). Wording kept close
# to the form; "earlier" is the time before DI unless the note says otherwise.
CHANGES = {
    "WDI-01": [
        (
            "handpump",
            "access",
            "better",
            "Arakot handpump was defunct",
            "Handpump has water in the dry season; water decent, slight iron",
            "",
        ),
        ("spring", "access", "better", "Dry-season flow about 1-2 L/min", "Dry-season flow about 2-3 L/min", ""),
        (
            "handpump",
            "upkeep",
            "worse",
            "DI line carried roof water to Arakot 1",
            "Rooftop pipe broken, so no roof water reaches the handpump",
            "",
        ),
    ],
    "WDI-02": [
        (
            "village",
            "access",
            "better",
            "Severe water crisis; people walked 2-3 km downhill for water",
            "Water available in the village for all 28 households (about 200 people)",
            "Himmotthan solar pumping from the spring is a separate scheme and explains much of this.",
        ),
        (
            "village",
            "vegetation",
            "better",
            "Little water for plants or fields",
            "Vegetation and farming have come back with the water",
            "",
        ),
        (
            "spring",
            "access",
            "better",
            "Lower flow in springs downhill at Silogi",
            "People report more water in the downhill springs; water quality good",
            "",
        ),
    ],
    "WDI-03": [
        (
            "village",
            "access",
            "same",
            "Naula is the only source when JJM does not supply",
            "No impact from DI seen",
            "Geologist found no link between the DI handpump and the naula.",
        ),
        (
            "handpump",
            "upkeep",
            "worse",
            "School handpump fitted with DI in 2025",
            "Handpump broken (possible vehicle damage); first flush not working",
            "",
        ),
    ],
    "WDI-04": [
        ("handpump", "access", "better", "Handpump gave less water", "Handpump flow has increased", ""),
        ("handpump", "quality", "unclear", "High iron in handpump water", "Iron is still the main concern", ""),
    ],
    "WDI-05": [
        (
            "handpump",
            "quality",
            "better",
            "Handpump water very bad (red/brown), handpump defunct",
            "Handpump has water in the dry season",
            "No lab test yet.",
        ),
        ("spring", "access", "better", "Lower spring flow", "Discharge has improved for about 20 households", ""),
        ("handpump", "upkeep", "worse", "DI line connected", "DI line disconnected during house construction", ""),
    ],
    "WDI-06": [
        (
            "village",
            "access",
            "same",
            "Dries in lean months; people fetch water from Balench",
            "Still dries every summer",
            "Arakot 2 DI may feed this spring; not verified.",
        )
    ],
    "WDI-07": [
        ("handpump", "access", "better", "Handpump had no water in the dry season", "Has water in the dry season", ""),
        (
            "handpump",
            "quality",
            "better",
            "Handpump defunct",
            "Very good quality water; travellers drink and wash here",
            "",
        ),
        ("spring", "access", "better", "Lower spring flow", "Nearby houses say the flow has increased", ""),
    ],
    "WDI-08": [("handpump", "access", "better", "Handpump defunct", "Handpump working; water tapped directly", "")],
}

LINK_OVERRIDE = {
    "WDI-06": "Arakot 2 may feed Paniyar Dhar as well as Balench (Rajat, 2026-10-24); not verified",
}

# Where each DI handpump sits relative to its spring, in the planner's classes (Module C SHARE). The planner's recharge
# zones (Module B) have not been run for these sites, so a handpump above its spring with a reported link is placed
# "in_catchment" (the planner's share for a site in the surface catchment outside the top zones). Change a class here
# once the planner has been run on the spring.
LOCATION = {
    "FV26-DI-UNI": ("outside", "Geologist found no connection between this handpump and the naula."),
}
LOCATION_DEFAULT = (
    "in_catchment",
    "Above the spring with a reported link; the planner's recharge zones are not run for this site yet, so the "
    "'in the catchment' share is used.",
)

INSTALL = {"FV26-DI-UNI": (2025, "Installed last year for the school (field visit, 20 Oct 2026)")}
VISIT_DATE_OVERRIDE = {"FV26-DI-KUN": "2026-10-21"}


def rain_fields(f, sec, m):
    """Rain at the spring, chosen as the planner does (scripts/module_c_di_impact.py rainfall()): IMD gauges first,
    else CHIRPS. Snow is the ERA5 winter snowfall read at the spring's height (water equivalent, mm)."""
    imd, chirps = num(f.get("rain_imd_mean_annual_mm")), num(f.get("rain_chirps_mean_annual_mm_2018_2025"))
    if imd:
        annual, source = imd, f"IMD gridded rain gauges, mean of {f.get('rain_imd_years_used') or '2001-2025'}"
    else:
        annual = chirps or num(m.get("rainfall_mean_annual_mm"))
        source = "CHIRPS satellite estimate, 2018-2025 mean"
    return {
        "annual_rain_mm": "" if annual is None else round(annual),
        "annual_rain_source": source,
        "rain_chirps_mm": "" if chirps is None else round(chirps),
        "rain_monsoon_share_pct": f.get("rain_imd_monsoon_share_pct") or f.get("rain_chirps_monsoon_share_pct", ""),
        "rain_dry_season_mm": f.get("rain_chirps_dry_season_mm", ""),
        "snow_mm": sec.get("snow_at_elevation_mm", ""),
    }


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def metres(lat1, lon1, lat2, lon2):
    from math import asin, cos, radians, sin, sqrt

    a, b, c, d = map(radians, (lat1, lon1, lat2, lon2))
    return 6371000 * 2 * asin(sqrt(sin((c - a) / 2) ** 2 + cos(a) * cos(c) * sin((d - b) / 2) ** 2))


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
    features = {r["record_id"]: r for r in read(FEATURES)}
    secondary = {r["record_id"]: r for r in read(SECONDARY)}

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
                **rain_fields(features.get(record_id, {}), secondary.get(record_id, {}), m),
                "households": f.get("households", ""),
                "people": f.get("people", ""),
                "handpump_ids": ";".join(handpump_ids),
                "di_link_status": LINK_OVERRIDE.get(site_id) or f.get("di_link_status")
                or (pumps.get(handpump_ids[0], {}).get("link_basis", "") if handpump_ids else "")
                or "Reported by the SRHU report (SRC-028); not visited",
                "report_catchment_ha": get("catchment_area_ha_source_value"),
                "visit_date": visit_date,
                "water_before": f.get("before_after_di_recall", ""),
                "community_notes": f.get("community_notes", ""),
                "impact_beyond_water": IMPACT_STORY.get(site_id, ""),
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
            if field_id in TEAM_FLOWS:
                before, after_dry, after_monsoon = TEAM_FLOWS[field_id]
                add(site_id, "spring", record_id, "before_di_agreed", "before_di", "", "lean_flow_lpm", before, before,
                    f"{before:g} L/min", "agreed", TEAM_SOURCE, "Dry-season flow before DI.")
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "lean_flow_lpm",
                    after_dry, after_dry, f"{after_dry:g} L/min", "agreed", TEAM_SOURCE, "Dry-season flow after DI.")
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "monsoon_flow_lpm",
                    after_monsoon, after_monsoon, f"{after_monsoon:g} L/min", "agreed", TEAM_SOURCE,
                    "Monsoon flow after DI.")
            direction = DIRECTION.get(f.get("flow_vs_10_20_years", ""))
            if direction:
                add(site_id, "spring", record_id, "field_visit_2026_10", "after_di", visit_date, "reported_change",
                    text=direction, basis="recall", source=FORM,
                    note=f"Flow compared with 10-20 years ago: {f['flow_vs_10_20_years']}. "
                    + (f.get("community_notes") or ""))
        # Handpumps
        for i, hp_id in enumerate(handpump_ids):
            p = pumps.get(hp_id)
            if p is None:
                rp = next(x for x in REPORT_HANDPUMPS if x["handpump_id"] == hp_id)
                pump_rows.append({"handpump_id": hp_id, "site_id": site_id, "primary": "yes" if i == 0 else "no",
                                  "name": rp["name"], "latitude": rp["latitude"], "longitude": rp["longitude"],
                                  "link_status": rp["link_status"], "source": rp["source"], "pump_status": PUMP_AFTER[hp_id][0],
                                  "notes": PUMP_AFTER[hp_id][1], "remarks": REMARKS.get(hp_id, "")})
                add(site_id, "handpump", hp_id, "before_di_agreed", "before_di", "", "pump_status", text="defunct",
                    basis="agreed", source=BEFORE_NOTE)
                add(site_id, "handpump", hp_id, "after_di_agreed", "after_di", "", "pump_status", text=PUMP_AFTER[hp_id][0],
                    basis="agreed", source=BEFORE_NOTE, note=PUMP_AFTER[hp_id][1])
                continue
            area, area_note = roof(p["roof_area_m2"], hp_id)
            height, distance = p["height_above_spring_dem_m"], p["distance_to_spring_m"]
            if p["linked_spring_field_id"] and p["linked_spring_field_id"] != field_id:
                # Handpump shared with another spring (Arakot 2): measure from this spring instead.
                height = round(float(p["elevation_m"]) - float(m["elevation_m"]))
                distance = round(metres(float(p["latitude"]), float(p["longitude"]), float(m["latitude"]), float(m["longitude"])))
            year, year_note = INSTALL.get(hp_id, ("", ""))
            hp_date = VISIT_DATE_OVERRIDE.get(hp_id, visit_date)
            pump_rows.append(
                {
                    "handpump_id": hp_id,
                    "site_id": site_id,
                    "primary": "yes" if i == 0 else "no",
                    "name": HANDPUMP_NAMES.get(hp_id, p["name"]),
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "elevation_m": p["elevation_m"],
                    "height_above_spring_m": height,
                    "distance_to_spring_m": distance,
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

                    "remarks": REMARKS.get(hp_id, ""),
                    "other_work": OTHER_WORK.get(hp_id, ""),
                    "di_note": re.sub(r"^disconnected\s*\((.*)\)$", r"\1", p["di_status"], flags=re.I),
                    "location_class": LOCATION.get(hp_id, LOCATION_DEFAULT)[0],
                    "location_note": LOCATION.get(hp_id, LOCATION_DEFAULT)[1],
                }
            )
            add(site_id, "handpump", hp_id, "before_di_agreed", "before_di", "", "pump_status", text="defunct",
                basis="agreed", source=BEFORE_NOTE, note=PUMP_BEFORE_DETAIL.get(hp_id, ""))
            add(site_id, "handpump", hp_id, "field_visit_2026_10", "after_di", hp_date, "pump_status",
                text=PUMP_AFTER.get(hp_id, ("not_checked", ""))[0],
                basis="agreed", source=FORM + "; " + BEFORE_NOTE, note=PUMP_AFTER.get(hp_id, ("", ""))[1])
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
    ("Sites", "9 DI springs from the WATSAN Spring Assessment Report and the SRHU reports. Arakot 2 may feed both "
     "Balench and Paniyar Dhar, so it is listed under both; count its water once. Kokhliyal is a Himmotthan site without DI, so it is not included."),
    ("period", "before_di = how things were before DI (agreed values; no measured before-DI flow exists). "
     "after_di = any record taken after DI was fitted."),
    ("record", "before_di_agreed = before-DI values agreed by Rajat on 2026-10-24 from the earlier RDI reports; "
     "watsan_report = WATSAN Spring Assessment Report values (undated, after DI); "
     "field_visit_2026_10 = DOCC/WATSAN field visit, 18-21 Oct 2026."),
    ("basis", "agreed = value agreed by Rajat (2026-10-24) from reports and field forms; measured = bucket and stopwatch; estimate = judged by eye; report = value printed in a report, method "
     "not stated; recall = what people said; observed = condition seen on the visit."),
    ("village_change", "A change people described: value_text = now, note = earlier (then | any caveat), with "
     "change_area and change_direction."),
    ("remarks", "Handpump table: one short line on water quality, breakages and the DI line, from the field forms."),
    ("impact_beyond_water", "Sites table: a short account of what people told us in the community interaction part "
     "of the field form."),
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
