"""Modules B and C and the tool server. Tests that need the elevation map skip when its tile is not in the layer cache."""

import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import module_b_springshed as module_b  # noqa: E402
import module_c_di_impact as module_c  # noqa: E402
import spring_tool_server as server  # noqa: E402

NAULI = {"name": "Nauli Dhara", "latitude": 29.91903, "longitude": 78.55647, "elevation_m": 1481}
CACHE = Path(os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
HAS_DEM = (CACHE / "dem" / "Copernicus_DSM_COG_10_N29_00_E078_00_DEM.tif").is_file()


def test_rathi_fit_uses_all_35_springsheds():
    fit = module_b.rathi_fit()
    assert fit["n"] == 35
    assert 0.5 < fit["b"] < 0.9  # area grows more slowly than flow


def test_target_area_from_flow_readings():
    default = module_b.target_area({})
    assert (default["low"], default["mid"], default["high"]) == module_b.DEFAULT_AREA_HA
    small, big = module_b.target_area({"monsoon_flow_lpm": 10}), module_b.target_area({"monsoon_flow_lpm": 60})
    assert small["low"] < small["mid"] < small["high"] and small["mid"] < big["mid"]
    lean = module_b.target_area({"lean_flow_lpm": 3})
    assert lean["kind"] == "lean flow" and lean["high"] / lean["mid"] > small["high"] / small["mid"]  # wider when guessed


def test_factor_weights_sum_to_100():
    factors = module_b.load_factors()
    assert set(factors) == {"slope", "land_cover", "rock", "structure", "soil", "soil_depth"}
    assert sum(f["weight"] for f in factors.values()) == 100
    assert all(0 <= s <= 1 for f in factors.values() for s in f["classes"].values())


def test_soil_classes():
    assert module_b.soil_class(5, 80).startswith("Sandy (")
    assert module_b.soil_class(15, 60).startswith("Sandy loam")
    assert module_b.soil_class(24, 35).startswith("Loam")
    assert module_b.soil_class(30, 30).startswith("Clay loam")
    assert module_b.soil_class(45, 20).startswith("Clay (")
    classes = module_b.load_factors()["soil"]["classes"]
    assert all(module_b.soil_class(c, s) in classes for c, s in ((5, 80), (15, 60), (24, 35), (30, 30), (45, 20)))


def test_soilgrids_folder_layouts(tmp_path):
    import build_spring_features as layers_mod
    (tmp_path / "0-5 soilgrids").mkdir()
    (tmp_path / "0-5 soilgrids" / "Slit.tif").write_bytes(b"")
    (tmp_path / "clay_5-15cm_mean.tif").write_bytes(b"")
    assert layers_mod.soilgrids_file(tmp_path, "silt_0-5cm_mean").name == "Slit.tif"
    assert layers_mod.soilgrids_file(tmp_path, "clay_5-15cm_mean").name == "clay_5-15cm_mean.tif"
    assert layers_mod.soilgrids_file(tmp_path, "sand_0-5cm_mean") is None


def test_terrain_tile_encoding_round_trips():
    import struct
    import zlib
    heights = np.array([[0.0, 1481.25], [-20.5, 4000.0]], np.float32)
    png = server.Terrain._png(heights)
    data, i = b"", 8
    while i < len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        if png[i + 4:i + 8] == b"IDAT":
            data += png[i + 8:i + 8 + n]
        i += 12 + n
    rgb = np.frombuffer(zlib.decompress(data), np.uint8).reshape(2, 7)[:, 1:].reshape(2, 2, 3).astype(float)
    decoded = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
    assert np.allclose(decoded, heights, atol=0.01)


@pytest.mark.skipif(not HAS_DEM, reason="Copernicus DEM tile for Nauli Dhara not in the layer cache")
def test_terrain_has_no_sea_level_wall_at_the_edge_of_the_local_dem(tmp_path, monkeypatch):
    """Offline, a map tile half outside the local DEM takes the nearest local height, not 0 m (a wall in 3D)."""
    import shutil
    (tmp_path / "dem").mkdir()
    shutil.copy(CACHE / "dem" / "Copernicus_DSM_COG_10_N29_00_E078_00_DEM.tif", tmp_path / "dem")
    terrain = server.Terrain(tmp_path)
    monkeypatch.setattr(terrain, "_web", lambda z, x, y: None)  # no internet
    z = 10
    n = 2 ** z
    x, y = int((79.0 + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(29.5))) / math.pi) / 2 * n)  # spans 79 E
    heights, covered = terrain._heights(z, x, y)
    assert 0 < covered.mean() < 1
    filled = terrain._fill(z, x, y, heights, covered)
    assert filled.min() > 100 and np.array_equal(filled[covered], heights[covered])
    far = terrain._fill(z, 10, 10, np.zeros((256, 256), np.float32), np.zeros((256, 256), bool))
    assert far.min() > 100  # nothing local or public: the median local height, not sea level


