"""Build the October 2026 field-visit tables (Tehri Garhwal springs and DI handpumps).

Inputs:  data/01_staged/field_visit/csv/field_visit_springs_2026-10.csv           (transcribed from the field forms)
         data/01_staged/field_visit/csv/field_visit_discharge_readings_2026-10.csv (bucket readings)
         data/01_staged/field_visit/csv/field_visit_di_sites_2026-10.csv           (DI handpumps)
         data/01_staged/field_visit/csv/field_visit_screen_scores_2026-10.csv      (quick vulnerability screen)
         data/01_staged/common/csv/spring_records_common_v1.csv                    (source coordinate of linked dataset springs)
         data/02_processed/spring_master/spring_master_v1.csv                      (test/input split of linked dataset springs)
Output:  data/02_processed/field_visit/field_visit_springs_v1.csv and field_visit_di_sites_v1.csv

Rules agreed with Rajat (2026-10-22):
- Field form values are the primary reference; WATSAN DTR values are kept beside them for reference only.
- Coordinates follow the field summary table (photo GPS stamps agree with it).
- Elevation is read from the Copernicus DEM at the field coordinate, as for every other dataset spring.
  The form altitude is kept as written.
- Measured flow = mean of the bucket readings (60 x litres / seconds). Estimates stay as low-high ranges.
- Screen bands for the 10-30 field screen: below 15 Low, 15-20 Medium, above 20 High. The team's scores are kept
  as written; a recomputed score applies the form's own rules to the answers on the same form.
- Every field spring is test data (all are in Tehri Garhwal); none is used to build or tune the model.

Usage: python scripts/build_field_visit.py [--cache DIR]
"""

import argparse
import csv
import math
import os
import statistics
from pathlib import Path

from build_spring_features import dem_features, dem_tiles_for, metres_per_degree

import rasterio


ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "data" / "01_staged" / "field_visit" / "csv"
SPRINGS_CSV = STAGED / "field_visit_springs_2026-10.csv"
READINGS_CSV = STAGED / "field_visit_discharge_readings_2026-10.csv"
DI_CSV = STAGED / "field_visit_di_sites_2026-10.csv"
SCORES_CSV = STAGED / "field_visit_screen_scores_2026-10.csv"
COMMON_CSV = ROOT / "data" / "01_staged" / "common" / "csv" / "spring_records_common_v1.csv"
MASTER_CSV = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1.csv"
OUT_DIR = ROOT / "data" / "02_processed" / "field_visit"

SCREEN_INDICATORS = ["lean_flow", "monsoon_over_lean", "low_flow_months", "water_quality", "flow_vs_past",
                     "households_per_lpm", "pollution_30m", "disturbance_uphill", "protection_committee", "recharge_works"]
# Rajat, 2026-10-22: below 15 Low, 15-20 Medium, above 20 High (sum of 10 scores, 10-30).
SCREEN_BANDS = [(14, "Low"), (20, "Medium"), (30, "High")]


def read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, digits=1):
    return "" if value is None else f"{value:.{digits}f}"


def screen_band(total):
    for upper, band in SCREEN_BANDS:
        if total <= upper:
            return band
    raise ValueError(f"screen total {total} is above 30")


def flow_from_readings(readings):
    """Mean, low and high L/min from bucket readings (litres, seconds)."""
    flows = [60 * float(r["litres"]) / float(r["seconds"]) for r in readings]
    return statistics.mean(flows), min(flows), max(flows)


def distance_m(lat1, lon1, lat2, lon2):
    m_lat, m_lon = metres_per_degree((lat1 + lat2) / 2)
    return math.hypot((lat1 - lat2) * m_lat, (lon1 - lon2) * m_lon)


