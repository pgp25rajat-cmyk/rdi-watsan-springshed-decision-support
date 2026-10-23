"""The secondary layers collected after the SRHU geologist reports (October 2026), read at any point.

Used by the dataset build (scripts/build_spring_secondary_features.py) and by the tool (Modules A, B and C through
Module A's LayerSession), so a spring typed into the tool gets the same values as the springs in the master file.

Layers, all under the local layers folder (DOCC/Data/Secondary data) unless noted:
- NGDR(Bhukosh) GEOMORPHOLOGY_250K / LINEAMENT_250K, LANDSLIDE_POLYGON, ORIENTED_STRUCTURE_PLANE zips (SRC-029 to SRC-032).
  Uttarakhand only.
- Sentinel2/S2_NDVI_Tehri_OctNov2025_20m.tif (SRC-033). Tehri district only.
- Infiltration/Ksat_0-30cm_SaxtonRawls_mmh.tif (TRN-018).
- SoilGrids/BDRICM_M_250m_Uttarakhand.tif (SoilGrids 2017 depth to bedrock, cm, capped at 200; SRC-034).
- ERA5 winter snowfall (SRC-035), small enough to keep in the repo: data/02_processed/climate/.
Every layer is optional: a missing one leaves its values blank and is listed in .missing.
"""

from __future__ import annotations

import io
import json
import csv
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SNOW_TIF = ROOT / "data" / "02_processed" / "climate" / "era5_snowfall_winter_mean_v1.tif"
SNOW_CURVE = SNOW_TIF.with_name(SNOW_TIF.stem + "_curve.csv")  # median snow per 250 m band of ERA5 cells

DIP_RADIUS_M = 5000
LANDSLIDE_RADIUS_M = 500
FOREST_RADIUS_M = 500
DENSE_NDVI, OPEN_NDVI = 0.70, 0.50  # provisional forest cut-offs (README in Secondary data/Sentinel2)
RASTERS = {
    "ndvi": "Sentinel2/S2_NDVI_Tehri_OctNov2025_20m.tif",
    "ksat": "Infiltration/Ksat_0-30cm_SaxtonRawls_mmh.tif",
    "depth": "SoilGrids/BDRICM_M_250m_Uttarakhand.tif",
}

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
    ("era5_snowfall_winter_mm", "mm", "ERA5 (NSF NCAR copy), winters 2019-20 to 2024-25", "Mean snowfall per winter (Nov-Apr) as water equivalent, in the 27 km ERA5 cell. Says how snowy the area is, not the spring's own slope."),
    ("snow_at_elevation_mm", "mm", "ERA5 snowfall vs ERA5 ground height, winters 2019-20 to 2024-25", "Mean snowfall per winter (water equivalent) read off the ERA5 snow-height curve at the spring's elevation. ERA5 cells average lower ground than most springs, so this is the value the model uses."),
    ("report_catchment_ha", "ha", "SRHU geohydrology reports, traced", "Catchment drawn by the report geologists, measured from the traced outline (Badeda, Makhdet only; test springs)."),
]


_curve = None


def snow_at_elevation(elevation_m):
    """Winter snowfall (mm water) at a height, from the ERA5 snow-height curve; None without the curve or height."""
    global _curve
    if elevation_m is None:
        return None
    if _curve is None:
        if not SNOW_CURVE.exists():
            return None
        rows = list(csv.DictReader(SNOW_CURVE.open()))
        _curve = (np.array([float(r["elevation_m"]) for r in rows]), np.array([float(r["snow_mm"]) for r in rows]))
    return float(np.interp(float(elevation_m), *_curve))


def to_utm_transformer():
    from pyproj import Transformer
    return Transformer.from_crs(4326, 32644, always_xy=True)


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
    return next(iter(sorted(Path(folder).glob(f"{prefix}*.zip"))), None)


def window_values(src, lon, lat, radius_m):
    """Valid raster values in a square window of the given radius around the point (None outside the raster)."""
    from rasterio.windows import Window
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


def sample_grid(src, xs, ys):
    """Nearest raster value at many lon/lat points (NaN outside it or at nodata). Reads only the window covering them."""
    from rasterio.windows import from_bounds
    pad = 2 * max(abs(src.res[0]), abs(src.res[1]))
    window = from_bounds(xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad, src.transform)
    window = window.round_offsets().round_lengths()
    fill = src.nodata if src.nodata is not None else np.nan
    data = src.read(1, window=window, boundless=True, fill_value=fill).astype("float64")
    if src.nodata is not None and np.isfinite(src.nodata):
        data[data == src.nodata] = np.nan
    t = src.window_transform(window)
    rows = np.floor((ys - t.f) / t.e).astype(int)
    cols = np.floor((xs - t.c) / t.a).astype(int)
    inside = (rows >= 0) & (rows < data.shape[0]) & (cols >= 0) & (cols < data.shape[1])
    out = np.full(xs.shape, np.nan)
    out[inside] = data[rows[inside], cols[inside]]
    return out


