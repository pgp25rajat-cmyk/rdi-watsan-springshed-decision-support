"""Module B: where a spring's water soaks in, and the best places to recharge it, drawn on the map.

There is no ready-made "point in, springshed out" method (docs: Project1 plan, section 4.4), so this is a
transparent hybrid that a geologist can check and correct in the field:

1. Surface catchment. The 30 m Copernicus DEM is depression-filled and routed (D8, pyflwdir). The land draining
   to the spring cell is its surface catchment. A 30 m DEM and a phone GPS can both be one cell off, so the
   catchments of the 8 cells around the spring are also allowed (unless a cell is a stream). Both are reported:
   the exact-cell catchment and the GPS-tolerant one, which can differ many times over.
2. Links. Ground can send water to the spring in two ways: on the slope that drains to it (the surface catchment,
   plus a narrow margin for DEM error), or from further away, beyond the ridge, along a mapped fault or a DEM
   lineament (a likely crack) that passes near the spring, or up-dip when the field form gives the rock tilt.
3. Recharge potential. Every cell gets a 0-1 score from slope, land cover, rock type, distance to faults or
   lineaments and soil, with the weights and class scores in config/module_b_recharge_factors_v1.csv (AHP-style
   overlay, Nijesh 2024 / Joshi 2024; weights are a draft for WATSAN to change).
4. Size. The recharge area the flow needs comes from the spring's peak (monsoon) flow, using the area-flow relation
   fitted to the 35 Rathi (2021) springsheds; with no flow reading, the typical 1-10 ha of hill springsheds is used.
   Zones are grown to this size, so matching it is by design, not evidence that a zone is right.
5. Top three zones. Every linked cell is scored: potential x link strength x closeness. The best cell seeds a zone,
   grown among cells with the same link up to the needed area; a deep valley between a far zone and the spring
   lowers or rules it out; the zone is set aside and the search repeats. The best three are R1-R3, wherever they
   lie: all on the spring's own slope, all beyond the ridge, or a mix.

The zones are candidate places to inspect, not delineated springsheds or sites ready for works. Streams stop a zone
from growing by default (field answer streams_block_zones = false turns this off). Every number used is listed in
config/assumption_register_v1.csv.
Usage (one spring):
    python scripts/module_b_springshed.py --lat 29.91903 --lon 78.55647 [--elevation 1481] [--monsoon-flow-lpm 12]
           [--dip-direction 220 --dip-angle 30] [--geojson out.geojson]
Layers are read with scripts/build_spring_features.py through Module A's LayerSession (--cache, --local-layers).
"""

from __future__ import annotations

import argparse
import base64
import csv
import heapq
import json
import math
import os
import statistics
import struct
import sys
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FACTORS_CSV = ROOT / "config" / "module_b_recharge_factors_v1.csv"
LITERATURE_CSV = ROOT / "data" / "01_staged" / "literature" / "csv" / "literature_spring_records_common_v1.csv"
INPUT_CSV = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1_input.csv"

WINDOW_M = 4300  # DEM read around the spring (half-width): the whole search area plus a margin
BELOW_TOLERANCE_M = 3  # DEM noise: cells this much below the spring still count as level with it
STREAM_BARRIER_KM2 = 0.5  # D8 drainage area at which a channel is a stream a zone does not cross
STREAM_DISPLAY_KM2 = 0.1  # smaller channels are shown on the map but are not barriers
NEAR_SPRING_M = 90  # stream barriers and the valley check do not apply this close to the spring
RIDGE_MARGIN_M = 60  # the spring's own slope reaches this far past the catchment divide (DEM error)
DIP_SECTOR_DEG = 40  # half-width of the up-dip sector when the rock tilt is known
MIN_DIP_DEG = 5
DEFAULT_AREA_HA = (1.5, 3.0, 8.0)  # small / likely / large recharge area without a flow reading
# The top recharge zones: on the spring's own slope, or beyond the ridge through a fault, crack or tilted rock layer
N_ZONES = 3
ZONE_MAX_M = 4000  # farthest a zone may be from the spring
LINKED_MIN_HEAD_M = 20  # ground beyond the spring's slope must be at least this much higher for water to flow down
CONDUIT_NEAR_SPRING_M = 200  # a fault or lineament this close to the spring can be the path the water takes
CONDUIT_CORRIDOR_M = 250  # cells this close to that line count as linked to the spring
MIN_ZONE_POTENTIAL = 0.5  # recharge potential a zone cell needs
FALLBACK_POTENTIAL = 0.35  # used, with a warning, when no linked ground reaches MIN_ZONE_POTENTIAL
MIN_ZONE_HA = 1.0  # smaller patches are dropped
ZONE_GAP_M = 90  # zones are kept at least this far apart
DECAY_M = 4000  # closeness: a zone 1 km away scores 0.78 of the same zone at the spring, 3 km away 0.47
DEEP_VALLEY_M = 30  # a valley this much below the spring between a far zone and the spring halves its score
CUT_VALLEY_M = 100  # a valley this much below the spring rules the zone out
DOWN_DIP_FACTOR = 0.6  # with a measured tilt, the spring's own slope counts less where the layers dip away from it
LINK_KINDS = ["None", "Surface slope", "GSI fault", "Rock layers (up-dip)", "DEM lineament", "Mapped lineament"]
LINK_WEIGHT = {"Surface slope": 1.0, "GSI fault": 0.9, "Rock layers (up-dip)": 0.9, "DEM lineament": 0.7, "Mapped lineament": 0.9}
LINK_PHRASE = {"Surface slope": "on the slope that drains to the spring",
               "GSI fault": "linked to the spring by a mapped fault",
               "Mapped lineament": "linked to the spring by a lineament mapped by GSI geologists (a joint, fracture or shear zone)",
               "Rock layers (up-dip)": "linked to the spring by rock layers tilting down towards it",
               "DEM lineament": "linked to the spring by a lineament (a straight line on the elevation map, likely a crack)"}
NODATA = -9999.0
VALIDATION = ("Not yet validated: no field-walked springshed boundary has been compared with these zones. "
              "They are candidate places to inspect, not delineated springsheds.")
GPS_SENSITIVE_RATIO = 3  # warn when allowing 30 m of GPS error makes the catchment this many times bigger
# Catchment to the ridge, the way the SRHU geologists draw it: the whole valley above the spring, bounded by the ridges.
# Standard GIS practice: snap the outlet to the main drainage line within a few cells (ArcGIS "Snap Pour Point"), then
# take everything upslope of it that is higher than the spring. Fixed from practice, not fitted to the report maps.
SNAP_M = 90  # 3 cells of the 30 m DEM
SNAP_MAX_KM2 = 5.0  # never snap onto a river: a channel draining more than 500 ha is a gad or river, not a spring's valley
RIDGE_BELOW_M = 10  # ground down to this far below the spring still counts (DEM noise at the outlet)
VALLEY_MAX_M, VALLEY_MAX_STEPS = 1500, 200  # how far down the flow path the spring's valley is followed
GSI_DIP_RADIUS_M = 2000  # without a field reading, a GSI bedding or foliation measurement this close gives the tilt
NDVI_CLASSES = ((0.70, "Tree cover: dense (NDVI 0.70 or more)"), (0.50, "Tree cover: open (NDVI 0.50-0.70)"),
                (-1.0, "Tree cover: sparse (NDVI under 0.50)"))

WORLDCOVER = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
              60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
              90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}
LEGEND = [("Very low", (255, 255, 204, 70)), ("Low", (217, 240, 163, 120)), ("Medium", (173, 221, 142, 150)),
          ("High", (65, 171, 93, 170)), ("Very high", (0, 104, 55, 190))]


