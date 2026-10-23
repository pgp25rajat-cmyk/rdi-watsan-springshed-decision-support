"""Per-spring values from the secondary layers collected after the SRHU geologist reports (October 2026).

Adds one row per record of data/02_processed/spring_features/spring_features_v1.csv, keyed by record_id, to
data/02_processed/spring_features/spring_secondary_features_v1.csv. build_spring_master.py joins it, and Module A
uses it as the comparison set for its shallow-soil, landslide and snow indicators.
The layers and the per-point reading are in scripts/secondary_layers.py (the tool reads them the same way).

Usage: python scripts/build_spring_secondary_features.py --layers "DOCC/Data/Secondary data"
"""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np

from secondary_layers import COLUMNS, DENSE_NDVI, OPEN_NDVI, SNOW_TIF, SecondaryLayers

ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_features_v1.csv"
OUT_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_secondary_features_v1.csv"
OUT_META = ROOT / "data" / "02_processed" / "spring_features" / "spring_secondary_features_v1_metadata.json"
REPORT_CATCHMENTS = ROOT / "data" / "01_staged" / "literature" / "geojson" / "report_catchments_v1.geojson"
NAMES = ["record_id"] + [c[0] for c in COLUMNS]
DIGITS = {"ndvi_s2_2025": 2, "soil_ksat_0_30cm_mm_h": 1, "report_catchment_ha": 1}


def fmt(value, digits=0):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return ""
    if isinstance(value, str):
        return value
    return f"{value:.{digits}f}" if digits else str(int(round(value)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layers", type=Path, required=True, help="DOCC/Data/Secondary data")
    args = parser.parse_args()
    layers = SecondaryLayers(args.layers)
    catchments = {f["properties"]["record_id"]: f["properties"]["area_ha_traced"]
                  for f in json.loads(REPORT_CATCHMENTS.read_text(encoding="utf-8"))["features"]}

    with open(FEATURES_CSV, newline="", encoding="utf-8") as handle:
        features = list(csv.DictReader(handle))
    rows, filled = [], {name: 0 for name in NAMES[1:]}
    for f in features:
        values = {"report_catchment_ha": catchments.get(f["record_id"])}
        if f["coordinate_status"] == "ok":
            height = f["source_elevation_m"] or f["dem_elevation_m"]  # recorded height first, as the tool does
            values.update(layers.point(float(f["longitude_dd"]), float(f["latitude_dd"]), float(height) if height else None))
        row = {"record_id": f["record_id"], **{n: fmt(values.get(n), DIGITS.get(n, 0)) for n in NAMES[1:]}}
        for name in NAMES[1:]:
            filled[name] += bool(row[name])
        rows.append(row)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=NAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    OUT_META.write_text(json.dumps({
        "built": date.today().isoformat(), "records": len(rows), "filled": filled,
        "layers": [str(p.relative_to(args.layers)) for _, p in layers.files()] + ([str(SNOW_TIF.relative_to(ROOT))] if SNOW_TIF.exists() else []),
        "missing_layers": layers.missing,
        "notes": ["Module A scores shallow soil and landslides from these columns; Modules B and C read the layers directly.",
                  "Bhukosh layers cover Uttarakhand; Sentinel-2 NDVI covers Tehri district; dip points cover Kumaon sheets only.",
                  f"Forest cut-offs are provisional: dense NDVI >= {DENSE_NDVI}, open {OPEN_NDVI}-{DENSE_NDVI}."],
    }, indent=2), encoding="utf-8")
    print(f"{len(rows)} records -> {OUT_CSV.relative_to(ROOT)}")
    for name, count in filled.items():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
