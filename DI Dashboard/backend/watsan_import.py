"""Load the WATSAN DI sites data file (data/02_processed/watsan_di/) into the dashboard database.

The file is built from the same field-visit, report and spring-master tables as the planner by
scripts/build_watsan_di_sites.py. Every value keeps its record (before-DI recall, WATSAN report, field visit),
its basis (measured, estimate, report, recall, observed) and its source.

- Each site becomes a dashboard site; its first handpump is the selected handpump, the rest are additional handpumps.
- The October 2026 field visit becomes one saved visit per handpump (the spring reading sits on the first one).
- Every row also becomes a source observation (used for the before/after and last-two-records results) and an
  evidence record (shown under Sources).

The import runs when the server starts and only when the files have changed. Sites edited in the portal and
visits entered in the portal are kept.
"""

import csv
import hashlib
import re
from pathlib import Path

from .store import now

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data/02_processed/watsan_di"
FILES = ("watsan_di_sites_v1.csv", "watsan_di_handpumps_v1.csv", "watsan_di_observations_v1.csv")
RECORD_LABELS = {
    "before_di_recall": "Before DI (recalled)",
    "before_di_agreed": "Before DI",
    "after_di_agreed": "After DI",
    "watsan_report": "WATSAN report (undated)",
    "field_visit_2026_10": "Field visit, Oct 2026",
    "rajat_2026_10_24": "Team note (Rajat, Oct 2026)",
}
VISITOR = "DOCC/WATSAN field team"
# Planner defaults (scripts/module_c_di_impact.py): RDI design collects 70-80% of roof rain.
COLLECTION_FACTOR = 0.8


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(value):
    try:
        return None if value in ("", None) else float(value)
    except ValueError:
        return None


def readings_from(text):
    """'2 L in 4.9 s; 2 L in 5.3 s' -> [{'litres': 2, 'seconds': 4.9, 'rate_lpm': ...}, ...]"""
    rows = []
    for litres, seconds in re.findall(r"([\d.]+)\s*L in\s*([\d.]+)\s*s", text or ""):
        litres, seconds = float(litres), float(seconds)
        rows.append({"litres": litres, "seconds": seconds, "rate_lpm": 60 * litres / seconds})
    return rows


def site_key(site_id):
    return site_id.lower()