# --------------------------------------------------------------------------- tables
@lru_cache(maxsize=1)
def load_factors(path=FACTORS_CSV):
    """factor id -> {"name", "weight", "why", "classes": {class: score}} in file order."""
    factors = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            f = factors.setdefault(row["factor"], {"name": row["factor_name"], "weight": float(row["weight_pct"]),
                                                   "why": row["why"], "classes": {}})
            f["classes"][row["class"]] = float(row["score"])
            if row["why"] and not f["why"]:
                f["why"] = row["why"]
    return factors


@lru_cache(maxsize=1)
def rathi_fit():
    """Power law area_ha = a * peak_flow_lpm ** b fitted (log-log least squares) to the 35 Rathi (2021) springsheds.
    Their areas were tuned by the authors to follow an area-flow relation, so the scatter understates the real error."""
    q, area = [], []
    with LITERATURE_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["record_id"].startswith("RAT-") and row["discharge_max_m3_per_day_source_value"] and row["springshed_area_km2_source_value"]:
                q.append(float(row["discharge_max_m3_per_day_source_value"]) * 1000 / 1440)
                area.append(float(row["springshed_area_km2_source_value"]) * 100)
    b, log_a = np.polyfit(np.log(q), np.log(area), 1)
    return {"a": float(math.exp(log_a)), "b": float(b), "n": len(q), "q_range": (min(q), max(q))}


@lru_cache(maxsize=1)
def monsoon_to_lean_ratio():
    """Median monsoon / lean-season flow among the input springs with two different readings (never the test springs).
    Most WATSAN rows repeat one reading in both columns; those say nothing about the ratio and are skipped."""
    ratios = []
    with INPUT_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                dry, wet = float(row["discharge_dry_lpm"]), float(row["discharge_monsoon_lpm"])
            except (KeyError, ValueError):
                continue
            if dry > 0 and wet > dry:
                ratios.append(wet / dry)
    return (statistics.median(ratios), len(ratios)) if ratios else (3.0, 0)


def target_area(field):
    """Small / likely / large target areas (ha) and the reason, from the flow readings on the field form."""
    fit = rathi_fit()
    monsoon, lean = _number(field.get("monsoon_flow_lpm")), _number(field.get("lean_flow_lpm"))
    if monsoon and monsoon > 0:
        likely, spread = fit["a"] * monsoon ** fit["b"], 2.0
        basis = (f"Sized from the monsoon flow ({monsoon:g} L/min) with the area-flow relation of {fit['n']} delineated "
                 f"Garhwal springsheds (Rathi 2021): area = {fit['a']:.3f} x flow^{fit['b']:.2f}. Those areas are paired with each "
                 "spring's long-term maximum flow; one monsoon reading can be lower or higher, so treat the size as a rough guide.")
        if monsoon > fit["q_range"][1] * 1.5 or monsoon < fit["q_range"][0] / 1.5:
            spread = 3.0
            basis += f" That flow is outside the {fit['q_range'][0]:.0f}-{fit['q_range'][1]:.0f} L/min those springs cover, so the range is wider."
        kind = "monsoon flow"
    elif lean and lean > 0:
        ratio, n = monsoon_to_lean_ratio()
        peak = lean * ratio
        likely, spread = fit["a"] * peak ** fit["b"], 2.5
        basis = (f"Sized from the lean-season flow ({lean:g} L/min) times {ratio:.1f}, the median monsoon/lean ratio of {n} "
                 f"springs in the data, with the Rathi (2021) area-flow relation. A monsoon reading would narrow this.")
        kind = "lean flow"
    else:
        small, likely, large = DEFAULT_AREA_HA
        return {"low": small, "mid": likely, "high": large, "kind": "default",
                "basis": "No flow reading was given, so this is a default, not a size for this spring: the typical size of "
                         "delineated hill springsheds (1-10 ha; Rathi 2021, Spring Atlas profiles). A monsoon flow reading would "
                         "size it for this spring."}
    likely = max(likely, 0.5)
    return {"low": round(max(likely / spread, 0.3), 2), "mid": round(likely, 2), "high": round(likely * spread, 2),
            "kind": kind, "basis": basis}


def _number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def rock_classes(text):
    """Rock classes named in a GSI lithology text, e.g. ["Phyllite", "Quartzite", "Carbonate"]; ["Other"] if none."""
    from build_spring_master import LITHOLOGY_CLASSES
    lowered, hits = (text or "").lower(), []
    for key, label in LITHOLOGY_CLASSES:
        if key in lowered and label not in hits:
            hits.append(label)
    return hits or ["Other"]


def slope_class(deg):
    return "0-10 degrees" if deg < 10 else "10-20 degrees" if deg < 20 else "20-30 degrees" if deg < 30 else "30-40 degrees" if deg < 40 else "over 40 degrees"


def depth_class(cm):
    return "under 50 cm" if cm < 50 else "50-100 cm" if cm < 100 else "100-150 cm" if cm < 150 else "150 cm or more"


def ridge_catchment(flw, upa, z, row, col, dist, idx):
    """The whole valley above the spring up to the ridges, kept to ground no lower than the spring: the basin of the main
    drainage line within SNAP_M of the spring (but not a river), plus the side slopes of the valley the spring drains
    into, down to where it meets a stream. Returns (mask, snapped cell, its drainage km2)."""
    from scipy.ndimage import label
    z_s = z[row, col]
    near = (dist <= SNAP_M) & (z <= z_s + BELOW_TOLERANCE_M) & (upa <= SNAP_MAX_KM2) & (z > NODATA)
    near[row, col] = True
    choice = np.where(near, upa, -1.0)
    r, c = np.unravel_index(int(np.argmax(choice)), z.shape)
    basin = flw.basins(idxs=np.array([idx(r, c)])) > 0
    basin &= z >= z_s - RIDGE_BELOW_M
    basin[row, col] = True
    parts, _ = label(basin)
    keep = {parts[row, col], parts[r, c]} - {0}
    mask = np.isin(parts, list(keep))
    # The side slopes: follow the water down from the spring to just before it joins a stream (STREAM_BARRIER_KM2,
    # the model's own stream size) and take that valley's ground above the spring, ridge to ridge (Rajat 2026-10-23)
    down, cell = flw.idxs_ds, idx(row, col)
    outlet = cell
    for _ in range(VALLEY_MAX_STEPS):
        nxt = int(down[cell])
        rr, cc = divmod(nxt, z.shape[1])
        if nxt == cell or upa[rr, cc] >= STREAM_BARRIER_KM2 or dist[rr, cc] > VALLEY_MAX_M:
            break
        cell = outlet = nxt
    if upa.flat[outlet] < STREAM_BARRIER_KM2:
        side = flw.basins(idxs=np.array([outlet])) > 0
        side &= z >= z_s - RIDGE_BELOW_M
        side[row, col] = True
        parts, _ = label(side)
        mask |= parts == parts[row, col]
    return mask, (int(r), int(c)), float(upa[r, c])


def structure_class(dist):
    return "within 100 m" if dist <= 100 else "100-250 m" if dist <= 250 else "250-500 m" if dist <= 500 else "over 500 m"


SOIL_DEPTHS = (("0_5cm", 5), ("5_15cm", 10), ("15_30cm", 15))  # SoilGrids layers and their thickness (cm)


def soil_class(clay, sand):
    if sand >= 70:
        return "Sandy (sand 70% or more)"
    if sand >= 50 and clay < 20:
        return "Sandy loam (sand 50-70%, clay under 20%)"
    if clay < 27:
        return "Loam or silt loam (clay under 27%)"
    if clay < 40:
        return "Clay loam (clay 27-40%)"
    return "Clay (clay 40% or more)"


