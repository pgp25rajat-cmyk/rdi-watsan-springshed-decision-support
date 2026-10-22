"""Per-spring values from the secondary layers collected after the SRHU geologist reports (October 2026).

Adds one row per record of data/02_processed/spring_features/spring_features_v1.csv, keyed by record_id, to
data/02_processed/spring_features/spring_secondary_features_v1.csv. build_spring_master.py joins it.
These are data columns only: no module reads them yet (Rajat, 2026-10-22: finalise the data, change the model later).

Layers (all under SECONDARY_DIR, i.e. DOCC/Data/Secondary data):
- NGDR(Bhukosh) GEOMORPHOLOGY_250K / LINEAMENT_250K, LANDSLIDE_POLYGON, ORIENTED_STRUCTURE_PLANE zips (SRC-029 to SRC-032).
  Uttarakhand only: springs outside the state are left blank.
- Sentinel2/S2_NDVI_Tehri_OctNov2025_20m.tif (SRC-033). Tehri district only.
- Infiltration/Ksat_0-30cm_SaxtonRawls_mmh.tif (TRN-018).
- SoilGrids/BDRICM_M_250m_Uttarakhand.tif (SoilGrids 2017 depth to bedrock, cm, capped at 200; SRC-034).
- Report catchments traced from the SRHU reports (data/01_staged/literature/geojson/report_catchments_v1.geojson).

Usage: python scripts/build_spring_secondary_features.py --layers "DOCC/Data/Secondary data"
"""

import argparse
import csv
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import Window
import shapely
from shapely import STRtree, prepare
from shapely.geometry import Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_features_v1.csv"
OUT_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_secondary_features_v1.csv"
OUT_META = ROOT / "data" / "02_processed" / "spring_features" / "spring_secondary_features_v1_metadata.json"
REPORT_CATCHMENTS = ROOT / "data" / "01_staged" / "literature" / "geojson" / "report_catchments_v1.geojson"

DIP_RADIUS_M = 5000
LANDSLIDE_RADIUS_M = 500
FOREST_RADIUS_M = 500
DENSE_NDVI, OPEN_NDVI = 0.70, 0.50  # provisional forest cut-offs (README in Secondary data/Sentinel2)

# (column, unit, from, meaning) - also the data dictionary rows in build_spring_master.py
COLUMNS = [
    ("bhukosh_geomorphology_250k", "", "GSI Bhukosh geomorphology 1:250k", "Landform class of the map polygon at the spring (coarse: most hill springs are Highly Dissected Structural Hills and Valleys)."),
    ("bhukosh_lineament_distance_m", "m", "GSI Bhukosh lineaments 1:250k", "Distance to the nearest mapped lineament of any kind."),
    ("bhukosh_lineament_nearest_type", "", "GSI Bhukosh lineaments 1:250k", "Fault, Joint/Fracture, Drainage parallel, Axial trace of fold, Shear zone, ..."),
    ("bhukosh_joint_distance_m", "m", "GSI Bhukosh lineaments 1:250k", "Distance to the nearest mapped joint or fracture lineament."),
    ("landslide_distance_m", "m", "GSI Bhukosh landslide polygons", "Distance to the nearest mapped landslide (0 = inside one)."),
    ("landslide_count_500m", "count", "GSI Bhukosh landslide polygons", "Mapped landslides within 500 m."),
    ("landslide_landform_nearest", "", "GSI Bhukosh landslide polygons", "Landform (geom11) of the nearest landslide, e.g. colluvial foot slope."),
    ("gsi_dip_points_5km", "count", "GSI Bhukosh Geology 50K structure planes", "Measured bedding/foliation/joint planes within 5 km. Kumaon sheets only (53O, 62C, 53N)."),
    ("gsi_dip_nearest_distance_m", "m", "GSI Bhukosh Geology 50K structure planes", "Distance to the nearest measurement within 5 km."),
    ("gsi_dip_nearest_type", "", "GSI Bhukosh Geology 50K structure planes", "Bedding, foliation/cleavage/schistosity or joint."),
    ("gsi_dip_nearest_deg", "deg", "GSI Bhukosh Geology 50K structure planes", "Dip amount of the nearest measurement."),
    ("gsi_dip_nearest_direction_deg", "deg", "GSI Bhukosh Geology 50K structure planes", "Dip direction (azimuth) of the nearest measurement."),
    ("gsi_dip_median_5km_deg", "deg", "GSI Bhukosh Geology 50K structure planes", "Median dip amount of bedding and foliation within 5 km."),
    ("ndvi_s2_2025", "", "Sentinel-2 Oct-Nov 2025 NDVI", "Post-monsoon NDVI around the spring (60 m window). Tehri district only."),
    ("forest_dense_500m_pct", "%", "Sentinel-2 Oct-Nov 2025 NDVI", "Share within 500 m with NDVI >= 0.70 (provisional dense-forest cut-off)."),
    ("forest_open_500m_pct", "%", "Sentinel-2 Oct-Nov 2025 NDVI", "Share within 500 m with NDVI 0.50-0.70 (provisional open-forest cut-off)."),
    ("soil_ksat_0_30cm_mm_h", "mm/h", "SoilGrids 2.0, Saxton & Rawls 2006", "Topsoil infiltration capacity (texture estimate; ignores cracks and roots)."),
    ("soil_depth_to_bedrock_cm", "cm", "SoilGrids 2017 BDRICM", "Depth to bedrock (R horizon). Capped at 200: read 200 as 200 cm or deeper."),
    ("report_catchment_ha", "ha", "SRHU geohydrology reports, traced", "Catchment drawn by the report geologists, measured from the traced outline (Badeda, Makhdet only; test springs)."),
]
NAMES = ["record_id"] + [c[0] for c in COLUMNS]

