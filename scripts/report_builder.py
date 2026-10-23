"""The detailed spring report: one HTML page laid out like the SRHU geohydrology reports received from RDI
(Badera, Domsi and Makhdet; data/Reference data received from RDI), built from one tool run.

Every map is drawn here from the grids the model used (Module B's "_report" key), as inline SVG over a PNG raster,
with a legend, scale bar, north arrow and graticule. No plotting library is needed. The page prints to PDF from the
browser. The text is written from the numbers; it describes the maps, not field observations.
"""
from __future__ import annotations

import html
import math
from datetime import datetime

import numpy as np

import module_b_springshed as module_b

# ---------------------------------------------------------------------- colours and classes
DEM_COLORS = ["#2b83ba", "#abdda4", "#ffffbf", "#fdae61", "#d7191c"]
SLOPE_CLASSES = [("0-10 degrees (gentle)", "#1a9850"), ("10-20 degrees (moderate)", "#91cf60"), ("20-30 degrees (moderately steep)", "#fee08b"),
                 ("30-40 degrees (steep)", "#fc8d59"), ("over 40 degrees (very steep)", "#d73027")]
ASPECTS = [("North", "#e8504f"), ("North-east", "#f39c3d"), ("East", "#f2df52"), ("South-east", "#7dcf5b"), ("South", "#4fc7c7"),
           ("South-west", "#4f9de0"), ("West", "#5a63d8"), ("North-west", "#c25bd0")]
WORLDCOVER_COLORS = {10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000", 60: "#b4b4b4", 70: "#f0f0f0",
                     80: "#0064c8", 90: "#0096a0", 95: "#00cf75", 100: "#fae6a0"}
SOIL_COLORS = {"Sandy": "#f6e8c3", "Sandy loam": "#dfc27d", "Loam or silt loam": "#bf812d", "Clay loam": "#8c510a", "Clay": "#543005"}
DEPTH_COLORS = {"under 50 cm": "#fee6ce", "50-100 cm": "#fdae6b", "100-150 cm": "#e6550d", "150 cm or more": "#a63603"}
POTENTIAL_COLORS = ["#ffffcc", "#d9f0a3", "#addd8e", "#41ab5d", "#006837"]
CATEGORY_COLORS = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3", "#1b9e77", "#d95f02"]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
ZONE_COLORS = {"R1": "#6a3d9a", "R2": "#e66101", "R3": "#0571b0"}
SPRING_COLOR, HP_COLOR, CATCH_COLOR, STREAM_COLOR = "#0b63c5", "#c0392b", "#111111", "#2c7fb8"

SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
SATELLITE_CREDIT = "Satellite image: Esri World Imagery (Esri, Maxar, Earthstar Geographics), loaded when the report is opened online."
MAP_W = 660  # px of the map frame (the page is A4 portrait)
MAP_H_MAX = 560
MIN_SPAN_M = 700


def esc(text):
    return html.escape(str(text if text is not None else ""))


def dms(value, pos, neg):
    hemi = pos if value >= 0 else neg
    v = abs(value)
    d = int(v)
    m = int((v - d) * 60)
    s = (v - d - m / 60) * 3600
    return f"{d}°{m:02d}'{s:05.2f}\"{hemi}"


def fmt(value, digits=0):
    if value is None:
        return "-"
    return f"{value:,.{digits}f}"


def png_uri(rgb):
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]) if rgb.shape[2] == 3 else rgb
    return module_b._png(rgba)


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float64)


# ---------------------------------------------------------------------- geometry helpers
def hillshade(z, dx, dy, azimuth=315, altitude=45):
    gy, gx = np.gradient(z, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(azimuth), math.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0, 1)


def contour_lines(z, level):
    """Marching squares on a grid: polylines in (row, col) cell-centre coordinates."""
    from shapely.geometry import MultiLineString
    from shapely.ops import linemerge
    a, b, c, d = z[:-1, :-1], z[:-1, 1:], z[1:, 1:], z[1:, :-1]  # top-left, top-right, bottom-right, bottom-left
    rows, cols = np.mgrid[0:z.shape[0] - 1, 0:z.shape[1] - 1]

    def cross(p, q):
        with np.errstate(divide="ignore", invalid="ignore"):
            f = (level - p) / (q - p)
        return ((p < level) != (q < level)) & np.isfinite(f), np.clip(np.nan_to_num(f), 0, 1)

    top, ft = cross(a, b)
    right, fr = cross(b, c)
    bottom, fb = cross(d, c)
    left, fl = cross(a, d)
    pts = {"t": (rows, cols + ft), "r": (rows + fr, cols + 1), "b": (rows + 1, cols + fb), "l": (rows + fl, cols)}
    has = {"t": top, "r": right, "b": bottom, "l": left}
    n = top.astype(int) + right + bottom + left
    segs = []
    pairs = [("t", "r"), ("t", "b"), ("t", "l"), ("r", "b"), ("r", "l"), ("b", "l")]
    two = n == 2
    for e1, e2 in pairs:
        m = two & has[e1] & has[e2]
        if m.any():
            r1, c1 = pts[e1][0][m], pts[e1][1][m]
            r2, c2 = pts[e2][0][m], pts[e2][1][m]
            segs += [((x1, y1), (x2, y2)) for x1, y1, x2, y2 in zip(c1, r1, c2, r2)]
    four = n == 4
    if four.any():
        centre = ((a + b + c + d) / 4)[four] >= level
        tl = (a[four] >= level)
        for i, (same, ul) in enumerate(zip(centre, tl)):
            rr = {k: (pts[k][0][four][i], pts[k][1][four][i]) for k in pts}
            combos = (("t", "l"), ("b", "r")) if same != ul else (("t", "r"), ("b", "l"))
            for e1, e2 in combos:
                segs.append(((rr[e1][1], rr[e1][0]), (rr[e2][1], rr[e2][0])))
    if not segs:
        return []
    merged = linemerge(MultiLineString(segs))
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    return [list(g.coords) for g in geoms]  # (col, row) pairs


def satellite_tiles(frame):
    """Esri World Imagery tiles covering the frame, as SVG images. The browser fetches them when the report opens;
    offline they stay blank and the shaded relief underneath shows through."""
    lat0 = (frame.north + frame.south) / 2
    want = 1 / (2 * frame.px_per_m)  # ground metres per image pixel, for a sharp print
    zoom = int(max(12, min(18, round(math.log2(156543.03 * math.cos(math.radians(lat0)) / want)))))
    n = 2 ** zoom

    def tile_x(lon):
        return (lon + 180) / 360 * n

    def tile_y(lat):
        r = math.radians(lat)
        return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n

    def lon_of(x):
        return x / n * 360 - 180

    def lat_of(y):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))

    out = []
    for ty in range(int(tile_y(frame.north)), int(tile_y(frame.south)) + 1):
        for tx in range(int(tile_x(frame.west)), int(tile_x(frame.east)) + 1):
            x0, y0 = frame.xy(lon_of(tx), lat_of(ty))
            x1, y1 = frame.xy(lon_of(tx + 1), lat_of(ty + 1))
            out.append(f'<image href="{SATELLITE.format(z=zoom, x=tx, y=ty)}" x="{x0:.2f}" y="{y0:.2f}" width="{x1 - x0 + 0.6:.2f}" '
                       f'height="{y1 - y0 + 0.6:.2f}" preserveAspectRatio="none"/>')
    return "".join(out)


class MapFrame:
    """One map: a crop of the model's grid, drawn to an SVG frame with lon/lat helpers."""

    def __init__(self, g, extent):
        self.g = g
        z, t = g["z"], g["t"]
        west, south, east, north = extent
        c0 = max(0, int((west - t.c) / t.a))
        c1 = min(z.shape[1], int(math.ceil((east - t.c) / t.a)))
        r0 = max(0, int((north - t.f) / t.e))
        r1 = min(z.shape[0], int(math.ceil((south - t.f) / t.e)))
        self.r0, self.r1, self.c0, self.c1 = r0, r1, c0, c1
        self.west, self.east = t.c + c0 * t.a, t.c + c1 * t.a
        self.north, self.south = t.f + r0 * t.e, t.f + r1 * t.e
        width_m = (self.east - self.west) * g["m_lon"]
        height_m = (self.north - self.south) * g["m_lat"]
        self.w = MAP_W
        self.h = MAP_W * height_m / width_m
        if self.h > MAP_H_MAX:
            self.w, self.h = MAP_W * MAP_H_MAX / self.h, MAP_H_MAX
        self.px_per_m = self.w / width_m
        self.dx, self.dy = abs(t.a) * g["m_lon"], abs(t.e) * g["m_lat"]

    def crop(self, grid):
        return grid[self.r0:self.r1, self.c0:self.c1]

    def xy(self, lon, lat):
        return ((lon - self.west) / (self.east - self.west) * self.w, (self.north - lat) / (self.north - self.south) * self.h)

    def cell_xy(self, col, row):  # crop-relative cell-centre coordinates
        return ((col + 0.5) / (self.c1 - self.c0) * self.w, (row + 0.5) / (self.r1 - self.r0) * self.h)