def _sample(grid, gt, xs, ys):
    """Nearest value of a coarse grid (array, transform) at every cell centre; NaN outside it or where it is 0."""
    rows = np.floor((ys - gt.f) / gt.e).astype(int)
    cols = np.floor((xs - gt.c) / gt.a).astype(int)
    inside = (rows >= 0) & (rows < grid.shape[0]) & (cols >= 0) & (cols < grid.shape[1])
    out = np.full(xs.shape, np.nan)
    out[inside] = grid[rows[inside], cols[inside]]
    out[out <= 0] = np.nan
    return out


def soil_layers(local, xs, ys):
    """Clay, sand and coarse fragments (%) averaged over 0-30 cm at every cell, or None without SoilGrids."""
    soil = getattr(local, "soil", None) or {}
    out = {}
    for prop, stem in (("clay", "sg_clay"), ("sand", "sg_sand"), ("coarse", "sg_coarse_fragments")):
        layers = [(soil.get(f"{stem}_{d}_pct"), w) for d, w in SOIL_DEPTHS]
        layers = [(g, w) for g, w in layers if g is not None]
        if not layers:
            return None
        total = sum(w * _sample(g[0], g[1], xs, ys) for g, w in layers)
        out[prop] = total / sum(w for _, w in layers)
    return out if np.isfinite(out["clay"]).any() else None


# --------------------------------------------------------------------------- grid helpers
def _grid_coords(shape, t):
    rows, cols = np.indices(shape)
    return t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e


def _mask_to_feature(mask, t, properties, smooth_deg):
    """Polygon (WGS84 GeoJSON feature) of the True cells, with the stair-steps of the 30 m grid softened."""
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    if not mask.any():
        return None
    parts = [shape(geom) for geom, value in shapes(mask.astype("uint8"), mask=mask, transform=t) if value == 1]
    geom = unary_union(parts).buffer(smooth_deg, join_style="round").buffer(-smooth_deg, join_style="round")
    geom = geom.simplify(smooth_deg / 3, preserve_topology=True)
    return {"type": "Feature", "geometry": mapping(geom), "properties": properties}