def build(folder=DEFAULT_DIR):
    """Return (digest, sites, visits, evidence, observations), or None when the data file is not there."""
    folder = Path(folder)
    if not all((folder / name).is_file() for name in FILES):
        return None
    digest = hashlib.sha256(b"".join((folder / name).read_bytes() for name in FILES)).hexdigest()
    site_rows = read(folder / FILES[0])
    pump_rows = read(folder / FILES[1])
    obs_rows = read(folder / FILES[2])
    stamp = now()
    sites, visits, evidence, observations = [], [], [], []
    pumps_by_site = {}
    for p in pump_rows:
        pumps_by_site.setdefault(p["site_id"], []).append(p)

    for r in site_rows:
        sid = site_key(r["site_id"])
        pumps = pumps_by_site.get(r["site_id"], [])
        handpumps = [
            {
                "id": p["handpump_id"],
                "name": p["name"],
                "primary": p.get("primary") == "yes",
                "latitude": num(p.get("latitude")),
                "longitude": num(p.get("longitude")),
                "elevation_m": num(p.get("elevation_m")),
                "height_above_spring_m": num(p.get("height_above_spring_m")),
                "distance_to_spring_m": num(p.get("distance_to_spring_m")),
                "bore_depth_m": num(p.get("bore_depth_m")),
                "roof_area_m2": num(p.get("roof_area_m2")),
                "roof_note": p.get("roof_note", ""),
                "di_year": num(p.get("di_install_year")),
                "di_install_note": p.get("di_install_note", ""),
                "link_status": p.get("link_status", ""),
                "remarks": p.get("remarks", ""),
                "other_work": p.get("other_work", ""),
                "di_note": p.get("di_note", ""),
                "pump_status": p.get("pump_status", ""),
                "di_status": p.get("di_status", ""),
                "location_class": p.get("location_class", ""),
                "location_note": p.get("location_note", ""),
                "location_status": "field_gps" if "Field form" in p.get("source", "") else "report",
            }
            for p in pumps
        ]
        primary = handpumps[0] if handpumps else None
        link = r.get("di_link_status", "")
        notes = [link] if link else []
        if r.get("top_concerns"):
            notes.append("Concern raised on the visit: " + r["top_concerns"])
        notes += [f"{h['name']}: {h['roof_note']}" for h in handpumps if h["roof_note"]]
        households = num(r.get("households"))
        sites.append(
            {
                "id": sid,
                "imported": True,
                "data_file_id": r["site_id"],
                "spring_record_id": r["spring_record_id"],
                "field_site_id": r.get("field_site_id", ""),
                "role": r["role"],
                "name": r["spring_name"],
                "spring_name": r["spring_name"],
                "other_names": r.get("other_names", ""),
                "village": r["village"],
                "district": r["district"],
                "handpump_name": primary["name"] if primary else "DI handpump to be added",
                "gps_later": False,
                "latitude": num(r["latitude"]),
                "longitude": num(r["longitude"]),
                "elevation_m": num(r.get("elevation_m")),
                "pump_gps_later": not (primary and primary["latitude"] is not None),
                "pump_latitude": primary["latitude"] if primary else None,
                "pump_longitude": primary["longitude"] if primary else None,
                "di_year": primary["di_year"] if primary else None,
                "roof_area_m2": primary["roof_area_m2"] if primary else None,
                "collection_factor": COLLECTION_FACTOR if primary and primary["roof_area_m2"] else None,
                "annual_rain_mm": num(r.get("annual_rain_mm")),
                "annual_rain_source": r.get("annual_rain_source", ""),
                "rain_chirps_mm": num(r.get("rain_chirps_mm")),
                "rain_monsoon_share_pct": num(r.get("rain_monsoon_share_pct")),
                "rain_dry_season_mm": num(r.get("rain_dry_season_mm")),
                "snow_mm": num(r.get("snow_mm")),
                "link_basis": "unknown" if "not established" in link.lower() or not primary else "reported",
                "water_before": r.get("water_before", ""),
                "supply": "",
                "households": int(households) if households is not None else None,
                "people": num(r.get("people")),
                "collection_before": "",
                "other_works": r.get("other_works", ""),
                "additional_handpumps": [h for h in handpumps[1:]],
                "handpumps": handpumps,
                "location_status": "field_gps" if r.get("field_site_id") else "report",
                "location_notes": "Spring position from the field visit."
                if r.get("field_site_id")
                else "Spring position from the SRHU report; not visited.",
                "evidence_notes": notes,
                "field_history": {
                    "seasonal_account": r.get("community_notes", ""),
                    "impact_beyond_water": r.get("impact_beyond_water", ""),
                    "source_spring_note": r.get("notes", ""),
                },
                "setup_complete": True,
                "registered_at": stamp,
                "updated_at": stamp,
            }
        )

        # One saved visit per handpump visited in October 2026; the spring reading goes on the first.
        field = [o for o in obs_rows if o["site_id"] == r["site_id"] and o["record"] == "field_visit_2026_10"]
        spring_obs = next((o for o in field if o["asset"] == "spring" and o["metric"] == "flow_lpm"), None)
        visited = [p for p in pumps if p.get("visit_date")] or ([] if not spring_obs else [None])
        for i, p in enumerate(visited):
            date = (p or {}).get("visit_date") or r.get("visit_date")
            vid = f"wdi-visit-{sid}-{(p or {}).get('handpump_id', 'spring').lower()}"
            spring = {"status": "not_measured", "reason": "Recorded with " + visited[0]["name"]} if i else spring_record(spring_obs)
            pump_id = (p or {}).get("handpump_id")
            changes = [
                {
                    "area": o["change_area"],
                    "direction": o["change_direction"],
                    "before": o["note"].split(" | ")[0],
                    "after": o["value_text"],
                    "basis": "people_said",
                    "who": "People met on the field visit",
                    "asset": o["asset"],
                    "caveat": o["note"].split(" | ")[1] if " | " in o["note"] else "",
                }
                for o in field
                if o["metric"] == "village_change" and (i == 0 or o["asset_id"] == pump_id)
            ]
            visits.append(
                {
                    "id": vid,
                    "imported": True,
                    "site_id": sid,
                    "status": "submitted",
                    "visit_date": date,
                    "visitor": VISITOR,
                    "season": "post_monsoon",
                    "period": "after_di",
                    "spring": spring,
                    "pump": {
                        "status": p.get("pump_status", "not_checked") if p else "not_checked",
                        "yield_text": (p or {}).get("pump_yield_text", ""),
                    },
                    "di": {"status": p.get("di_status", "not_checked") if p else "not_checked"},
                    "safety": {
                        "filter": (p or {}).get("filter") or "not_checked",
                        "first_flush": (p or {}).get("first_flush") or "not_checked",
                        "overflow": "not_checked",
                    },
                    "tests": [],
                    "change_status": "some" if changes else "not_discussed",
                    "changes": changes,
                    "other_work": r.get("other_works", "") if i == 0 else "",
                    "notes": (p or {}).get("notes", ""),
                    **({"pump_asset_name": p["name"]} if p and i else {}),
                    "entry_method": "source_review",
                    "rule_version": "2.0",
                    "created_at": stamp,
                    "saved_at": stamp,
                }
            )

    visit_ids = {v["id"] for v in visits}
    for o in obs_rows:
        sid = site_key(o["site_id"])
        if o["record"] == "field_visit_2026_10":
            suffix = o["asset_id"].lower() if o["asset"] == "handpump" else None
            vid = f"wdi-visit-{sid}-{suffix}" if suffix else None
            if vid not in visit_ids:
                vid = next((v for v in sorted(visit_ids) if v.startswith(f"wdi-visit-{sid}-")), None)
        else:
            vid = None
        low, high = num(o["value_low"]), num(o["value_high"])
        observations.append(
            {
                "id": o["obs_id"],
                "site_id": sid,
                "asset": o["asset"],
                "asset_id": o["asset_id"],
                "record": o["record"],
                "record_label": RECORD_LABELS.get(o["record"], o["record"]),
                "period": o["period"],
                "date": o["date"] or None,
                "metric": o["metric"],
                "low": low,
                "high": high,
                "text": o["value_text"],
                "basis": o["basis"],
                "source": o["source"],
                "note": o["note"],
                "visit_id": vid,
            }
        )
        value = o["value_text"] if low is None else (f"{low:g}" if high in (None, low) else f"{low:g}-{high:g}")
        evidence.append(
            {
                "id": "wdi-ev-" + o["obs_id"].lower(),
                "site_id": sid,
                "visit_id": vid,
                "asset": o["asset"] if o["asset"] in ("spring", "handpump", "village") else "site",
                "field": o["metric"] + (" · " + RECORD_LABELS.get(o["record"], o["record"])),
                "value": value + (" L/min" if o["metric"].endswith("_lpm") and low is not None else ""),
                "basis": o["basis"],
                "review_status": "source_transcribed",
                "source_excerpt": " ".join(x for x in (o["source"] + ".", o["note"]) if x),
                "saved_at": stamp,
            }
        )
    return digest, sites, visits, evidence, observations


def spring_record(o):
    """Spring part of the imported field visit, in the same shape as a portal visit."""
    if o is None:
        return {"status": "not_measured", "reason": "Spring not seen on the visit (water tapped at the handpump)."}
    low, high = num(o["value_low"]), num(o["value_high"])
    if o["basis"] == "measured":
        readings = readings_from(o["value_text"])
        mean = sum(r["rate_lpm"] for r in readings) / len(readings) if readings else low
        return {
            "status": "measured",
            "readings": readings,
            "flow_lpm": mean,
            "recalculated_lpm": mean,
            "flow_m3_s": mean / 60000,
            "capture": "full",
            "point": "Outlet/pipe",
            "method": "bucket_stopwatch",
        }
    if low is not None:
        return {"status": "not_measured", "reason": o["value_text"], "reported_range": [low, high]}
    return {"status": "not_measured", "reason": o["value_text"] or "Not measured"}


def load(store, folder=DEFAULT_DIR):
    """Import the data file into the store if it is there and has changed. Returns True when it imported."""
    built = build(folder)
    if built is None:
        return False
    return store.import_records(*built)