def _two_valley_context(slope_potential, far_potential):
    """A spring on a slope facing west; its own catchment rises east to a ridge at col 50, then a saddle, then higher
    ground in the next valley. A fault runs from the spring east, over the ridge, into that higher ground."""
    from affine import Affine
    from shapely.geometry import LineString, box
    from shapely import points
    n, cell = 80, 30.0
    t = Affine(cell, 0, 0, 0, -cell, n * cell)
    rows, cols = np.indices((n, n))
    xs, ys = t.c + (cols + 0.5) * cell, t.f - (rows + 0.5) * cell
    row = col = 40
    sx, sy = xs[row, col], ys[row, col]
    z = (1000 + np.where(cols <= 50, (cols - 40) * 6.0, 60 - (cols - 50) * 1.0 + np.clip(cols - 56, 0, None) * 5.0)).astype(float)
    core = (cols >= 38) & (cols <= 50) & (np.abs(rows - row) <= 8)
    potential = np.where(core, slope_potential, far_potential)
    fault = LineString([(sx, sy), (sx + 2400, sy)])
    zeros = np.zeros(z.shape, bool)
    return {"z": z, "t": t, "dist": np.hypot(xs - sx, ys - sy), "bearing": np.zeros_like(z), "valid": ~zeros, "water": zeros,
            "potential": potential, "row": row, "col": col, "z_s": 1000.0,
            "conduits": [(fault, "GSI fault", "Test thrust (thrust)")], "cell_points": points(xs.ravel(), ys.ravel()),
            "spring_utm": (sx, sy), "up_dip": None, "unit_names": np.full(z.shape, "", dtype=object), "drains": core, "core": core,
            "stream_block": zeros, "target_mid": 2.0, "cell_ha": cell * cell / 1e4, "cell_m": cell, "land": np.full(z.shape, 10),
            "soil": None, "slope": np.full(z.shape, 10.0), "fault_cells": zeros, "smooth": 10.0,
            "to_lonlat": lambda x, y: (x, y), "window_utm": box(0, 0, n * cell, n * cell)}


def _zones(ctx):
    kind, weight, link_id, links = module_b.link_map(ctx)
    found = module_b._rank_zones(ctx, kind, weight, link_id, module_b.MIN_ZONE_POTENTIAL)
    return [module_b._describe_zone(ctx, i, f, links) for i, f in enumerate(found, start=1)], found


def test_top_zones_come_from_one_ranking_wherever_they_are():
    # good ground on the spring's own slope wins: all three zones lie there, nothing is forced beyond the ridge
    zones, found = _zones(_two_valley_context(slope_potential=0.8, far_potential=0.6))
    assert [z["id"] for z in zones] == ["R1", "R2", "R3"]
    assert zones[0]["link"]["kind"] == "Surface slope"
    assert all(module_b.MIN_ZONE_HA <= z["area_ha"] <= 2.5 for z in zones)
    assert not any((a["mask"] & b["mask"]).any() for i, a in enumerate(found) for b in found[i + 1:])
    # poor ground on the slope, good ground across the ridge on the fault: the best zone is the far one
    ctx = _two_valley_context(slope_potential=0.52, far_potential=0.9)
    zones, found = _zones(ctx)
    assert zones[0]["link"]["kind"] == "GSI fault" and zones[0]["height_above_spring_m"]["min"] >= module_b.LINKED_MIN_HEAD_M
    assert not (found[0]["mask"] & ctx["core"]).any()
    # with no fault near the spring, ground beyond the ridge is not linked, so every zone is on the spring's slope
    from shapely.geometry import LineString
    sx, sy = ctx["spring_utm"]
    ctx["conduits"] = [(LineString([(sx, sy + 900), (sx + 2400, sy + 900)]), "GSI fault", "Far fault")]
    zones, _ = _zones(ctx)
    assert zones and all(z["link"]["kind"] == "Surface slope" for z in zones)


