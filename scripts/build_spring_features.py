"""Build the processed per-spring feature table from the common file and public layers.

Input:  data/01_staged/common/csv/spring_records_common_v1.csv
Output: data/02_processed/spring_features/spring_features_v1.csv (+ data dictionary,
        coverage table and metadata JSON)

Public layers (downloaded once into a local cache, never committed):
- Copernicus DEM GLO-30 (AWS open data, 1-arcsecond tiles)
- ESA WorldCover 10 m 2021 v200 (AWS open data, 3-degree tiles)
- CHIRPS precipitation, annual and monthly 2018-2025, as republished by FAO WaPOR v3 (L1-PCP-A/M, ~5 km)
- FAO WaPOR v3 reference evapotranspiration, annual 2018-2025 (L1-RET-A, ~30 km)
- FAO/IIASA Harmonized World Soil Database v2.0 (30 arc-second raster + database tables exported to CSV)
- Google Open Buildings 2.5D Temporal v1 (building counts within 1 km, 2016 and 2023; Google Cloud Storage)

Layers downloaded by hand (logins or manual export), read from --local-layers DIR:
- Bhoonidhi/*.zip      NRSC CartoDEM v3 30 m tiles, as downloaded from Bhoonidhi
- IMD/*.nc             IMD 0.25 degree daily gridded rainfall (one calendar year per file; every year found is used,
                       2001-2025 with 2012 missing as of 2026-10-14)
- SoilGrids/<prop>_<depth>_mean.tif   ISRIC SoilGrids 2.0 exports (clay, silt, sand, bdod, ocd, cfvo;
                       depths 0-5, 5-15 and 15-30 cm)
DEM lineament candidates come from scripts/extract_dem_lineaments.py (--lineaments FILE).
DEM hydrology (drainage area, wetness index, distance to stream) comes from scripts/spring_hydrology.py.
GSI NGDR (Bhukosh) Uttarakhand lithology polygons, fault lines and fold axes are read from
data/00_raw/ngdr_geology/ (committed; staged attribute tables in data/01_staged/ngdr_geology/).

Rules: staged source text is never edited. Parsed numbers are new columns with
a parse note. Unit conversions are new columns named *_converted. Layer values
describe the pixel or buffer around the coordinate as given; they are not field
measurements. Usage: python scripts/build_spring_features.py [--cache DIR]
"""

import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.windows import from_bounds
from scipy.stats import kendalltau
from pyproj import Transformer
from shapely import STRtree, LineString, Point
from shapely.geometry import shape
from shapely import transform as shapely_transform

from spring_hydrology import STREAM_THRESHOLD_KM2, hydrology_features


ROOT = Path(__file__).resolve().parents[1]
COMMON_CSV = ROOT / "data" / "01_staged" / "common" / "csv" / "spring_records_common_v1.csv"
OUT_DIR = ROOT / "data" / "02_processed" / "spring_features"

DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
WAPOR_URL = "https://storage.googleapis.com/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET/{code}/WAPOR-3.{code}.{period}.tif"
HWSD_URLS = [
    "https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/HWSD/HWSD2_RASTER.zip",
    "https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/HWSD/HWSD2_DB.zip",
]
YEARS = list(range(2018, 2026))
IMD_BOUNDS = (75.0, 28.0, 82.0, 34.0)  # lon / lat box around the Uttarakhand and Himachal hills; IMD is blank outside it
OBT_URL = "https://storage.googleapis.com/open-buildings-temporal-data/v1/manifests/39_EPSG_{epsg}_{year}_06_30.json"
OBT_YEARS = (2016, 2023)
OBT_RADIUS_M = 1000
OBT_MIN_BASE = 25  # growth % is taken against at least this many buildings, so a few new houses in an empty area do not read as +300 %
NGDR_DIR = ROOT / "data" / "00_raw" / "ngdr_geology"
NGDR_LITHOLOGY = NGDR_DIR / "lithology" / "LITHOLOGY_STATE_UTTARAKHAND.geojson"
NGDR_FAULTS = NGDR_DIR / "faults" / "FAULT_STATE_UTTARAKHAND.geojson"
NGDR_FOLDS = NGDR_DIR / "folds" / "FOLD_STATE_UTTARAKHAND.geojson"
LINEAMENTS_FILE = ROOT / "data" / "02_processed" / "lineaments" / "dem_lineament_candidates_v1.geojson"

# SoilGrids exports: (property, column stem, unit, divisor to reach the unit, description). 0 = no data.
SOILGRID_DEPTHS = [("0-5cm", "0_5cm"), ("5-15cm", "5_15cm"), ("15-30cm", "15_30cm")]
SOILGRID_PROPERTIES = [
    ("clay", "sg_clay", "%", 10, "Clay (g/kg / 10)"),
    ("silt", "sg_silt", "%", 10, "Silt (g/kg / 10)"),
    ("sand", "sg_sand", "%", 10, "Sand (g/kg / 10)"),
    ("cfvo", "sg_coarse_fragments", "%", 10, "Coarse fragments, volume share (cm3/dm3 / 10)"),
    ("bdod", "sg_bulk_density", "g/cm3", 100, "Bulk density of the fine earth (cg/cm3 / 100)"),
    ("ocd", "sg_org_carbon_density", "kg/m3", 10, "Organic carbon density (hg/m3 / 10)"),
]
SOILGRIDS = [(f"{prop}_{depth}_mean", f"{stem}_{label}_{unit.replace('%', 'pct').replace('/', '_')}", divisor)
             for prop, stem, unit, divisor, _ in SOILGRID_PROPERTIES for depth, label in SOILGRID_DEPTHS]
IMD_MONSOON_MONTHS = (6, 9)
IMD_TREND_MIN_YEARS = 15

# Study region: Uttarakhand and Himachal Pradesh springs in the common file.
REGION = {"lat_min": 28.5, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 81.5}

WORLDCOVER_CLASSES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
    60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
    90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}
WC_SHARE_COLUMNS = {10: "tree", 20: "shrub", 30: "grass", 40: "cropland", 50: "built", 60: "bare", 80: "water"}

DISTRICT_FIXES = {
    "nanital": "Nainital", "nainital": "Nainital", "tehri garhwal": "Tehri Garhwal", "tehri-garhwal": "Tehri Garhwal",
    "pauri garhwal": "Pauri Garhwal", "pauri": "Pauri Garhwal",
}

# Coordinates corrected where the error and the fix are both certain. The staged value is not edited;
# the correction is applied here and named in coordinate_correction.
COORDINATE_FIXES = {
    "ATL-SPR-0006": (29.44050, None, "latitude 26.44050 read as 29.44050 (typing slip: Sunkiya -2, ATL-SPR-0007, is at 29.44343; "
                                     "the DEM at the corrected point is 2,049 m against 2,035 m in the source)"),
    "ATL-SPR-0818": (None, 80.029444, "longitude repeated the latitude; taken from HIM-SPR-0204 (Malla Naula, Khatigaon), which has the "
                                      "same latitude 29.59992 and the same elevation 1,279 m"),
}
FIELD_VISIT_CSV = ROOT / "data" / "01_staged" / "field_visit" / "csv" / "field_visit_springs_2026-10.csv"