def _png(rgba):
    """RGBA array -> PNG data URL, written with the standard library (no imaging package needed)."""
    height, width = rgba.shape[:2]
    raw = b"".join(b"\x00" + rgba[r].tobytes() for r in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _lines_in_window(lines, to_lonlat, box_utm, props):
    """GeoJSON line features (WGS84) of the UTM lines that cross the window."""
    from shapely import transform as shapely_transform
    from shapely.geometry import mapping
    features = []
    for geom, p in zip(lines, props):
        part = geom.intersection(box_utm)
        if part.is_empty:
            continue
        part = shapely_transform(part, lambda xy: np.column_stack(to_lonlat(xy[:, 0], xy[:, 1])))
        features.append({"type": "Feature", "geometry": mapping(part), "properties": p})
    return {"type": "FeatureCollection", "features": features}


def _grow(seed, allowed, priority, limit, start=None):
    """Add 4-connected cells from the seed, best priority first. Returns the cells in the order they were added
    (start cells first). 4-connection means a one-cell-wide stream or fault line is a real barrier."""
    nrow, ncol = allowed.shape
    order = list(start or [seed])
    taken = np.zeros(allowed.shape, bool)
    for cell in order:
        taken[cell] = True
    heap = []

    def push_neighbours(r, c):
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= rr < nrow and 0 <= cc < ncol and not taken[rr, cc] and allowed[rr, cc]:
                taken[rr, cc] = True
                heapq.heappush(heap, (-priority[rr, cc], rr, cc))

    for r, c in order:
        push_neighbours(r, c)
    while heap and len(order) < limit:
        _, r, c = heapq.heappop(heap)
        order.append((r, c))
        push_neighbours(r, c)
    return order


ZONE_CHECKS = [
    "Walk each zone with a geologist before spending money: look for deep soil, open cracks in the rock, and seepage or "
    "green patches between the zone and the spring.",
]
LINKED_CHECKS = [
    "Walk the crack or fault line between the spring and the zone: seepage, small springs, a line of greener vegetation "
    "or a gully along it all support a link.",
    "Measure the spring's water temperature and conductivity (EC) every month. Water that soaked in higher up and farther "
    "away is usually cooler and steadier through the year than the local slope alone would give.",
    "After a heavy rain, note how long the spring takes to rise. A slow, smooth rise days later points to a farther or deeper "
    "source than a quick, sharp rise.",
    "If there is budget, an oxygen-18 isotope test of the spring water estimates the height at which it fell as rain; it "
    "should match the zone's height.",
]


def _valley_between(c, near):
    """How far the lowest ground on the straight line from the spring to a cell dips below the spring (m), ignoring the
    ground right at the spring. A valley deeper than the spring in between would catch the water first."""
    z, dist, row, col = c["z"], c["dist"], c["row"], c["col"]
    steps = max(2, int(dist[near] / 15))
    rr = np.linspace(row, near[0], steps).round().astype(int)
    cc = np.linspace(col, near[1], steps).round().astype(int)
    between = [z[r, q] for r, q in zip(rr, cc) if dist[r, q] > NEAR_SPRING_M and c["valid"][r, q]]
    return max(0.0, c["z_s"] - min(between)) if between else 0.0


def link_map(c):
    """Every cell that can send water to the spring, and how: on the slope that drains to it (its surface catchment),
    or beyond it along a fault or lineament passing near the spring, or up-dip when the rock tilt is known.
    Returns (kind, weight, link_id, links): kind indexes LINK_KINDS, link_id indexes links (faults and lineaments)."""
    import shapely
    z, dist, z_s = c["z"], c["dist"], c["z_s"]
    shape_ = z.shape
    kind = np.zeros(shape_, np.int8)
    weight = np.zeros(shape_)
    link_id = np.full(shape_, -1, np.int32)
    reach = c["valid"] & (dist <= ZONE_MAX_M)
    linked_ok = reach & (z >= z_s + LINKED_MIN_HEAD_M)

    def offer(mask, k, w, lid=-1):
        better = mask & (w > weight)
        kind[better], weight[better], link_id[better] = k, w, lid

    links = []
    spring_pt = shapely.Point(c["spring_utm"])
    for geom, k, name in c["conduits"]:
        if geom.distance(spring_pt) <= CONDUIT_NEAR_SPRING_M:
            corridor = shapely.distance(c["cell_points"], geom).reshape(shape_) <= CONDUIT_CORRIDOR_M
            links.append({"kind": k, "name": name, "geom": geom})
            offer(linked_ok & corridor, LINK_KINDS.index(k), LINK_WEIGHT[k], len(links) - 1)
    up_sector = None
    if c["up_dip"] is not None:
        off = np.abs((c["bearing"] - c["up_dip"] + 180) % 360 - 180)
        up_sector = off <= DIP_SECTOR_DEG
        unit = c["unit_names"][c["row"], c["col"]]
        same_unit = (c["unit_names"] == unit) if unit else np.ones(shape_, bool)
        offer(linked_ok & up_sector & same_unit, LINK_KINDS.index("Rock layers (up-dip)"), LINK_WEIGHT["Rock layers (up-dip)"])
    slope_w = np.full(shape_, LINK_WEIGHT["Surface slope"])
    if up_sector is not None:
        # with a measured tilt, water soaking in where the layers dip away from the spring mostly leaves its slope
        slope_w = np.where(up_sector, slope_w, slope_w * DOWN_DIP_FACTOR)
    on_slope = reach & c["drains"] & (z >= z_s - BELOW_TOLERANCE_M)
    better = on_slope & (slope_w > weight)
    kind[better], weight[better], link_id[better] = LINK_KINDS.index("Surface slope"), slope_w[better], -1
    return kind, weight, link_id, links


def _rank_zones(c, kind, weight, link_id, min_potential):
    """Greedy search for the best recharge zones: take the best remaining cell (potential x link strength x closeness),
    grow a zone around it among cells with the same link, check the valley in between, set it aside and repeat.
    Returns the zones (dicts with "mask") sorted best first, at most N_ZONES."""
    from scipy.ndimage import binary_dilation
    z, dist, potential = c["z"], c["dist"], c["potential"]
    score = potential * weight * np.exp(-dist / DECAY_M)
    avail = (weight > 0) & ~c["water"] & ~c["stream_block"] & (potential >= min_potential)
    n_target = max(1, math.ceil(max(c["target_mid"], MIN_ZONE_HA) / c["cell_ha"]))
    gap = max(1, round(ZONE_GAP_M / c["cell_m"]))
    found = []
    for _ in range(80):
        if len(found) >= N_ZONES + 2 or not avail.any():
            break
        seed = np.unravel_index(np.argmax(np.where(avail, score, -1.0)), z.shape)
        region = avail & (kind == kind[seed]) & (link_id == link_id[seed])
        cells = _grow(tuple(int(v) for v in seed), region, score, n_target)
        m = np.zeros(z.shape, bool)
        m[tuple(zip(*cells))] = True
        if m.sum() * c["cell_ha"] < MIN_ZONE_HA:
            avail &= ~m
            continue
        k = LINK_KINDS[int(kind[seed])]
        near = np.unravel_index(np.argmin(np.where(m, dist, np.inf)), z.shape)
        valley = 0.0 if k == "Surface slope" else _valley_between(c, near)
        if valley > CUT_VALLEY_M:
            avail &= ~m
            continue
        found.append({"mask": m, "kind": k, "link": int(link_id[seed]), "valley": valley, "distance": float(dist[near]),
                      "score": float(score[m].mean()) * (0.5 if valley > DEEP_VALLEY_M else 1.0)})
        avail &= ~binary_dilation(m, iterations=gap)
    found.sort(key=lambda f: -f["score"])
    return found[:N_ZONES]


def _describe_zone(c, i, f, links):
    m = f["mask"]
    z_s, cell_ha = c["z_s"], c["cell_ha"]
    area = float(m.sum() * cell_ha)
    height = c["z"][m] - z_s
    codes, counts = np.unique(c["land"][m], return_counts=True)
    land_pct = {WORLDCOVER.get(int(code), "No data"): round(100 * n / m.sum()) for code, n in zip(codes, counts) if code}
    units = [u for u in c["unit_names"][m] if u]
    unit = max(set(units), key=units.count) if units else ""
    texture = None
    if c["soil"] is not None and np.isfinite(c["soil"]["clay"][m]).any():
        clay, sand = float(np.nanmean(c["soil"]["clay"][m])), float(np.nanmean(c["soil"]["sand"][m]))
        texture = {"class": soil_class(clay, sand), "clay_pct": round(clay), "sand_pct": round(sand)}
    in_catchment = round(100 * float((m & c["core"]).sum()) / m.sum())
    zid = f"R{i}"
    link = links[f["link"]] if f["link"] >= 0 else None
    link_name = link["name"] if link else ("The slope that drains to the spring" if f["kind"] == "Surface slope"
                                           else "The rock layers tilt down towards the spring")
    link_feature = None
    if link:
        fc = _lines_in_window([link["geom"]], c["to_lonlat"], c["window_utm"], [{"kind": f["kind"], "name": link["name"]}])
        link_feature = fc["features"][0] if fc["features"] else None
    top_land = ", ".join(f"{v}% {k.lower()}" for k, v in sorted(land_pct.items(), key=lambda kv: -kv[1])[:2])
    where = (f"{f['distance']:.0f} m from the spring" if f["distance"] >= 60 else "starting at the spring")
    why = [f"{area:.1f} ha, {where} and on average {height.mean():.0f} m above it",
           LINK_PHRASE[f["kind"]] + (f" ({link['name']})" if link and f["kind"] in ("GSI fault", "Mapped lineament") else ""),
           f"recharge potential {float(c['potential'][m].mean()):.2f}", top_land]
    depth_cm = None
    if c.get("soil_depth") is not None:
        depth_cm = float(np.nanmean(c["soil_depth"][m]))
    if texture:
        why.append(f"{texture['class'].split(' (')[0].lower()} soil" + (f" about {depth_cm:.0f} cm deep" if depth_cm else ""))
    elif depth_cm:
        why.append(f"soil about {depth_cm:.0f} cm deep")
    if f["kind"] != "Surface slope" and in_catchment >= 20:
        why.append(f"{in_catchment}% of it inside the surface catchment")
    if f["valley"] > DEEP_VALLEY_M:
        why.append(f"but a valley about {f['valley']:.0f} m below the spring lies in between and may catch some water first")
    factor_means = {f: float(np.nanmean(v[m])) for f, v in c.get("scores", {}).items()}
    return {
        "id": zid, "rank": i, "area_ha": round(area, 2), "factor_scores": {f: round(v, 2) for f, v in factor_means.items()},
        "geojson": _mask_to_feature(m, c["t"], {"id": zid, "rank": i, "link": f["kind"], "area_ha": round(area, 2)}, c["smooth"]),
        "link": {"kind": f["kind"], "name": link_name, "geojson": link_feature},
        "in_catchment_pct": in_catchment, "distance_m": round(f["distance"]),
        "height_above_spring_m": {"min": round(float(height.min())), "mean": round(float(height.mean())), "max": round(float(height.max()))},
        "mean_potential": round(float(c["potential"][m].mean()), 2), "mean_slope_deg": round(float(c["slope"][m].mean()), 1),
        "land_cover_pct": dict(sorted(land_pct.items(), key=lambda kv: -kv[1])), "soil": texture,
        "soil_depth_cm": None if depth_cm is None else round(depth_cm),
        "rock_unit": unit.capitalize(), "valley_between_m": round(f["valley"]),
        "crosses_fault": bool((c["fault_cells"] & m).any()),
        "score": round(f["score"], 3), "why": "; ".join(w for w in why if w) + ".",
    }


# --------------------------------------------------------------------------- main
def delineate(inputs, session):
    """Module B under the shared contract (docs/module-contract.md): one spring in, one result dict out.

    inputs: {"spring": {name, latitude, longitude, elevation_m}, "field": {monsoon_flow_lpm, lean_flow_lpm,
             dip_direction_deg, dip_angle_deg, ...}}
    session: Module A's LayerSession (its DEM, WorldCover, GSI geology and lineaments are reused).
    The returned dict also holds "_zones": shapely geometries for Module C; drop keys starting with "_" before saving.
    """
    import pyflwdir
    import rasterio.features
    from pyproj import Transformer
    from scipy.ndimage import binary_dilation
    from shapely import STRtree, box, points as shapely_points
    from shapely.geometry import shape

    spring = inputs["spring"]
    field = inputs.get("field") or {}
    lat, lon = float(spring["latitude"]), float(spring["longitude"])
    given_elevation = _number(spring.get("elevation_m"))
    name = spring.get("name") or f"{lat:.5f}, {lon:.5f}"
    mod = session.mod
    session.ensure(lat, lon)
    layers = session.layers
    warnings, rationale, missing = [], [], []

    def unavailable(reason):
        return {"module": "B", "title": "Springshed (recharge area)", "version": "v1 draft", "status": "unavailable",
                "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": given_elevation},
                "result": None, "confidence": "Low", "validation": VALIDATION, "rationale": [reason], "missing_inputs": [], "warnings": warnings,
                "report_markdown": f"# Springshed: {name}\n\n{reason}\n", "_zones": None}

    z, t = mod.read_window(layers.dem, lon, lat, WINDOW_M)
    if z is None:
        return unavailable("No elevation map (DEM) covers this location in the map set, so the springshed could not be drawn.")
    z = z.astype(np.float64)
    z[z <= -1000] = NODATA
    row, col = mod.centre_index(t, lon, lat)
    if not (2 <= row < z.shape[0] - 2 and 2 <= col < z.shape[1] - 2) or z[row, col] == NODATA:
        return unavailable("The elevation map has no value at the spring, so the springshed could not be drawn.")
    m_lat, m_lon = mod.metres_per_degree(lat)
    dx, dy = abs(t.a) * m_lon, abs(t.e) * m_lat
    cell_ha = dx * dy / 1e4
    xs, ys = _grid_coords(z.shape, t)
    dist = np.hypot((xs - lon) * m_lon, (ys - lat) * m_lat)
    bearing = (np.degrees(np.arctan2((xs - lon) * m_lon, (ys - lat) * m_lat)) + 360) % 360
    valid = z != NODATA

    # 1. surface catchment
    flw = pyflwdir.from_dem(z.astype(np.float32), nodata=NODATA, transform=t, latlon=True, outlets="edge")
    upa = flw.upstream_area(unit="km2")
    z_s = float(z[row, col])
    idx = lambda r, c: r * z.shape[1] + c  # noqa: E731
    own = flw.basins(idxs=np.array([idx(row, col)])) > 0
    stream = upa >= STREAM_BARRIER_KM2
    outlets = [idx(r, c) for r in range(row - 1, row + 2) for c in range(col - 1, col + 2)
               if (r, c) == (row, col) or not stream[r, c]]
    core = flw.basins(idxs=np.array(outlets)) > 0
    own_ha, core_ha = float(own.sum() * cell_ha), float(core.sum() * cell_ha)
    valley, snap_cell, snap_km2 = ridge_catchment(flw, upa, z, row, col, dist, idx)
    valley |= core
    valley_ha = float(valley.sum() * cell_ha)
    snap_m = float(dist[snap_cell])
    touches_edge = bool(valley[0, :].any() or valley[-1, :].any() or valley[:, 0].any() or valley[:, -1].any())
    if touches_edge:
        warnings.append(f"The surface catchment reaches the edge of the {WINDOW_M / 1000:.1f} km map window, so it is incomplete: "
                        "the area shown is a lower limit. This often means the point is in a stream channel rather than on a slope, "
                        "so check the coordinate.")
    if own_ha > 0 and core_ha / own_ha >= GPS_SENSITIVE_RATIO:
        warnings.append(f"The catchment depends heavily on the exact GPS point: {own_ha:.1f} ha drains to the map cell at the coordinate, "
                        f"but {core_ha:.1f} ha if the outlet is one cell (30 m) off. Both are drawn. Re-take the GPS at the outlet "
                        "and walk the ridge above it to see which is right.")
    if given_elevation is not None and abs(given_elevation - z_s) > 50:
        warnings.append(f"The elevation given ({given_elevation:.0f} m) differs from the map ({z_s:.0f} m) by {abs(given_elevation - z_s):.0f} m. "
                        "The coordinate may be off; the zone is drawn from the map point.")

    # 2. where water can come from: the slope draining to the spring (with a margin for DEM error), and the
    #    up-dip direction when the rock tilt is known (faults and lineaments are added once the geology is read)
    above = z >= z_s + 5
    cells_per_m = 1 / min(dx, dy)
    ridge = binary_dilation(valley, iterations=max(1, round(RIDGE_MARGIN_M * cells_per_m))) & above
    dip_dir, dip_angle = _number(field.get("dip_direction_deg")), _number(field.get("dip_angle_deg"))
    up_dip = None
    if dip_dir is not None and (dip_angle is None or dip_angle >= MIN_DIP_DEG):
        up_dip = (dip_dir + 180) % 360
        rationale.append(f"The rock layers tilt down towards {dip_dir:.0f} degrees, so water can reach the spring from up-dip "
                         f"(towards {up_dip:.0f} degrees), even beyond the ridge; that direction was searched as well.")
    elif dip_dir is not None:
        rationale.append(f"The rock layers are nearly flat ({dip_angle:g} degrees), so their tilt was not used.")
    dip_source = "field" if dip_dir is not None else None
    secondary = getattr(session, "secondary", None)
    if dip_dir is None and secondary is not None:
        measured = secondary.dip_near(lon, lat, GSI_DIP_RADIUS_M)
        if measured:
            d_m, g_angle, g_dir, g_type = measured[0]
            dip_source = "gsi"
            if g_angle >= MIN_DIP_DEG:
                up_dip = (g_dir + 180) % 360
                rationale.append(f"No field reading of the rock tilt was given, so the nearest GSI measurement was used: "
                                 f"{g_type.lower() or 'bedding'} dipping {g_angle:.0f} degrees towards {g_dir:.0f} degrees, {d_m / 1000:.1f} km away "
                                 f"(GSI Geology 50K). Water may reach the spring from up-dip (towards {up_dip:.0f} degrees); a compass "
                                 "reading at the outlet would confirm it.")
            else:
                rationale.append(f"The nearest GSI measurement ({d_m / 1000:.1f} km away) shows nearly flat layers ({g_angle:.0f} degrees), "
                                 "so the tilt was not used.")

    # 3. recharge potential
    factors = load_factors()
    gy, gx = np.gradient(np.where(valid, z, z_s), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    scores, used = {}, []
    vec_class = np.vectorize(lambda d: factors["slope"]["classes"][slope_class(d)])
    scores["slope"] = vec_class(slope)
    used.append("slope")

    land = np.zeros(z.shape, np.int16)
    ndvi_used = False
    wc, wt = mod.read_window(layers.wc, lon, lat, WINDOW_M + 100) if layers.wc else (None, None)
    if wc is not None:
        rr = np.clip(((ys - wt.f) / wt.e).astype(int), 0, wc.shape[0] - 1)
        cc = np.clip(((xs - wt.c) / wt.a).astype(int), 0, wc.shape[1] - 1)
        land = wc[rr, cc].astype(np.int16)
        lc = factors["land_cover"]["classes"]
        scores["land_cover"] = np.vectorize(lambda code: lc.get(WORLDCOVER.get(int(code), ""), 0.5))(land)
        used.append("land_cover")
        ndvi_src = session.secondary.raster("ndvi") if getattr(session, "secondary", None) else None
        if ndvi_src is not None:
            from secondary_layers import sample_grid
            ndvi = sample_grid(ndvi_src, xs, ys) / 100
            trees = (land == 10) & np.isfinite(ndvi)
            if trees.any():
                for cut, label in NDVI_CLASSES:
                    cells = trees & (ndvi >= cut)
                    scores["land_cover"][cells] = lc[label]
                    trees &= ~cells
                ndvi_used = True
    else:
        warnings.append("No land-cover map covers this location, so land cover was left out of the recharge potential.")

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
    to_lonlat = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True).transform
    ux, uy = to_utm(xs.ravel(), ys.ravel())
    cell_points = shapely_points(ux, uy)
    window_utm = box(ux.min() - 200, uy.min() - 200, ux.max() + 200, uy.max() + 200)
    ngdr = layers.ngdr
    rock = np.full(z.shape, "", dtype=object)
    unit_names = np.full(z.shape, "", dtype=object)
    faults_fc = {"type": "FeatureCollection", "features": []}
    fault_cells = np.zeros(z.shape, bool)
    struct_lines = []
    conduits = []  # (UTM line, kind, name): faults and lineaments that may carry water to the spring
    geology = None
    if getattr(ngdr, "ok", False):
        hits = ngdr.unit_tree.query(window_utm, predicate="intersects")
        import shapely
        for i in hits:
            geom, props = ngdr.units[i]
            inside = shapely.contains_xy(geom, ux, uy).reshape(z.shape) & (rock == "")
            if inside.any():
                text = ngdr._clean(props.get("lithologic")).rstrip(".")
                classes = rock_classes(text)
                rock[inside] = classes[0] if len(classes) == 1 else f"Mixed ({', '.join(classes)})"
                unit_names[inside] = text.capitalize() or "Unnamed unit"
        fault_ids = list(ngdr.fault_tree.query(window_utm.buffer(600)))
        fault_geoms = [ngdr.faults[i][0] for i in fault_ids]
        fault_props = [{"name": ngdr._clean(ngdr.faults[i][1].get("fault_name")) or "Unnamed fault",
                        "type": ngdr._clean(ngdr.faults[i][1].get("fault_type")) or "Fault"} for i in fault_ids]
        faults_fc = _lines_in_window(fault_geoms, to_lonlat, window_utm, fault_props)
        if faults_fc["features"]:
            fault_cells = rasterio.features.rasterize([(f["geometry"], 1) for f in faults_fc["features"]], out_shape=z.shape,
                                                      transform=t, all_touched=True, dtype="uint8").astype(bool)
        struct_lines += fault_geoms
        conduits += [(g, "GSI fault", f"{p['name']} ({p['type'].lower()})" if p["name"] != "Unnamed fault" else p["type"].capitalize())
                     for g, p in zip(fault_geoms, fault_props)]
    if (rock != "").sum() > 0.5 * rock.size:
        rk = factors["rock"]["classes"]

        def rock_score(label):  # a mixed unit scores the mean of its rocks
            names = label[7:-1].split(", ") if label.startswith("Mixed (") else [label]
            return statistics.fmean(rk.get(n, rk.get("Other", 0.5)) for n in names)
        scores["rock"] = np.vectorize(rock_score)(np.where(rock == "", "Other", rock))
        used.append("rock")
        spring_rock = rock[row, col] or "Other"
        nearest = None
        if getattr(ngdr, "ok", False):
            f = ngdr.features(lon, lat)
            nearest = f.get("distance_to_gsi_fault_m")
            geology = {"rock_class": spring_rock, "unit": unit_names[row, col] or f.get("gsi_lithology", ""),
                       "nearest_fault_m": None if nearest is None else round(float(nearest)),
                       "nearest_fault_name": f.get("gsi_nearest_fault_name") or f.get("gsi_nearest_fault_type") or ""}
    else:
        warnings.append("This location is outside the GSI geology map used here (Uttarakhand only), so rock type and mapped faults "
                        "were left out. Record the rock at the outlet and the tilt of the layers in the field.")

    lineaments_fc = {"type": "FeatureCollection", "features": []}
    local = layers.local
    if getattr(local, "lines", None) is not None:
        line_ids = list(local.tree.query(window_utm.buffer(600)))
        line_geoms = [local.lines[i] for i in line_ids]
        lineaments_fc = _lines_in_window(line_geoms, to_lonlat, window_utm, [{"type": "DEM lineament (candidate)"}] * len(line_geoms))
        struct_lines += line_geoms
        conduits += [(g, "DEM lineament", "Lineament (straight line on the elevation map, possibly a crack)") for g in line_geoms]
    mapped_fc = {"type": "FeatureCollection", "features": []}
    if getattr(session, "secondary", None) is not None:
        mapped = session.secondary.lineaments_in(window_utm.buffer(600))
        if mapped:
            mapped_fc = _lines_in_window([g for g, _ in mapped], to_lonlat, window_utm,
                                         [{"type": f"Mapped lineament: {k.lower() or 'unspecified'} (GSI 1:250k)"} for _, k in mapped])
            struct_lines += [g for g, _ in mapped]
            conduits += [(g, "Mapped lineament", f"GSI mapped lineament ({k.lower() or 'unspecified'})") for g, k in mapped]
    if struct_lines:
        tree = STRtree(struct_lines)
        _, near = tree.query_nearest(cell_points, return_distance=True, all_matches=False)
        struct_dist = near.reshape(z.shape)
        st = factors["structure"]["classes"]
        scores["structure"] = np.vectorize(lambda d: st[structure_class(d)])(struct_dist)
        used.append("structure")
    else:
        struct_dist = np.full(z.shape, np.inf)
        warnings.append("No faults or lineaments were found near this spring, so fractures were left out of the recharge potential.")

    soil = soil_layers(local, xs, ys) if "soil" in factors else None
    if soil is not None:
        sc = factors["soil"]["classes"]
        bonus = next((v for k, v in sc.items() if k.startswith("Stony")), 0.0)
        base = np.vectorize(lambda c, sa: sc[soil_class(c, sa)] if np.isfinite(c) and np.isfinite(sa) else np.nan)(soil["clay"], soil["sand"])
        base = np.where(np.isfinite(base), base, np.nanmean(base))  # cells without soil data take the window mean
        scores["soil"] = np.clip(base + np.where(np.nan_to_num(soil["coarse"]) >= 35, bonus, 0.0), 0, 1)
        used.append("soil")
    elif "soil" in factors:
        warnings.append("No SoilGrids layers were found (DOCC\\Data\\SoilGrids), so soil was left out of the recharge potential.")

    depth_src = session.secondary.raster("depth") if getattr(session, "secondary", None) else None
    soil_depth = None
    if "soil_depth" in factors and depth_src is not None:
        from secondary_layers import sample_grid
        soil_depth = sample_grid(depth_src, xs, ys)
        if np.isfinite(soil_depth).any():
            soil_depth = np.where(np.isfinite(soil_depth), soil_depth, np.nanmean(soil_depth))
            sd = factors["soil_depth"]["classes"]
            scores["soil_depth"] = np.vectorize(lambda cm: sd[depth_class(cm)])(soil_depth)
            used.append("soil_depth")
        else:
            soil_depth = None
    if "soil_depth" in factors and soil_depth is None:
        warnings.append("No soil-depth map covers this location (SoilGrids BDRICM in DOCC\\Data\\Secondary data\\SoilGrids), so soil depth "
                        "was left out of the recharge potential.")

    total_weight = sum(factors[f]["weight"] for f in used)
    potential = sum(scores[f] * factors[f]["weight"] for f in used) / total_weight
    water = land == 80

    # 4. size: how much recharge area this flow needs
    target = target_area(field)
    near_spring = dist <= NEAR_SPRING_M
    streams_block = field.get("streams_block_zones") not in (False, "false", "no", "0", 0)
    stream_block = stream & ~near_spring if streams_block else np.zeros(z.shape, bool)
    smooth = abs(t.a) * 0.6

    # 5. the top recharge zones, wherever they are: on the spring's own slope or beyond it along a link
    ctx = {"z": z, "t": t, "dist": dist, "bearing": bearing, "valid": valid, "water": water, "potential": potential,
           "row": row, "col": col, "z_s": z_s, "conduits": conduits, "cell_points": cell_points, "spring_utm": to_utm(lon, lat),
           "up_dip": up_dip, "unit_names": unit_names, "drains": valley | ridge, "core": valley, "stream_block": stream_block,
           "target_mid": target["mid"], "cell_ha": cell_ha, "cell_m": min(dx, dy), "land": land, "soil": soil,
           "slope": slope, "fault_cells": fault_cells, "smooth": smooth, "to_lonlat": to_lonlat, "window_utm": window_utm,
           "soil_depth": soil_depth, "scores": scores}
    kind, weight, link_id, links = link_map(ctx)
    found = _rank_zones(ctx, kind, weight, link_id, MIN_ZONE_POTENTIAL)
    if not found:
        found = _rank_zones(ctx, kind, weight, link_id, FALLBACK_POTENTIAL)
        if found:
            warnings.append(f"No ground linked to the spring reaches a recharge potential of {MIN_ZONE_POTENTIAL}, so weaker ground "
                            f"(from {FALLBACK_POTENTIAL}) was used. Recharge works here will need more care (pits, trenches, planting).")
    zones = [_describe_zone(ctx, i, f, links) for i, f in enumerate(found, start=1)]
    zones = [zn for zn in zones if zn["geojson"]]
    if not zones:
        warnings.append("No recharge zone could be found: no ground above the spring and linked to it scored well enough for recharge.")
    catchment_feature = _mask_to_feature(valley, t, {"area_ha": round(valley_ha, 2)}, smooth)
    outlet_feature = _mask_to_feature(core, t, {"area_ha": round(core_ha, 2)}, smooth)
    own_feature = _mask_to_feature(own, t, {"area_ha": round(own_ha, 2)}, smooth) if own.any() else None
    catchment_geom = shape(catchment_feature["geometry"]) if catchment_feature else None

    # recharge-potential picture for the map: only ground that can send water to the spring
    show = (weight > 0) & ~water
    level = np.clip((potential * len(LEGEND)).astype(int), 0, len(LEGEND) - 1)
    rgba = np.zeros(z.shape + (4,), np.uint8)
    for i, (_, color) in enumerate(LEGEND):
        rgba[show & (level == i)] = color
    south, north = t.f + z.shape[0] * t.e, t.f
    west, east = t.c, t.c + z.shape[1] * t.a
    overlay = {"image": _png(rgba), "bounds": [[south, west], [north, east]],
               "legend": [{"label": label, "color": "#%02x%02x%02x" % color[:3]} for label, color in LEGEND]}

    streams_fc = {"type": "FeatureCollection", "features": []}
    try:
        feats = flw.streams(mask=upa >= STREAM_DISPLAY_KM2)
        streams_fc["features"] = [{"type": "Feature", "geometry": f["geometry"],
                                   "properties": {"order": int(f["properties"].get("strord", 1) or 1)}} for f in feats]
    except Exception as error:  # streams are display only
        warnings.append(f"Streams could not be drawn: {error}")

    # words
    n_links = len(links) + (1 if up_dip is not None else 0)
    searched = (f"Searched all ground within {ZONE_MAX_M / 1000:.0f} km that can send water to the spring: the slope that drains to it "
                f"(its surface catchment), and ground at least {LINKED_MIN_HEAD_M} m higher beyond it along "
                f"{len(links)} fault{'s' if len(links) != 1 else ''} or lineament{'s' if len(links) != 1 else ''} passing within "
                f"{CONDUIT_NEAR_SPRING_M} m of the spring" + (" and in the up-dip direction of the rock layers" if up_dip is not None else "") + ".")
    rationale[:0] = [
        f"The catchment, drawn the way geologists draw it, is the whole valley above the spring up to the surrounding ridges: "
        f"{valley_ha:.1f} ha" + (" or more" if touches_edge else "") + ". "
        + (f"It follows the drainage line {snap_m:.0f} m from the spring, which drains {snap_km2 * 100:.0f} ha in all. " if snap_m >= 15 else "")
        + f"Only {core_ha:.1f} ha runs off straight to the outlet itself ({own_ha:.1f} ha to the exact map cell). "
        "Rain soaking in anywhere in the valley can feed the spring, but the rocks decide the real recharge area.",
        f"This flow needs about {target['mid']:.1f} ha of recharge area (range {target['low']:.1f}-{target['high']:.1f} ha). " + target["basis"]
        + " Each zone is grown to about this size, so its area matching it is by design, not a check that the zone is right.",
        searched + " Each patch was scored on recharge potential (" + ", ".join(factors[f]["name"].lower() for f in used)
        + "), how strong its link to the spring is, and how close it is. The best three are R1-R3, wherever they lie.",
    ]
    if zones:
        rationale.append(f"R1, the best place to recharge this spring: {zones[0]['why'][0].lower()}{zones[0]['why'][1:]}")
        on_slope = sum(1 for zn in zones if zn["link"]["kind"] == "Surface slope")
        if on_slope == len(zones):
            rationale.append("All the top zones are on the spring's own slope, inside or at the edge of its surface catchment.")
        elif on_slope == 0:
            rationale.append("None of the top zones is on the spring's own slope: the ground there scores lower than ground linked to "
                             "the spring by a fault, crack or the rock tilt. Check those links in the field before relying on them.")
        else:
            rationale.append(f"{on_slope} of the top zones {'is' if on_slope == 1 else 'are'} on the spring's own slope; the other"
                             f"{'s lie' if len(zones) - on_slope > 1 else ' lies'} beyond it, linked by a fault, crack or the rock tilt.")
    if not streams_block:
        rationale.append("Streams were not treated as barriers (your choice): zones may cross a stream channel.")
    if valley_ha < target["mid"]:
        rationale.append(f"The catchment ({valley_ha:.1f} ha) is smaller than the {target['mid']:.1f} ha this flow needs, so part of "
                         "the water probably soaks in beyond the ridge.")
    if target["kind"] == "default":
        missing.append({"id": "monsoon_flow_lpm", "indicator": "Monsoon flow", "needs": "One bucket reading in the monsoon sizes the zones for this spring."})
    elif target["kind"] == "lean flow":
        missing.append({"id": "monsoon_flow_lpm", "indicator": "Monsoon flow", "needs": "A monsoon reading sizes the zones better than the lean-season flow."})
    if dip_dir is None:
        missing.append({"id": "dip_direction_deg", "indicator": "Rock tilt (dip direction and angle)",
                        "needs": "A compass reading of the rock layers near the outlet shows whether water comes from beyond the ridge."
                                 + (" The GSI measurement used instead is up to 2 km away." if dip_source == "gsi" else "")})
    missing.append({"id": "field_walk", "indicator": "Field check", "needs": "Walk the zones with a geologist before spending money on works."})
    confidence = "Medium" if target["kind"] == "monsoon flow" and dip_dir is not None and "rock" in used else "Low"
    linked = any(zn["link"]["kind"] != "Surface slope" for zn in zones)

    result = {
        "spring_cell": {"latitude": round(float(ys[row, col]), 6), "longitude": round(float(xs[row, col]), 6), "elevation_m": round(z_s),
                        "moved_m": 0, "note": "The 30 m map cell at the given coordinate."},
        "surface_catchment": {"area_ha": round(valley_ha, 2), "geojson": catchment_feature,
                              "note": "The whole valley above the spring up to the ridges, as the SRHU geologists draw it: the basin of the "
                                      f"drainage line within {SNAP_M} m of the spring (not a river), on ground no lower than the spring.",
                              "snapped_m": round(snap_m), "snapped_drainage_ha": round(snap_km2 * 100, 1)},
        "outlet_catchment": {"area_ha": round(core_ha, 2), "geojson": outlet_feature,
                             "note": "Land running off straight to the outlet, allowing 30 m of GPS and map error (the spring cell or any of its 8 neighbours)."},
        "exact_cell_catchment": {"area_ha": round(own_ha, 2), "geojson": own_feature,
                                 "note": "The land draining to the map cell at the exact coordinate."},
        "target_area_ha": {"low": target["low"], "mid": target["mid"], "high": target["high"], "basis": target["basis"],
                           "kind": target["kind"]},
        "streams_block_zones": streams_block,
        "recharge_zones": zones,
        "search": {"searched": searched, "links": n_links, "checks": ZONE_CHECKS + (LINKED_CHECKS if linked else [])},
        "potential_overlay": overlay,
        "factors": [{"id": f, "name": factors[f]["name"], "weight_pct": round(100 * factors[f]["weight"] / total_weight),
                     "how": factors[f]["why"]} for f in used],
        "geology": geology,
        "faults": faults_fc,
        "lineaments": lineaments_fc,
        "mapped_lineaments": mapped_fc,
        "streams": streams_fc,
    }
    if ndvi_used:
        rationale.append("Forest density from Sentinel-2 (Tehri district) was used: dense forest scores higher than open or sparse tree cover.")
    summary = plain_summary(result)
    output = {
        "module": "B", "title": "Springshed (recharge area)", "version": "v1 draft", "summary": summary,
        "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": given_elevation if given_elevation is not None else round(z_s)},
        "status": "provisional", "result": result, "confidence": confidence, "validation": VALIDATION,
        "rationale": rationale, "missing_inputs": missing, "warnings": warnings,
        "report_markdown": report_markdown(name, lat, lon, result, summary + rationale, warnings),
        "_zones": {"zones": [{"id": zn["id"], "kind": zn["link"]["kind"], "geom": shape(zn["geojson"]["geometry"])} for zn in zones],
                   "catchment": catchment_geom, "dem": (z, t), "spring_elevation_m": z_s},
        # the grids behind the result, for the detailed report's maps (scripts/report_builder.py)
        "_report": {"z": z, "t": t, "xs": xs, "ys": ys, "slope": slope, "catchment": valley, "land": land if wc is not None else None,
                    "soil": soil, "soil_depth": soil_depth, "unit_names": unit_names, "potential": potential, "show": show,
                    "used": used, "factors": factors, "row": row, "col": col, "m_lat": m_lat, "m_lon": m_lon, "cell_ha": cell_ha},
    }
    return output