def test_di_site_share_follows_the_zone_link():
    near, far = Point(78.556, 29.92).buffer(0.001), Point(78.57, 29.93).buffer(0.002)
    b = {"result": {"geology": None}, "_zones": {"zones": [{"id": "R1", "kind": "Surface slope", "geom": near},
                                                          {"id": "R2", "kind": "DEM lineament", "geom": far}],
                                                "catchment": None, "dem": None, "spring_elevation_m": None}}
    sites = [{"id": "a", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100, "first_flush": True, "filter": True},
             {"id": "b", "latitude": 29.93, "longitude": 78.57, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    out = module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}}, b_output=b)
    a, c = out["result"]["sites"]
    assert a["location_class"] == "in_zone_slope" and a["zone_id"] == "R1" and "R1" in a["location_note"]
    assert c["location_class"] == "in_zone_crack" and c["share_reaching_spring"] == {"low": 0.05, "mid": 0.2, "high": 0.5}


def test_png_writer_round_trips():
    import base64
    import io
    Image = pytest.importorskip("PIL.Image")
    rgba = np.zeros((4, 6, 4), np.uint8)
    rgba[1, 2] = (10, 20, 30, 40)
    image = Image.open(io.BytesIO(base64.b64decode(module_b._png(rgba).split(",", 1)[1])))
    assert image.size == (6, 4) and (np.array(image) == rgba).all()


def test_di_arithmetic_without_a_zone():
    out = module_c.estimate({"spring": NAULI, "field": {"lean_flow_lpm": 2},
                             "di": {"sites": [{"id": "a", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100,
                                               "first_flush": False, "filter": True}],
                                    "assumptions": {"annual_rain_mm": 1600}}})
    site = out["result"]["sites"][0]
    assert site["volume_m3_per_year"] == pytest.approx(100 * 1.6 * 0.8 * 0.85, abs=0.1)
    assert site["location_class"] == "outside"
    assert any("first-flush" in f for f in site["flags"])
    assert out["result"]["roofs_for_10pct"] >= 1
    assert out["result"]["rain"]["source"] == "entered by the user"


def test_di_site_on_the_slope_counts_more_than_a_linked_one():
    square = lambda d: Point(78.556, 29.92).buffer(d)  # noqa: E731
    b = {"result": {"geology": {"rock_class": "Quartzite"}},
         "_zones": {"zones": [{"id": "R1", "kind": "Surface slope", "geom": square(0.001)},
                              {"id": "R2", "kind": "GSI fault", "geom": square(0.002).difference(square(0.001))}],
                    "catchment": square(0.003), "dem": None, "spring_elevation_m": None}}
    sites = [{"id": "in", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100, "first_flush": True, "filter": True},
             {"id": "wide", "latitude": 29.9215, "longitude": 78.556, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    out = module_c.estimate({"spring": NAULI, "field": {"lean_flow_lpm": 2}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}},
                            b_output=b)
    inside, wide = out["result"]["sites"]
    assert inside["location_class"] == "in_zone_slope" and wide["location_class"] == "in_zone_linked"
    assert inside["added_flow_lpm_lean"]["mid"] > wide["added_flow_lpm_lean"]["mid"] > 0
    lean_minutes = 5 * module_c.DAYS_PER_MONTH * 1440
    assert inside["added_flow_lpm_lean"]["mid"] == pytest.approx(108.8 * 0.6 * 1000 / lean_minutes, abs=0.001)
    assert out["result"]["totals"]["pct_of_lean_flow"]["mid"] > 0


def test_di_plan_is_not_ready_without_safeguards():
    sites = [{"id": "a", "name": "School", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100, "first_flush": False, "filter": True},
             {"id": "b", "name": "Temple", "latitude": 29.921, "longitude": 78.556, "roof_area_m2": 80, "first_flush": True, "filter": True}]
    out = module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}})
    safety = out["result"]["safety"]
    assert not safety["ready"]
    assert any(a.startswith("Fit a first-flush diverter at School") for a in safety["actions"])
    assert out["rationale"][0].startswith("Not ready for DI yet")
    assert any("gain is zero" in r for r in out["rationale"])  # the no-connection case is always stated
    assert out["validation"].startswith("Not yet validated")
    site = out["result"]["sites"][0]
    assert site["volume_m3_per_year"] == pytest.approx(site["runoff_m3_per_year"] * 0.85, abs=0.1)
    sites[0]["first_flush"] = True
    assert module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}})["result"]["safety"]["ready"]


