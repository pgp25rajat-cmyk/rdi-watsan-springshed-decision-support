"""Module C: best-case impact of DI (direct injection) recharge on a spring.

DI sends rooftop rainwater down a defunct handpump into the aquifer. There is no before/after DI measurement in
any of our data, so nothing can be trained; this is transparent water-balance arithmetic with every assumption
shown (docs: Project1 plan, section 4.5). The numbers are upper bounds to plan and monitor against, not predictions.

For each DI site:
- Roof runoff reaching the handpump = roof area x annual rain x collection coefficient (gutter, pipe, splash losses).
- Water injected per year  V = that runoff x injection efficiency (first flush, overflow, downtime, clogging). The two
  factors cover different losses, so none is counted twice.
- Snow (ERA5 winter snowfall, water equivalent, read at the spring's height off the ERA5 snow-height curve) melting off the roof adds to the rain where it is snowy: snowfall x
  SNOW_CAPTURE, a judgement, because snow slides off, blows away or melts slowly past the gutters.
- Handpump depth. Water is injected at the bottom of the handpump (default 70 m; most are 50-80 m), not at the surface.
  Where that point is well below the spring outlet, less of the water can come back up to the spring: a depth factor
  scales the share (DEPTH_FACTOR, judgement).
- Flow path. The ground profile along the straight line from each handpump to the spring is returned for a cross-section
  like the SRHU reports' "groundwater flow path" figure: ground, borehole, injection point, spring and the assumed water
  table (parallel to the ground, as in the reports, unless the water level in the handpump is given). The hydraulic
  gradient is the fall of that water table over the distance. A valley deeper than the spring on the way is flagged.
- Share that reaches the spring. Set by where the site sits relative to Module B's top recharge zones: inside a zone
  on the spring's own slope most of it can, inside a zone linked by a fault or rock tilt some, by a crack less,
  elsewhere in the surface catchment little, below the spring none.
  These shares are judgement (low / mid / best case), to be replaced by monitoring. Being inside a zone does not
  show the site is connected to the spring: with no connection the gain is zero, and every result says so.
- Added spring flow. Spread over the whole year (annual average), or, best case, all coming out in the lean season.
  The lean-season figure is a water-volume equivalent under that timing assumption, not an expected gain.
- Illustrative storage rise near the handpump after the wettest month: that month's volume / (circle of influence x
  specific yield). A storage calculation, not a predicted recharge mound (that needs recharge rate, aquifer
  properties and boundaries), and the rock at the spring may not be the rock at the injection depth.
- Travel time to the spring: distance / (K x gradient / effective porosity). Specific yield stands in for effective
  porosity and the ground-surface slope (at least 0.02) for the water-table gradient; an order of magnitude only,
  and it does not show that a flow path exists.
- Safety gate: a DI plan is "not ready" while any site lacks a first-flush diverter or a filter; the actions are listed.

Usage: called by the tool server (scripts/spring_tool_server.py) after Modules A and B. Its inputs follow
docs/module-contract.md plus "di": {"sites": [...], "assumptions": {...}}.
"""

from __future__ import annotations

import math
import statistics


MINUTES_PER_YEAR = 525_600
DAYS_PER_MONTH = 30.44
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

VALIDATION = ("Not yet validated: no monitored DI site has been compared with these estimates. They are planning "
              "scenarios that depend on the assumed shares; the real gain could be zero.")
MIN_GRADIENT = 0.02  # assumed lowest water-table gradient for the travel time
BELOW_SPRING_M = 3  # a site this much lower than the spring (DEM noise allowed) counts as below it
DEFAULTS = {"annual_rain_mm": None, "collection_coefficient": 0.8, "injection_efficiency": 0.85,
            "lean_season_months": 5, "radius_of_influence_m": 50}
LIMITS = {"collection_coefficient": (0.3, 1.0), "injection_efficiency": (0.3, 1.0), "lean_season_months": (1, 12),
          "radius_of_influence_m": (5, 500), "annual_rain_mm": (100, 6000)}
MIN_LEAN_MONTHS = 3  # shortest spread used when the spring is low for only a month or two
DEFAULT_DEPTH_M = 70  # RDI: handpumps are usually 50-80 m deep (Rajat, 2026-10-23)
DEPTH_LIMITS = (5, 200)
SNOW_CAPTURE = 0.5  # share of the snow on a roof that melts into the gutters (judgement)
# Injection point (handpump ground minus depth) compared with the spring outlet -> factor on the share reaching the
# spring. Water put in below the outlet has to rise against gravity to come out there; most of it will flow on, deeper,
# to the valley. Judgement, to be replaced by monitoring (config/assumption_register_v1.csv).
DEPTH_FACTOR = [(10, 1.0, "above the spring outlet"), (-10, 0.7, "about level with the spring outlet"),
                (-50, 0.4, "below the spring outlet"), (-1e9, 0.2, "far below the spring outlet")]
