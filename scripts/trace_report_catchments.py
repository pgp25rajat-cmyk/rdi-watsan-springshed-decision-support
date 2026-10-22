"""Trace the catchment boundary drawn in each SRHU hydrogeology report and place it on the map.

WATSAN has no boundary files (Rajat, 2026-10-22), so the boundary is taken from the report itself. Each report
prints its catchment as a filled polygon on a geology map with a latitude/longitude grid. This script:
1. extracts that map image from the PDF (poppler's pdfimages);
2. finds the grid ticks on the map frame and joins each pair into a grid line; their crossings are control
   points with known coordinates, fitted to the image by an affine transform in UTM 44N;
3. traces the filled polygon (the largest patch of the fill colour, outline included);
4. checks the fit: the printed spring and handpump markers against their printed coordinates.

Results (2026-10-22): Makhdet 94.3 ha (report 91.07 ha), markers within 40 m. Badeda 12.4 ha, markers within
5 m; the report's 40.51 ha appears only in its land-use map, whose grid labels repeat and whose projection is
given as UTM 43N, so that map looks redrawn and its area is not used.
Both springs are in the held-out test set: use these boundaries only for the final check, never for tuning.

Usage: python scripts/trace_report_catchments.py REPORT_DIR
REPORT_DIR is DOCC/Data/Reference data received from RDI. Writes
data/01_staged/literature/geojson/report_catchments_v1.geojson.
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage
import shapely
from shapely.geometry import Point, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "01_staged" / "literature" / "geojson" / "report_catchments_v1.geojson"


def dms(degrees, minutes, seconds):
    return degrees + minutes / 60 + seconds / 3600


# Pixel positions of the grid ticks were read from the extracted images (tick marks just outside the map frame).
# Each grid line is (value, pixel point at one frame edge, pixel point at the opposite edge).
REPORTS = [
    {
        "record_id": "RDI-SPR-0008", "name": "Badeda Spring", "source_id": "SRC-027",
        "pdf": "Badera Geohydrology  report.pdf", "image": 7, "figure": "Figure 7 Geological Map",
        "report_area_ha": 40.51,
        "lon_lines": [(dms(78, 18, s), (top, 31), (bottom, 598))
                      for s, top, bottom in [(40, 149.0, 135.5), (45, 334.0, 320.5), (50, 518.5, 505.5), (55, 703.5, 690.5)]],
        "lat_lines": [(dms(30, 10, s), (26, left), (854, right))
                      for s, left, right in [(25, 136.5, 155.5), (20, 349.0, 368.5), (15, 561.5, 581.5)]],
        "checks": {"spring": (dms(78, 18, 46.42), dms(30, 10, 17.26)), "handpump": (dms(78, 18, 46.25), dms(30, 10, 24.21))},
        "note": "Same outline on the DEM, soil, slope, aspect, geology, geomorphology and soil depth maps. The 40.51 ha "
                "in the land-use table is not supported by the report's own outline.",
    },
    {
        "record_id": "RDI-SPR-0009", "name": "Makhdet Spring", "source_id": "SRC-028",
        "pdf": "Domsi & Makhdet Geohydrology report.pdf", "image": 9, "figure": "Figure 7 Geological Map",
        "report_area_ha": 91.07,
        # This map is turned 90 degrees: north points left, so longitude lines run across the page.
        "lon_lines": [(lon, (43, y), (757, y)) for lon, y in zip(
            [dms(78, 15, 0)] + [dms(78, 14, s) for s in (50, 40, 30, 20, 10, 0)],
            [179.5, 327.5, 475.5, 622.5, 770.5, 918.5, 1065.5])],
        "lat_lines": [(lat, (x, 39), (x, 1101)) for lat, x in zip(
            [dms(30, 29, 10), dms(30, 29, 0), dms(30, 28, 50), dms(30, 28, 40), dms(30, 28, 30)],
            [86.5, 234.5, 382.0, 529.5, 677.5])],
        "checks": {"spring": (dms(78, 14, 4.83), dms(30, 28, 57.86)), "handpump": (dms(78, 14, 12.1), dms(30, 28, 53.3))},
        "note": "Printed markers sit about 40 m from the printed GPS points, so the outline may be shifted by that much.",
    },
]

TO_UTM = Transformer.from_crs(4326, 32644, always_xy=True)
TO_WGS = Transformer.from_crs(32644, 4326, always_xy=True)


def crossing(a1, a2, b1, b2):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = a1, a2, b1, b2
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def pixel_to_utm(report):
    pixels, world = [], []
    for lon, a1, a2 in report["lon_lines"]:
        for lat, b1, b2 in report["lat_lines"]:
            pixels.append(crossing(a1, a2, b1, b2))
            world.append(TO_UTM.transform(lon, lat))
    design = np.c_[np.array(pixels), np.ones(len(pixels))]
    coef, *_ = np.linalg.lstsq(design, np.array(world), rcond=None)
    residual = float(np.abs(design @ coef - np.array(world)).max())
    return Affine(coef[0, 0], coef[1, 0], coef[2, 0], coef[0, 1], coef[1, 1], coef[2, 1]), residual


def trace(image_path, transform):
    rgb = np.asarray(Image.open(image_path).convert("RGB")).astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    fill = (g > 150) & (r < 140) & (b > 120) & (g - r > 60)  # teal geology fill
    mask = ndimage.binary_fill_holes(ndimage.binary_closing(fill, iterations=4))
    labels, _ = ndimage.label(mask)
    largest = labels == (np.bincount(labels.ravel())[1:].argmax() + 1)
    largest = ndimage.binary_dilation(largest, iterations=1)  # out to the middle of the outline
    polygons = [shape(s) for s, v in features.shapes(largest.astype("uint8"), mask=largest, transform=transform) if v == 1]
    return max(polygons, key=lambda p: p.area).simplify(3)


def markers(image_path):
    """Pixel centres of the bright green spring/handpump symbols."""
    rgb = np.asarray(Image.open(image_path).convert("RGB")).astype(int)
    lime = (rgb[..., 1] > 200) & (rgb[..., 2] < 60) & (rgb[..., 0] > 50)
    labels, n = ndimage.label(lime)
    keep = [i + 1 for i, size in enumerate(ndimage.sum(lime, labels, range(1, n + 1))) if size > 10]
    return [(c[1], c[0]) for c in ndimage.center_of_mass(lime, labels, keep)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()
    out_features = []
    with tempfile.TemporaryDirectory() as tmp:
        for report in REPORTS:
            prefix = Path(tmp) / report["record_id"]
            subprocess.run(["pdfimages", "-png", str(args.report_dir / report["pdf"]), str(prefix)], check=True)
            image = Path(f"{prefix}-{report['image']:03d}.png")
            transform, residual = pixel_to_utm(report)
            polygon = trace(image, transform)
            found = [Point(transform * xy) for xy in markers(image)]
            checks = {}
            for label, (lon, lat) in report["checks"].items():
                point = Point(TO_UTM.transform(lon, lat))
                checks[f"{label}_inside"] = polygon.contains(point)
                checks[f"{label}_marker_offset_m"] = round(min(point.distance(m) for m in found), 1) if found else None
            area = round(polygon.area / 1e4, 2)
            print(f"{report['name']}: {area} ha (report {report['report_area_ha']} ha); grid fit within {residual:.1f} m; {checks}")
            out_features.append({"type": "Feature", "properties": {
                "record_id": report["record_id"], "spring_name": report["name"], "source_id": report["source_id"],
                "traced_from": f"{report['pdf']}, {report['figure']}", "area_ha_traced": area,
                "area_ha_report": report["report_area_ha"], "grid_fit_max_error_m": round(residual, 1), **checks,
                "dataset_split": "test", "note": report["note"]},
                "geometry": mapping(shapely.transform(polygon, lambda xy: np.c_[TO_WGS.transform(xy[:, 0], xy[:, 1])]))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": out_features}, indent=1), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