def _code_value(ref):
    """'module_c_di_impact:SHARE[in_zone_slope]' -> the value in the code."""
    module_name, path = ref.split(":")
    module = {"module_b_springshed": module_b, "module_c_di_impact": module_c}.get(module_name)
    if module is None:
        import module_a_vulnerability as module
    name, *keys = re.findall(r"[^\[\]]+", path)
    value = getattr(module, name)
    for key in keys:
        value = value[key]
    return value


def test_assumption_register_matches_the_code():
    import csv
    rows = list(csv.DictReader((ROOT / "config" / "assumption_register_v1.csv").open(encoding="utf-8")))
    assert len({r["rule_id"] for r in rows}) == len(rows)
    assert {r["status"] for r in rows} <= {"sourced", "fitted", "assumption", "user setting"}
    checked = 0
    for r in rows:
        if not r["code_ref"] or r["status"] == "fitted":
            continue
        value = _code_value(r["code_ref"])
        if isinstance(value, dict):  # e.g. LINK_WEIGHT: compare the values in order
            value = list(value.values())
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        listed = [float(v) for v in r["value"].split("|")]
        if r["rule_id"] == "B-20":  # main threshold and its fallback
            values = [module_b.MIN_ZONE_POTENTIAL, module_b.FALLBACK_POTENTIAL]
        assert [float(v) for v in values] == pytest.approx(listed), r["rule_id"]
        checked += 1
    assert checked >= 35


def test_bad_assumption_is_ignored_with_a_warning():
    out = module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": [], "assumptions": {"annual_rain_mm": 1600,
                                                                                                "collection_coefficient": 7}}})
    assert any("collection_coefficient" in w for w in out["warnings"])
    assert out["result"]["assumptions"][1]["value"] == 0.8


def test_request_checks():
    with pytest.raises(ValueError):
        server.clean_request({"spring": {"latitude": 12.9, "longitude": 77.6}})  # outside the hills covered
    with pytest.raises(ValueError):
        server.clean_request({"spring": {"latitude": "x", "longitude": 78}})
    spring, field, di = server.clean_request({"spring": {"latitude": 29.9, "longitude": 78.5}, "field": {"dip_angle_deg": "30", "households": ""}})
    assert field == {"dip_angle_deg": 30.0} and di == {}
    assert server.finite({"a": [float("nan"), 1.0, np.float64(2)]}) == {"a": [None, 1.0, 2.0]}


def test_page_questions_match_module_a():
    """app/src/questions.ts must use Module A's ids and allowed values."""
    import module_a_vulnerability as module_a
    text = (ROOT / "app" / "src" / "questions.ts").read_text(encoding="utf-8")
    page = {}
    for block in re.split(r"\n  \{ ", text)[1:]:
        found = re.match(r"id: '(\w+)'", block)
        if not found:
            continue
        kind = re.search(r"kind: '(\w+)'", block).group(1)
        page[found.group(1)] = (kind, re.findall(r"\['(\w+)', '", block))
    scored = {k: v for k, v in module_a.OPTIONAL.items() if v[0] != "text"}
    assert set(scored) <= set(page)
    for question_id, (kind, values) in page.items():
        if question_id in scored:
            assert kind == scored[question_id][0]
            if kind == "choice":
                assert values == scored[question_id][1]