PROFILE_STEP_M = 15
NEAR_OUTLET_M = 90  # as Module B's NEAR_SPRING_M: dips this close to the spring are not counted as a valley on the way

# Share of a site's injected water that can reach the spring: (low, mid, best case). Judgement, to be replaced by monitoring.
SHARE = {
    "in_zone_slope": (0.3, 0.6, 1.0),
    "in_zone_linked": (0.1, 0.3, 0.6),
    "in_zone_crack": (0.05, 0.2, 0.5),
    "in_catchment": (0.05, 0.15, 0.3),
    "outside": (0.0, 0.02, 0.1),
    "below_spring": (0.0, 0.0, 0.0),
}
LOCATION_NOTE = {
    "in_zone_slope": "Inside recharge zone {zone}, on the slope that drains to the spring: most of the injected water can reach it.",
    "in_zone_linked": ("Inside recharge zone {zone}, linked to the spring by a mapped fault or tilted rock layers: some of the "
                       "water may reach it if that link is real."),
    "in_zone_crack": ("Inside recharge zone {zone}, linked to the spring by a lineament (a likely crack): some of the water may "
                      "reach it if that crack carries water."),
    "in_catchment": "In the surface catchment but outside the top recharge zones: little of the water is likely to reach this spring.",
    "outside": "Outside the spring's catchment and its recharge zones: the water will mostly feed other springs or streams.",
    "below_spring": ("Lower than the spring outlet on the surface: water injected here is unlikely to feed this spring "
                     "(surface height alone cannot prove it either way)."),
}
ZONE_CLASS = {"Surface slope": "in_zone_slope", "GSI fault": "in_zone_linked", "Rock layers (up-dip)": "in_zone_linked",
              "DEM lineament": "in_zone_crack"}
# Specific yield (also used as effective porosity) and hydraulic conductivity (m/day) ranges by rock.
# Hard-rock values follow the 0.5-3 % used for fractured Himalayan rocks (CGWB GEC-2015 norms, to confirm with WATSAN).
AQUIFER = {
    "hard rock": {"sy": (0.005, 0.03), "k": (0.05, 5.0)},
    "carbonate": {"sy": (0.01, 0.05), "k": (0.5, 50.0)},
    "alluvium / debris": {"sy": (0.08, 0.16), "k": (1.0, 30.0)},
}
BENCHMARKS = [
    "ICIMOD reports +23% and +48% average spring flow after full springshed treatment (trenches, pits, plantation over the "
    "whole recharge area) at two Indian Himalayan pilot springs. That is for whole-springshed treatment, not DI alone, so it is "
    "context only, not evidence of what DI does; DI at a few handpumps should add well below that unless roofs are large.",
    "RDI's handpump design collects about 70-80% of roof rain. A 100 m2 roof under 1,600 mm of rain injects about 100-110 m3 a year.",
]
MONITORING = [
    "Measure the spring every month on a fixed date: three bucket-and-stopwatch readings, and note the weather of the last 3 days.",
    "Start before the DI works if at all possible, so there is a baseline year to compare with.",
    "Read the water level in each DI handpump with a dip meter weekly in the monsoon and monthly otherwise.",
    "Keep a rain gauge in the village and log each DI injection (date, roof, rough volume).",
    "Test water quality (turbidity, coliform, iron) at the spring before and after the first monsoon of injection.",
]


def _number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _range(low, mid, high, digits=2):
    return {"low": round(low, digits), "mid": round(mid, digits), "high": round(high, digits)}


def aquifer_for(rock_text):
    text = (rock_text or "").lower()
    if "alluvium" in text or "debris" in text:
        return "alluvium / debris"
    if "carbonate" in text and "mixed" not in text:
        return "carbonate"
    return "hard rock"