class SecondaryLayers:
    """Opens each layer the first time it is needed. Geometries are kept in UTM 44N (metres)."""

    def __init__(self, folder):
        self.folder = Path(folder) if folder else None
        self._vectors = None
        self._rasters = None
        self.to_utm = to_utm_transformer()

    # ---------------------------------------------------------------- files
    @property
    def bhukosh_dir(self):
        return self.folder / "NGDR(Bhukosh)" if self.folder else None

    def files(self):
        """The files this reader uses, for the map set manifest: (source id, path)."""
        out = []
        if self.folder:
            for sid, prefix in (("SRC-029", "GEOMORPHOLOGY_250K"), ("SRC-031", "LANDSLIDE_POLYGON"), ("SRC-032", "ORIENTED_STRUCTURE_PLANE")):
                path = find_zip(self.bhukosh_dir, prefix) if self.bhukosh_dir.exists() else None
                if path:
                    out.append((sid, path))
            for sid, key in (("SRC-033", "ndvi"), ("TRN-018", "ksat"), ("SRC-034", "depth")):
                if (self.folder / RASTERS[key]).exists():
                    out.append((sid, self.folder / RASTERS[key]))
        return out

    @property
    def missing(self):
        have = {p.name for _, p in self.files()}
        need = ["NGDR(Bhukosh) geomorphology/lineament, landslide and structure-plane zips"] if not any(
            n.startswith(("GEOMORPHOLOGY", "LANDSLIDE", "ORIENTED")) for n in have) else []
        need += [rel for rel in RASTERS.values() if Path(rel).name not in have]
        if not SNOW_TIF.exists():
            need.append(str(SNOW_TIF.relative_to(ROOT)))
        return need

    # ---------------------------------------------------------------- vectors
    @property
    def vectors(self):
        if self._vectors is None:
            self._vectors = self._load_vectors()
        return self._vectors

    def _load_vectors(self):
        import shapely
        from shapely import STRtree, prepare
        from shapely.geometry import Point, shape
        from shapely.ops import unary_union

        def utm(geometry):
            return shapely.transform(geometry, lambda xy: np.c_[self.to_utm.transform(xy[:, 0], xy[:, 1])])

        v = {"ok": False}
        if not self.bhukosh_dir or not self.bhukosh_dir.exists():
            return v
        gm_zip = find_zip(self.bhukosh_dir, "GEOMORPHOLOGY_250K")
        if gm_zip:
            geomorph = [(shape(f["geometry"]), f["properties"].get("descriptio") or "") for f in
                        read_zipped_geojson(gm_zip, "GEOMORPHOLOGY") if f["geometry"]]
            state = unary_union([g.buffer(0) for g, _ in geomorph])
            prepare(state)
            lineaments = [(utm(shape(f["geometry"])), f["properties"].get("l2descript") or "") for f in
                          read_zipped_geojson(gm_zip, "LINEAMENT") if f["geometry"]]
            v.update(ok=True, state=state, geomorph=geomorph, geomorph_tree=STRtree([g for g, _ in geomorph]),
                     lineaments=lineaments, line_tree=STRtree([g for g, _ in lineaments]))
            joints = [g for g, kind in lineaments if "joint" in kind.lower() or "fracture" in kind.lower()]
            v.update(joints=joints, joint_tree=STRtree(joints))
        ls_zip = find_zip(self.bhukosh_dir, "LANDSLIDE_POLYGON")
        if ls_zip:
            slides = [(utm(shape(f["geometry"]).buffer(0)), f["properties"].get("geom11") or "") for f in
                      read_zipped_geojson(ls_zip, "LANDSLIDE") if f["geometry"]]
            v.update(slides=slides, slide_tree=STRtree([g for g, _ in slides]))
        sp_zip = find_zip(self.bhukosh_dir, "ORIENTED_STRUCTURE_PLANE")
        if sp_zip:
            found = [f for f in read_zipped_geojson(sp_zip, "ORIENTED") if f["geometry"]]
            planes = [f["properties"] for f in found]
            points = [Point(self.to_utm.transform(*f["geometry"]["coordinates"][:2])) for f in found]
            v.update(planes=planes, plane_points=points, plane_tree=STRtree(points))
        return v

    def lineaments_in(self, box_utm):
        """Mapped (Bhukosh 1:250k) lineaments crossing a UTM box: [(line, kind)]."""
        v = self.vectors
        if "line_tree" not in v:
            return []
        return [v["lineaments"][i] for i in v["line_tree"].query(box_utm)]

    def landslides_in(self, box_utm):
        v = self.vectors
        if "slide_tree" not in v:
            return []
        return [v["slides"][i] for i in v["slide_tree"].query(box_utm)]

    def dip_near(self, lon, lat, radius_m):
        """Measured bedding/foliation planes within radius, nearest first: [(distance m, dip deg, dip direction deg, type)]."""
        from shapely.geometry import Point
        v = self.vectors
        if "plane_tree" not in v:
            return []
        point = Point(self.to_utm.transform(lon, lat))
        out = []
        for j in v["plane_tree"].query(point, predicate="dwithin", distance=radius_m):
            p = v["planes"][j]
            if "JOINT" in (p.get("point_type") or "").upper() or p.get("dip_amount") is None or p.get("dip_direct") is None:
                continue
            out.append((float(v["plane_points"][j].distance(point)), float(p["dip_amount"]), float(p["dip_direct"]), p.get("point_type") or ""))
        return sorted(out)

    # ---------------------------------------------------------------- rasters
    def raster(self, key):
        """An open rasterio dataset ("ndvi", "ksat", "depth" or "snow"), or None when the file is not there."""
        if self._rasters is None:
            import rasterio
            paths = {k: self.folder / rel for k, rel in RASTERS.items()} if self.folder else {}
            paths["snow"] = SNOW_TIF
            self._rasters = {k: rasterio.open(p) for k, p in paths.items() if p.exists()}
        return self._rasters.get(key)

    def _point_value(self, key, lon, lat):
        src = self.raster(key)
        if src is None:
            return None
        row, col = src.index(lon, lat)
        if not (0 <= row < src.height and 0 <= col < src.width):
            return None
        value = float(next(src.sample([(lon, lat)]))[0])
        return value if np.isfinite(value) and value != src.nodata else None

    # ---------------------------------------------------------------- one point
    def point(self, lon, lat, elevation_m=None):
        """The COLUMNS values at a point (numbers or text; None where a layer does not cover it).
        elevation_m (the spring's height) is needed only for snow_at_elevation_mm."""
        from shapely.geometry import Point
        row = {c[0]: None for c in COLUMNS if c[0] != "report_catchment_ha"}
        v = self.vectors
        point_ll, point = Point(lon, lat), Point(self.to_utm.transform(lon, lat))
        if v.get("ok") and v["state"].contains(point_ll):
            hits = [v["geomorph"][i][1] for i in v["geomorph_tree"].query(point_ll, predicate="within")]
            row["bhukosh_geomorphology_250k"] = hits[0] if hits else None
            i = v["line_tree"].nearest(point)
            row["bhukosh_lineament_distance_m"] = v["lineaments"][i][0].distance(point)
            row["bhukosh_lineament_nearest_type"] = v["lineaments"][i][1]
            row["bhukosh_joint_distance_m"] = v["joints"][v["joint_tree"].nearest(point)].distance(point)
            if "slide_tree" in v:
                i = v["slide_tree"].nearest(point)
                row["landslide_distance_m"] = v["slides"][i][0].distance(point)
                row["landslide_landform_nearest"] = v["slides"][i][1]
                row["landslide_count_500m"] = len(v["slide_tree"].query(point, predicate="dwithin", distance=LANDSLIDE_RADIUS_M))
            if "plane_tree" in v:
                near = sorted(v["plane_tree"].query(point, predicate="dwithin", distance=DIP_RADIUS_M),
                              key=lambda j: v["plane_points"][j].distance(point))
                row["gsi_dip_points_5km"] = len(near)
                if near:
                    p = v["planes"][near[0]]
                    row["gsi_dip_nearest_distance_m"] = v["plane_points"][near[0]].distance(point)
                    row["gsi_dip_nearest_type"] = p["point_type"]
                    row["gsi_dip_nearest_deg"] = p["dip_amount"]
                    row["gsi_dip_nearest_direction_deg"] = p["dip_direct"]
                    dips = [v["planes"][j]["dip_amount"] for j in near
                            if "JOINT" not in v["planes"][j]["point_type"] and v["planes"][j]["dip_amount"] is not None]
                    row["gsi_dip_median_5km_deg"] = float(np.median(dips)) if dips else None
        ndvi = self.raster("ndvi")
        if ndvi is not None:
            around = window_values(ndvi, lon, lat, 30)
            if around is not None and around.size:
                row["ndvi_s2_2025"] = float(np.mean(around)) / 100
                ring = window_values(ndvi, lon, lat, FOREST_RADIUS_M) / 100
                row["forest_dense_500m_pct"] = 100 * float(np.mean(ring >= DENSE_NDVI))
                row["forest_open_500m_pct"] = 100 * float(np.mean((ring >= OPEN_NDVI) & (ring < DENSE_NDVI)))
        row["soil_ksat_0_30cm_mm_h"] = self._point_value("ksat", lon, lat)
        row["soil_depth_to_bedrock_cm"] = self._point_value("depth", lon, lat)
        row["era5_snowfall_winter_mm"] = self._point_value("snow", lon, lat)
        row["snow_at_elevation_mm"] = snow_at_elevation(elevation_m)
        return row