STRENGTH = {"slope": ("gentle slopes", "steep slopes"), "land_cover": ("forest or other natural cover", "built-up, farmed or bare land"),
            "rock": ("rock that lets water through", "tight rock that passes little water"),
            "structure": ("cracks or faults close by", "no mapped cracks close by"),
            "soil": ("soil that soaks water in fast", "clayey soil that soaks water in slowly"),
            "soil_depth": ("deep soil that can hold water", "thin soil")}


def _zone_words(zn):
    """Why a zone is good (and its weak points) in everyday words."""
    good = [STRENGTH[f][0] for f, v in sorted(zn.get("factor_scores", {}).items(), key=lambda kv: -kv[1]) if v >= 0.75 and f in STRENGTH]
    weak = [STRENGTH[f][1] for f, v in sorted(zn.get("factor_scores", {}).items(), key=lambda kv: kv[1]) if v <= 0.4 and f in STRENGTH]
    return good[:3], weak[:2]


def plain_summary(result):
    """A few sentences in everyday words: what the catchment is, how much recharge area the spring needs, and why R1-R3."""
    sc, target, zones = result["surface_catchment"], result["target_area_ha"], result["recharge_zones"]
    lines = [f"The catchment of this spring is the valley above it, up to the surrounding ridges: about {sc['area_ha']:.1f} ha. "
             "Rain falling here runs or seeps towards the spring."]
    if target["kind"] == "default":
        lines.append(f"Without a flow reading, a typical hill-spring recharge area of about {target['mid']:.0f} ha is assumed.")
    else:
        lines.append(f"For the flow it gives, the spring needs roughly {target['mid']:.1f} ha of land where water soaks in "
                     "(its recharge area). This can be inside the valley, or beyond the ridge if the rock carries water across.")
    for zn in zones:
        good, weak = _zone_words(zn)
        where = "on the spring's own slope" if zn["link"]["kind"] == "Surface slope" else LINK_PHRASE[zn["link"]["kind"]].replace("linked to the spring by", "connected through")
        text = (f"{zn['id']} ({zn['area_ha']:.1f} ha, about {zn['height_above_spring_m']['mean']} m above the spring, {where})"
                + (" was picked because it has " + (good[0] if len(good) == 1 else ", ".join(good[:-1]) + " and " + good[-1]) if good else " is the best of the remaining ground"))
        if weak:
            text += "; its weak point" + ("s are " if len(weak) > 1 else " is ") + " and ".join(weak)
        lines.append(text + ".")
    if not zones:
        lines.append("No ground above the spring scored well enough to suggest a recharge zone.")
    return lines