def rainfall(features, layers, lon, lat, override):
    """Annual rain (mm) with its source, and the monthly pattern (CHIRPS 2018-2025 mean, scaled to that annual total)."""
    monthly = None
    if layers is not None and getattr(layers, "pcp_m", None) is not None:
        values = []
        for m in range(1, 13):
            v = [layers.pcp_m.sample(f"{y}-{m:02d}", lon, lat) for y in range(2018, 2026)]
            v = [x for x in v if not math.isnan(x)]
            values.append(statistics.fmean(v) if v else float("nan"))
        if not any(math.isnan(v) for v in values) and sum(values) > 0:
            monthly = values
    if override:
        annual, source = float(override), "entered by the user"
    elif features.get("rain_imd_mean_annual_mm"):
        annual = float(features["rain_imd_mean_annual_mm"])
        source = f"IMD gridded rain gauges, mean of {features.get('rain_imd_years_used', '2001-2025')}"
    elif features.get("rain_chirps_mean_annual_mm_2018_2025"):
        annual = float(features["rain_chirps_mean_annual_mm_2018_2025"])
        source = ("CHIRPS satellite estimate, 2018-2025 mean. At the dataset springs CHIRPS read about 45% above the IMD gauges "
                  "(a comparison, not a correction factor), so this may be optimistic; add the IMD files or enter a local value")
    elif monthly:
        annual, source = sum(monthly), "CHIRPS monthly, 2018-2025 mean"
    else:
        return None
    if monthly:
        total = sum(monthly)
        monthly = [round(v * annual / total, 1) for v in monthly]
    return {"annual_mm": round(annual), "source": source, "monthly_mm": monthly}


def depth_factor(injection_z, spring_z):
    """(factor, words) for an injection point at injection_z (m) against the spring outlet at spring_z."""
    gap = injection_z - spring_z
    for above, factor, words in DEPTH_FACTOR:
        if gap >= above:
            return factor, words
    return DEPTH_FACTOR[-1][1:]


def profile(dem, s_lat, s_lon, lat, lon, m_lat, m_lon):
    """Ground heights along the straight line from the handpump to the spring: [[distance m, height m], ...]."""
    if dem is None:
        return None
    z, t = dem
    length = math.hypot((lat - s_lat) * m_lat, (lon - s_lon) * m_lon)
    steps = max(2, min(300, int(length / PROFILE_STEP_M) + 1))
    out = []
    for k in range(steps):
        f = k / (steps - 1)
        y, x = s_lat + (lat - s_lat) * f, s_lon + (lon - s_lon) * f
        row, col = int((y - t.f) / t.e), int((x - t.c) / t.a)
        if not (0 <= row < z.shape[0] and 0 <= col < z.shape[1]) or z[row, col] <= -1000:
            return None
        out.append([round(length * f, 1), round(float(z[row, col]), 1)])
    return out


def flow_path(points, depth, water_level, spring_z, sy, k):
    """The cross-section numbers: injection point, assumed water table, gradient, travel time and any valley on the way."""
    if not points or len(points) < 2:
        return None
    length = points[-1][0]
    ground_site = points[0][1]
    injection_z = ground_site - depth
    head = ground_site - water_level if water_level is not None else None
    if head is not None:
        gradient = (head - spring_z) / length if length > 0 else 0.0
        basis = f"water level {water_level:g} m below ground in the handpump (given)"
    else:
        gradient = (ground_site - spring_z) / length if length > 0 else 0.0
        basis = "water table assumed to follow the ground slope, as in the SRHU reports (no water level given)"
    inner = [z for d, z in points if 30 < d < length - NEAR_OUTLET_M]  # the ground right at the outlet is DEM and GPS noise
    lowest = min(inner) if inner else None
    valley = None if lowest is None or lowest >= spring_z - 5 else round(spring_z - lowest)
    travel = None
    if gradient > 0 and length > 0:
        g = max(gradient, MIN_GRADIENT)
        travel = {"low": round(length * sy[0] / (k[1] * g), 1), "high": round(length * sy[1] / (k[0] * g))}
    return {"profile": points, "length_m": round(length), "ground_at_handpump_m": round(ground_site), "depth_m": depth,
            "injection_elevation_m": round(injection_z), "spring_elevation_m": round(spring_z),
            "water_level_m": water_level, "head_at_handpump_m": None if head is None else round(head),
            "hydraulic_gradient": round(gradient, 3), "gradient_basis": basis, "travel_time_days": travel,
            "valley_between_m": valley}


def site_elevation(lat, lon, dem, mod, layers):
    if dem is not None:
        z, t = dem
        row, col = mod.centre_index(t, lon, lat)
        if 0 <= row < z.shape[0] and 0 <= col < z.shape[1] and z[row, col] > -1000:
            return float(z[row, col])
    if layers is not None:
        z, t = mod.read_window(layers.dem, lon, lat, 60)
        if z is not None:
            row, col = mod.centre_index(t, lon, lat)
            if 0 <= row < z.shape[0] and 0 <= col < z.shape[1] and z[row, col] > -1000:
                return float(z[row, col])
    return None