@pytest.mark.skipif(not HAS_DEM, reason="Copernicus DEM tile for Nauli Dhara not in the layer cache")
def test_full_assessment_of_nauli_dhara():
    tool = server.Tool()
    sites = [{"id": "s1", "latitude": 29.9185, "longitude": 78.5556, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    response = tool.assess({"spring": NAULI, "field": {"flow_vs_past": "a_bit_less", "lean_flow_lpm": 2.5, "monsoon_flow_lpm": 12},
                            "di": {"sites": sites}})
    a, b, c = response["A"], response["B"], response["C"]
    assert a["result"]["class"] in {"Low", "Medium", "High"}
    zones = b["result"]["recharge_zones"]
    assert 1 <= len(zones) <= 3 and [z["id"] for z in zones] == [f"R{i}" for i in range(1, len(zones) + 1)]
    assert all(z["geojson"]["geometry"]["type"] in ("Polygon", "MultiPolygon") for z in zones)
    assert [z["score"] for z in zones] == sorted((z["score"] for z in zones), reverse=True)
    assert b["result"]["potential_overlay"]["image"].startswith("data:image/png;base64,")
    assert b["result"]["surface_catchment"]["area_ha"] > 0 and b["result"]["search"]["checks"]
    exact = b["result"]["exact_cell_catchment"]
    assert 0 < exact["area_ha"] <= b["result"]["surface_catchment"]["area_ha"] and exact["geojson"]
    assert any("depends heavily on the exact GPS point" in w for w in b["warnings"])  # 0.7 vs 21 ha
    assert all(response[m]["validation"].startswith("Not yet validated") for m in "ABC")
    assert "_zones" not in b
    assert [r["radius_m"] for r in a["result"]["map"]["rings"]] == [500, 1000]
    assert c["result"]["sites"][0]["location_class"] in module_c.SHARE
    import json
    json.dumps(response, allow_nan=False)
    assert (server.RUNS / response["run_id"] / "report.md").is_file()


def test_depth_factor_and_flow_path():
    assert module_c.depth_factor(1500, 1480)[0] == 1.0
    assert module_c.depth_factor(1475, 1480)[0] == 0.7
    assert module_c.depth_factor(1450, 1480)[0] == 0.4
    assert module_c.depth_factor(1400, 1480)[0] == 0.2
    points = [[0, 1560], [100, 1530], [200, 1500], [300, 1480]]
    path = module_c.flow_path(points, 70, None, 1480, (0.005, 0.03), (0.05, 5.0))
    assert path["injection_elevation_m"] == 1490 and path["hydraulic_gradient"] == pytest.approx(80 / 300, abs=1e-3)
    assert path["valley_between_m"] is None and path["travel_time_days"]["low"] < path["travel_time_days"]["high"]
    dip = module_c.flow_path([[0, 1560], [150, 1440], [400, 1480]], 70, 20, 1480, (0.005, 0.03), (0.05, 5.0))
    assert dip["valley_between_m"] == 40 and dip["head_at_handpump_m"] == 1540


def test_di_site_depth_changes_the_share():
    """A shallow handpump injecting above the outlet keeps the full share; a deep one below it gets less."""
    z = np.full((40, 40), 1480.0)
    z[:, :20] = 1600.0
    from rasterio.transform import from_origin
    t = from_origin(78.5, 30.0, 0.0003, 0.0003)
    spring = {"name": "S", "latitude": 30.0 - 0.0003 * 20.5, "longitude": 78.5 + 0.0003 * 25.5, "elevation_m": 1480}
    site = {"id": "a", "latitude": 30.0 - 0.0003 * 20.5, "longitude": 78.5 + 0.0003 * 5.5, "roof_area_m2": 100,
            "first_flush": True, "filter": True}
    b = {"_zones": {"zones": [], "catchment": None, "dem": (z, t), "spring_elevation_m": 1480.0}, "result": {}}
    shallow = module_c.estimate({"spring": spring, "di": {"sites": [{**site, "depth_m": 60}], "assumptions": {"annual_rain_mm": 1600}}}, b_output=b)
    deep = module_c.estimate({"spring": spring, "di": {"sites": [{**site, "depth_m": 140}], "assumptions": {"annual_rain_mm": 1600}}}, b_output=b)
    s, d = shallow["result"]["sites"][0], deep["result"]["sites"][0]
    assert s["flow_path"]["depth_factor"] == 1.0 and d["flow_path"]["depth_factor"] == 0.4
    assert d["reaching_m3_per_year"]["mid"] < s["reaching_m3_per_year"]["mid"]
    assert shallow["summary"] and "may reach the spring" in shallow["summary"][0]


def test_snow_rises_with_height():
    from secondary_layers import snow_at_elevation
    assert snow_at_elevation(None) is None
    low, mid, high = (snow_at_elevation(z) for z in (1200, 2000, 2900))
    assert low < 5 < mid < high