TO_UTM = Transformer.from_crs(4326, 32644, always_xy=True)


def to_utm(geometry):
    return shapely.transform(geometry, lambda xy: np.c_[TO_UTM.transform(xy[:, 0], xy[:, 1])])


def read_zipped_geojson(path, member_hint):
    """Bhukosh zips hold a zip that holds the GeoJSON."""
    with zipfile.ZipFile(path) as outer:
        inner_name = next(n for n in outer.namelist() if member_hint in n)
        data = outer.read(inner_name)
    if inner_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as inner:
            data = inner.read(next(n for n in inner.namelist() if n.endswith(".geojson")))
    return json.loads(data)["features"]


def find_zip(folder, prefix):
    return next(p for p in sorted(folder.glob(f"{prefix}*.zip")))


def nearest(tree, geoms, point):
    index = tree.nearest(point)
    return index, geoms[index].distance(point)


def window_values(src, lon, lat, radius_m):
    """Valid raster values in a square window of the given radius around the point."""
    row, col = src.index(lon, lat)
    half_x = max(1, int(round(radius_m / (abs(src.res[0]) * 111320 * np.cos(np.radians(lat))))))
    half_y = max(1, int(round(radius_m / (abs(src.res[1]) * 110540))))
    if not (0 <= row < src.height and 0 <= col < src.width):
        return None
    window = Window(col - half_x, row - half_y, 2 * half_x + 1, 2 * half_y + 1)
    values = src.read(1, window=window, boundless=True, fill_value=src.nodata if src.nodata is not None else np.nan).astype("float64")
    valid = np.isfinite(values)
    if src.nodata is not None and np.isfinite(src.nodata):
        valid &= values != src.nodata
    return values[valid]