def lean_months_from_field(field, assumptions, given):
    """The months the extra water is spread over: the spring's own low- or no-flow months from the vulnerability
    questions (at least MIN_LEAN_MONTHS), else the default (Rajat, 2026-10-23). A value sent in the assumptions wins.
    Sets assumptions["lean_season_months"] and returns a note saying where the number came from."""
    if given.get("lean_season_months") not in (None, ""):
        return "Set by the user."
    months = max(_number(field.get("low_flow_months")) or 0, _number(field.get("dry_months")) or 0)
    if months > 0:
        assumptions["lean_season_months"] = min(12, max(MIN_LEAN_MONTHS, round(months)))
        return (f"From the field answers: {months:g} month{'s' if months != 1 else ''} with low or no flow"
                f"{f' (at least {MIN_LEAN_MONTHS} used)' if months < MIN_LEAN_MONTHS else ''}.")
    return f"Default {DEFAULTS['lean_season_months']} months: the low-flow months were not given."


def estimate(inputs, session=None, features=None, b_output=None):
    """Module C under the shared contract. inputs: {"spring", "field", "di": {"sites", "assumptions"}}.
    session: Module A's LayerSession (rain pattern, site elevations); features: the layer values at the spring;
    b_output: Module B's output including its "_zones" (shapely zones, the DEM window and the spring elevation)."""
    from shapely.geometry import Point

    spring = inputs["spring"]
    lat, lon = float(spring["latitude"]), float(spring["longitude"])
    name = spring.get("name") or f"{lat:.5f}, {lon:.5f}"
    field = inputs.get("field") or {}
    di = inputs.get("di") or {}
    sites = di.get("sites") or []
    features = features or {}
    warnings, rationale, missing = [], [], []

    assumptions = dict(DEFAULTS)
    for key, value in (di.get("assumptions") or {}).items():
        if key in DEFAULTS and value not in (None, ""):
            v = _number(value)
            lo, hi = LIMITS[key]
            if v is None or not lo <= v <= hi:
                warnings.append(f"Assumption ignored: {key} = {value!r} (allowed {lo}-{hi}).")
                continue
            assumptions[key] = v
    months_note = lean_months_from_field(field, assumptions, di.get("assumptions") or {})
    layers = getattr(session, "layers", None) if session is not None else None
    mod = getattr(session, "mod", None)
    rain = rainfall(features, layers, lon, lat, assumptions["annual_rain_mm"])
    base = {"module": "C", "title": "Potential impact of DI recharge", "version": "v1 draft",
            "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": spring.get("elevation_m")}}
    if rain is None:
        return {**base, "status": "unavailable", "result": None, "confidence": "Low", "validation": VALIDATION,
                "rationale": ["No rainfall value was found for this location. Enter the yearly rainfall under the DI assumptions."],
                "missing_inputs": [{"id": "annual_rain_mm", "indicator": "Yearly rainfall", "needs": "A yearly rainfall value in mm."}],
                "warnings": warnings, "report_markdown": f"# DI impact: {name}\n\nNo rainfall value was found.\n"}

    zones = (b_output or {}).get("_zones") or {}
    b_result = (b_output or {}).get("result") or {}
    spring_z = zones.get("spring_elevation_m") or _number(spring.get("elevation_m"))
    rock_text = ((b_result.get("geology") or {}).get("rock_class")) or field.get("rock_at_outlet") or ""
    aquifer = aquifer_for(rock_text)
    sy, k = AQUIFER[aquifer]["sy"], AQUIFER[aquifer]["k"]
    if not zones:
        warnings.append("No recharge zones were available from the springshed section, so every site is treated as outside them.")
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * math.radians(lat))
    m_per_deg_lon = 111412.84 * math.cos(math.radians(lat))
    snow_cell = _number(features.get("era5_snowfall_winter_mm"))
    snow_mm = _number(features.get("snow_at_elevation_mm"))
    if snow_mm is None and snow_cell is not None:
        from secondary_layers import snow_at_elevation
        snow_mm = snow_at_elevation(spring_z)  # only where the ERA5 layer is in place
    snow_mm = snow_mm or 0.0
    snow_used = snow_mm * SNOW_CAPTURE
    rain["snow_mm"] = round(snow_mm)
    rain["snow_used_mm"] = round(snow_used)
    rain_m = (rain["annual_mm"] + snow_used) / 1000
    cc, eff = assumptions["collection_coefficient"], assumptions["injection_efficiency"]
    lean_months = assumptions["lean_season_months"]
    lean_minutes = lean_months * DAYS_PER_MONTH * 1440
    radius = assumptions["radius_of_influence_m"]
    wettest_share = max(rain["monthly_mm"]) / rain["annual_mm"] if rain["monthly_mm"] else 0.25

    results, monthly_total = [], [0.0] * 12
    for i, s in enumerate(sites):
        try:
            s_lat, s_lon = float(s["latitude"]), float(s["longitude"])
            roof = float(s.get("roof_area_m2") or 0)
        except (KeyError, TypeError, ValueError):
            warnings.append(f"DI site {i + 1} was skipped: it needs a latitude, longitude and roof area.")
            continue
        if roof <= 0 or roof > 5000:
            warnings.append(f"DI site {s.get('name') or i + 1} was skipped: roof area must be between 1 and 5,000 m2.")
            continue
        site_id = str(s.get("id") or f"site-{i + 1}")
        label = s.get("name") or f"DI site {i + 1}"
        point = Point(s_lon, s_lat)
        z = site_elevation(s_lat, s_lon, zones.get("dem"), mod, layers) if mod else None
        height = None if z is None or spring_z is None else z - spring_z
        distance = math.hypot((s_lat - lat) * m_per_deg_lat, (s_lon - lon) * m_per_deg_lon)
        depth = _number(s.get("depth_m"))
        depth_given = depth is not None
        if depth is None or not DEPTH_LIMITS[0] <= depth <= DEPTH_LIMITS[1]:
            if depth_given:
                warnings.append(f"{label}: handpump depth {depth:g} m is outside {DEPTH_LIMITS[0]}-{DEPTH_LIMITS[1]} m, so {DEFAULT_DEPTH_M} m was used.")
            depth, depth_given = DEFAULT_DEPTH_M, False
        water_level = _number(s.get("water_level_m"))
        if water_level is not None and not 0 <= water_level < depth:
            warnings.append(f"{label}: water level {water_level:g} m is not between 0 and the handpump depth, so it was ignored.")
            water_level = None
        path = None
        if spring_z is not None:
            points = profile(zones.get("dem"), s_lat, s_lon, lat, lon, m_per_deg_lat, m_per_deg_lon)
            if points is None and z is not None:
                points = [[0.0, round(z, 1)], [round(distance, 1), round(spring_z, 1)]]
            path = flow_path(points, depth, water_level, spring_z, sy, k)
        zone = None
        if height is not None and height < -BELOW_SPRING_M:
            where = "below_spring"
        elif (zone := next((zn for zn in zones.get("zones") or [] if zn["geom"].contains(point)), None)):
            where = ZONE_CLASS.get(zone["kind"], "in_zone_linked")
        elif zones.get("catchment") is not None and zones["catchment"].contains(point):
            where = "in_catchment"
        else:
            where = "outside"
        runoff = roof * rain_m * cc
        volume = runoff * eff
        factor, depth_words = (1.0, "")
        if path is not None:
            factor, depth_words = depth_factor(path["injection_elevation_m"], spring_z)
            path["depth_factor"], path["depth_words"] = factor, depth_words
        share = [f * factor for f in SHARE[where]]
        reaching = [volume * f for f in share]
        annual = [volume * f * 1000 / MINUTES_PER_YEAR for f in share]
        lean = [volume * f * 1000 / lean_minutes for f in share]
        peak_month = volume * wettest_share
        rise = (peak_month / (math.pi * radius ** 2 * sy[1]), peak_month / (math.pi * radius ** 2 * sy[0]))
        travel = path["travel_time_days"] if path else None
        flags = []
        if not s.get("first_flush"):
            flags.append("No first-flush diverter: the first dirty roof water goes straight into the drinking-water aquifer.")
        if not s.get("filter"):
            flags.append("No filter: silt can clog the handpump and reach the spring.")
        if roof > 300:
            flags.append("Large roof: check the handpump can take the peak monsoon inflow without overflowing.")
        if where in ("outside", "below_spring"):
            flags.append("Consider moving this site into one of the top recharge zones (R1-R3). Keep this site's record: "
                         "surface position alone does not prove it is cut off from the spring.")
        if distance > 2000:
            flags.append("More than 2 km from the spring.")
        if path and path["valley_between_m"]:
            flags.append(f"The ground between this handpump and the spring dips about {path['valley_between_m']} m below the spring: "
                         "water moving that way may come out in that valley first.")
        if path and factor < 1:
            flags.append(f"Water is injected at {depth:g} m depth, about {path['injection_elevation_m']} m above sea level, which is "
                         f"{depth_words} ({spring_z:.0f} m): only {factor:.0%} of the usual share is counted.")
        if not depth_given:
            flags.append(f"Handpump depth not given: {DEFAULT_DEPTH_M} m assumed (most are 50-80 m).")
        if rain["monthly_mm"]:
            for m in range(12):
                melt = snow_used / 3 if m in (0, 1, 2) else 0.0  # snowmelt counted in January-March
                monthly_total[m] += roof * (rain["monthly_mm"][m] + melt) / 1000 * cc * eff
        results.append({
            "id": site_id, "name": label, "latitude": s_lat, "longitude": s_lon,
            "elevation_m": None if z is None else round(z), "roof_area_m2": roof,
            "runoff_m3_per_year": round(runoff, 1), "volume_m3_per_year": round(volume, 1), "location_class": where,
            "location_note": LOCATION_NOTE[where].format(zone=zone["id"] if zone else ""), "zone_id": zone["id"] if zone else None,
            "share_reaching_spring": _range(*share), "reaching_m3_per_year": _range(*reaching, digits=1),
            "depth_m": depth, "depth_given": depth_given, "water_level_m": water_level, "flow_path": path,
            "added_flow_lpm_annual": _range(*annual, digits=3),
            "added_flow_lpm_lean": _range(*lean, digits=3),
            "water_level_rise_m": {"low": round(rise[0], 2), "high": round(rise[1], 2)},
            "travel_time_days": travel, "distance_to_spring_m": round(distance),
            "height_above_spring_m": None if height is None else round(height), "flags": flags,
        })

    lean_flow = _number(field.get("lean_flow_lpm"))
    total_volume = sum(r["volume_m3_per_year"] for r in results)
    tot_reaching = _range(*(sum(r["reaching_m3_per_year"][x] for r in results) for x in ("low", "mid", "high")), digits=1)
    tot_annual = _range(*(sum(r["added_flow_lpm_annual"][x] for r in results) for x in ("low", "mid", "high")), digits=3)
    tot_lean = _range(*(sum(r["added_flow_lpm_lean"][x] for r in results) for x in ("low", "mid", "high")), digits=3)
    pct = None
    if lean_flow and lean_flow > 0 and results:
        pct = _range(*(100 * tot_lean[x] / lean_flow for x in ("low", "mid", "high")), digits=1)
    one_roof = 100 * rain_m * cc * eff * SHARE["in_zone_slope"][1] * 1000 / lean_minutes
    roofs_for_10pct = math.ceil(0.1 * lean_flow / one_roof) if lean_flow and lean_flow > 0 else None

    if results:
        inside = sum(1 for r in results if r["location_class"].startswith("in_zone"))
        snow_words = f" plus about {snow_used:.0f} mm of melted snow" if snow_used >= 1 else ""
        rationale.append(f"Water going in: {len(results)} DI {'handpump' if len(results) == 1 else 'handpumps'} with {sum(r['roof_area_m2'] for r in results):,.0f} m2 of roof can inject about "
                         f"{total_volume:,.0f} m3 ({total_volume * 1000:,.0f} litres) a year at {rain['annual_mm']:,} mm of rain{snow_words}.")
        rationale.append(f"Water reaching the spring: about {tot_reaching['mid']:,.0f} m3 a year (range {tot_reaching['low']:,.0f}-{tot_reaching['high']:,.0f}), "
                         "depending on where each handpump sits relative to the recharge zones and how deep it injects. The rest feeds "
                         "other springs, streams or deeper groundwater.")
        rationale.append(f"{inside} of {len(results)} {'lies' if inside == 1 else 'lie'} inside the top recharge zones. If the assumed share of the water "
                         f"reaches the spring (shown per site) and all of it comes out in the {lean_months:g}-month lean season, that is "
                         f"{tot_lean['mid']:.2f} L/min then (range {tot_lean['low']:.2f}-{tot_lean['high']:.2f}); spread over the year it is "
                         f"{tot_annual['mid']:.2f} L/min. These are water-volume equivalents under those assumptions, not expected gains.")
        rationale.append("If a site turns out not to be connected to the spring, which only monitoring can show, its gain is zero.")
        if pct:
            rationale.append(f"Under the same assumptions that is about {pct['mid']:.0f}% of the present lean-season flow of {lean_flow:g} L/min "
                             f"(range {pct['low']:.0f}-{pct['high']:.0f}%).")
        rationale.append("The storage rise shown per site is an illustration of how much water the rock would have to hold near "
                         "the handpump after the wettest month, not a predicted water-level rise.")
    else:
        rationale.append("No DI sites were placed yet. Add them on the map to see what they would add.")
    if roofs_for_10pct:
        rationale.append(f"To add 10% to the lean flow ({0.1 * lean_flow:.2f} L/min), about {roofs_for_10pct} {'roof' if roofs_for_10pct == 1 else 'roofs'} of 100 m2 on the spring's own slope inside a recharge zone would be needed, "
                         "if 60% of their water reaches the spring and all of it comes out in the lean season (both assumptions).")
    if not lean_flow:
        missing.append({"id": "lean_flow_lpm", "indicator": "Lean-season flow",
                        "needs": "A May-June bucket reading turns the added flow into a % of what the spring gives now."})
    if not zones:
        missing.append({"id": "springshed", "indicator": "Springshed", "needs": "The springshed section must run to place the sites."})

    benchmarks = [f"One 100 m2 roof inside a recharge zone on the spring's own slope could add about {one_roof:.2f} L/min to the lean-season flow, "
                  "if 60% of its water reaches the spring and all of it comes out in the lean season."] + BENCHMARKS
    safety = safety_gate(results)
    assumption_rows = [
        {"id": "annual_rain_mm", "label": "Yearly rain", "value": rain["annual_mm"], "unit": "mm", "note": rain["source"]},
        {"id": "collection_coefficient", "label": "Roof rain reaching the handpump", "value": cc, "unit": "share",
         "note": "Gutter, pipe and splash losses. RDI design 0.7-0.8 for metal or concrete roofs."},
        {"id": "injection_efficiency", "label": "Share of that water actually injected", "value": eff, "unit": "share",
         "note": "First flush, overflow, downtime and clogging (a different loss from the one above). Assumed 0.8-0.9."},
        {"id": "share", "label": "Share reaching the spring", "value": "0 if not connected; otherwise 0.3-1.0 in a recharge zone on the spring's slope; 0.1-0.6 in one linked by a fault or rock tilt; 0.05-0.5 by a crack; up to 0.3 elsewhere in the catchment",
         "unit": "share", "note": "Judgement until monitoring data exist; not measured connection."},
        {"id": "lean_season_months", "label": "Lean season", "value": lean_months, "unit": "months",
         "note": f"{months_note} Timing assumption: all extra water comes out evenly in these months. Needs evidence of storage and slow release."},
        {"id": "specific_yield", "label": "Specific yield of the rock", "value": f"{sy[0] * 100:g}-{sy[1] * 100:g}", "unit": "%",
         "note": f"{aquifer.capitalize()} ({rock_text or 'rock not known'}), from the rock at the spring, which may differ at the injection depth. "
                 "Also used in place of effective porosity for the travel time. CGWB GEC-2015 norms, to confirm with WATSAN."},
        {"id": "radius_of_influence_m", "label": "Storage circle around the handpump", "value": radius, "unit": "m",
         "note": "Unknown; 20-150 m is plausible. Used only for the illustrative storage rise."},
        {"id": "conductivity", "label": "Rock permeability (K)", "value": f"{k[0]:g}-{k[1]:g}", "unit": "m/day",
         "note": f"Wide range for fractured rock. The travel time uses the gradient of the assumed water table (at least {MIN_GRADIENT}): the ground slope, "
                 "or the handpump water level when given. An order of magnitude only."},
        {"id": "snow", "label": "Winter snow (water equivalent)", "value": round(snow_mm), "unit": "mm",
         "note": f"ERA5 winters 2019-20 to 2024-25, read off the snow-height curve at the spring's elevation"
                 f"{f' (the 27 km cell itself averages {snow_cell:.0f} mm)' if snow_cell is not None else ''}. {SNOW_CAPTURE:.0%} of it ({snow_used:.0f} mm) is counted as melting into the gutters (judgement). "
                 "The rain gauges may already catch some of it."},
        {"id": "depth", "label": "Handpump depth (injection point)", "value": f"{DEFAULT_DEPTH_M} m unless given", "unit": "",
         "note": "Injection below the spring outlet counts less: x1.0 above it, x0.7 about level (within 10 m), x0.4 up to 50 m below, x0.2 deeper. Judgement."},
    ]
    result = {
        "rain": rain, "sites": results,
        "totals": {"volume_m3_per_year": round(total_volume, 1), "reaching_m3_per_year": tot_reaching, "added_flow_lpm_annual": tot_annual,
                   "added_flow_lpm_lean": tot_lean, "lean_flow_lpm": lean_flow, "pct_of_lean_flow": pct},
        "monthly_injection_m3": [round(v, 1) for v in monthly_total] if rain["monthly_mm"] and results else None,
        "roofs_for_10pct": roofs_for_10pct, "assumptions": assumption_rows, "safety": safety,
        "benchmarks": benchmarks, "monitoring_plan": MONITORING,
    }
    if results and not safety["ready"]:
        rationale.insert(0, "Not ready for DI yet: " + "; ".join(a for a in safety["actions"] if a.startswith("Fit")) + ".")
    summary = plain_summary(results, result["totals"])
    return {**base, "status": "provisional", "result": result, "summary": summary, "confidence": "Low", "validation": VALIDATION, "rationale": rationale,
            "missing_inputs": missing, "warnings": warnings, "report_markdown": report_markdown(name, result, rationale, warnings)}