def report_markdown(name, lat, lon, result, rationale, warnings):
    lines = [f"# Springshed and recharge zones: {name}", "",
             f"Location {lat:.5f}, {lon:.5f}; map elevation {result['spring_cell']['elevation_m']} m.", "",
             f"Catchment to the ridge: {result['surface_catchment']['area_ha']:.1f} ha "
             f"({result['outlet_catchment']['area_ha']:.1f} ha runs off straight to the outlet, {result['exact_cell_catchment']['area_ha']:.1f} ha to the exact map cell). "
             f"Recharge area this flow needs: about {result['target_area_ha']['mid']:.1f} ha"
             + (" (a default: no flow reading was given)" if result["target_area_ha"]["kind"] == "default" else "") + ".", "",
             f"*{VALIDATION}*", ""]
    if result["recharge_zones"]:
        lines += ["## Top candidate recharge zones (places to inspect)", *(f"- {zn['id']}: {zn['why']}" for zn in result["recharge_zones"]), ""]
    lines += ["## Why", *(f"- {r}" for r in rationale), "", "## Field checks", *(f"- {c}" for c in result["search"]["checks"]), ""]
    if warnings:
        lines += ["## Notes", *(f"- {w}" for w in warnings), ""]
    lines += ["A first estimate from maps (Module B v1 draft). Walk the zones with a geologist before spending money on works."]
    return "\n".join(lines)


