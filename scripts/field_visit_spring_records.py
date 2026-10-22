"""Common-file records for springs first seen on the October 2026 DoCC field visit.

Springs the dataset already lists (dataset_spring_id filled) are not added again: their field GPS
moves the existing record in scripts/build_spring_features.py instead. Every other field spring
becomes one FLD-SPR-nnnn record, with values copied as text from the staged field table.

Usage (adds or replaces the FLD rows in the current common file without re-staging the other sources):
    python scripts/field_visit_spring_records.py
stage_watsan_and_spring_atlas.py calls build() as well, so a full re-stage keeps them.
"""

import csv
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIELD_DIR = ROOT / "data" / "01_staged" / "field_visit" / "csv"
SPRINGS_CSV = FIELD_DIR / "field_visit_springs_2026-10.csv"
READINGS_CSV = FIELD_DIR / "field_visit_discharge_readings_2026-10.csv"
COMMON_CSV = ROOT / "data" / "01_staged" / "common" / "csv" / "spring_records_common_v1.csv"
COMMON_METADATA = ROOT / "data" / "01_staged" / "common" / "metadata" / "spring_records_common_v1_metadata.json"
PREFIX = "FLD"
SOURCE_ID = "SRC-026"
SOURCE_DATASET = "DoCC field visit October 2026 - field form (Field_Form_Spring_DI_v1)"
REFERENCE = ("DoCC/SRHU field visit with RDI/WATSAN, Tehri Garhwal, 13 and 18-21 October 2026: field forms, site summary "
             "table and GPS-stamped photos (kept off the repository), transcribed in data/01_staged/field_visit/")


def read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def flow_text(spring, readings):
    """Flow today as text: bucket mean where measured, else the form's range, with how it was found.
    No other numbers: the feature build reads the lowest and highest number in this text as the flow range."""
    if readings:
        flows = [60 * float(r["litres"]) / float(r["seconds"]) for r in readings]
        return f"{statistics.mean(flows):.1f} L/min (mean of the bucket readings)"
    low, high = spring["flow_today_lpm_low"], spring["flow_today_lpm_high"]
    if not low:
        return ""
    value = low if low == high else f"{low}-{high}"
    return f"{value} L/min ({spring['flow_today_status']})"


def field_flows():
    """{dataset record id: (low, high, text)} for dataset springs whose flow was read or estimated on the visit.
    Rajat (2026-10-22): the field form flow is the primary value; the source report's value stays as reference."""
    readings = {}
    for r in read(READINGS_CSV):
        readings.setdefault(r["field_site_id"], []).append(r)
    flows = {}
    for spring in read(SPRINGS_CSV):
        text = flow_text(spring, readings.get(spring["field_site_id"]))
        if not spring["dataset_spring_id"] or not text:
            continue
        if spring["field_site_id"] in readings:
            low = high = round(statistics.mean(60 * float(r["litres"]) / float(r["seconds"]) for r in readings[spring["field_site_id"]]), 1)
        else:
            low, high = float(spring["flow_today_lpm_low"]), float(spring["flow_today_lpm_high"])
        flows[spring["dataset_spring_id"]] = (low, high, f"{text}, {spring['visit_date']}")
    return flows


def build(common_columns, point_wkt):
    """One common-file row per field spring that is not already in the dataset."""
    readings = {}
    for r in read(READINGS_CSV):
        readings.setdefault(r["field_site_id"], []).append(r)
    records = []
    for spring in read(SPRINGS_CSV):
        if spring["dataset_spring_id"]:
            continue
        seasons = [spring["flow_by_month_jan_dec"]]
        if spring["lean_flow_lpm_low"]:
            seasons.append(f"lean flow {spring['lean_flow_lpm_low']}-{spring['lean_flow_lpm_high']} L/min (recall)")
        if spring["ever_dried"]:
            seasons.append(f"ever dried: {spring['ever_dried']}")
        if spring["flow_vs_10_20_years"]:
            seasons.append(f"flow vs 10-20 years ago: {spring['flow_vs_10_20_years']}")
        row = {column: "" for column in common_columns}
        row.update({
            "record_id": f"{PREFIX}-SPR-{len(records) + 1:04d}",
            "source_id": SOURCE_ID,
            "source_dataset": SOURCE_DATASET,
            "source_record_locator": f"data/01_staged/field_visit/csv/field_visit_springs_2026-10.csv, {spring['field_site_id']}",
            "district": spring["district"],
            "village": spring["village"],
            "spring_name": spring["spring_name"],
            "latitude_source_value": spring["latitude"],
            "longitude_source_value": spring["longitude"],
            "elevation_m_source_value": spring["elevation_form_m"],
            "land_use_source_value": f"uphill forest {spring['uphill_forest_pct']}%" if spring["uphill_forest_pct"] else "",
            "spring_type_source_value": spring["spring_type_form"],
            "discharge_lpm_source_value": flow_text(spring, readings.get(spring["field_site_id"])),
            "seasonality_source_value": "; ".join(s for s in seasons if s),
            "rock_type_source_value": spring["rock_at_outlet_form"],
            "geometry_wkt": point_wkt(spring["longitude"], spring["latitude"]),
            "staging_quality_flag": "Field record: coordinate from a GPS-stamped photo; flow estimated by eye unless bucket readings are named; "
                                    "form elevation is approximate (use the DEM value).",
            "source_notes": f"Visited {spring['visit_date']}. Coordinate source: {spring['coordinate_source']}. {spring['notes']}".strip(),
            "source_reference": REFERENCE,
            "value_status_summary": "Coordinate from GPS photo; flow and recall from the field form; rock and spring type are field guesses.",
            "intervention_source_value": spring["recharge_works_uphill"],
        })
        records.append(row)
    return records


def main():
    with open(COMMON_CSV, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, [r for r in reader if not r["record_id"].startswith(PREFIX)]
    added = build(columns, lambda lon, lat: f"POINT ({lon} {lat})" if lon and lat else "")
    with open(COMMON_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows + added)
    metadata = json.loads(COMMON_METADATA.read_text(encoding="utf-8"))
    metadata["field_visit_common_records"] = len(added)
    metadata["combined_common_records"] = len(rows) + len(added)
    note = ("Field visit records (FLD prefix) are springs first seen on the October 2026 DoCC field visit; "
            "see data/01_staged/field_visit/README.md.")
    if note not in metadata["notes"]:
        metadata["notes"].append(note)
    COMMON_METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"{len(added)} field visit records; common file now {len(rows) + len(added)} rows")


if __name__ == "__main__":
    main()