def plain_summary(results, totals):
    """Per handpump, in everyday words: water in, where it goes in, the path to the spring, and water out."""
    lines = []
    for r in results:
        sh, got = r["share_reaching_spring"], r["reaching_m3_per_year"]
        text = f"{r['name']}: about {r['volume_m3_per_year']:,.0f} m3 a year goes in at {r['depth_m']:g} m depth"
        p = r.get("flow_path")
        if p:
            gap = p["injection_elevation_m"] - p["spring_elevation_m"]
            text += (f" ({abs(gap)} m {'above' if gap >= 0 else 'below'} the spring outlet). It is {p['length_m']:,} m from the spring"
                     + (f", and the ground falls {p['ground_at_handpump_m'] - p['spring_elevation_m']} m towards it (gradient {p['hydraulic_gradient']:.2f})"
                        if p["hydraulic_gradient"] > 0 else ", but the spring is not downhill of it"))
            if p["travel_time_days"]:
                t = p["travel_time_days"]
                text += f"; water would take roughly {_days(t['low'])} to {_days(t['high'])} to get there"
        text += f". Of that, about {got['mid']:,.0f} m3 a year ({sh['mid']:.0%}) may reach the spring (range {got['low']:,.0f}-{got['high']:,.0f}), if the handpump is connected to it."
        lines.append(text)
    if len(results) > 1:
        lines.append(f"All handpumps together: {totals['volume_m3_per_year']:,.0f} m3 in, about {totals['reaching_m3_per_year']['mid']:,.0f} m3 a year to the spring.")
    return lines