def path_d(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


def geojson_paths(frame, geometry):
    """SVG path data for a GeoJSON (Multi)Polygon or (Multi)LineString in lon/lat."""
    if not geometry:
        return []
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Polygon":
        rings = coords
    elif kind == "MultiPolygon":
        rings = [r for poly in coords for r in poly]
    elif kind == "LineString":
        return [path_d([frame.xy(*p[:2]) for p in coords])]
    elif kind == "MultiLineString":
        return [path_d([frame.xy(*p[:2]) for p in line]) for line in coords]
    else:
        return []
    return [path_d([frame.xy(*p[:2]) for p in ring]) + " Z" for ring in rings]


def nice(value, steps=(1, 2, 2.5, 5)):
    exp = 10 ** math.floor(math.log10(value))
    for s in steps + (10,):
        if s * exp >= value:
            return s * exp
    return 10 * exp


# ---------------------------------------------------------------------- the report
class Report:
    def __init__(self, response, request, b_output, session=None, place=None):
        self.r = response
        self.request = request or {}
        self.g = (b_output or {}).get("_report")
        self.session = session
        self.place = place or {}
        self.A, self.B, self.C = (response.get(m) or {} for m in "ABC")
        self.a, self.b, self.c = (m.get("result") for m in (self.A, self.B, self.C))
        self.fig_no, self.table_no = 0, 0
        self.figures, self.tables = [], []
        self.name = response["spring"]["name"]
        self.sites = (self.c or {}).get("sites") or []
        if self.g is not None:
            self.inside = self.g["catchment"]
            self.frame = MapFrame(self.g, self._extent())
            f = self.frame
            self.hs = hillshade(np.where(self.g["z"] > -1000, self.g["z"], np.nan), f.dx, f.dy)
            self.hs = np.nan_to_num(self.hs, nan=0.7)

    # ---------------------------------------------------------------- layout helpers
    def _extent(self, grow=1.3, min_span=MIN_SPAN_M):
        g = self.g
        rows, cols = np.nonzero(g["catchment"])
        t = g["t"]
        lons = list(t.c + (cols + 0.5) * t.a) + [self.r["spring"]["longitude"]]
        lats = list(t.f + (rows + 0.5) * t.e) + [self.r["spring"]["latitude"]]
        for s in self.sites:
            lons.append(s["longitude"])
            lats.append(s["latitude"])
        for zn in (self.b or {}).get("recharge_zones") or []:
            geom = (zn.get("geojson") or {}).get("geometry")
            for ring in (geom or {}).get("coordinates", [])[:1] if geom and geom["type"] == "Polygon" else []:
                lons += [p[0] for p in ring]
                lats += [p[1] for p in ring]
        west, east, south, north = min(lons), max(lons), min(lats), max(lats)
        span_x = max((east - west) * g["m_lon"] * grow, min_span) / g["m_lon"]
        span_y = max((north - south) * g["m_lat"] * grow, min_span) / g["m_lat"]
        cx, cy = (west + east) / 2, (south + north) / 2
        return cx - span_x / 2, cy - span_y / 2, cx + span_x / 2, cy + span_y / 2

    def figure(self, title, svg, legend=None, note=None):
        self.fig_no += 1
        caption = f"Figure {self.fig_no}: {title}"
        self.figures.append(caption)
        items = ""
        if legend:
            items = '<div class="legend">' + "".join(
                f'<span><i style="background:{c}{";border:1px solid #888" if c.lower() in ("#ffffff", "#f0f0f0", "#ffffcc", "#ffffbf") else ""}"></i>{esc(lbl)}</span>'
                if kind == "fill" else f'<span><i class="{kind}" style="border-color:{c};color:{c}"></i>{esc(lbl)}</span>'
                for lbl, c, kind in legend) + "</div>"
        return (f'<figure><div class="map-title">{esc(title).upper()} · {esc(self.name).upper()}</div>{svg}{items}'
                + (f'<p class="fig-note">{note}</p>' if note else "") + f"<figcaption>{esc(caption)}</figcaption></figure>")

    def table(self, title, head, rows, cls=""):
        self.table_no += 1
        caption = f"Table {self.table_no}: {title}"
        self.tables.append(caption)
        thead = "".join(f"<th>{esc(h)}</th>" for h in head) if head else ""
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
        return (f'<table class="t {cls}">' + (f"<thead><tr>{thead}</tr></thead>" if thead else "")
                + f"<tbody>{body}</tbody></table><p class='tcap'>{esc(caption)}</p>")

    # ---------------------------------------------------------------- map drawing
    def raster(self, rgb_inside, outside="hillshade"):
        """The crop as a PNG: the layer colour inside the catchment (shaded by relief), grey relief outside."""
        f = self.frame
        hs = f.crop(self.hs)[..., None]
        inside = f.crop(self.inside)[..., None]
        if rgb_inside is None:
            rgb = 120 + 125 * hs.repeat(3, axis=2)
        else:
            layer = f.crop(rgb_inside) * (0.72 + 0.28 * hs)
            grey = 200 + 50 * hs.repeat(3, axis=2) if outside == "hillshade" else np.full(layer.shape, 255.0)
            rgb = np.where(inside, layer, grey)
        return f'<image href="{png_uri(np.clip(rgb, 0, 255).astype(np.uint8))}" x="0" y="0" width="{f.w:.1f}" height="{f.h:.1f}" preserveAspectRatio="none" style="image-rendering:pixelated"/>'

    def class_rgb(self, idx, colors):
        """An RGB grid from an integer class grid (-1 = no class, drawn light grey)."""
        lut = np.array([hex_rgb(c) for c in colors] + [hex_rgb("#dddddd")])
        return lut[np.where(idx >= 0, idx, len(colors))]

    def overlays(self, catchment=True, streams=True, zones=False, structure=False, sites=True, labels=True, contours=None, arrows=False,
                 links=False, catchment_color=CATCH_COLOR):
        f = self.frame
        out = []
        if contours:
            out.append(self.contour_svg(*contours))
        if arrows:
            out.append(self.arrow_svg())
        if streams and self.b:
            for feat in (self.b.get("streams") or {}).get("features", []):
                order = feat["properties"].get("order", 1)
                for d in geojson_paths(f, feat["geometry"]):
                    out.append(f'<path d="{d}" fill="none" stroke="{STREAM_COLOR}" stroke-width="{0.8 + 0.5 * order:.1f}" opacity="0.9"/>')
        if structure and self.b:
            for key, color, dash in (("faults", "#b2182b", ""), ("mapped_lineaments", "#762a83", "6 3"), ("lineaments", "#9970ab", "2 3")):
                for feat in (self.b.get(key) or {}).get("features", []):
                    for d in geojson_paths(f, feat["geometry"]):
                        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" stroke-dasharray="{dash}"/>')
        if zones and self.b:
            for zn in self.b.get("recharge_zones") or []:
                color = ZONE_COLORS.get(zn["id"], "#1b7837")
                for d in geojson_paths(f, (zn.get("geojson") or {}).get("geometry")):
                    out.append(f'<path d="{d}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="2.6"/>')
                geom = (zn.get("geojson") or {}).get("geometry") or {}
                ring = geom.get("coordinates", [[]])[0] if geom.get("type") == "Polygon" else (geom.get("coordinates", [[[]]])[0][0] if geom.get("type") == "MultiPolygon" else [])
                if ring:
                    x, y = f.xy(sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
                    out.append(self.label(x - 8, y + 5, zn["id"], size=14, weight=800, color=color))
        if catchment and self.b and self.b.get("surface_catchment"):
            for d in geojson_paths(f, (self.b["surface_catchment"].get("geojson") or {}).get("geometry")):
                out.append(f'<path d="{d}" fill="none" stroke="{catchment_color}" stroke-width="2.4"/>')
        if links:
            sx, sy = f.xy(self.r["spring"]["longitude"], self.r["spring"]["latitude"])
            for i, s in enumerate(self.sites, start=1):
                x, y = f.xy(s["longitude"], s["latitude"])
                out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{sx:.1f}" y2="{sy:.1f}" stroke="#0b63c5" stroke-width="2.4" '
                           f'stroke-dasharray="7 4" marker-end="url(#arrow)"/>')
                mx, my = (x + sx) / 2, (y + sy) / 2
                out.append(self.label(mx + 6, my, f"A{i}-A{i}'", size=11, color="#0b63c5"))
        if sites:
            for i, s in enumerate(self.sites, start=1):
                x, y = f.xy(s["longitude"], s["latitude"])
                out.append(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" fill="{HP_COLOR}" stroke="#fff" stroke-width="1.5"/>')
                if labels:
                    out.append(self.label(x + 9, y - 8, f"HP{i}: {s['name']}", size=11))
            x, y = f.xy(self.r["spring"]["longitude"], self.r["spring"]["latitude"])
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{SPRING_COLOR}" stroke="#fff" stroke-width="2"/>')
            if labels:
                out.append(self.label(x + 10, y + 16, "Spring", size=12, weight=700))
        return "".join(out)

    @staticmethod
    def label(x, y, text, size=11, weight=600, color="#111"):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" stroke="#fff" '
                f'stroke-width="3" paint-order="stroke">{esc(text)}</text>')

    def contour_svg(self, interval, color="#7a5230", label_every=5):
        f = self.frame
        z = f.crop(self.g["z"]).astype(float)
        z[z <= -1000] = np.nan
        lo, hi = np.nanmin(z), np.nanmax(z)
        out = []
        level = math.ceil(lo / interval) * interval
        while level <= hi:
            major = round(level / interval) % label_every == 0
            for line in contour_lines(z, level):
                pts = [f.cell_xy(c, r) for c, r in line]
                if len(pts) < 2:
                    continue
                out.append(f'<path d="{path_d(pts)}" fill="none" stroke="{color}" stroke-width="{1.2 if major else 0.6}" opacity="0.85"/>')
                if major and len(pts) > 12:
                    x, y = pts[len(pts) // 2]
                    out.append(self.label(x, y, f"{level:.0f}", size=9, weight=500, color="#5a3a1a"))
            level += interval
        return "".join(out)

    def arrow_svg(self):
        """Downslope arrows (the direction water moves over and through the slope), inside the catchment."""
        f = self.frame
        z = f.crop(self.g["z"]).astype(float)
        inside = f.crop(self.inside)
        gy, gx = np.gradient(z, f.dy, f.dx)
        step = max(2, int(round(60 / max(f.dx, f.dy))))
        out = []
        for r in range(step // 2, z.shape[0], step):
            for c in range(step // 2, z.shape[1], step):
                if not inside[r, c]:
                    continue
                vx, vy = -gx[r, c], gy[r, c]  # downslope: columns go east, rows go south (so north-up flips y)
                norm = math.hypot(vx, vy)
                if norm < 1e-3:
                    continue
                x, y = f.cell_xy(c, r)
                length = 14
                x2, y2 = x + vx / norm * length, y + vy / norm * length
                out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#08519c" stroke-width="1.3" marker-end="url(#arrow-sm)"/>')
        return "".join(out)

    def furniture(self):
        """Frame, graticule labels (degrees, minutes, seconds), north arrow and scale bar."""
        f = self.frame
        out = [f'<rect x="0" y="0" width="{f.w:.1f}" height="{f.h:.1f}" fill="none" stroke="#333" stroke-width="1"/>']
        span = f.east - f.west
        step = nice(span / 4, (1, 2, 2.5, 5)) if span > 0 else 0.001
        lon = math.ceil(f.west / step) * step
        while lon < f.east:
            x, _ = f.xy(lon, f.north)
            out.append(f'<line x1="{x:.1f}" y1="{f.h:.1f}" x2="{x:.1f}" y2="{f.h + 5:.1f}" stroke="#333"/>'
                       f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="-5" stroke="#333"/>'
                       f'<text x="{x:.1f}" y="{f.h + 16:.1f}" font-size="9" text-anchor="middle" fill="#333">{dms(lon, "E", "W")[:-4]}"E</text>')
            lon += step
        span_lat = f.north - f.south
        step = nice(span_lat / 4, (1, 2, 2.5, 5)) if span_lat > 0 else 0.001
        lat = math.ceil(f.south / step) * step
        while lat < f.north:
            _, y = f.xy(f.west, lat)
            out.append(f'<line x1="0" y1="{y:.1f}" x2="-5" y2="{y:.1f}" stroke="#333"/>'
                       f'<line x1="{f.w:.1f}" y1="{y:.1f}" x2="{f.w + 5:.1f}" y2="{y:.1f}" stroke="#333"/>'
                       f'<text x="-8" y="{y + 3:.1f}" font-size="9" text-anchor="end" fill="#333">{dms(lat, "N", "S")[:-4]}"N</text>')
            lat += step
        # north arrow
        nx, ny = f.w - 30, 18
        out.append(f'<g transform="translate({nx:.1f},{ny:.1f})"><polygon points="0,0 9,26 0,20 -9,26" fill="#222"/>'
                   f'<polygon points="0,0 0,20 -9,26" fill="#fff" stroke="#222" stroke-width="1"/>'
                   f'<text x="0" y="40" font-size="12" font-weight="700" text-anchor="middle" fill="#222" stroke="#fff" stroke-width="3" paint-order="stroke">N</text></g>')
        # scale bar
        metres = nice((f.w / 4) / f.px_per_m, (1, 2, 2.5, 5))
        bar = metres * f.px_per_m
        x0, y0 = 14, f.h - 18
        unit = f"{metres / 1000:g} km" if metres >= 1000 else f"{metres:g} m"
        out.append(f'<g><rect x="{x0 - 6}" y="{y0 - 16}" width="{bar + 58:.1f}" height="28" fill="#fff" opacity="0.85"/>'
                   f'<rect x="{x0}" y="{y0}" width="{bar / 2:.1f}" height="5" fill="#222"/>'
                   f'<rect x="{x0 + bar / 2:.1f}" y="{y0}" width="{bar / 2:.1f}" height="5" fill="#fff" stroke="#222" stroke-width="0.8"/>'
                   f'<text x="{x0}" y="{y0 - 4}" font-size="9" fill="#222">0</text>'
                   f'<text x="{x0 + bar:.1f}" y="{y0 - 4}" font-size="9" text-anchor="middle" fill="#222">{unit}</text></g>')
        return "".join(out)

    def svg(self, body):
        f = self.frame
        defs = ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#0b63c5"/></marker>'
                '<marker id="arrow-sm" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#08519c"/></marker>'
                f'<clipPath id="clip{self.fig_no}"><rect x="0" y="0" width="{f.w:.1f}" height="{f.h:.1f}"/></clipPath></defs>')
        pad_l, pad_t, pad_b, pad_r = 78, 10, 24, 12
        return (f'<svg class="map" viewBox="{-pad_l} {-pad_t} {f.w + pad_l + pad_r:.1f} {f.h + pad_t + pad_b:.1f}" '
                f'xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif">{defs}'
                f'<g clip-path="url(#clip{self.fig_no})">{body}</g>{self.furniture()}</svg>')

    # ---------------------------------------------------------------- statistics inside the catchment
    def shares(self, idx, labels):
        """[(label, area ha, %)] of an integer class grid inside the catchment, largest first."""
        inside = self.inside
        total = inside.sum()
        out = []
        for i, lbl in enumerate(labels):
            n = int((inside & (idx == i)).sum())
            if n:
                out.append((lbl, n * self.g["cell_ha"], 100 * n / total))
        return sorted(out, key=lambda x: -x[1])

    def share_table(self, title, rows):
        return self.table(title, ["Class", "Area (ha)", "Share of catchment"],
                          [[esc(lbl), f"{ha:.2f}", f"{pct:.1f}%"] for lbl, ha, pct in rows], "narrow")

    @staticmethod
    def share_words(rows, n=2):
        return " and ".join(f"{lbl.lower()} ({pct:.0f}%)" for lbl, _, pct in rows[:n])

    # ---------------------------------------------------------------- sections
    def cover(self):
        s = self.r["spring"]
        p = self.place
        where = [f"{esc(p['village'])} village" if p.get("village") else "", f"Block: {esc(p['block'])}" if p.get("block") else "",
                 f"District: {esc(p['district'])}" if p.get("district") else "", f"State: {esc(p['state'])}" if p.get("state") else ""]
        coords = [f"Spring: {dms(s['latitude'], 'N', 'S')}, {dms(s['longitude'], 'E', 'W')}"]
        coords += [f"HP{i} ({esc(x['name'])}): {dms(x['latitude'], 'N', 'S')}, {dms(x['longitude'], 'E', 'W')}" for i, x in enumerate(self.sites, start=1)]
        created = self.r.get("created_at") or datetime.now().isoformat(timespec="seconds")
        return f"""<section class="cover">
<div class="cover-top">SCIENTIFIC HYDROGEOLOGICAL ASSESSMENT REPORT</div>
<div class="cover-project">Spring vulnerability, springshed and Direct Injection (DI) recharge impact</div>
<h1>{esc(self.name)}</h1>
<div class="cover-place">{"<br>".join(w for w in where if w) or "Location from the coordinates below"}</div>
<div class="cover-gps">GPS coordinates<br>{"<br>".join(coords)}</div>
<div class="cover-foot">Prepared with the Spring Health &amp; Recharge Planner (RDI / WATSAN)<br>
Run {esc(self.r.get('run_id'))} · {esc(datetime.fromisoformat(created).strftime('%d %B %Y, %H:%M'))} · map set {esc(self.r.get('map_set'))}<br>
<span class="small">A desk assessment from maps and the field answers entered. The maps are drawn by the tool from the same data the model uses.
They are not field-verified; walk the recharge zones with a geologist before spending money on works.</span></div>
</section>"""

    def contents(self, sections):
        items = "".join(f"<li>{esc(t)}</li>" if not sub else f"<li class='sub'>{esc(t)}</li>" for t, sub in sections)
        figs = "".join(f"<li>{esc(x)}</li>" for x in self.figures)
        tabs = "".join(f"<li>{esc(x)}</li>" for x in self.tables)
        return (f'<section class="toc"><h2>Table of contents</h2><ul class="toc-list plain">{items}</ul>'
                f'<h3>List of figures</h3><ul class="plain">{figs}</ul><h3>List of tables</h3><ul class="plain">{tabs}</ul></section>')

    def location(self):
        s = self.r["spring"]
        p = self.place
        rows = [["Spring", esc(self.name), dms(s["latitude"], "N", "S"), dms(s["longitude"], "E", "W"),
                 f"{s['latitude']:.6f}, {s['longitude']:.6f}", fmt(s.get("elevation_m"))]]
        for i, x in enumerate(self.sites, start=1):
            rows.append([f"HP{i} (DI handpump)", esc(x["name"]), dms(x["latitude"], "N", "S"), dms(x["longitude"], "E", "W"),
                         f"{x['latitude']:.6f}, {x['longitude']:.6f}", fmt(x.get("elevation_m"))])
        text = [f"<p><b>Village:</b> {esc(p.get('village') or '-')} &nbsp; <b>Block:</b> {esc(p.get('block') or '-')} &nbsp; "
                f"<b>District:</b> {esc(p.get('district') or '-')} &nbsp; <b>State:</b> {esc(p.get('state') or '-')}<br>"
                "<b>Projection:</b> WGS 84 (maps drawn in geographic coordinates; areas computed in metres, UTM zone 44N for distances).</p>"]
        out = "<h2>1. Location and site characteristics</h2>" + "".join(text)
        out += self.table("Spring and handpump positions", ["Point", "Name", "Latitude", "Longitude", "Decimal degrees", "Elevation (m)"], rows)
        if self.sites:
            words = []
            for i, x in enumerate(self.sites, start=1):
                h = x.get("height_above_spring_m")
                rel = "" if h is None else (f"{h} m above the spring" if h > 0 else f"{-h} m below the spring" if h < 0 else "level with the spring")
                words.append(f"HP{i} ({esc(x['name'])}) is {fmt(x.get('distance_to_spring_m'))} m from the spring" + (f" and {rel}" if rel else ""))
            out += "<p>" + "; ".join(words) + ".</p>"
        if self.g is not None:
            near = self.frame
            self.frame = MapFrame(self.g, self._extent(grow=2.6, min_span=1600))
            svg = self.svg(self.raster(None) + satellite_tiles(self.frame) + self.overlays(zones=False, catchment_color="#ffe94d"))
            self.frame = near
            out += self.figure("Location map", svg, [("Spring", SPRING_COLOR, "dot"), ("DI handpump", HP_COLOR, "square"),
                                                     ("Catchment to the ridge", "#e0c400", "line"), ("Drainage line", STREAM_COLOR, "line")],
                               "The spring's catchment (yellow) on the satellite image. " + SATELLITE_CREDIT)
        return out

    def study_area(self):
        out = ["<h2>2. Study area analysis</h2>"]
        b, g = self.b or {}, self.g
        geo = b.get("geology") or {}
        rows = []
        if self.sites:
            out.append("<h3>Handpump characteristics</h3>")
            for i, x in enumerate(self.sites, start=1):
                path = x.get("flow_path") or {}
                h = x.get("height_above_spring_m")
                zone = x.get("zone_id")
                lines = [f"<b>HP{i}: {esc(x['name'])}</b>", f"Position {dms(x['latitude'], 'N', 'S')}, {dms(x['longitude'], 'E', 'W')}; ground about {fmt(x.get('elevation_m'))} m",
                         f"Bore depth used: {fmt(x.get('depth_m'))} m" + ("" if x.get("depth_given") else " (assumed)")
                         + (f"; water injected at about {path['injection_elevation_m']} m above sea level" if path.get("injection_elevation_m") is not None else ""),
                         f"Roof area: {fmt(x.get('roof_area_m2'))} m²; water it can inject: about {fmt(x.get('volume_m3_per_year'))} m³ a year",
                         esc(x.get("location_note") or "") + (f" (zone {zone})" if zone else "")]
                if h is not None:
                    lines.append(f"{abs(h)} m {'above' if h >= 0 else 'below'} the spring, {fmt(x.get('distance_to_spring_m'))} m away")
                out.append("<ul class='facts'>" + "".join(f"<li>{w}</li>" for w in lines if w) + "</ul>")
        out.append("<h3>Spring characteristics</h3>")
        s = self.r["spring"]
        facts = [f"Position {dms(s['latitude'], 'N', 'S')}, {dms(s['longitude'], 'E', 'W')}; elevation about {fmt(s.get('elevation_m'))} m"]
        if geo:
            facts.append(f"Rock at the spring (GSI 1:50k): {esc(geo.get('unit') or geo.get('rock_class'))}")
            if geo.get("nearest_fault_m") is not None:
                facts.append(f"Nearest mapped fault: {fmt(geo['nearest_fault_m'])} m" + (f" ({esc(geo['nearest_fault_name'])})" if geo.get("nearest_fault_name") else ""))
        answers = (self.request.get("field") or {})
        for key, label, unit in (("monsoon_flow_lpm", "Monsoon flow", "L/min"), ("lean_flow_lpm", "Lean-season flow", "L/min")):
            if answers.get(key) not in (None, ""):
                facts.append(f"{label}: {esc(answers[key])} {unit}")
        if self.a:
            facts.append(f"Vulnerability: {esc(self.a.get('class'))} ({self.a.get('score')} of 100)")
        if b:
            facts.append(f"Catchment to the ridge: {b['surface_catchment']['area_ha']:.1f} ha")
        out.append("<ul class='facts'>" + "".join(f"<li>{w}</li>" for w in facts) + "</ul>")
        if g is not None:
            out.append(self.summary_table())
        return "".join(out)

    def summary_table(self):
        b = self.b or {}
        geo = b.get("geology") or {}
        rows = []
        soil_rows, depth_rows, lc_rows, slope_rows = self._soil(), self._depth(), self._land(), self._slope()
        if soil_rows:
            rows.append(["Dominant soil texture (SoilGrids, top 30 cm)", esc(self.share_words(soil_rows))])
        if depth_rows:
            rows.append(["Soil depth to bedrock (SoilGrids)", esc(self.share_words(depth_rows))])
        if slope_rows:
            rows.append(["Slope", esc(self.share_words(slope_rows))])
        if lc_rows:
            rows.append(["Land cover (ESA WorldCover 2021)", esc(self.share_words(lc_rows, 3))])
        if geo:
            rows.append(["Rock at the spring (GSI 1:50k)", esc(geo.get("unit") or geo.get("rock_class"))])
        aq = next((a for a in (self.c or {}).get("assumptions", []) if a["id"] == "specific_yield"), None)
        if aq:
            rows.append(["Aquifer type used for DI", esc(aq["note"].split(" (")[0]) + f"; specific yield {esc(aq['value'])}%"])
        if self.g is not None:
            z = self.g["z"][self.inside]
            rows.append(["Elevation of the catchment", f"{z.min():.0f}-{z.max():.0f} m"])
        rows.append(["Catchment to the ridge", f"{b['surface_catchment']['area_ha']:.1f} ha" if b else "-"])
        zones = b.get("recharge_zones") or []
        if zones:
            rows.append(["Top recharge zones", "; ".join(f"{zn['id']} {zn['area_ha']:.1f} ha, potential {zn['mean_potential']:.2f}" for zn in zones)])
        return self.table("Summary of spring details", ["Parameter", "Description"], rows)

    def methodology(self):
        factors = (self.b or {}).get("factors") or []
        weights = ", ".join(f"{esc(f['name'].lower())} {f['weight_pct']}%" for f in factors)
        return f"""<h2>3. Methodology</h2>
<p>The assessment combines the field answers entered for the spring with map layers, the same overlay approach used in the SRHU
geohydrology reports. The 30 m elevation model gives the elevation, slope, aspect, drainage lines and the catchment (the valley above the
spring up to the ridges). Geology, geomorphology, soil texture, soil depth and land cover are read for every 30 m cell of that area. Each
layer is scored for how well it lets rain soak in, and the scores are combined by weight ({weights or 'see the assumptions'}) into a
recharge-potential map. The best patches that can send water to the spring, on its own slope or along a fault, crack or the tilt of the rock
layers, are picked as recharge zones R1-R3. Vulnerability is scored from the field answers and location stresses. For each DI handpump the
water that the roof can inject is worked out from the rainfall, and the share reaching the spring from where the handpump sits and how deep it injects.</p>
<p><b>Data sources:</b></p>
<ul class="plain two">
<li>Copernicus DEM GLO-30 (30 m)</li><li>ESA WorldCover 2021 (10 m) and Sentinel-2 NDVI</li>
<li>GSI Geology 1:50k (NGDR)</li><li>GSI Bhukosh geomorphology and lineaments 1:250k</li>
<li>SoilGrids 250 m texture and depth to bedrock</li><li>{esc(((self.c or {}).get('rain') or {}).get('source') or 'IMD / CHIRPS rainfall')}</li>
<li>ERA5 snowfall (winters 2019-2025)</li><li>Field answers and GPS entered in the tool</li>
</ul>"""

    # each thematic section returns (title, html)
    def _slope(self):
        if self.g is None:
            return []
        sl = self.g["slope"]
        self._slope_idx = np.digitize(sl, [10, 20, 30, 40])
        return self.shares(self._slope_idx, [c for c, _ in SLOPE_CLASSES])

    def _aspect(self):
        f = self.frame
        gy, gx = np.gradient(np.where(self.g["z"] > -1000, self.g["z"], np.nan), f.dy, f.dx)
        # rows run south, so the uphill-north component is -gy; aspect is the direction the slope faces (downhill)
        aspect = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
        idx = (((aspect + 22.5) % 360) // 45).astype(int)
        idx[self.g["slope"] < 2] = -1
        self._aspect_idx = idx
        return self.shares(idx, [a for a, _ in ASPECTS])

    def _soil(self):
        soil = self.g.get("soil") if self.g else None
        if soil is None:
            return []
        names = list(SOIL_COLORS)
        clay, sand = soil["clay"], soil["sand"]
        idx = np.full(clay.shape, -1)
        ok = np.isfinite(clay) & np.isfinite(sand)
        labels = np.vectorize(lambda c, s: module_b.soil_class(c, s).split(" (")[0])(np.where(ok, clay, 0), np.where(ok, sand, 0))
        for i, n in enumerate(names):
            idx[ok & (labels == n)] = i
        self._soil_idx = idx
        return self.shares(idx, names)

    def _depth(self):
        d = self.g.get("soil_depth") if self.g else None
        if d is None:
            return []
        names = list(DEPTH_COLORS)
        idx = np.where(np.isfinite(d), np.digitize(d, [50, 100, 150]), -1)
        self._depth_idx = idx
        return self.shares(idx, names)

    def _land(self):
        land = self.g.get("land") if self.g else None
        if land is None:
            return []
        codes = sorted(WORLDCOVER_COLORS)
        idx = np.full(land.shape, -1)
        for i, code in enumerate(codes):
            idx[land == code] = i
        self._land_idx, self._land_codes = idx, codes
        return self.shares(idx, [module_b.WORLDCOVER[c] for c in codes])

    def thematic(self):
        if self.g is None:
            return [("3.1 Thematic maps", "<p>The map layers were not available for this run, so the thematic maps could not be drawn.</p>")]
        f, g, out = self.frame, self.g, []
        z_in = g["z"][self.inside]
        z_s = g["z"][g["row"], g["col"]]
        sites_above = [x for x in self.sites if (x.get("height_above_spring_m") or 0) > 0]

        # DEM
        lo, hi = float(z_in.min()), float(z_in.max())
        edges = np.linspace(lo, hi, 6)
        idx = np.clip(np.digitize(g["z"], edges[1:-1]), 0, 4)
        legend = [(f"{edges[i]:.0f}-{edges[i + 1]:.0f} m", DEM_COLORS[i], "fill") for i in range(5)]
        svg = self.svg(self.raster(self.class_rgb(idx, DEM_COLORS)) + self.overlays())
        relation = ""
        if self.sites:
            relation = (f" {len(sites_above)} of the {len(self.sites)} handpumps {'is' if len(sites_above) == 1 else 'are'} higher than the spring, "
                        "so water injected there has a natural gradient towards it." if sites_above else
                        " The handpumps are not higher than the spring, so water injected there has no natural gradient towards it.")
        text = (f"<p>The elevation model shows the catchment ranging from about {lo:.0f} m to {hi:.0f} m above sea level, a relief of "
                f"{hi - lo:.0f} m. The spring emerges at about {z_s:.0f} m, {'at the lowest point' if z_s - lo < 10 else f'{z_s - lo:.0f} m above the lowest cell'} "
                f"of the catchment.{relation}</p>")
        out.append(("3.1 Digital Elevation Model (DEM)", text + self.figure("Digital Elevation Model (DEM)", svg, legend)))

        # soil texture
        rows = self._soil()
        if rows:
            names = list(SOIL_COLORS)
            svg = self.svg(self.raster(self.class_rgb(self._soil_idx, [SOIL_COLORS[n] for n in names])) + self.overlays())
            soil = g["soil"]
            clay, sand = soil["clay"][self.inside], soil["sand"][self.inside]
            coarse = soil.get("coarse")
            coarse_in = coarse[self.inside] if coarse is not None else None
            dominant = rows[0][0].lower()
            soaks = {"sandy": "drains fast and lets water soak in quickly", "sandy loam": "lets water soak in well",
                     "loam or silt loam": "balances soaking in and holding moisture", "clay loam": "soaks water in moderately and holds moisture well",
                     "clay": "soaks water in slowly, so more of the rain runs off"}[dominant]
            text = (f"<p>The catchment is mostly {esc(self.share_words(rows))}. {dominant.capitalize()} soil {soaks}. "
                    f"On average the top 30 cm hold about {np.nanmean(clay):.0f}% clay and {np.nanmean(sand):.0f}% sand"
                    + (f", with {np.nanmean(coarse_in):.0f}% stones and gravel" if coarse_in is not None and np.isfinite(coarse_in).any() else "")
                    + ". SoilGrids is a 250 m global estimate, so small patches of terrace or forest soil are not shown.</p>")
            legend = [(n, SOIL_COLORS[n], "fill") for n in names if any(r[0] == n for r in rows)]
            out.append(("3.2 Soil texture analysis", text + self.figure("Soil texture map", svg, legend) + self.share_table("Soil texture in the catchment", rows)))

        # slope
        rows = self._slope()
        svg = self.svg(self.raster(self.class_rgb(self._slope_idx, [c for _, c in SLOPE_CLASSES])) + self.overlays())
        sl_in = g["slope"][self.inside]
        sl_s = g["slope"][g["row"], g["col"]]
        text = (f"<p>Slopes in the catchment range from about {np.percentile(sl_in, 5):.0f}° to {np.percentile(sl_in, 95):.0f}° "
                f"(middle 90% of the area), mostly {esc(self.share_words(rows))}. The ground at the spring slopes at about {sl_s:.0f}°. "
                "Gentle and moderate slopes hold rain long enough for it to soak in; steep slopes shed it as runoff and need trenches or "
                "planting to slow the water down.</p>")
        out.append(("3.3 Slope analysis", text + self.figure("Slope map", svg, [(c, col, "fill") for c, col in SLOPE_CLASSES])
                     + self.share_table("Slope classes in the catchment", rows)))

        # aspect
        rows = self._aspect()
        svg = self.svg(self.raster(self.class_rgb(self._aspect_idx, [c for _, c in ASPECTS])) + self.overlays())
        sunny = sum(p for lbl, _, p in rows if lbl in ("South", "South-west", "South-east", "West"))
        text = (f"<p>The catchment mostly faces {esc(self.share_words(rows))}. "
                + (f"About {sunny:.0f}% faces south or west, which gets more sun, so soils dry out faster and less water is left to soak in. "
                   if sunny >= 50 else f"Only {sunny:.0f}% faces south or west; the shadier slopes keep their soil moist for longer, which helps recharge. ")
                + "Aspect does not enter the recharge-potential score; it is shown for context, as in the SRHU reports.</p>")
        out.append(("3.4 Aspect analysis", text + self.figure("Aspect map", svg, [(c, col, "fill") for c, col in ASPECTS])
                     + self.share_table("Aspect in the catchment", rows)))

        # contours, drainage and hydraulic gradient
        relief = float(np.nanmax(f.crop(g["z"])) - np.nanmin(f.crop(g["z"])))
        interval = 10 if relief < 250 else 20 if relief < 600 else 50
        svg = self.svg(self.raster(None) + self.overlays(contours=(interval,), arrows=True))
        sc = (self.b or {}).get("surface_catchment") or {}
        grad = []
        for i, x in enumerate(self.sites, start=1):
            p = x.get("flow_path") or {}
            if p.get("hydraulic_gradient") is not None:
                grad.append(f"HP{i} to the spring: gradient {p['hydraulic_gradient']:.2f} ({p['gradient_basis']})")
        text = (f"<p>Contours are drawn every {interval} m (labelled every {interval * 5} m). The arrows show the downhill direction across the "
                "catchment, which is the way rain runs off and, on these hill slopes, the way shallow groundwater moves. "
                "Drainage lines that drain more than 10 ha are shown in blue"
                + (f"; the catchment follows the drainage line {sc.get('snapped_m')} m from the spring" if (sc.get("snapped_m") or 0) >= 15 else "")
                + ".</p>" + ("<ul class='bullets'>" + "".join(f"<li>{esc(w)}</li>" for w in grad) + "</ul>" if grad else ""))
        out.append(("3.5 Hydraulic gradient, contour and drainage analysis",
                    text + self.figure("Hydraulic gradient, contour and drainage map", svg,
                                       [("Contour", "#7a5230", "line"), ("Drainage line", STREAM_COLOR, "line"), ("Downhill flow direction", "#08519c", "line"),
                                        ("Catchment", CATCH_COLOR, "line")])))

        # geology
        units = g["unit_names"]
        if (units != "").any():
            names = [n for n in dict.fromkeys(units[self.inside]) if n] or [n for n in dict.fromkeys(f.crop(units).ravel()) if n]
            names = names[:len(CATEGORY_COLORS)]
            idx = np.full(units.shape, -1)
            for i, n in enumerate(names):
                idx[units == n] = i
            svg = self.svg(self.raster(self.class_rgb(idx, CATEGORY_COLORS[:len(names)])) + self.overlays(structure=True))
            rows = self.shares(idx, names)
            geo = (self.b or {}).get("geology") or {}
            n_faults = len(((self.b or {}).get("faults") or {}).get("features", []))
            n_lin = len(((self.b or {}).get("mapped_lineaments") or {}).get("features", [])) + len(((self.b or {}).get("lineaments") or {}).get("features", []))
            text = (f"<p>The catchment is underlain by {esc(self.share_words(rows))} (GSI 1:50k). In these hard rocks, water moves mainly "
                    "through joints, fractures and weathered zones rather than through the rock itself, so cracks and faults decide where recharge "
                    f"reaches the spring. {n_faults} mapped fault{'s' if n_faults != 1 else ''} and {n_lin} lineament{'s' if n_lin != 1 else ''} "
                    "(straight features that may be cracks) cross the map"
                    + (f"; the nearest fault is {fmt(geo['nearest_fault_m'])} m from the spring" if geo.get("nearest_fault_m") is not None else "")
                    + ".</p>")
            legend = [(n.capitalize()[:80], CATEGORY_COLORS[i], "fill") for i, n in enumerate(names)]
            legend += [("GSI fault", "#b2182b", "line"), ("Mapped lineament (1:250k)", "#762a83", "dash"), ("Lineament from the DEM", "#9970ab", "dot-line")]
            out.append(("3.6 Geological analysis", text + self.figure("Geological map", svg, legend) + self.share_table("Rock units in the catchment", rows)))

        # geomorphology
        gm = self.geomorph()
        if gm is not None:
            idx, names = gm
            svg = self.svg(self.raster(self.class_rgb(idx, CATEGORY_COLORS[:len(names)])) + self.overlays())
            rows = self.shares(idx, names)
            text = (f"<p>The catchment falls in {esc(self.share_words(rows))} (GSI Bhukosh geomorphology, 1:250k). "
                    "Dissected structural hills have steep slopes and narrow valleys: they shed much of the rain as runoff, but water that "
                    "gets into the fractured rock and valley fill feeds springs like this one. At 1:250k this map shows the landform setting, "
                    "not slope-by-slope detail.</p>")
            out.append(("3.7 Geomorphological analysis", text + self.figure("Geomorphology map", svg,
                                                                            [(n, CATEGORY_COLORS[i], "fill") for i, n in enumerate(names)])))

        # soil depth
        rows = self._depth()
        if rows:
            names = list(DEPTH_COLORS)
            svg = self.svg(self.raster(self.class_rgb(self._depth_idx, [DEPTH_COLORS[n] for n in names])) + self.overlays())
            d_in = g["soil_depth"][self.inside]
            text = (f"<p>Soil depth to bedrock is mostly {esc(self.share_words(rows))}, about {np.nanmean(d_in):.0f} cm on average. "
                    "Deeper soil holds more rain and releases it slowly to the fractured rock below; thin soil over rock lets water run off "
                    "or pass straight into cracks. SoilGrids depth is a 250 m estimate: check a few pits in the recharge zones.</p>")
            out.append(("3.8 Soil depth analysis", text + self.figure("Soil depth map", svg, [(n, DEPTH_COLORS[n], "fill") for n in names])
                         + self.share_table("Soil depth in the catchment", rows)))

        # land use land cover
        rows = self._land()
        if rows:
            codes = self._land_codes
            svg = self.svg(self.raster(self.class_rgb(self._land_idx, [WORLDCOVER_COLORS[c] for c in codes])) + self.overlays())
            forest = sum(p for lbl, _, p in rows if lbl in ("Tree cover", "Shrubland"))
            built = sum(p for lbl, _, p in rows if lbl in ("Built-up", "Cropland", "Bare / sparse vegetation"))
            text = (f"<p>The catchment is {esc(self.share_words(rows, 3))} (ESA WorldCover 2021, 10 m from Sentinel images). "
                    + (f"Tree and shrub cover on {forest:.0f}% of the area slows runoff and lets rain soak in; protecting it protects the spring. "
                       if forest >= 40 else f"Only {forest:.0f}% has tree or shrub cover, so much of the rain runs off quickly; planting and "
                       "trenches on the open slopes would help recharge. ")
                    + (f"Farms, buildings and bare ground cover {built:.0f}%; terraces hold some water, roofs and roads shed it." if built >= 5 else "")
                    + "</p>")
            legend = [(module_b.WORLDCOVER[c], WORLDCOVER_COLORS[c], "fill") for c in codes if any(r[0] == module_b.WORLDCOVER[c] for r in rows)]
            out.append(("3.9 Land use land cover analysis", text + self.figure("Land use land cover map", svg, legend)
                         + self.share_table("Land use and land cover in the catchment", rows)))
        return out

    def geomorph(self):
        sec = getattr(self.session, "secondary", None) if self.session is not None else None
        if sec is None:
            return None
        try:
            import shapely
            from shapely import box
            v = sec.vectors
            if not v.get("ok"):
                return None
            f, g = self.frame, self.g
            xs, ys = g["xs"], g["ys"]
            hits = v["geomorph_tree"].query(box(f.west, f.south, f.east, f.north), predicate="intersects")
            names, idx = [], np.full(xs.shape, -1)
            for i in hits:
                geom, label = v["geomorph"][i]
                inside = shapely.contains_xy(geom, xs, ys) & (idx < 0)
                if inside.any():
                    label = (label or "Unnamed").strip().capitalize()
                    if label not in names:
                        names.append(label)
                    idx[inside] = names.index(label)
            names = names[:len(CATEGORY_COLORS)]
            idx[idx >= len(names)] = -1
            return (idx, names) if names else None
        except Exception:
            return None

    def recharge(self):
        out = ["<h2>4. Integrated groundwater recharge assessment</h2>"]
        b = self.b or {}
        zones = b.get("recharge_zones") or []
        factors = b.get("factors") or []
        if factors:
            out.append("<p>The layers above were combined into one recharge-potential score (0 to 1) for every 30 m cell that can send water "
                       "to the spring. Weights used: " + ", ".join(f"{esc(x['name'].lower())} {x['weight_pct']}%" for x in factors) + ".</p>")
        if self.g is not None:
            pot = self.g["potential"]
            idx = np.where(self.g["show"], np.clip((pot * 5).astype(int), 0, 4), -1)
            labels = [lbl for lbl, _ in module_b.LEGEND]
            svg = self.svg(self.raster(self.class_rgb(idx, POTENTIAL_COLORS), outside="hillshade") + self.overlays(zones=True))
            legend = [(lbl, POTENTIAL_COLORS[i], "fill") for i, lbl in enumerate(labels)] + [(f"Recharge zone {k}", c, "line") for k, c in ZONE_COLORS.items()]
            rows = self.shares(idx, labels)
            out.append(self.figure("Recharge potential and recharge zones R1-R3", svg, legend,
                                   "Colour shows recharge potential inside the catchment. Zones R1-R3 are the best patches that can send water to the spring."))
            if rows:
                out.append(self.share_table("Recharge potential in the catchment", rows))
        if zones:
            out.append("<p><b>Key factors supporting recharge:</b></p><ul class='bullets'>")
            for zn in zones:
                good, weak = module_b._zone_words(zn)
                text = f"<b>{zn['id']}</b>: {esc(zn['why'])}"
                if good:
                    text += f" Strong points: {esc(', '.join(good))}."
                if weak:
                    text += f" Weak points: {esc(', '.join(weak))}."
                out.append(f"<li>{text}</li>")
            out.append("</ul>")
            out.append(self.table("Recharge zones", ["Zone", "Area (ha)", "Link to the spring", "Height above spring (m)", "Mean slope", "Potential", "Land cover"],
                                  [[zn["id"], f"{zn['area_ha']:.1f}", esc(zn["link"]["name"]), f"{zn['height_above_spring_m']['min']}-{zn['height_above_spring_m']['max']}",
                                    f"{zn['mean_slope_deg']:.0f}°", f"{zn['mean_potential']:.2f}",
                                    esc(", ".join(f"{v}% {k.lower()}" for k, v in list(zn['land_cover_pct'].items())[:2]))] for zn in zones]))
        summary = b.get("summary") or []
        if summary:
            out.append("<p>" + " ".join(esc(x) for x in summary[:2]) + "</p>")
        # groundwater flow path map
        if self.g is not None and self.sites:
            svg = self.svg(self.raster(None) + satellite_tiles(self.frame)
                           + self.overlays(zones=True, contours=(self._interval(), "#ffe9b0"), links=True, catchment_color="#ffe94d"))
            out.append(self.figure("Groundwater flow path map", svg,
                                   [("Assumed flow path, handpump to spring", "#0b63c5", "dash"), *[(f"Recharge zone {k}", c, "line") for k, c in ZONE_COLORS.items()],
                                    ("Contour", "#7a5230", "line"), ("Spring", SPRING_COLOR, "dot"), ("DI handpump", HP_COLOR, "square")],
                                   "Each dashed line is the straight path used for that handpump's cross-section below. " + SATELLITE_CREDIT))
        return "".join(out)

    def _interval(self):
        f, g = self.frame, self.g
        relief = float(np.nanmax(f.crop(g["z"])) - np.nanmin(f.crop(g["z"])))
        return 10 if relief < 250 else 20 if relief < 600 else 50

    # ---------------------------------------------------------------- charts
    def cross_section(self, i, x):
        p = x.get("flow_path") or {}
        prof = p.get("profile")
        if not prof:
            return ""
        W, H, L, R, T, B = 640, 260, 56, 20, 16, 36
        d = [q[0] for q in prof]
        zs = [q[1] for q in prof]
        inj = p.get("injection_elevation_m")
        head = p.get("head_at_handpump_m") or p.get("ground_at_handpump_m")
        spring_z = p.get("spring_elevation_m")
        lo = min(zs + [v for v in (inj, spring_z) if v is not None]) - 15
        hi = max(zs + [head or zs[0]]) + 15
        length = max(d[-1], 1)
        X = lambda v: L + (v / length) * (W - L - R)  # noqa: E731
        Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)  # noqa: E731
        ground = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in prof)
        out = [f'<svg class="chart" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif">']
        out.append(f'<polygon points="{X(0):.1f},{Y(lo):.1f} {ground} {X(length):.1f},{Y(lo):.1f}" fill="#e9dcc6" stroke="none"/>')
        out.append(f'<polyline points="{ground}" fill="none" stroke="#7a5230" stroke-width="2"/>')
        step = nice((hi - lo) / 5)
        v = math.ceil(lo / step) * step
        while v <= hi:
            out.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#ccc" stroke-width="0.6"/>'
                       f'<text x="{L - 6}" y="{Y(v) + 3:.1f}" font-size="10" text-anchor="end" fill="#444">{v:.0f}</text>')
            v += step
        dstep = nice(length / 5)
        v = 0
        while v <= length + 1e-6:
            out.append(f'<text x="{X(v):.1f}" y="{H - B + 14}" font-size="10" text-anchor="middle" fill="#444">{v:.0f}</text>')
            v += dstep
        out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 4}" font-size="10" text-anchor="middle" fill="#444">Distance from HP{i} along the flow path (m)</text>'
                   f'<text x="12" y="{(T + H - B) / 2:.0f}" font-size="10" text-anchor="middle" fill="#444" transform="rotate(-90 12 {(T + H - B) / 2:.0f})">Elevation (m)</text>')
        if head is not None and spring_z is not None:
            out.append(f'<line x1="{X(0):.1f}" y1="{Y(head):.1f}" x2="{X(length):.1f}" y2="{Y(spring_z):.1f}" stroke="#0b63c5" stroke-width="1.8" stroke-dasharray="6 4"/>')
        if inj is not None:
            out.append(f'<line x1="{X(0):.1f}" y1="{Y(zs[0]):.1f}" x2="{X(0):.1f}" y2="{Y(inj):.1f}" stroke="#555" stroke-width="3"/>'
                       f'<circle cx="{X(0):.1f}" cy="{Y(inj):.1f}" r="5" fill="#0b63c5"/>'
                       + self.label(X(0) + 8, Y(inj) + 4, f"Injection at {inj} m ({p.get('depth_m'):g} m deep)", size=10))
        out.append(f'<rect x="{X(0) - 6:.1f}" y="{Y(zs[0]) - 12:.1f}" width="12" height="12" fill="{HP_COLOR}"/>' + self.label(X(0) + 8, Y(zs[0]) - 6, f"HP{i}", size=11, weight=700))
        if spring_z is not None:
            out.append(f'<circle cx="{X(length):.1f}" cy="{Y(spring_z):.1f}" r="6" fill="{SPRING_COLOR}" stroke="#fff" stroke-width="1.5"/>'
                       + self.label(X(length) - 44, Y(spring_z) - 10, "Spring", size=11, weight=700))
        out.append("</svg>")
        notes = [f"Length {fmt(p.get('length_m'))} m; ground at HP{i} {fmt(p.get('ground_at_handpump_m'))} m; spring {fmt(spring_z)} m.",
                 f"Hydraulic gradient {p.get('hydraulic_gradient')}: {esc(p.get('gradient_basis'))}."]
        if p.get("travel_time_days"):
            tt = p["travel_time_days"]
            notes.append(f"Rough travel time to the spring: {tt['low']:g} to {tt['high']:,.0f} days (order of magnitude only).")
        if p.get("valley_between_m"):
            notes.append(f"A valley about {p['valley_between_m']} m below the spring lies on the way and may catch some of the water first.")
        return self.figure(f"Cross-section A{i}-A{i}' from HP{i} ({x['name']}) to the spring", "".join(out),
                           [("Ground surface", "#7a5230", "line"), ("Assumed water table", "#0b63c5", "dash"), ("Injection point", "#0b63c5", "dot")],
                           " ".join(notes))

    def monthly_chart(self):
        c = self.c or {}
        vals = c.get("monthly_injection_m3")
        if not vals:
            return ""
        W, H, L, R, T, B = 640, 220, 50, 14, 14, 30
        top = nice(max(vals) * 1.1 or 1)
        bw = (W - L - R) / 12
        out = [f'<svg class="chart" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif">']
        for k in range(5):
            v = top * k / 4
            y = T + (1 - v / top) * (H - T - B)
            out.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="#ddd" stroke-width="0.6"/>'
                       f'<text x="{L - 6}" y="{y + 3:.1f}" font-size="10" text-anchor="end" fill="#444">{v:,.0f}</text>')
        for m, v in enumerate(vals):
            h = v / top * (H - T - B)
            x = L + m * bw + bw * 0.15
            out.append(f'<rect x="{x:.1f}" y="{H - B - h:.1f}" width="{bw * 0.7:.1f}" height="{h:.1f}" fill="#2c7fb8" rx="2"/>'
                       f'<text x="{x + bw * 0.35:.1f}" y="{H - B + 14}" font-size="10" text-anchor="middle" fill="#444">{MONTHS[m]}</text>')
        out.append(f'<text x="12" y="{(T + H - B) / 2:.0f}" font-size="10" text-anchor="middle" fill="#444" transform="rotate(-90 12 {(T + H - B) / 2:.0f})">m³ injected</text></svg>')
        return self.figure("Water injected by the DI handpumps, month by month", "".join(out), None,
                           "From the monthly rainfall pattern, roof areas and collection losses (all handpumps together).")

    def score_bar(self):
        a = self.a or {}
        score = a.get("score")
        if score is None:
            return ""
        W, H = 640, 64
        x = lambda v: 20 + v / 100 * (W - 40)  # noqa: E731
        bands = [(0, 35, "#5aae61", "Low"), (35, 60, "#f6c344", "Medium"), (60, 100, "#d6604d", "High")]
        out = [f'<svg class="chart" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif">']
        for lo, hi, col, lbl in bands:
            out.append(f'<rect x="{x(lo):.1f}" y="22" width="{x(hi) - x(lo):.1f}" height="16" fill="{col}"/>'
                       f'<text x="{(x(lo) + x(hi)) / 2:.1f}" y="54" font-size="11" text-anchor="middle" fill="#333">{lbl} ({lo}-{hi})</text>')
        out.append(f'<polygon points="{x(score) - 7:.1f},6 {x(score) + 7:.1f},6 {x(score):.1f},20" fill="#111"/>'
                   f'<text x="{x(score):.1f}" y="4" font-size="0">.</text></svg>')
        return f'<div class="scorebar">{"".join(out)}<p class="fig-note">Score {score} of 100: <b>{esc(a.get("class"))}</b>.</p></div>'

    # ---------------------------------------------------------------- module sections
    def vulnerability(self):
        A, a = self.A, self.a
        out = ["<h2>5. Spring vulnerability</h2>"]
        if not a:
            return out[0] + "<p>" + " ".join(esc(x) for x in A.get("rationale", [])) + "</p>"
        out.append(self.score_bar())
        if A.get("summary"):
            out.append("<p>" + " ".join(esc(x) for x in A["summary"]) + "</p>")
        if a.get("critical_signs"):
            out.append("<p><b>Critical signs that make it High on their own:</b> " + esc("; ".join(a["critical_signs"])) + ".</p>")
        rows = [[esc(i["group"]), esc(i["indicator"]), esc(i.get("value")), f"{i['score']:.0f}" if i.get("score") is not None else "-",
                 f"{i['weight_used_pct']:.0f}%" if i.get("weight_used_pct") is not None else "-", f"{i['points']:.1f}" if i.get("points") is not None else "-"]
                for i in a.get("indicators", [])]
        out.append(self.table("Vulnerability indicators", ["Group", "Sign", "Value", "Score (0-100)", "Weight", "Points"], rows, "small"))
        out.append(f"<p class='fig-note'>{fmt(a.get('coverage_pct'))}% of the score's weight has data. Missing answers are left out and the rest is re-weighted.</p>")
        return "".join(out)

    def di_impact(self):
        C, c = self.C, self.c
        out = ["<h2>6. Potential impact of DI recharge</h2>"]
        if not c:
            return out[0] + "<p>" + " ".join(esc(x) for x in C.get("rationale", [])) + "</p>"
        tot = c["totals"]
        sites = self.sites
        if not sites:
            out.append("<p>No DI handpumps were entered for this run, so no impact was worked out.</p>")
            return "".join(out)
        vol = tot.get("volume_m3_per_year") or 0
        reach = tot["reaching_m3_per_year"]
        share = 100 * reach["mid"] / vol if vol else 0
        share_txt = "<1" if 0 < share < 1 else f"{share:.0f}"
        verdict = ("A good share of the water should reach the spring." if share >= 30 else
                   "Some of the water should reach the spring." if share >= 10 else
                   "Little of the water is expected to reach this spring.")
        out.append(f'<div class="key"><div class="big">{share_txt}%</div><div>of the water injected is expected to reach the spring '
                   f'(about {reach["mid"]:,.0f} of {vol:,.0f} m³ a year; range {reach["low"]:,.0f}-{reach["high"]:,.0f}). {esc(verdict)}</div></div>')
        if C.get("summary"):
            out.append("<p>" + " ".join(esc(x) for x in C["summary"]) + "</p>")
        rows = []
        for i, x in enumerate(sites, start=1):
            sh = x["share_reaching_spring"]
            rows.append([f"HP{i}", esc(x["name"]), fmt(x.get("roof_area_m2")), fmt(x.get("depth_m")), fmt(x.get("volume_m3_per_year")),
                         f"{100 * sh['low']:.0f}-{100 * sh['high']:.0f}%", fmt(x["reaching_m3_per_year"]["mid"], 1),
                         f"{x['added_flow_lpm_lean']['mid']:.2f}", esc(x.get("zone_id") or "-")])
        out.append(self.table("DI handpumps: water in and water reaching the spring",
                              ["", "Handpump", "Roof (m²)", "Depth (m)", "Injected (m³/yr)", "Share reaching", "Reaching (m³/yr)", "Lean-season L/min", "Zone"],
                              rows, "small"))
        out.append(self.monthly_chart())
        out.append("<h3>Flow path cross-sections</h3>")
        for i, x in enumerate(sites, start=1):
            out.append(self.cross_section(i, x))
            if x.get("flags"):
                out.append("<ul class='bullets small'>" + "".join(f"<li>{esc(fl)}</li>" for fl in x["flags"]) + "</ul>")
        if tot.get("pct_of_lean_flow"):
            pct = tot["pct_of_lean_flow"]
            out.append(f"<p>Under these assumptions the added lean-season flow is about {pct['mid']:.0f}% of the present "
                       f"{fmt(tot.get('lean_flow_lpm'), 1)} L/min (range {pct['low']:.0f}-{pct['high']:.0f}%).</p>")
        return "".join(out)

    def structures(self):
        b = self.b or {}
        zones = b.get("recharge_zones") or []
        out = ["<h2>7. Recommended recharge structures</h2>"]
        out.append("<p>Suggested from the slope, soil and land cover of each zone, following the SRHU and RDI practice. "
                   "Confirm the exact spots on the ground with a geologist.</p>")
        rows = []
        for zn in zones:
            slope = zn.get("mean_slope_deg") or 0
            works = ("recharge pits and percolation ponds" if slope < 10 else "staggered contour trenches and recharge pits" if slope < 20
                     else "continuous contour trenches with planting" if slope < 30 else "planting, brushwood and stone bunds (too steep for trenches)")
            land = list(zn.get("land_cover_pct", {}))
            if land and land[0] in ("Grassland", "Bare / sparse vegetation", "Shrubland"):
                works += "; native tree and grass planting"
            if zn.get("soil_depth_cm") is not None and zn["soil_depth_cm"] < 50:
                works += "; keep pits shallow (thin soil)"
            if zn.get("crosses_fault"):
                works += "; a recharge shaft where the fault crosses"
            rows.append([zn["id"], f"{zn['area_ha']:.1f} ha", f"{slope:.0f}°", esc(works)])
        if rows:
            out.append(self.table("Suggested works in the recharge zones", ["Zone", "Area", "Mean slope", "Suggested works"], rows))
        out.append("<ul class='bullets'>")
        if self.sites:
            out.append("<li>At each DI handpump: roof gutters and pipe, a first-flush device, a filter chamber with graded media, and the "
                       "injection line into the handpump. Keep the handpump's surroundings clean and test the water before and after.</li>")
        out.append("<li>Gully plugs and small check dams on the drainage lines above the spring slow runoff and let it soak in.</li>"
                   "<li>Protect the spring box and the ground just above it from grazing, digging and soak pits.</li></ul>")
        safety = (self.c or {}).get("safety") or {}
        if self.sites and safety.get("actions"):
            out.append("<p><b>Before injection:</b></p><ul class='bullets'>" + "".join(f"<li>{esc(a)}</li>" for a in safety["actions"]) + "</ul>")
        mon = (self.c or {}).get("monitoring_plan") or []
        if mon:
            out.append("<p><b>Monitoring:</b></p><ul class='bullets'>" + "".join(f"<li>{esc(m if isinstance(m, str) else m.get('what', ''))}</li>" for m in mon) + "</ul>")
        return "".join(out)

    def conclusion(self):
        out = ["<h2>8. Conclusion</h2><ul class='bullets'>"]
        a, b, c = self.a, self.b, self.c
        if a:
            out.append(f"<li><b>Vulnerability:</b> {esc(a['class'])} ({a['score']} of 100). " + esc((self.A.get("summary") or [""])[0]) + "</li>")
        if b:
            zones = b.get("recharge_zones") or []
            out.append(f"<li><b>Springshed:</b> the catchment to the ridge is about {b['surface_catchment']['area_ha']:.1f} ha"
                       + (f"; the best recharge zone is {zones[0]['id']} ({zones[0]['area_ha']:.1f} ha, {esc(zones[0]['link']['name'].lower())})." if zones else ".") + "</li>")
        if c and self.sites:
            tot = c["totals"]
            vol = tot.get("volume_m3_per_year") or 0
            share = 100 * tot["reaching_m3_per_year"]["mid"] / vol if vol else 0
            out.append(f"<li><b>DI recharge:</b> {len(self.sites)} handpump{'s' if len(self.sites) != 1 else ''} can inject about {vol:,.0f} m³ a year; "
                       f"about {'<1' if 0 < share < 1 else f'{share:.0f}'}% of it is expected to reach the spring, adding about "
                       f"{tot['added_flow_lpm_lean']['mid']:.2f} L/min in the lean season if it all comes out then.</li>")
        out.append("<li>These results come from maps and the answers entered, not from measurements of the connection. Monitoring the spring "
                   "flow before and after the works is the only way to show the effect.</li></ul>")
        return "".join(out)

    def appendix(self):
        out = ["<h2>Appendix: assumptions and notes</h2>"]
        for title, mod in (("Vulnerability", self.A), ("Springshed", self.B), ("DI impact", self.C)):
            missing = mod.get("missing_inputs") or []
            notes = list(mod.get("warnings") or [])
            if title == "Vulnerability" and missing:
                notes.append("Not answered, so left out of the score: " + "; ".join(m["indicator"] for m in missing) + ".")
            else:
                notes += [f"{m['indicator']}: {m['needs']}" for m in missing]
            if notes:
                out.append(f"<h3>{title}</h3><ul class='bullets small'>" + "".join(f"<li>{esc(n)}</li>" for n in notes) + "</ul>")
        rows = [[esc(x["label"]), esc(f"{x['value']} {x['unit']}".strip()), esc(x["note"])] for x in (self.c or {}).get("assumptions", [])]
        if rows and self.sites:
            out.append(self.table("DI assumptions", ["Assumption", "Value", "Note"], rows, "small"))
        return "".join(out)

    # ---------------------------------------------------------------- the page
    def html(self):
        location = self.location()
        study = self.study_area()
        method = self.methodology()
        themes = self.thematic()
        recharge = self.recharge()
        vuln = self.vulnerability()
        di = self.di_impact()
        works = self.structures()
        concl = self.conclusion()
        appx = self.appendix()
        sections = [("1. Location and site characteristics", False), ("2. Study area analysis", False), ("3. Methodology", False)]
        sections += [(t, True) for t, _ in themes]
        sections += [("4. Integrated groundwater recharge assessment", False), ("5. Spring vulnerability", False),
                     ("6. Potential impact of DI recharge", False), ("7. Recommended recharge structures", False), ("8. Conclusion", False),
                     ("Appendix: assumptions and notes", False)]
        body = (self.cover() + self.contents(sections) + f"<section>{location}</section><section>{study}</section><section>{method}"
                + "".join(f"<div class='theme'><h3>{esc(t)}</h3>{h}</div>" for t, h in themes) + "</section>"
                + f"<section>{recharge}</section><section>{vuln}</section><section>{di}</section><section>{works}{concl}</section><section>{appx}</section>")
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hydrogeological report: {esc(self.name)}</title><style>{CSS}</style></head><body>
<div class="toolbar"><button onclick="window.print()">Save as PDF / Print</button><span>Use “Save as PDF” in the print window. A4, portrait.</span></div>
<main>{body}</main></body></html>"""


CSS = """
:root{--ink:#1d2327;--muted:#5b6670;--rule:#d5dbe0;--accent:#1f5f8b}
*{box-sizing:border-box}
body{margin:0;background:#eef1f4;color:var(--ink);font:14px/1.55 Georgia,'Times New Roman',serif}
main{max-width:820px;margin:0 auto;background:#fff;padding:40px 54px 60px}
h1,h2,h3,.map-title,.toolbar,figcaption,.tcap,table,.legend,.key,.cover-top,.cover-project,.cover-foot,.toc{font-family:Arial,Helvetica,sans-serif}
h2{font-size:20px;color:var(--accent);border-bottom:2px solid var(--accent);padding-bottom:4px;margin:34px 0 12px}
h3{font-size:16px;margin:24px 0 8px;color:#16425f}
p{text-align:justify;margin:8px 0}
.toolbar{position:sticky;top:0;z-index:5;background:#16425f;color:#fff;padding:10px 16px;display:flex;gap:14px;align-items:center;font-size:13px}
.toolbar button{background:#fff;color:#16425f;border:0;border-radius:6px;padding:7px 14px;font-weight:700;cursor:pointer}
.cover{min-height:980px;display:flex;flex-direction:column;align-items:center;text-align:center;justify-content:center;gap:22px;border:3px double var(--accent);padding:40px}
.cover-top{font-size:26px;font-weight:800;letter-spacing:.04em;color:var(--accent)}
.cover-project{font-size:16px;font-weight:600}
.cover h1{font-size:30px;margin:10px 0}
.cover-place{font-size:16px;line-height:1.7}
.cover-gps{font-size:14px;line-height:1.7}
.cover-foot{font-size:13px;color:var(--muted);line-height:1.6;margin-top:30px}
.small{font-size:12px}
.toc-list li{margin:3px 0}.toc-list li.sub{list-style:none;margin-left:18px;font-size:13px}
ul.plain{list-style:none;padding-left:0;font-size:13px}ul.plain.two{columns:2}
ul.facts,ul.bullets{margin:6px 0 10px;padding-left:22px}ul.facts li,ul.bullets li{margin:3px 0}
ul.small{font-size:12.5px}
figure{margin:18px 0 22px;break-inside:avoid;page-break-inside:avoid}
.map-title{font-size:12px;font-weight:700;text-align:center;letter-spacing:.03em;margin-bottom:4px}
svg.map,svg.chart{width:100%;height:auto;display:block}
figcaption,.tcap{text-align:center;color:#2b6a99;font-size:12.5px;margin-top:6px}
.fig-note{font-size:12px;color:var(--muted);text-align:left;margin:4px 0}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11.5px;margin:6px 0 0 78px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend i{display:inline-block;width:14px;height:11px}
.legend i.line{height:0;border-top:2.5px solid}.legend i.dash{height:0;border-top:2.5px dashed}.legend i.dot-line{height:0;border-top:2.5px dotted}
.legend i.dot{width:11px;height:11px;border-radius:50%;background:currentColor;border:0}
.legend i.square{width:11px;height:11px;background:currentColor;border:0}
table.t{border-collapse:collapse;width:100%;font-size:12.5px;margin:10px 0 2px;break-inside:avoid}
table.t th,table.t td{border:1px solid var(--rule);padding:5px 7px;text-align:left;vertical-align:top}
table.t thead th{background:#eaf1f7}
table.t.narrow{width:auto;min-width:60%;margin-left:auto;margin-right:auto}
table.t.small{font-size:11.5px}
.key{display:flex;gap:16px;align-items:center;border:2px solid #1f5f8b;background:#eef6fc;border-radius:8px;padding:12px 16px;margin:10px 0;break-inside:avoid}
.key .big{font-size:34px;font-weight:800;color:#1f5f8b}
.scorebar{margin:10px 0}
.theme{break-before:auto}
@media (max-width:700px){main{padding:20px 16px}.legend{margin-left:0}.cover{min-height:auto}}
@page{size:A4;margin:14mm 12mm}
@media print{body{background:#fff;font-size:12px}.toolbar{display:none}main{max-width:none;padding:0}
.cover,.toc,section{break-after:page}h2{break-after:avoid}h3{break-after:avoid}}
"""


def build(response, request, b_output, session=None, place=None):
    return Report(response, request, b_output, session, place).html()