def field_visit_fixes(path=FIELD_VISIT_CSV):
    """Field GPS for dataset springs revisited on the October 2026 field visit (agreed with Rajat 2026-10-22).
    The source coordinates of these records are rounded to about 1 km."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {r["dataset_spring_id"]: (float(r["latitude"]), float(r["longitude"]),
                                         f"field GPS from the DoCC field visit on {r['visit_date']} ({r['field_site_id']}: "
                                         f"{r['coordinate_source']}); the source coordinate is rounded to about 1 km")
                for r in csv.DictReader(handle) if r["dataset_spring_id"]}


COORDINATE_FIXES.update(field_visit_fixes())
COORDINATE_NOTES = {
    "ATL-SPR-0792": "latitude repeats the longitude (80.05146); probably the Gunagad spring listed as ATL-SPR-0791 (same longitude, "
                    "1,613 m against 1,612 m), but the latitude cannot be recovered with certainty",
}
ELEVATION_GAP_M = 150
ELEVATION_MATCH_TOLERANCE_M = 25
ELEVATION_SEARCH_M = 2000

NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


# --------------------------------------------------------------------------- helpers
def fmt(value, digits=2):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{float(value):.{digits}f}"


class NotInMapSet(FileNotFoundError):
    """Offline mode: a file the run needs is not in the local map set, and nothing may be downloaded."""


OFFLINE = False  # set_offline(True): read only files already on disk (an approved map set); never download


def set_offline(flag=True):
    global OFFLINE
    OFFLINE = bool(flag)


def download(url, path):
    if path.exists() and path.stat().st_size > 0:
        return
    if OFFLINE:
        raise NotInMapSet(f"{path.name} is not in the local map set")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as handle:
        while chunk := response.read(1 << 20):
            handle.write(chunk)
    tmp.rename(path)


def to_float(text):
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


def parse_numbers(text):
    """Return (low, high, note) from free text such as '~2-8 lpm dry; 15-25+ lpm wet'."""
    text = (text or "").strip()
    if not text:
        return None, None, ""
    numbers = [float(n) for n in NUMBER.findall(text.replace(",", ""))]
    if not numbers:
        return None, None, "no number in source text"
    lowered = text.lower()
    if len(numbers) == 1:
        note = "single value" if re.fullmatch(r"~?\s*\d+(\.\d+)?\s*(ha|lpm|l/min|mm)?", lowered) else "single number in text"
    elif any(word in lowered for word in ("dry", "wet", "monsoon", "season")):
        note = "multi-season text: low = lowest number, high = highest number"
    else:
        note = "range: low and high numbers in text"
    if "~" in text or "approx" in lowered:
        note += "; approximate in source"
    return min(numbers), max(numbers), note


def sen_slope(xs, ys):
    """Theil-Sen slope: median of the slopes between every pair of years (robust to one very wet or dry year)."""
    return float(np.median([(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs))]))


def metres_per_degree(lat):
    lat_r = math.radians(lat)
    return 111132.92 - 559.82 * math.cos(2 * lat_r), 111412.84 * math.cos(lat_r)


def read_window(paths, lon, lat, radius_m):
    """Mosaic the tiles needed to cover a square of +/- radius_m around the point."""
    m_lat, m_lon = metres_per_degree(lat)
    dlat, dlon = radius_m / m_lat, radius_m / m_lon
    bounds = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    datasets = [ds for ds in paths if not (ds.bounds.right < bounds[0] or ds.bounds.left > bounds[2]
                                           or ds.bounds.top < bounds[1] or ds.bounds.bottom > bounds[3])]
    if not datasets:
        return None, None
    if len(datasets) == 1:
        ds = datasets[0]
        window = from_bounds(*bounds, transform=ds.transform).round_offsets().round_lengths()
        data = ds.read(1, window=window, boundless=True, fill_value=ds.nodata if ds.nodata is not None else 0)
        return data, ds.window_transform(window)
    data, transform = merge(datasets, bounds=bounds)
    return data[0], transform


def distance_grid(shape, transform, lon, lat):
    rows, cols = np.indices(shape)
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    m_lat, m_lon = metres_per_degree(lat)
    return np.hypot((xs - lon) * m_lon, (ys - lat) * m_lat)


def centre_index(transform, lon, lat):
    col = int((lon - transform.c) / transform.a)
    row = int((lat - transform.f) / transform.e)
    return row, col


# --------------------------------------------------------------------------- layers
def dem_tiles_for(points, cache):
    cells = set()
    for lat, lon in points:
        for dy in (-0.02, 0, 0.02):
            for dx in (-0.02, 0, 0.02):
                cells.add((math.floor(lat + dy), math.floor(lon + dx)))
    paths = []
    for la, lo in sorted(cells):
        name = f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM"
        path = cache / "dem" / f"{name}.tif"
        try:
            download(DEM_URL.format(name=name), path)
            paths.append(path)
        except Exception as error:  # ocean/no-data tiles do not exist
            print(f"DEM tile {name} unavailable: {error}")
    return paths


def worldcover_tiles_for(points, cache):
    tiles = set()
    for lat, lon in points:
        for dy in (-0.01, 0, 0.01):
            for dx in (-0.01, 0, 0.01):
                la, lo = math.floor((lat + dy) / 3) * 3, math.floor((lon + dx) / 3) * 3
                tiles.add(f"N{la:02d}E{lo:03d}")
    paths = []
    for tile in sorted(tiles):
        path = cache / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        try:
            download(WC_URL.format(tile=tile), path)
        except NotInMapSet as error:
            print(f"WorldCover tile {tile} unavailable: {error}")
            continue
        paths.append(path)
    return paths


def dem_features(dem_sets, lon, lat):
    data, transform = read_window(dem_sets, lon, lat, 1100)
    if data is None:
        return {}
    data = data.astype("float64")
    data[data <= -1000] = np.nan
    row, col = centre_index(transform, lon, lat)
    if not (1 <= row < data.shape[0] - 1 and 1 <= col < data.shape[1] - 1):
        return {}
    m_lat, m_lon = metres_per_degree(lat)
    dx, dy = abs(transform.a) * m_lon, abs(transform.e) * m_lat
    gy, gx = np.gradient(data, dy, dx)  # rows run north to south
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # Aspect: direction the slope faces, degrees clockwise from north.
    aspect = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
    dist = distance_grid(data.shape, transform, lon, lat)
    elev = data[row, col]
    within_1km = data[dist <= 1000]
    within_300 = data[dist <= 300]
    slope_500 = slope[dist <= 500]
    a = aspect[row, col]
    classes = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    flat = slope[row, col] < 2
    return {
        "dem_elevation_m": elev,
        "dem_slope_deg": slope[row, col],
        "dem_aspect_deg": None if flat else a,
        "dem_aspect_class": "Flat" if flat else classes[int(((a + 22.5) % 360) // 45)],
        "dem_mean_slope_500m_deg": np.nanmean(slope_500),
        "dem_relief_1km_m": np.nanmax(within_1km) - np.nanmin(within_1km),
        "dem_upslope_relief_1km_m": np.nanmax(within_1km) - elev,
        "dem_tpi_300m_m": elev - np.nanmean(within_300),
    }


def elevation_match_distance(dem_sets, lon, lat, target):
    """Distance to the nearest DEM cell whose elevation is within the tolerance of the source elevation."""
    data, transform = read_window(dem_sets, lon, lat, ELEVATION_SEARCH_M)
    if data is None:
        return None
    data = data.astype("float64")
    dist = distance_grid(data.shape, transform, lon, lat)
    hits = (np.abs(data - target) <= ELEVATION_MATCH_TOLERANCE_M) & (dist <= ELEVATION_SEARCH_M)
    return float(dist[hits].min()) if hits.any() else None


def worldcover_features(wc_sets, lon, lat):
    data, transform = read_window(wc_sets, lon, lat, 520)
    if data is None:
        return {}
    row, col = centre_index(transform, lon, lat)
    dist = distance_grid(data.shape, transform, lon, lat)
    ring = data[(dist <= 500) & (data > 0)]
    if ring.size == 0:
        return {}
    point_code = int(data[row, col])
    codes, counts = np.unique(ring, return_counts=True)
    majority = int(codes[np.argmax(counts)])
    result = {
        "wc_point_class_code": point_code,
        "wc_point_class": WORLDCOVER_CLASSES.get(point_code, ""),
        "wc_majority_500m_class": WORLDCOVER_CLASSES.get(majority, ""),
    }
    for code, name in WC_SHARE_COLUMNS.items():
        result[f"wc_share_500m_{name}_pct"] = 100.0 * float(np.sum(ring == code)) / ring.size
    return result


class WaporStack:
    """Reads one regional window per WaPOR raster, then samples points from memory."""

    def __init__(self, code, periods, scale=0.1, cache=None):
        """With a cache folder, each regional window is saved there once, so later runs start fast and work offline."""
        self.grids = {}
        for period in periods:
            saved = Path(cache) / "wapor" / f"{code}.{period}.npz" if cache else None
            if saved and saved.exists():
                with np.load(saved) as stored:
                    self.grids[period] = (stored["data"], rasterio.Affine(*stored["transform"]))
                continue
            if OFFLINE:
                print(f"WaPOR {code}.{period} is not in the local map set; left out")
                continue
            url = "/vsicurl/" + WAPOR_URL.format(code=code, period=period)
            with rasterio.open(url) as ds:
                window = from_bounds(REGION["lon_min"], REGION["lat_min"], REGION["lon_max"], REGION["lat_max"], ds.transform)
                window = window.round_offsets().round_lengths()
                data = ds.read(1, window=window).astype("float64")
                data[data == ds.nodata] = np.nan
                self.grids[period] = (data * scale, ds.window_transform(window))
            if saved:
                saved.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(saved, data=self.grids[period][0], transform=np.array(self.grids[period][1])[:6])

    def sample(self, period, lon, lat):
        if period not in self.grids:
            return float("nan")
        data, transform = self.grids[period]
        row, col = centre_index(transform, lon, lat)
        if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
            return data[row, col]
        return float("nan")


class NoLayer:
    """Stands in for a layer that was not opened: no values at any point."""

    def features(self, lon, lat):
        return {}

    def prefetch(self, points, workers=8):
        pass


HWSD_COLUMNS = ("soil_hwsd2_smu_id", "soil_dominant_wrb", "soil_dominant_share_pct", "soil_drainage", "soil_awc_mm_per_m",
                "soil_topsoil_sand_pct", "soil_topsoil_silt_pct", "soil_topsoil_clay_pct", "soil_topsoil_texture_usda",
                "soil_topsoil_coarse_fragments_pct", "soil_topsoil_org_carbon_pct")


class Hwsd:
    def __init__(self, cache):
        folder = cache / "hwsd"
        for url in HWSD_URLS:
            zipped = folder / url.rsplit("/", 1)[1]
            download(url, zipped)
            if not (folder / "HWSD2.bil").exists() or not (folder / "HWSD2.mdb").exists():
                subprocess.run(["unzip", "-o", "-q", str(zipped), "-d", str(folder)], check=True)
        for table in ("HWSD2_SMU", "HWSD2_LAYERS", "D_WRB4", "D_DRAINAGE", "D_TEXTURE_USDA"):
            if not (folder / f"{table}.csv").exists():
                raise FileNotFoundError(
                    f"{folder / table}.csv missing: run python scripts/export_hwsd_tables.py {folder / 'HWSD2.mdb'}"
                )
        # HWSD2.bil: 16-bit little-endian BIL grid, 43200 x 21600 cells of 30 arc-seconds from (-180, 90).
        self.raster = np.memmap(folder / "HWSD2.bil", dtype="<u2", mode="r", shape=(21600, 43200))
        self.smu = {}
        with (folder / "HWSD2_SMU.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                self.smu[str(int(float(row["HWSD2_SMU_ID"])))] = row
        self.topsoil = {}
        with (folder / "HWSD2_LAYERS.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["LAYER"] == "D1" and row["SEQUENCE"] in ("1", "1.0"):
                    self.topsoil[str(int(float(row["HWSD2_SMU_ID"])))] = row
        self.wrb = self._lookup(folder / "D_WRB4.csv", "CODE", "VALUE")
        self.drainage = self._lookup(folder / "D_DRAINAGE.csv", "CODE", "VALUE")
        self.texture = self._lookup(folder / "D_TEXTURE_USDA.csv", "CODE", "VALUE")

    @staticmethod
    def _lookup(path, key, value):
        with path.open(encoding="utf-8") as handle:
            return {row[key].strip(): row[value].strip() for row in csv.DictReader(handle)}

    def features(self, lon, lat):
        row, col = int((90 - lat) * 120), int((lon + 180) * 120)
        smu_id = int(self.raster[row, col])
        if smu_id in (0, 65535):
            return {}
        key = str(smu_id)
        smu = self.smu.get(key, {})
        top = self.topsoil.get(key, {})

        def num(row_, field):
            value = to_float(row_.get(field, ""))
            return None if value is None or value < 0 else value

        texture_code = str(int(float(top["TEXTURE_USDA"]))) if top.get("TEXTURE_USDA") not in (None, "", "None") else ""
        return {
            "soil_hwsd2_smu_id": smu_id,
            "soil_dominant_wrb": self.wrb.get(smu.get("WRB4", ""), smu.get("WRB4", "")),
            "soil_dominant_share_pct": num(smu, "SHARE"),
            "soil_drainage": self.drainage.get(smu.get("DRAINAGE", ""), smu.get("DRAINAGE", "")),
            "soil_awc_mm_per_m": num(smu, "AWC"),
            "soil_topsoil_sand_pct": num(top, "SAND"),
            "soil_topsoil_silt_pct": num(top, "SILT"),
            "soil_topsoil_clay_pct": num(top, "CLAY"),
            "soil_topsoil_texture_usda": self.texture.get(texture_code, ""),
            "soil_topsoil_coarse_fragments_pct": num(top, "COARSE"),
            "soil_topsoil_org_carbon_pct": num(top, "ORG_CARBON"),
        }


class OpenBuildingsTemporal:
    """Google Open Buildings 2.5D Temporal v1: estimated building count within OBT_RADIUS_M in 2016 and 2023.

    Tiles are 12.5 km squares in UTM 43N/44N; the building_fractional_count band summed over an area gives
    the number of buildings. Read at the 8 m overview (enough for a 1 km circle). Only tiles in the same UTM
    zone as the spring are read, so a circle crossing the 78 E zone edge loses the part in the other zone.
    """

    def __init__(self, cache):
        self.tiles = {}
        for year in OBT_YEARS:
            self.tiles[year] = []
            for epsg in (32643, 32644):
                path = cache / "open_buildings" / f"39_EPSG_{epsg}_{year}_06_30.json"
                download(OBT_URL.format(epsg=epsg, year=year), path)
                manifest = json.loads(path.read_text(encoding="utf-8"))
                prefix = manifest["uriPrefix"].replace("gs://", "/vsicurl/https://storage.googleapis.com/")
                for source in manifest["tilesets"][0]["sources"]:
                    a, size = source["affineTransform"], source["dimensions"]
                    self.tiles[year].append((epsg, a["translateX"], a["translateY"] + a["scaleY"] * size["height"],
                                             a["translateX"] + a["scaleX"] * size["width"], a["translateY"], prefix + source["uris"][0]))
        self.local = threading.local()  # open tiles and transformers per thread (neither is thread-safe)
        self.done = {}

    def _open(self, url):
        handles = self.local.__dict__.setdefault("handles", {})
        if url not in handles:
            if len(handles) > 64:
                for handle in handles.values():
                    handle.close()
                handles.clear()
            handles[url] = rasterio.open(url)
        return handles[url]

    def _to_utm(self, epsg):
        transformers = self.local.__dict__.setdefault("to_utm", {})
        if epsg not in transformers:
            transformers[epsg] = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        return transformers[epsg]

    def prefetch(self, points, workers=8):
        """Fetch many springs in parallel (remote reads dominate); features() then returns the stored values."""
        with ThreadPoolExecutor(workers) as pool:
            for (lat, lon), result in zip(points, pool.map(lambda p: self._features(p[1], p[0]), points)):
                self.done[(lon, lat)] = result

    def count(self, year, lon, lat):
        tiles = self.tiles[year]
        home = None
        for epsg, left, bottom, right, top, _ in tiles:
            x, y = self._to_utm(epsg).transform(lon, lat)
            if left <= x < right and bottom < y <= top:
                home = epsg
                break
        if home is None:
            return None
        r = OBT_RADIUS_M
        box = (x - r, y - r, x + r, y + r)
        cells = int(2 * r / 8)
        stack = []
        for epsg, left, bottom, right, top, url in tiles:
            if epsg != home or right <= box[0] or left >= box[2] or top <= box[1] or bottom >= box[3]:
                continue
            ds = self._open(url)
            window = from_bounds(*box, transform=ds.transform)
            data = ds.read(1, window=window, out_shape=(cells, cells), boundless=True, fill_value=-99.0)
            stack.append(np.where(data < -90, np.nan, data))
        if not stack:
            return None
        grid = np.nanmax(np.stack(stack), axis=0) if len(stack) > 1 else stack[0]
        yy, xx = (np.indices(grid.shape) + 0.5) * (2 * r / cells) - r
        inside = (np.hypot(xx, yy) <= r) & ~np.isnan(grid)
        if inside.sum() < 0.5 * (np.hypot(xx, yy) <= r).sum():
            return None
        # mean count per 0.5 m pixel x number of 0.5 m pixels in the circle
        return float(np.mean(grid[inside]) * math.pi * r * r / 0.25)

    def features(self, lon, lat):
        if (lon, lat) in self.done:
            return self.done[(lon, lat)]
        return self._features(lon, lat)

    def _features(self, lon, lat):
        try:
            counts = {year: self.count(year, lon, lat) for year in OBT_YEARS}
        except rasterio.errors.RasterioIOError as error:  # offline, or the tile server is down: leave the columns blank
            print(f"Open Buildings not read at {lat:.5f}, {lon:.5f}: {error}", file=sys.stderr)
            return {}
        if any(v is None for v in counts.values()):
            return {}
        first, last = counts[OBT_YEARS[0]], counts[OBT_YEARS[-1]]
        return {
            f"obt_buildings_1km_{OBT_YEARS[0]}": first,
            f"obt_buildings_1km_{OBT_YEARS[-1]}": last,
            "obt_buildings_added_1km": last - first,
            "obt_building_growth_pct": 100 * (last - first) / max(first, OBT_MIN_BASE),
        }


# Rajat's SoilGrids exports sit in one folder per depth ("0-5 soilgrids/clay.tif"), with these file names
SOILGRID_FILE_NAMES = {"clay": ("clay",), "silt": ("silt", "slit"), "sand": ("sand",), "cfvo": ("coarse",),
                       "bdod": ("bulk",), "ocd": ("organic carbon",)}


def soilgrids_file(folder, stem):
    """The file for one SoilGrids layer, e.g. stem "clay_0-5cm_mean": either SoilGrids/clay_0-5cm_mean.tif or
    SoilGrids/0-5 soilgrids/clay.tif (names matched without regard to case). None if neither exists."""
    path = folder / f"{stem}.tif"
    if path.exists():
        return path
    prop, depth = stem.split("_")[:2]
    sub = folder / f"{depth.removesuffix('cm')} soilgrids"
    if sub.is_dir():
        for candidate in sub.glob("*.tif"):
            if candidate.stem.lower() in SOILGRID_FILE_NAMES.get(prop, ()):
                return candidate
    return None


class LocalLayers:
    """Layers Rajat downloaded by hand (CartoDEM, IMD, SoilGrids) plus DEM lineament candidates."""

    def __init__(self, folder, lineaments_file):
        folder = Path(folder)
        self.found = []
        self.cartodem = []
        for path in sorted((folder / "Bhoonidhi").glob("*.zip")):
            for name in self._zip_tifs(path):
                try:  # GDAL's /vsizip/ form with forward slashes also works for Windows paths
                    self.cartodem.append(rasterio.open(f"/vsizip/{path.resolve().as_posix()}/{name}"))
                except rasterio.errors.RasterioIOError as error:
                    print(f"CartoDEM tile not opened, skipped: {path.name} ({error})", file=sys.stderr)
        if self.cartodem:
            self.found.append(f"CartoDEM: {len(self.cartodem)} tiles")
        self.imd = {}  # year -> (days x rows x cols array, transform)
        for path in sorted((folder / "IMD").glob("*.nc")):
            with rasterio.open(path) as ds:
                # read only the hills (IMD_BOUNDS): the all-India grid for 24 years would need over 1 GB of memory
                rows, cols = zip(*(centre_index(ds.transform, x, y) for x in IMD_BOUNDS[::2] for y in IMD_BOUNDS[1::2]))
                r0, c0 = max(0, min(rows)), max(0, min(cols))
                window = rasterio.windows.Window(c0, r0, min(ds.width, max(cols) + 1) - c0, min(ds.height, max(rows) + 1) - r0)
                data = ds.read(window=window).astype("float64")
                year = date.fromordinal(date(1900, 12, 31).toordinal() + int(ds.tags(1)["NETCDF_DIM_TIME"])).year
                transform = ds.window_transform(window)
            data[data < 0] = np.nan
            self.imd[year] = (data, transform)
        if self.imd:
            self.found.append(f"IMD: {len(self.imd)} years ({', '.join(map(str, sorted(self.imd)))})")
        self.soil = {}
        for stem, column, divisor in SOILGRIDS:
            path = soilgrids_file(folder / "SoilGrids", stem)
            if path is not None:
                with rasterio.open(path) as ds:
                    self.soil[column] = (ds.read(1).astype("float64") / divisor, ds.transform)
        if self.soil:
            self.found.append(f"SoilGrids: {len(self.soil)} layers")
        self.lines = None
        if Path(lineaments_file).exists():
            collection = json.loads(Path(lineaments_file).read_text(encoding="utf-8"))
            self.to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
            geoms = []
            for feature in collection["features"]:
                xs, ys = self.to_utm.transform(*zip(*feature["geometry"]["coordinates"]))
                geoms.append(LineString(list(zip(xs, ys))))
            self.lines = geoms
            self.tree = STRtree(geoms)
            self.found.append(f"DEM lineaments: {len(geoms)} segments")

    @staticmethod
    def _zip_tifs(path):
        import zipfile
        return [n for n in zipfile.ZipFile(path).namelist() if n.lower().endswith(".tif")]

    @staticmethod
    def _cell(transform, shape, lon, lat):
        row, col = centre_index(transform, lon, lat)
        return (row, col) if 0 <= row < shape[0] and 0 <= col < shape[1] else None

    def features(self, lon, lat):
        result = {}
        for ds in self.cartodem:
            b = ds.bounds
            if b.left <= lon < b.right and b.bottom <= lat < b.top:
                row, col = ds.index(lon, lat)
                window = rasterio.windows.Window(col - 1, row - 1, 3, 3)
                z = ds.read(1, window=window, boundless=True, fill_value=-32768).astype("float64")
                z[z <= -1000] = np.nan
                if z.shape == (3, 3) and not np.isnan(z).any():
                    m_lat, m_lon = metres_per_degree(lat)
                    dx, dy = ds.res[0] * m_lon, ds.res[1] * m_lat
                    gx = (z[1, 2] - z[1, 0]) / (2 * dx)
                    gy = (z[0, 1] - z[2, 1]) / (2 * dy)
                    result["cartodem_elevation_m"] = z[1, 1]
                    result["cartodem_slope_deg"] = math.degrees(math.atan(math.hypot(gx, gy)))
                break
        years = {}
        for year, (data, transform) in sorted(self.imd.items()):
            cell = self._cell(transform, data.shape[1:], lon, lat)
            series = data[:, cell[0], cell[1]] if cell else None
            if series is None or np.isnan(series).all():
                continue
            start = date(year, IMD_MONSOON_MONTHS[0], 1).timetuple().tm_yday - 1
            end = date(year, IMD_MONSOON_MONTHS[1], 30).timetuple().tm_yday
            total = np.nansum(series)
            # dry season as in the CHIRPS columns: January-April and November-December of the same calendar year
            may_1, nov_1 = ((date(year, m, 1) - date(year, 1, 1)).days for m in (5, 11))
            years[year] = {"total": total, "monsoon": np.nansum(series[start:end]),
                           "dry": np.nansum(series[:may_1]) + np.nansum(series[nov_1:]),
                           "rainy_days": int(np.sum(series >= 2.5)), "max_1day": np.nanmax(series)}
            result[f"rain_imd_{year}_mm"] = total
        if years:
            totals = [v["total"] for v in years.values()]
            mean = statistics.fmean(totals)
            result["rain_imd_mean_annual_mm"] = mean
            result["rain_imd_min_annual_mm"] = min(totals)
            result["rain_imd_max_annual_mm"] = max(totals)
            result["rain_imd_cv_annual_pct"] = 100 * statistics.pstdev(totals) / mean if mean else None
            result["rain_imd_monsoon_share_pct"] = 100 * sum(v["monsoon"] for v in years.values()) / sum(totals) if sum(totals) else None
            result["rain_imd_rainy_days"] = statistics.fmean(v["rainy_days"] for v in years.values())
            result["rain_imd_max_1day_mm"] = max(v["max_1day"] for v in years.values())
            missing = [y for y in range(min(years), max(years) + 1) if y not in years]
            result["rain_imd_years_used"] = f"{min(years)}-{max(years)}" + (f" ({len(years)} years; missing {', '.join(map(str, missing))})" if missing else "")
            if len(years) >= IMD_TREND_MIN_YEARS:
                xs = sorted(years)
                annual_slope = sen_slope(xs, [years[y]["total"] for y in xs])
                dry_totals = [years[y]["dry"] for y in xs]
                result["rain_imd_trend_mm_per_year"] = annual_slope
                result["rain_imd_trend_pct_per_decade"] = 1000 * annual_slope / mean if mean else None
                result["rain_imd_trend_kendall_p"] = kendalltau(xs, [years[y]["total"] for y in xs]).pvalue
                dry_mean = statistics.fmean(dry_totals)
                result["rain_imd_dry_season_trend_pct_per_decade"] = 1000 * sen_slope(xs, dry_totals) / dry_mean if dry_mean else None
        for column, (grid, transform) in self.soil.items():
            cell = self._cell(transform, grid.shape, lon, lat)
            if cell and grid[cell] > 0:
                result[column] = grid[cell]
        # The 0-5 cm export has no silt layer; SoilGrids fractions sum to ~100 %, so silt = 100 - clay - sand.
        if result.get("sg_silt_0_5cm_pct") is None and result.get("sg_clay_0_5cm_pct") and result.get("sg_sand_0_5cm_pct"):
            result["sg_silt_0_5cm_pct"] = 100 - result["sg_clay_0_5cm_pct"] - result["sg_sand_0_5cm_pct"]
        for stem, unit in (("sg_clay", "pct"), ("sg_sand", "pct"), ("sg_silt", "pct"), ("sg_coarse_fragments", "pct"),
                           ("sg_bulk_density", "g_cm3"), ("sg_org_carbon_density", "kg_m3")):
            parts = [(result.get(f"{stem}_{label}_{unit}"), weight) for (_, label), weight in zip(SOILGRID_DEPTHS, (5, 10, 15))]
            if all(v is not None for v, _ in parts):
                result[f"{stem}_0_30cm_{unit}"] = sum(v * w for v, w in parts) / 30
        if self.lines is not None:
            x, y = self.to_utm.transform(lon, lat)
            point = Point(x, y)
            nearest = self.tree.query_nearest(point)
            result["lineament_dem_distance_m"] = min(self.lines[i].distance(point) for i in nearest)
            circle = point.buffer(1000)
            inside = sum(self.lines[i].intersection(circle).length for i in self.tree.query(circle))
            result["lineament_dem_density_1km_km_per_km2"] = (inside / 1000) / math.pi
        return result


class NgdrGeology:
    """GSI NGDR state-scale lithology polygons and fault lines (Uttarakhand only)."""

    def __init__(self):
        self.ok = NGDR_LITHOLOGY.exists() and NGDR_FAULTS.exists()
        self.folds = []
        if not self.ok:
            return
        project = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
        self.to_utm = project

        def load(path):
            features = json.loads(path.read_text(encoding="utf-8"))["features"]
            return [(shapely_transform(shape(f["geometry"]), lambda xy: np.column_stack(project(xy[:, 0], xy[:, 1]))), f["properties"]) for f in features if f.get("geometry")]

        self.units = load(NGDR_LITHOLOGY)
        self.unit_tree = STRtree([g for g, _ in self.units])
        self.faults = load(NGDR_FAULTS)
        self.fault_tree = STRtree([g for g, _ in self.faults])
        thrusts = [(g, p) for g, p in self.faults if "THRUST" in (p.get("fault_type") or "") or "THRUST" in (p.get("fault_name") or "")]
        self.thrusts = thrusts
        self.thrust_tree = STRtree([g for g, _ in thrusts])
        if NGDR_FOLDS.exists():
            self.folds = load(NGDR_FOLDS)
            self.fold_tree = STRtree([g for g, _ in self.folds])

    @staticmethod
    def _clean(value):
        value = (value or "").strip()
        return "" if value.upper() == "BLANK" else value

    def features(self, lon, lat):
        if not self.ok:
            return {}
        point = Point(*self.to_utm(lon, lat))
        result = {}
        hits = [i for i in self.unit_tree.query(point, predicate="intersects")]
        if not hits:  # outside the Uttarakhand map: fault distances would only reach the state edge
            return {}
        geom, props = self.units[hits[0]]
        result.update({
            "gsi_lithology": self._clean(props.get("lithologic")).rstrip("."),
            "gsi_group": self._clean(props.get("group_name")),
            "gsi_formation": self._clean(props.get("formation")),
            "gsi_age": self._clean(props.get("age")),
            "gsi_map_unit": self._clean(props.get("notation_lithology")),
            "gsi_distance_to_contact_m": geom.boundary.distance(point),
        })
        i = self.fault_tree.query_nearest(point)[0]
        geom, props = self.faults[i]
        result["distance_to_gsi_fault_m"] = geom.distance(point)
        result["gsi_nearest_fault_type"] = self._clean(props.get("fault_type"))
        result["gsi_nearest_fault_name"] = self._clean(props.get("fault_name"))
        result["distance_to_gsi_thrust_m"] = self.thrusts[self.thrust_tree.query_nearest(point)[0]][0].distance(point)
        circle = point.buffer(1000)
        inside = sum(self.faults[j][0].intersection(circle).length for j in self.fault_tree.query(circle))
        result["gsi_fault_density_1km_km_per_km2"] = (inside / 1000) / math.pi
        if self.folds:
            i = self.fold_tree.query_nearest(point)[0]
            geom, props = self.folds[i]
            result["distance_to_gsi_fold_axis_m"] = geom.distance(point)
            result["gsi_nearest_fold_type"] = self._clean(props.get("fold_type"))
            result["distance_to_gsi_anticline_m"] = min(
                (g.distance(point) for g, p in self.folds if "ANTI" in (p.get("fold_type") or "")), default=None)
            result["distance_to_gsi_syncline_m"] = min(
                (g.distance(point) for g, p in self.folds if "SYN" in (p.get("fold_type") or "")), default=None)
            circle = point.buffer(2000)
            result["gsi_fold_axes_within_2km"] = len(self.fold_tree.query(circle, predicate="intersects"))
        return result


# --------------------------------------------------------------------------- columns
COLUMNS = [
    # identity and cleaned location
    ("record_id", "", "Common file", "Copied."),
    ("source_id", "", "Common file", "Copied."),
    ("source_dataset", "", "Common file", "Copied."),
    ("spring_name", "", "Common file", "Copied."),
    ("village", "", "Common file", "Copied."),
    ("district_clean", "", "Common file", "District with spelling variants unified (Nanital to Nainital, Tehri-Garhwal to Tehri Garhwal, Pauri to Pauri Garhwal)."),
    ("latitude_dd", "decimal degrees", "Common file", "Source latitude parsed as a number."),
    ("longitude_dd", "decimal degrees", "Common file", "Source longitude parsed as a number."),
    ("coordinate_status", "", "Derived", "ok, missing, or outside_study_region (lat 28.5-33.5, lon 75.5-81.5). Layer values are only computed for ok."),
    ("coordinate_precision_decimals", "", "Derived", "Decimal places in the source latitude; 2 or fewer means about 1 km uncertainty."),
    ("coordinate_correction", "", "Derived", "Blank, or what was corrected in the source coordinate and why (only where the fix is certain)."),
    ("colocated_group_id", "", "Derived", "Records from different rows within 30 m of each other share a group id; likely the same spring listed twice. Not merged."),
    ("colocated_group_size", "", "Derived", "Number of records in the group."),
    # cleaned source values
    ("source_elevation_m", "m", "Common file", "Source elevation parsed as a number."),
    ("source_discharge_lpm_low", "L/min", "Common file", "Lowest number in the source discharge text."),
    ("source_discharge_lpm_high", "L/min", "Common file", "Highest number in the source discharge text."),
    ("source_discharge_parse_note", "", "Derived", "How the low/high values were read from the text."),
    ("source_max_flow_lpm_converted", "L/min", "Common file (Rathi 2021)", "Max flow in m3/day x 1000 / 1440. Unit conversion only."),
    ("source_recharge_area_ha_low", "ha", "Common file", "Lowest number in the source recharge-area text (WATSAN text estimates, Atlas field delineation)."),
    ("source_recharge_area_ha_high", "ha", "Common file", "Highest number in the source recharge-area text; equals low for single values."),
    ("source_springshed_area_ha_converted", "ha", "Common file (Rathi 2021)", "Springshed area in km2 x 100."),
    ("source_catchment_area_ha", "ha", "Common file (Chamba report)", "Surface micro-watershed area; not a recharge area."),
    ("source_rainfall_mm", "mm/year", "Common file", "Source rainfall parsed as a number."),
    ("source_slope_deg", "degrees", "Common file", "Source slope parsed as a number (WATSAN, Himmotthan, Chamba)."),
    ("source_tds_mg_l", "mg/l", "Common file", "Source TDS parsed as a number."),
    ("source_ph", "", "Common file", "Source pH parsed as a number."),
    # DEM
    ("dem_elevation_m", "m (EGM2008)", "Copernicus DEM GLO-30", "Elevation of the 30 m cell containing the coordinate."),
    ("dem_minus_source_elevation_m", "m", "Derived", "DEM elevation minus source elevation; large gaps point to coordinate or elevation errors."),
    ("elevation_match_distance_m", "m", "Derived from Copernicus DEM GLO-30", f"Only where the gap is over {ELEVATION_GAP_M} m: distance to the nearest DEM cell within {ELEVATION_MATCH_TOLERANCE_M} m of the source elevation, searched up to {ELEVATION_SEARCH_M / 1000:.0f} km. Small = the coordinate is a little off on a steep slope; blank = no such cell nearby, so the coordinate or the source elevation is badly wrong."),
    ("dem_slope_deg", "degrees", "Copernicus DEM GLO-30", "Slope at the cell (central differences)."),
    ("dem_aspect_deg", "degrees from north", "Copernicus DEM GLO-30", "Direction the slope faces; blank when slope < 2 degrees."),
    ("dem_aspect_class", "", "Copernicus DEM GLO-30", "8-point aspect class, or Flat."),
    ("dem_mean_slope_500m_deg", "degrees", "Copernicus DEM GLO-30", "Mean slope within 500 m of the coordinate."),
    ("dem_relief_1km_m", "m", "Copernicus DEM GLO-30", "Highest minus lowest elevation within 1 km."),
    ("dem_upslope_relief_1km_m", "m", "Copernicus DEM GLO-30", "Highest elevation within 1 km minus the spring cell elevation (head available upslope)."),
    ("dem_tpi_300m_m", "m", "Copernicus DEM GLO-30", "Spring elevation minus mean elevation within 300 m; negative = valley/hollow position."),
    ("dem_drainage_area_ha", "ha", "Derived from Copernicus DEM GLO-30", "Upslope area draining to the spring cell: depression-filled DEM, multiple-flow-direction routing (Freeman 1991). The surface catchment above the spring, not its recharge area (scripts/spring_hydrology.py)."),
    ("dem_drainage_area_max30m_ha", "ha", "Derived from Copernicus DEM GLO-30", "Largest drainage area in the 3 x 3 cells around the spring (allows for ~30 m GPS error). A big jump from the cell value means a hollow or stream line lies next to the point."),
    ("dem_drainage_area_d8_ha", "ha", "Derived from Copernicus DEM GLO-30", "Same as dem_drainage_area_ha but with single-direction (D8) routing. Kept as a check; D8 is noisier at a single cell."),
    ("dem_twi", "", "Derived from Copernicus DEM GLO-30", "Topographic wetness index ln(a / tan slope), a = MFD drainage area per metre of contour. Higher = wetter, more convergent position. Typical hillslope 4-8, hollows and valley floors 8-14."),
    ("dem_distance_to_stream_m", "m", "Derived from Copernicus DEM GLO-30", f"Straight-line distance to the nearest DEM-derived stream cell (D8 drainage area at least {STREAM_THRESHOLD_KM2} km2)."),
    ("dem_nearest_stream_order", "", "Derived from Copernicus DEM GLO-30", "Strahler order of that nearest stream cell (1 = headwater)."),
    ("dem_nearest_stream_area_km2", "km2", "Derived from Copernicus DEM GLO-30", "D8 drainage area of that nearest stream cell."),
    ("dem_height_above_stream_m", "m", "Derived from Copernicus DEM GLO-30", "Height above the stream the spring cell drains to, along its D8 flow path (HAND)."),
    ("dem_catchment_window_edge", "", "Derived from Copernicus DEM GLO-30", "Y when the spring cell's catchment reaches the edge of the +/- 20 km DEM window, so the drainage areas are minimums (spring on a large river)."),
    ("cartodem_elevation_m", "m (as supplied by NRSC)", "NRSC CartoDEM v3 30 m (Bhoonidhi)", "Elevation of the CartoDEM cell containing the coordinate."),
    ("cartodem_minus_copernicus_m", "m", "Derived", "CartoDEM minus Copernicus elevation. A check on both DEMs; the datums differ slightly."),
    ("cartodem_slope_deg", "degrees", "NRSC CartoDEM v3 30 m (Bhoonidhi)", "Slope at the cell from its 3 x 3 neighbourhood."),
    # Land cover
    ("wc_point_class_code", "", "ESA WorldCover 2021 v200", "Class code of the 10 m cell at the coordinate."),
    ("wc_point_class", "", "ESA WorldCover 2021 v200", "Class name at the coordinate."),
    ("wc_majority_500m_class", "", "ESA WorldCover 2021 v200", "Most common class within 500 m."),
] + [
    (f"wc_share_500m_{name}_pct", "%", "ESA WorldCover 2021 v200", f"Share of {WORLDCOVER_CLASSES[code].lower()} within 500 m.")
    for code, name in WC_SHARE_COLUMNS.items()
] + [
    # Climate
    ("rain_chirps_mean_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Mean of annual totals 2018-2025 at the ~5 km cell."),
    ("rain_chirps_min_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Driest year 2018-2025."),
    ("rain_chirps_max_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Wettest year 2018-2025."),
    ("rain_chirps_cv_annual_pct", "%", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Year-to-year coefficient of variation."),
    ("rain_chirps_monsoon_share_pct", "%", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-M", "Share of rain falling June-September (mean 2018-2025)."),
    ("rain_chirps_dry_season_mm", "mm", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-M", "Mean November-April total (2018-2025 seasons within calendar years)."),
    ("et0_wapor_mean_annual_mm_2018_2025", "mm/year", "FAO WaPOR v3 L1-RET-A", "Mean annual reference evapotranspiration at the ~30 km cell."),
    ("aridity_index_p_over_et0", "", "Derived", "Mean annual CHIRPS rain divided by mean annual ET0."),
    ("rain_source_minus_chirps_mm", "mm/year", "Derived", "Source rainfall minus CHIRPS mean, where the source gives rainfall."),
    ("rain_imd_mean_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Mean of the yearly totals over the IMD years used (rain_imd_years_used) at the ~25 km cell."),
    ("rain_imd_min_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Driest year."),
    ("rain_imd_max_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Wettest year."),
    ("rain_imd_cv_annual_pct", "%", "IMD 0.25 degree gridded daily rainfall", "Year-to-year coefficient of variation."),
    ("rain_imd_monsoon_share_pct", "%", "IMD 0.25 degree gridded daily rainfall", "Share of rain falling 1 June-30 September."),
    ("rain_imd_rainy_days", "days/year", "IMD 0.25 degree gridded daily rainfall", "Mean days per year with at least 2.5 mm (IMD rainy-day definition)."),
    ("rain_imd_max_1day_mm", "mm", "IMD 0.25 degree gridded daily rainfall", "Wettest single day."),
    ("rain_imd_years_used", "", "IMD 0.25 degree gridded daily rainfall", "IMD years found and used."),
    ("rain_imd_trend_mm_per_year", "mm/year per year", "Derived from IMD", f"Theil-Sen trend of yearly rainfall (median of all year-pair slopes); negative = getting drier. Needs at least {IMD_TREND_MIN_YEARS} years."),
    ("rain_imd_trend_pct_per_decade", "% per decade", "Derived from IMD", "The same trend as a share of mean yearly rain, per 10 years."),
    ("rain_imd_trend_kendall_p", "", "Derived from IMD", "Mann-Kendall test p-value for the yearly totals (below 0.05 = a trend unlikely to be chance)."),
    ("rain_imd_dry_season_trend_pct_per_decade", "% per decade", "Derived from IMD", "Theil-Sen trend of January-April plus November-December rain, as a share of its mean, per 10 years."),
] + [
    (f"rain_imd_{year}_mm", "mm", "IMD 0.25 degree gridded daily rainfall", f"Total rain in {year}.") for year in range(2021, 2026)
] + [
    # Soil
    ("soil_hwsd2_smu_id", "", "HWSD v2.0", "Soil mapping unit at the ~1 km cell."),
    ("soil_dominant_wrb", "", "HWSD v2.0", "WRB soil name of the dominant soil in the mapping unit."),
    ("soil_dominant_share_pct", "%", "HWSD v2.0", "Share of the mapping unit covered by the dominant soil."),
    ("soil_drainage", "", "HWSD v2.0", "Drainage class of the dominant soil."),
    ("soil_awc_mm_per_m", "mm/m", "HWSD v2.0", "Available water capacity of the dominant soil."),
    ("soil_topsoil_sand_pct", "%", "HWSD v2.0", "Sand, 0-20 cm, dominant soil."),
    ("soil_topsoil_silt_pct", "%", "HWSD v2.0", "Silt, 0-20 cm, dominant soil."),
    ("soil_topsoil_clay_pct", "%", "HWSD v2.0", "Clay, 0-20 cm, dominant soil."),
    ("soil_topsoil_texture_usda", "", "HWSD v2.0", "USDA texture class, 0-20 cm."),
    ("soil_topsoil_coarse_fragments_pct", "%", "HWSD v2.0", "Coarse fragments, 0-20 cm."),
    ("soil_topsoil_org_carbon_pct", "%", "HWSD v2.0", "Organic carbon, 0-20 cm."),
] + [
    (f"{stem}_{label}_{unit.replace('%', 'pct').replace('/', '_')}", unit, "ISRIC SoilGrids 2.0 (250 m)",
     f"{text}, {depth.replace('cm', ' cm')}, predicted mean." + (" Derived as 100 - clay - sand (no silt export at this depth)." if (prop, label) == ("silt", "0_5cm") else ""))
    for prop, stem, unit, _, text in SOILGRID_PROPERTIES for depth, label in SOILGRID_DEPTHS
] + [
    (f"{stem}_0_30cm_{unit.replace('%', 'pct').replace('/', '_')}", unit, "Derived from ISRIC SoilGrids 2.0",
     f"{text.split(' (')[0]}, 0-30 cm, depth-weighted mean of the three layers.")
    for _, stem, unit, _, text in SOILGRID_PROPERTIES
] + [
    # Geology placeholders
    ("gsi_lithology", "", "GSI NGDR Uttarakhand lithology (Bhukosh)", "Lithology description of the map polygon containing the spring. Uttarakhand only; GSI columns are blank for springs outside it."),
    ("gsi_group", "", "GSI NGDR Uttarakhand lithology", "Stratigraphic group (e.g. Garhwal, Jaunsar, Central Crystalline)."),
    ("gsi_formation", "", "GSI NGDR Uttarakhand lithology", "Formation name."),
    ("gsi_age", "", "GSI NGDR Uttarakhand lithology", "Geological age."),
    ("gsi_map_unit", "", "GSI NGDR Uttarakhand lithology", "Map unit notation."),
    ("gsi_distance_to_contact_m", "m", "GSI NGDR Uttarakhand lithology", "Distance to the edge of the spring's map polygon (a rock-type contact or map edge)."),
    ("distance_to_gsi_fault_m", "m", "GSI NGDR Uttarakhand faults (Bhukosh)", "Distance to the nearest mapped fault or thrust (observed, inferred or interpreted)."),
    ("gsi_nearest_fault_type", "", "GSI NGDR Uttarakhand faults", "Type of that nearest fault (FAULT, FAULT INFERRED, THRUST, ...)."),
    ("gsi_nearest_fault_name", "", "GSI NGDR Uttarakhand faults", "Name of that fault where GSI gives one (e.g. MAIN BOUNDART THRUST (MBT), as spelt by GSI)."),
    ("distance_to_gsi_thrust_m", "m", "GSI NGDR Uttarakhand faults", "Distance to the nearest mapped thrust."),
    ("gsi_fault_density_1km_km_per_km2", "km/km2", "GSI NGDR Uttarakhand faults", "Length of mapped faults within 1 km, per km2."),
    ("distance_to_gsi_fold_axis_m", "m", "GSI NGDR Uttarakhand folds (Bhukosh)", "Distance to the nearest mapped fold axis (290 axes in the state layer)."),
    ("gsi_nearest_fold_type", "", "GSI NGDR Uttarakhand folds", "Type of that fold (ANTICLINE, SYNCLINE, ANTIFORM, SYNFORM, OVERTURNED ...)."),
    ("distance_to_gsi_anticline_m", "m", "GSI NGDR Uttarakhand folds", "Distance to the nearest anticline or antiform axis (rocks dip away; fractured crest)."),
    ("distance_to_gsi_syncline_m", "m", "GSI NGDR Uttarakhand folds", "Distance to the nearest syncline or synform axis (rocks dip inward; can trap groundwater)."),
    ("gsi_fold_axes_within_2km", "count", "GSI NGDR Uttarakhand folds", "Number of fold axes within 2 km."),
    # Settlement growth
    (f"obt_buildings_1km_{OBT_YEARS[0]}", "count", "Google Open Buildings 2.5D Temporal v1", f"Estimated number of buildings within {OBT_RADIUS_M} m in {OBT_YEARS[0]} (building_fractional_count summed over the circle, 8 m overview)."),
    (f"obt_buildings_1km_{OBT_YEARS[-1]}", "count", "Google Open Buildings 2.5D Temporal v1", f"Same for {OBT_YEARS[-1]}."),
    ("obt_buildings_added_1km", "count", "Derived", f"Buildings in {OBT_YEARS[-1]} minus buildings in {OBT_YEARS[0]}; a stand-in for population growth near the spring. Model estimates from yearly imagery, so small changes are noise."),
    ("obt_building_growth_pct", "%", "Derived", f"Buildings added as a share of the {OBT_YEARS[0]} count (at least {OBT_MIN_BASE} buildings used as the base)."),
    ("lineament_dem_distance_m", "m", "Derived from Copernicus DEM GLO-30", "Distance to the nearest DEM lineament candidate (scripts/extract_dem_lineaments.py). Unvalidated."),
    ("lineament_dem_density_1km_km_per_km2", "km/km2", "Derived from Copernicus DEM GLO-30", "Length of DEM lineament candidates within 1 km, per km2."),
    ("processing_notes", "", "Derived", "Row-level notes on missing or questionable inputs."),
]
COLUMN_NAMES = [name for name, *_ in COLUMNS]


def colocated_groups(rows):
    """Group records (from any rows) whose coordinates are within 30 m."""
    cell = 0.0005
    buckets = {}
    for index, row in enumerate(rows):
        if row["coordinate_status"] == "ok":
            key = (int(row["latitude_dd"] / cell), int(row["longitude_dd"] / cell))
            buckets.setdefault(key, []).append(index)
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for (ky, kx), members in buckets.items():
        neighbours = [j for dy in (-1, 0, 1) for dx in (-1, 0, 1) for j in buckets.get((ky + dy, kx + dx), [])]
        for i in members:
            for j in neighbours:
                if j <= i:
                    continue
                a, b = rows[i], rows[j]
                m_lat, m_lon = metres_per_degree(a["latitude_dd"])
                d = math.hypot((a["latitude_dd"] - b["latitude_dd"]) * m_lat, (a["longitude_dd"] - b["longitude_dd"]) * m_lon)
                if d <= 30:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(len(rows)):
        if rows[i]["coordinate_status"] == "ok":
            groups.setdefault(find(i), []).append(i)
    counter = 0
    for members in sorted(groups.values(), key=lambda m: m[0]):
        if len(members) > 1:
            counter += 1
            for i in members:
                rows[i]["colocated_group_id"] = f"COLOC-{counter:04d}"
                rows[i]["colocated_group_size"] = len(members)


def clean_row(src):
    notes = []
    row = {name: "" for name in COLUMN_NAMES}
    for name in ("record_id", "source_id", "source_dataset", "spring_name", "village"):
        row[name] = src[name]
    district = src["district"].strip()
    row["district_clean"] = DISTRICT_FIXES.get(district.lower(), district)
    lat, lon = to_float(src["latitude_source_value"]), to_float(src["longitude_source_value"])
    if src["record_id"] in COORDINATE_FIXES:
        fix_lat, fix_lon, why = COORDINATE_FIXES[src["record_id"]]
        lat, lon = fix_lat or lat, fix_lon or lon
        row["coordinate_correction"] = why
    if src["record_id"] in COORDINATE_NOTES:
        notes.append(COORDINATE_NOTES[src["record_id"]])
    if lat is None or lon is None:
        row["coordinate_status"] = "missing"
        notes.append("no coordinates in source; layer values not computed")
    else:
        row["latitude_dd"], row["longitude_dd"] = lat, lon
        decimals = len(src["latitude_source_value"].split(".")[1]) if "." in src["latitude_source_value"] else 0
        row["coordinate_precision_decimals"] = decimals
        inside = REGION["lat_min"] <= lat <= REGION["lat_max"] and REGION["lon_min"] <= lon <= REGION["lon_max"]
        row["coordinate_status"] = "ok" if inside else "outside_study_region"
        if not inside:
            notes.append("coordinate outside study region; likely a typing error in the source")
        if decimals <= 2 and not row["coordinate_correction"]:
            notes.append("coordinate rounded to about 1 km; point layer values are indicative only")

    row["source_elevation_m"] = to_float(src["elevation_m_source_value"])
    low, high, note = parse_numbers(src["discharge_lpm_source_value"])
    row["source_discharge_lpm_low"], row["source_discharge_lpm_high"], row["source_discharge_parse_note"] = low, high, note
    max_flow = to_float(src.get("discharge_max_m3_per_day_source_value", ""))
    row["source_max_flow_lpm_converted"] = None if max_flow is None else max_flow * 1000 / 1440
    low, high, _ = parse_numbers(src["recharge_area_ha_source_value"])
    row["source_recharge_area_ha_low"], row["source_recharge_area_ha_high"] = low, high
    shed = to_float(src.get("springshed_area_km2_source_value", ""))
    row["source_springshed_area_ha_converted"] = None if shed is None else shed * 100
    row["source_catchment_area_ha"] = to_float(src.get("catchment_area_ha_source_value", ""))
    low, high, _ = parse_numbers(src["rainfall_source_value"])
    row["source_rainfall_mm"] = low if low == high else None
    row["source_slope_deg"] = to_float(src["slope_degrees_source_value"])
    row["source_tds_mg_l"] = to_float(src["tds_source_value"])
    row["source_ph"] = to_float(src["ph_source_value"])
    row["_notes"] = notes
    return row


def open_layers(points, cache, local_layers, lineaments=LINEAMENTS_FILE, soil_hwsd=True, buildings=True):
    """Open every layer once; DEM and WorldCover tiles covering the points are downloaded into the cache.
    soil_hwsd=False skips the 2 GB HWSD soil map (Module A does not use it; its tables need a Linux export step).
    buildings=False skips Google Open Buildings, which is read over the internet for every spring."""
    cache = Path(cache)
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    # Use the platform trust store (or an explicitly configured CURL_CA_BUNDLE).
    # Probing an old machine's /root certificate path fails for unprivileged cloud users.
    print("Opening layers")
    layers = argparse.Namespace(
        dem=[rasterio.open(p) for p in dem_tiles_for(points, cache)],
        wc=[rasterio.open(p) for p in worldcover_tiles_for(points, cache)],
        pcp_a=WaporStack("L1-PCP-A", [str(y) for y in YEARS], cache=cache),
        pcp_m=WaporStack("L1-PCP-M", [f"{y}-{m:02d}" for y in YEARS for m in range(1, 13)], cache=cache),
        ret_a=WaporStack("L1-RET-A", [str(y) for y in YEARS], cache=cache),
        hwsd=Hwsd(cache) if soil_hwsd else NoLayer(),
        local=LocalLayers(local_layers, lineaments),
        ngdr=NgdrGeology(),
        buildings=OpenBuildingsTemporal(cache) if buildings else NoLayer(),
    )
    ngdr = layers.ngdr
    print("GSI NGDR geology: " + (f"{len(ngdr.units)} lithology polygons, {len(ngdr.faults)} faults, {len(ngdr.folds)} fold axes" if ngdr.ok else "not found"))
    print("Local layers: " + ("; ".join(layers.local.found) or "none found"))
    return layers


def point_features(layers, lon, lat, source_elevation=None, notes=None):
    """All layer values at one coordinate, keyed by the spring_features_v1 column names."""
    notes = [] if notes is None else notes
    row = dem_features(layers.dem, lon, lat)
    if row.get("dem_elevation_m") is not None and source_elevation is not None:
        row["dem_minus_source_elevation_m"] = row["dem_elevation_m"] - source_elevation
        if abs(row["dem_minus_source_elevation_m"]) > ELEVATION_GAP_M:
            notes.append(f"DEM and source elevation differ by more than {ELEVATION_GAP_M} m; check coordinate")
            row["elevation_match_distance_m"] = elevation_match_distance(layers.dem, lon, lat, source_elevation)
    row.update(hydrology_features(read_window, centre_index, metres_per_degree, layers.dem, lon, lat))
    row.update(worldcover_features(layers.wc, lon, lat))

    annual = [layers.pcp_a.sample(str(y), lon, lat) for y in YEARS]
    annual = [v for v in annual if not math.isnan(v)]
    if annual:
        mean = statistics.fmean(annual)
        row["rain_chirps_mean_annual_mm_2018_2025"] = mean
        row["rain_chirps_min_annual_mm_2018_2025"] = min(annual)
        row["rain_chirps_max_annual_mm_2018_2025"] = max(annual)
        row["rain_chirps_cv_annual_pct"] = 100 * statistics.pstdev(annual) / mean if mean else None
        monthly = {(y, m): layers.pcp_m.sample(f"{y}-{m:02d}", lon, lat) for y in YEARS for m in range(1, 13)}
        year_totals = [sum(monthly[(y, m)] for m in range(1, 13)) for y in YEARS]
        monsoon = [sum(monthly[(y, m)] for m in (6, 7, 8, 9)) for y in YEARS]
        dry = [sum(monthly[(y, m)] for m in (1, 2, 3, 4, 11, 12)) for y in YEARS]
        if not any(math.isnan(v) for v in year_totals) and sum(year_totals):
            row["rain_chirps_monsoon_share_pct"] = 100 * sum(monsoon) / sum(year_totals)
            row["rain_chirps_dry_season_mm"] = statistics.fmean(dry)
        et0 = [layers.ret_a.sample(str(y), lon, lat) for y in YEARS]
        et0 = [v for v in et0 if not math.isnan(v)]
        if et0:
            row["et0_wapor_mean_annual_mm_2018_2025"] = statistics.fmean(et0)
            row["aridity_index_p_over_et0"] = mean / statistics.fmean(et0)
    row.update(layers.hwsd.features(lon, lat))
    row.update(layers.local.features(lon, lat))
    row.update(layers.ngdr.features(lon, lat))  # blank outside Uttarakhand
    row.update(layers.buildings.features(lon, lat))
    if row.get("cartodem_elevation_m") is not None and row.get("dem_elevation_m") is not None:
        row["cartodem_minus_copernicus_m"] = row["cartodem_elevation_m"] - row["dem_elevation_m"]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    parser.add_argument("--local-layers", default=os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers")))
    parser.add_argument("--lineaments", default=str(LINEAMENTS_FILE))
    parser.add_argument("--keep-hwsd", action="store_true",
                        help="Do not open the HWSD soil map (it needs a Linux export step); copy its columns from the "
                             "current table instead. HWSD is a fixed map, so the values do not change.")
    parser.add_argument("--only", help="Recompute only these records (comma-separated ids, or 'field-visit' for the field-visit "
                                        "springs) and copy every other row from the current table; used when the hand-downloaded "
                                        "layers are at hand for a few springs only.")
    args = parser.parse_args()
    cache = Path(args.cache)
    only, kept = None, {}
    if args.only:
        only = set(args.only.split(","))
        if "field-visit" in only:
            only.discard("field-visit")
            only |= set(field_visit_fixes()) | {r["record_id"] for r in csv.DictReader(COMMON_CSV.open(encoding="utf-8", newline=""))
                                                if r["record_id"].startswith("FLD-")}
        with (OUT_DIR / "spring_features_v1.csv").open(encoding="utf-8", newline="") as handle:
            kept = {r["record_id"]: r for r in csv.DictReader(handle) if r["record_id"] not in only}
    kept_soil = {}
    if args.keep_hwsd and (OUT_DIR / "spring_features_v1.csv").exists():
        with (OUT_DIR / "spring_features_v1.csv").open(encoding="utf-8", newline="") as handle:
            kept_soil = {r["record_id"]: {k: v for k, v in r.items() if k in HWSD_COLUMNS} for r in csv.DictReader(handle)}

    with COMMON_CSV.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = [clean_row(src) for src in source_rows]
    colocated_groups(rows)
    if only is not None:
        missing = only - {r["record_id"] for r in rows}
        if missing:
            raise SystemExit(f"--only: not in the common file: {', '.join(sorted(missing))}")
        for row in rows:
            if row["record_id"] in kept:  # layer values as last built; the colocated groups are recomputed
                old_row = kept[row["record_id"]]
                row.update({k: v for k, v in old_row.items() if not k.startswith("colocated_group")})
                row["_notes"] = [old_row["processing_notes"]] if old_row["processing_notes"] else []
            elif row["record_id"] not in only:
                raise SystemExit(f"--only: {row['record_id']} is new in the common file; add it to --only")
    points = [(r["latitude_dd"], r["longitude_dd"]) for r in rows
              if r["coordinate_status"] == "ok" and r["record_id"] not in kept]

    layers = open_layers(points, cache, args.local_layers, args.lineaments, soil_hwsd=not args.keep_hwsd)
    print("Reading building counts")
    layers.buildings.prefetch(points)
    for index, row in enumerate(rows):
        if row["coordinate_status"] != "ok" or row["record_id"] in kept:
            continue
        row.update(point_features(layers, row["longitude_dd"], row["latitude_dd"], row["source_elevation_m"], row["_notes"]))
        row.update(kept_soil.get(row["record_id"], {}))
        if row["source_rainfall_mm"] is not None and row.get("rain_chirps_mean_annual_mm_2018_2025", "") != "":
            row["rain_source_minus_chirps_mm"] = row["source_rainfall_mm"] - row["rain_chirps_mean_annual_mm_2018_2025"]
        if (index + 1) % 200 == 0:
            print(f"  {index + 1} rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "spring_features_v1.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMN_NAMES)
        for row in rows:
            row["processing_notes"] = "; ".join(row.pop("_notes"))
            out = []
            for name in COLUMN_NAMES:
                value = row.get(name, "")
                if isinstance(value, (float, np.floating)):
                    digits = (6 if name in ("latitude_dd", "longitude_dd") else 3 if name in ("aridity_index_p_over_et0", "rain_imd_trend_kendall_p")
                              else 2 if name == "dem_twi" or "drainage_area" in name or "bulk_density" in name else 1)
                    value = fmt(value, digits)
                elif value is None:
                    value = ""
                out.append(value)
            writer.writerow(out)

    with (OUT_DIR / "spring_features_v1_data_dictionary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column", "unit", "source", "method"])
        writer.writerows(COLUMNS)

    coverage = []
    prefixes = sorted({r["record_id"][:3] for r in rows})
    for name in COLUMN_NAMES:
        counts = {p: sum(1 for r in rows if r["record_id"][:3] == p and r.get(name, "") not in ("", None)) for p in prefixes}
        totals = {p: sum(1 for r in rows if r["record_id"][:3] == p) for p in prefixes}
        coverage.append([name] + [f"{100 * counts[p] / totals[p]:.0f}" for p in prefixes] + [f"{100 * sum(counts.values()) / len(rows):.0f}"])
    with (OUT_DIR / "spring_features_v1_coverage_pct.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column"] + [f"{p}_pct_filled" for p in prefixes] + ["all_pct_filled"])
        writer.writerows(coverage)

    previous = {}
    if only is not None and (OUT_DIR / "spring_features_v1_metadata.json").exists():
        previous = json.loads((OUT_DIR / "spring_features_v1_metadata.json").read_text(encoding="utf-8"))
    metadata = {
        "built": previous.get("built", date.today().isoformat()),
        "input": str(COMMON_CSV.relative_to(ROOT)),
        "records": len(rows),
        "records_with_layer_values": len(points),
        "coordinate_status_counts": {s: sum(1 for r in rows if r["coordinate_status"] == s) for s in ("ok", "missing", "outside_study_region")},
        "colocated_groups": len({r["colocated_group_id"] for r in rows if r["colocated_group_id"]}),
        "layers": {
            "Copernicus DEM GLO-30": {"url_pattern": DEM_URL, "resolution": "1 arc-second (~30 m)", "vertical_datum": "EGM2008",
                                      "licence": "Copernicus DEM licence (free use with attribution: produced using Copernicus WorldDEM-30, DLR/Airbus, ESA)"},
            "ESA WorldCover 2021 v200": {"url_pattern": WC_URL, "resolution": "10 m", "licence": "CC BY 4.0, ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)"},
            "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A / L1-PCP-M": {"url_pattern": WAPOR_URL, "years": YEARS, "resolution": "0.05 degree (~5 km)",
                                                              "licence": "FAO WaPOR CC BY-NC-SA 4.0 (non-commercial); CHIRPS by UCSB Climate Hazards Center"},
            "FAO WaPOR v3 L1-RET-A": {"url_pattern": WAPOR_URL, "years": YEARS, "resolution": "~30 km", "licence": "CC BY-NC-SA 4.0"},
            "HWSD v2.0": {"urls": HWSD_URLS, "resolution": "30 arc-second (~1 km)", "licence": "FAO/IIASA, CC BY-NC-SA 3.0 IGO (non-commercial)"},
            "NRSC CartoDEM v3 30 m": {"source": "Bhoonidhi (bhoonidhi.nrsc.gov.in), downloaded by hand 2026-10-10; 1-degree tiles P5_PAN_CD_N*_E*_30m",
                                      "licence": "NRSC data policy; raw tiles not committed"},
            "IMD 0.25 degree daily gridded rainfall": {"source": "IMD Pune, files RF25_ind2001_rfp25.nc to RF25_ind2025_rfp25.nc (calendar years 2001-2025; 2012 not downloaded), downloaded by hand 2026-10-10 (2025), 2026-10-12 (2021-2024) and 2026-10-14 (2001-2020)",
                                                       "licence": "IMD data policy; raw file not committed"},
            "ISRIC SoilGrids 2.0": {"source": "soilgrids.org map export, mean, bbox lon 76-81 lat 28.7-32.4; 0-5 cm downloaded by hand 2026-10-10, "
                                              "5-15 and 15-30 cm (files named by property) on 2026-10-12",
                                    "licence": "CC BY 4.0",
                                    "file_identification": "The 0-5 cm exports were saved unnamed as out.tif ... out (4).tif. Each was matched to the named "
                                                           "5-15 cm file it correlates with pixel by pixel (Spearman 0.95-0.99): out=bdod, out (1)=clay, "
                                                           "out (2)=cfvo (coarse fragments), out (3)=sand, out (4)=organic carbon. There is no 0-5 cm silt file. "
                                                           "The first build (2026-10-10) had identified these by value range and wrongly read out (2) as organic "
                                                           "carbon, out (3) as silt and out (4) as sand; fixed 2026-10-12. Organic carbon is treated as organic "
                                                           "carbon density (ocd, hg/m3) as Rajat described the download; if it was soil organic carbon "
                                                           "content (soc, dg/kg) the column is g/kg instead of kg/m3."},
            "GSI NGDR Uttarakhand lithology, faults and folds": {"files": [str(p.relative_to(ROOT)) for p in (NGDR_LITHOLOGY, NGDR_FAULTS, NGDR_FOLDS)],
                                                         "source": "GSI Bhukosh / NGDR state layers (SRC-013, SRC-014, SRC-015), added to the repo 2026-10-10 and 2026-10-12",
                                                         "note": "State-scale map; a spring's polygon is a map overlay, not a field observation."},
            "Google Open Buildings 2.5D Temporal v1": {"url_pattern": OBT_URL, "years": list(OBT_YEARS), "radius_m": OBT_RADIUS_M,
                                                       "licence": "CC BY 4.0 (Google Open Buildings)", "resolution": "0.5 m grid of 4 m effective resolution, read at the 8 m overview"},
            "DEM lineament candidates": {"file": str(LINEAMENTS_FILE.relative_to(ROOT)), "method": "scripts/extract_dem_lineaments.py"},
            "DEM hydrology": {"method": "scripts/spring_hydrology.py: depression filling and D8 routing with pyflwdir, Freeman (1991) MFD area, "
                                        "TWI = ln(a / tan slope)", "stream_threshold_km2": STREAM_THRESHOLD_KM2,
                              "window": "+/- 5 km around each spring, +/- 20 km when the D8 catchment reaches the edge"},
        },
        "local_layers_found": previous.get("local_layers_found", layers.local.found),
        "not_acquired": {
            "Bhuvan LULC 1:50k": "Bhuvan services blocked from the build environment; download needs a request.",
        },
    }
    metadata["records_with_layer_values"] = sum(1 for r in rows if r["coordinate_status"] == "ok")
    metadata["partial_rebuilds"] = previous.get("partial_rebuilds", [])
    if only is not None:
        metadata["partial_rebuilds"].append({"date": date.today().isoformat(), "records": sorted(only),
                                             "local_layers_found": layers.local.found})
    (OUT_DIR / "spring_features_v1_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in ("records", "records_with_layer_values", "coordinate_status_counts", "colocated_groups")}, indent=2))


if __name__ == "__main__":
    main()