def _days(d):
    return "under a day" if d < 1 else f"{d:.0f} day{'s' if round(d) != 1 else ''}" if d < 60 else f"{d / 30.4:.0f} months" if d < 730 else f"{d / 365:.0f} years"


def safety_gate(results):
    """Is the DI plan ready to recommend? Missing safeguards are actions, not just warnings next to a gain."""
    actions = []
    no_flush = [r["name"] for r in results if any(f.startswith("No first-flush") for f in r["flags"])]
    no_filter = [r["name"] for r in results if any(f.startswith("No filter") for f in r["flags"])]
    if no_flush:
        actions.append(f"Fit a first-flush diverter at {', '.join(no_flush)}")
    if no_filter:
        actions.append(f"Fit a filter at {', '.join(no_filter)}")
    if results:
        actions += ["Test the roof water and the spring water (turbidity, coliform, iron) before the first injection",
                    "Check each handpump for clogging and overflow after the first heavy rain, and clean the filter each season",
                    "Confirm with WATSAN that each site is suitable (no latrine or soak pit nearby, handpump casing sound)"]
    return {"ready": bool(results) and not no_flush and not no_filter, "actions": actions}


def report_markdown(name, result, rationale, warnings):
    lines = [f"# Potential impact of DI recharge: {name}", "",
             "Planning scenario, not a prediction (Module C v1 draft). " + VALIDATION, "",
             "## Summary", *(f"- {r}" for r in rationale), ""]
    if result["safety"]["actions"]:
        lines += ["## Before any injection" + ("" if result["safety"]["ready"] else " (not ready yet)"),
                  *(f"- [ ] {a}" for a in result["safety"]["actions"]), ""]
    if result["sites"]:
        lines += ["| Site | Where | Share assumed to reach the spring (low-mid-best) | Water injected (m3/yr) | Lean-season equivalent (L/min, low-mid-best; 0 if not connected) | Illustrative storage rise (m) |",
                  "|---|---|---|---|---|---|"]
        for s in result["sites"]:
            f = s["added_flow_lpm_lean"]
            sh = s["share_reaching_spring"]
            lines.append(f"| {s['name']} | {s['location_class'].replace('_', ' ')} | {sh['low']:.0%}-{sh['mid']:.0%}-{sh['high']:.0%} | {s['volume_m3_per_year']:.0f} | "
                         f"{f['low']:.2f} - {f['mid']:.2f} - {f['high']:.2f} | {s['water_level_rise_m']['low']:.1f}-{s['water_level_rise_m']['high']:.1f} |")
        lines.append("")
    lines += ["## Assumptions", *(f"- {a['label']}: {a['value']} {a['unit']} ({a['note']})" for a in result["assumptions"]), "",
              "## Monitoring plan", *(f"- {m}" for m in result["monitoring_plan"]), ""]
    if warnings:
        lines += ["## Notes", *(f"- {w}" for w in warnings), ""]
    return "\n".join(lines)
