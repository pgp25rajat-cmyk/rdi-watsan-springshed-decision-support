"""Where each WATSAN DI handpump sits for its spring, as the spring planner sees it (Modules B and C).

    python scripts/planner_di_locations.py

Runs the planner once for each WATSAN DI spring in data/02_processed/watsan_di/ with its DI handpumps and the
after-DI flows Rajat agreed (2026-10-24), and writes each handpump's location class (in a recharge zone on the
spring's slope, linked by a fault or crack, in the catchment, outside, below the spring) to
data/02_processed/watsan_di/planner_di_locations_v1.csv. scripts/build_watsan_di_sites.py reads that file, so the
DI dashboard uses the same share of injected water reaching the spring as the planner (Rajat, 2026-10-24).
Run it again, then the builder, after the planner's method or the DI sites change. It needs the planner's map
layers (SPRING_LAYER_CACHE, SPRING_LOCAL_LAYERS), as the tool does.
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "02_processed" / "watsan_di"
OUT = DATA / "planner_di_locations_v1.csv"
os.environ.setdefault("SPRING_RUNS_DIR", tempfile.mkdtemp(prefix="di-locations-"))  # keep these runs out of tool_runs
sys.path.insert(0, str(ROOT / "scripts"))
import spring_tool_server as tool_server  # noqa: E402

FIELDS = ["site_id", "spring_name", "handpump_id", "handpump_name", "location_class", "zone_id", "location_note",
          "lean_flow_lpm", "monsoon_flow_lpm", "volume_m3_per_year", "reaching_m3_mid", "map_set", "run_date"]


def number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def main():
    sites = list(csv.DictReader(open(DATA / "watsan_di_sites_v1.csv", encoding="utf-8")))
    pumps = list(csv.DictReader(open(DATA / "watsan_di_handpumps_v1.csv", encoding="utf-8")))
    flows = {}
    for o in csv.DictReader(open(DATA / "watsan_di_observations_v1.csv", encoding="utf-8")):
        if o["asset"] == "spring" and o["period"] == "after_di" and o["metric"] in ("lean_flow_lpm", "monsoon_flow_lpm"):
            low, high = number(o["value_low"]), number(o["value_high"])
            if low is not None:
                flows[(o["site_id"], o["metric"])] = (low + (high if high is not None else low)) / 2
    tool = tool_server.Tool()
    rows = []
    for s in sites:
        mine = [p for p in pumps if p["site_id"] == s["site_id"] and number(p["latitude"]) is not None]
        if not mine:
            continue
        field = {k: flows[(s["site_id"], k)] for k in ("lean_flow_lpm", "monsoon_flow_lpm") if (s["site_id"], k) in flows}
        request = {
            "spring": {"name": s["spring_name"], "latitude": float(s["latitude"]), "longitude": float(s["longitude"]),
                       "elevation_m": number(s["elevation_m"])},
            "field": field,
            "di": {"sites": [{"id": p["handpump_id"], "name": p["name"], "latitude": float(p["latitude"]),
                              "longitude": float(p["longitude"]), "roof_area_m2": number(p["roof_area_m2"]) or 100,
                              "depth_m": number(p["bore_depth_m"]) or 70, "first_flush": True, "filter": True}
                             for p in mine],
                   "assumptions": {}},
        }
        response = tool.assess(request)
        result = (response["C"] or {}).get("result") or {}
        by_id = {r["id"]: r for r in result.get("sites", [])}
        for p in mine:
            r = by_id.get(p["handpump_id"])
            if r is None:
                print(f"{s['spring_name']} / {p['name']}: no planner result ({response['C'].get('status')})")
                continue
            rows.append({
                "site_id": s["site_id"], "spring_name": s["spring_name"], "handpump_id": p["handpump_id"],
                "handpump_name": p["name"], "location_class": r["location_class"], "zone_id": r.get("zone_id") or "",
                "location_note": r["location_note"], "lean_flow_lpm": field.get("lean_flow_lpm", ""),
                "monsoon_flow_lpm": field.get("monsoon_flow_lpm", ""), "volume_m3_per_year": r["volume_m3_per_year"],
                "reaching_m3_mid": r["reaching_m3_per_year"]["mid"], "map_set": response["map_set"],
                "run_date": date.today().isoformat(),
            })
            print(f"{s['spring_name']:14} {p['name']:12} {r['location_class']:14} {r.get('zone_id') or '':3} "
                  f"reaching {r['reaching_m3_per_year']['mid']} of {r['volume_m3_per_year']} m3/yr")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(rows)} handpump rows)")


if __name__ == "__main__":
    main()