def public(output):
    """The output without the in-memory geometries (safe to turn into JSON)."""
    return {k: v for k, v in output.items() if not k.startswith("_")}


def main():
    import module_a_vulnerability as module_a
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--elevation", type=float)
    parser.add_argument("--name")
    parser.add_argument("--monsoon-flow-lpm", type=float)
    parser.add_argument("--lean-flow-lpm", type=float)
    parser.add_argument("--dip-direction", type=float)
    parser.add_argument("--dip-angle", type=float)
    parser.add_argument("--geojson", help="write the recharge zones and catchment to this GeoJSON file")
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    parser.add_argument("--local-layers", default=os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers")))
    args = parser.parse_args()
    session = module_a.LayerSession(args.cache, args.local_layers)
    field = {"monsoon_flow_lpm": args.monsoon_flow_lpm, "lean_flow_lpm": args.lean_flow_lpm,
             "dip_direction_deg": args.dip_direction, "dip_angle_deg": args.dip_angle}
    output = delineate({"spring": {"name": args.name, "latitude": args.lat, "longitude": args.lon, "elevation_m": args.elevation},
                        "field": field}, session)
    print(output["report_markdown"])
    if args.geojson and output["result"]:
        r = output["result"]
        features = [zn["geojson"] for zn in r["recharge_zones"]] + ([r["surface_catchment"]["geojson"]] if r["surface_catchment"]["geojson"] else [])
        Path(args.geojson).write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        print(f"Saved {args.geojson}")


if __name__ == "__main__":
    main()