def screen_totals(scores):
    """Team and recomputed totals per site, with bands; None when an indicator is missing."""
    by_site = {}
    for row in scores:
        by_site.setdefault(row["field_site_id"], {})[row["indicator"]] = row
    out = {}
    for site, rows in by_site.items():
        missing = [i for i in SCREEN_INDICATORS if i not in rows]
        if missing:
            raise ValueError(f"{site}: screen indicators missing {missing}")
        team = sum(int(rows[i]["team_score"]) for i in SCREEN_INDICATORS)
        new = sum(int(rows[i]["recomputed_score"]) for i in SCREEN_INDICATORS)
        first = rows[SCREEN_INDICATORS[0]]
        changes = [f"{i} {rows[i]['team_score']}->{rows[i]['recomputed_score']} ({rows[i]['recompute_note']})"
                   for i in SCREEN_INDICATORS if rows[i]["team_score"] != rows[i]["recomputed_score"]]
        out[site] = {
            "screen_team_total": team, "screen_team_total_written": first["team_total_written"],
            "screen_team_band_written": first["team_band_written"], "screen_team_band": screen_band(team),
            "screen_recomputed_total": new, "screen_recomputed_band": screen_band(new),
            "screen_recompute_changes": "; ".join(changes),
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    args = parser.parse_args()

    springs, di_sites = read(SPRINGS_CSV), read(DI_CSV)
    readings = {}
    for r in read(READINGS_CSV):
        readings.setdefault(r["field_site_id"], []).append(r)
    screens = screen_totals(read(SCORES_CSV))
    master = {r["record_id"]: r for r in read(MASTER_CSV)}
    # The master carries the field GPS for revisited springs, so offsets are measured from the source's own coordinate.
    source = {r["record_id"]: r for r in read(COMMON_CSV)}

    # DI handpumps linked by a report to a dataset spring that was not seen on the visit
    report_springs = {d["linked_dataset_spring_id"]: source[d["linked_dataset_spring_id"]] for d in di_sites
                      if d["linked_dataset_spring_id"] and not d["linked_spring_field_id"]}
    points = [(float(r["latitude"]), float(r["longitude"])) for r in springs + di_sites]
    points += [(float(r["latitude_source_value"]), float(r["longitude_source_value"])) for r in report_springs.values()]
    dem = [rasterio.open(p) for p in dem_tiles_for(points, Path(args.cache))]

    def dem_elevation(lat, lon):
        value = dem_features(dem, lon, lat).get("dem_elevation_m")
        return None if value is None or math.isnan(value) else float(value)

    spring_elev = {}
    out_springs = []
    for s in springs:
        lat, lon = float(s["latitude"]), float(s["longitude"])
        elev = dem_elevation(lat, lon)
        spring_elev[s["field_site_id"]] = elev
        row = dict(s)
        row["elevation_m"] = fmt(elev)
        row["elevation_source"] = "Copernicus DEM GLO-30 at the field coordinate"
        site_readings = readings.get(s["field_site_id"], [])
        if site_readings:
            mean, low, high = flow_from_readings(site_readings)
            row.update(flow_today_lpm=fmt(mean), flow_today_lpm_low=fmt(low), flow_today_lpm_high=fmt(high),
                       flow_today_basis=f"mean of {len(site_readings)} bucket readings")
        elif s["flow_today_lpm_low"]:
            row.update(flow_today_lpm="", flow_today_basis=f"{s['flow_today_status']} (range from the form)")
        else:
            row.update(flow_today_lpm="", flow_today_basis=s["flow_today_status"])
        record = source.get(s["dataset_spring_id"])
        if record:
            src_lat, src_lon = record["latitude_source_value"], record["longitude_source_value"]
            row["dataset_latitude"], row["dataset_longitude"] = src_lat, src_lon
            row["dataset_offset_m"] = fmt(distance_m(lat, lon, float(src_lat), float(src_lon)), 0)
            row["dataset_split"] = master[s["dataset_spring_id"]]["dataset_split"]
        else:
            row.update(dataset_latitude="", dataset_longitude="", dataset_offset_m="", dataset_split="test (new spring)")
        row.update(screens[s["field_site_id"]])
        out_springs.append(row)

    out_di = []
    for d in di_sites:
        lat, lon = float(d["latitude"]), float(d["longitude"])
        elev = dem_elevation(lat, lon)
        row = dict(d)
        row["elevation_m"] = fmt(elev)
        spring = d["linked_spring_field_id"]
        report_spring = report_springs.get(d["linked_dataset_spring_id"]) if not spring else None
        if spring and spring in spring_elev and elev is not None and spring_elev[spring] is not None:
            target = next(s for s in springs if s["field_site_id"] == spring)
            row["height_above_spring_dem_m"] = fmt(elev - spring_elev[spring], 0)
            row["distance_to_spring_m"] = fmt(distance_m(lat, lon, float(target["latitude"]), float(target["longitude"])), 0)
        elif report_spring and elev is not None:
            s_lat, s_lon = float(report_spring["latitude_source_value"]), float(report_spring["longitude_source_value"])
            s_elev = dem_elevation(s_lat, s_lon)
            row["height_above_spring_dem_m"] = "" if s_elev is None else fmt(elev - s_elev, 0)
            row["distance_to_spring_m"] = fmt(distance_m(lat, lon, s_lat, s_lon), 0)
        else:
            row["height_above_spring_dem_m"] = row["distance_to_spring_m"] = ""
        out_di.append(row)

    write(OUT_DIR / "field_visit_springs_v1.csv", out_springs)
    write(OUT_DIR / "field_visit_di_sites_v1.csv", out_di)
    for r in out_springs:
        print(f"{r['field_site_id']:9} {r['spring_name']:14} elev {r['elevation_m']:>7} flow {r['flow_today_lpm'] or '-':>5} "
              f"offset {r['dataset_offset_m'] or '-':>4} m  screen team {r['screen_team_total']} {r['screen_team_band']:6} "
              f"recomputed {r['screen_recomputed_total']} {r['screen_recomputed_band']}")
    for r in out_di:
        print(f"{r['di_site_id']:13} elev {r['elevation_m']:>7}  above spring {r['height_above_spring_dem_m'] or '-':>4} m  "
              f"distance {r['distance_to_spring_m'] or '-':>4} m")


if __name__ == "__main__":
    main()