def fmt(value, digits=0):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return ""
    return f"{value:.{digits}f}" if digits else str(int(round(value)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layers", type=Path, required=True, help="DOCC/Data/Secondary data")
    args = parser.parse_args()
    bhukosh = args.layers / "NGDR(Bhukosh)"

    geomorph = [(shape(f["geometry"]), f["properties"].get("descriptio") or "") for f in
                read_zipped_geojson(find_zip(bhukosh, "GEOMORPHOLOGY_250K"), "GEOMORPHOLOGY") if f["geometry"]]
    state = unary_union([g.buffer(0) for g, _ in geomorph])
    prepare(state)
    geomorph_tree = STRtree([g for g, _ in geomorph])
    lineaments = [(to_utm(shape(f["geometry"])), f["properties"].get("l2descript") or "") for f in
                  read_zipped_geojson(find_zip(bhukosh, "GEOMORPHOLOGY_250K"), "LINEAMENT") if f["geometry"]]
    line_geoms = [g for g, _ in lineaments]
    joint_geoms = [g for g, kind in lineaments if "joint" in kind.lower() or "fracture" in kind.lower()]
    line_tree, joint_tree = STRtree(line_geoms), STRtree(joint_geoms)
    slides = [(to_utm(shape(f["geometry"]).buffer(0)), f["properties"].get("geom11") or "") for f in
              read_zipped_geojson(find_zip(bhukosh, "LANDSLIDE_POLYGON"), "LANDSLIDE") if f["geometry"]]
    slide_geoms = [g for g, _ in slides]
    slide_tree = STRtree(slide_geoms)
    planes = [f for f in read_zipped_geojson(find_zip(bhukosh, "ORIENTED_STRUCTURE_PLANE"), "ORIENTED") if f["geometry"]]
    plane_points = [Point(TO_UTM.transform(*f["geometry"]["coordinates"][:2])) for f in planes]
    plane_tree = STRtree(plane_points)
    catchments = {f["properties"]["record_id"]: f["properties"]["area_ha_traced"]
                  for f in json.loads(REPORT_CATCHMENTS.read_text(encoding="utf-8"))["features"]}

    rasters = {
        "ndvi": args.layers / "Sentinel2" / "S2_NDVI_Tehri_OctNov2025_20m.tif",
        "ksat": args.layers / "Infiltration" / "Ksat_0-30cm_SaxtonRawls_mmh.tif",
        "depth": args.layers / "SoilGrids" / "BDRICM_M_250m_Uttarakhand.tif",
    }
    sources = {k: rasterio.open(p) for k, p in rasters.items() if p.exists()}

    with open(FEATURES_CSV, newline="", encoding="utf-8") as handle:
        features = list(csv.DictReader(handle))
    rows, filled = [], {name: 0 for name in NAMES[1:]}
    for f in features:
        row = {name: "" for name in NAMES}
        row["record_id"] = f["record_id"]
        row["report_catchment_ha"] = fmt(catchments.get(f["record_id"]), 1)
        if f["coordinate_status"] == "ok":
            lon, lat = float(f["longitude_dd"]), float(f["latitude_dd"])
            point_ll, point = Point(lon, lat), Point(TO_UTM.transform(lon, lat))
            if state.contains(point_ll):
                hits = [geomorph[i][1] for i in geomorph_tree.query(point_ll, predicate="within")]
                row["bhukosh_geomorphology_250k"] = hits[0] if hits else ""
                i, d = nearest(line_tree, line_geoms, point)
                row["bhukosh_lineament_distance_m"], row["bhukosh_lineament_nearest_type"] = fmt(d), lineaments[i][1]
                row["bhukosh_joint_distance_m"] = fmt(nearest(joint_tree, joint_geoms, point)[1])
                i, d = nearest(slide_tree, slide_geoms, point)
                row["landslide_distance_m"], row["landslide_landform_nearest"] = fmt(d), slides[i][1]
                row["landslide_count_500m"] = str(len(slide_tree.query(point, predicate="dwithin", distance=LANDSLIDE_RADIUS_M)))
                near = sorted(plane_tree.query(point, predicate="dwithin", distance=DIP_RADIUS_M),
                              key=lambda j: plane_points[j].distance(point))
                row["gsi_dip_points_5km"] = str(len(near))
                if near:
                    p = planes[near[0]]["properties"]
                    row["gsi_dip_nearest_distance_m"] = fmt(plane_points[near[0]].distance(point))
                    row["gsi_dip_nearest_type"] = p["point_type"]
                    row["gsi_dip_nearest_deg"] = fmt(p["dip_amount"])
                    row["gsi_dip_nearest_direction_deg"] = fmt(p["dip_direct"])
                    dips = [planes[j]["properties"]["dip_amount"] for j in near
                            if "JOINT" not in planes[j]["properties"]["point_type"] and planes[j]["properties"]["dip_amount"] is not None]
                    row["gsi_dip_median_5km_deg"] = fmt(float(np.median(dips))) if dips else ""
            if "ndvi" in sources:
                around = window_values(sources["ndvi"], lon, lat, 30)
                if around is not None and around.size:
                    row["ndvi_s2_2025"] = fmt(float(np.mean(around)) / 100, 2)
                    ring = window_values(sources["ndvi"], lon, lat, FOREST_RADIUS_M) / 100
                    row["forest_dense_500m_pct"] = fmt(100 * float(np.mean(ring >= DENSE_NDVI)))
                    row["forest_open_500m_pct"] = fmt(100 * float(np.mean((ring >= OPEN_NDVI) & (ring < DENSE_NDVI))))
            for key, column, digits in (("ksat", "soil_ksat_0_30cm_mm_h", 1), ("depth", "soil_depth_to_bedrock_cm", 0)):
                if key in sources:
                    value = float(next(sources[key].sample([(lon, lat)]))[0])
                    if np.isfinite(value) and value != sources[key].nodata:
                        row[column] = fmt(value, digits)
        for name in NAMES[1:]:
            filled[name] += bool(row[name])
        rows.append(row)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=NAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    OUT_META.write_text(json.dumps({
        "built": date.today().isoformat(), "records": len(rows), "filled": filled,
        "layers": {k: str(p.relative_to(args.layers)) for k, p in rasters.items() if p.exists()},
        "missing_layers": [str(p.relative_to(args.layers)) for p in rasters.values() if not p.exists()],
        "notes": ["Data columns only; not used by Modules A-C yet.",
                  "Bhukosh layers cover Uttarakhand; Sentinel-2 NDVI covers Tehri district; dip points cover Kumaon sheets only.",
                  f"Forest cut-offs are provisional: dense NDVI >= {DENSE_NDVI}, open {OPEN_NDVI}-{DENSE_NDVI}."],
    }, indent=2), encoding="utf-8")
    print(f"{len(rows)} records -> {OUT_CSV.relative_to(ROOT)}")
    for name, count in filled.items():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
