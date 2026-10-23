"""The spring tool on this computer: the map page in app/ plus the three modules behind it.

    python scripts/spring_tool_server.py            then open http://127.0.0.1:8765
    (or double-click start_tool.bat on Windows)

One spring goes in (location, field answers, planned DI sites); three results come back:
    A  vulnerability score          scripts/module_a_vulnerability.py
    B  springshed / recharge zone   scripts/module_b_springshed.py
    C  potential impact of DI       scripts/module_c_di_impact.py
Runs on 127.0.0.1 only; no account, key or paid service. When an approved map set exists
(scripts/module_a_snapshot.py), only its files are read and nothing is downloaded.

Endpoints:
    GET  /api/health    server, version and map set
    GET  /api/springs   the dataset springs for the search box and the map
    GET  /api/di_sites  WATSAN's existing DI handpumps (field visit, Oct 2026) for the map
    POST /api/assess    body and reply: see app/src/api.ts
    GET  /api/terrain/{z}/{x}/{y}.png   elevation tiles for the 3D map (Terrarium encoding), cut from the same
                        Copernicus DEM files the modules use, so the 3D view works without internet; gaps are
                        filled from public Terrarium tiles (saved for offline use) or the nearest local height
Each assessment is saved in data/03_outputs/tool_runs/<run_id>/ (result.json and report.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import mimetypes
import os
import re
import sys
import struct
import threading
import traceback
import zlib
import webbrowser
from collections import OrderedDict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import module_a_snapshot as map_set  # noqa: E402
import module_a_vulnerability as module_a  # noqa: E402
import module_b_springshed as module_b  # noqa: E402
import module_c_di_impact as module_c  # noqa: E402

VERSION = "v1.2 draft (2026-10-23)"
DIST = ROOT / "app" / "dist"
RUNS = Path(os.environ.get("SPRING_RUNS_DIR", str(ROOT / "data" / "03_outputs" / "tool_runs")))
SPRINGS_CSV = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1_clean.csv"
DI_SITES_CSV = ROOT / "data" / "02_processed" / "field_visit" / "field_visit_di_sites_v1.csv"  # WATSAN's existing DI sites
MAX_BODY = 1 << 20
MAX_SITES = 50
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".woff2": "font/woff2"}
STUDY_AREA = {"lat": (28.5, 33.5), "lon": (75.5, 81.5)}
TERRAIN_PATH = re.compile(r"/api/terrain/(\d+)/(\d+)/(\d+)\.png")


class CachedSession:
    """Module A's LayerSession with the layer values at each spring kept, so A and C read them once."""

    def __init__(self, session):
        self.session = session
        self.cache = OrderedDict()

    def __getattr__(self, name):
        return getattr(self.session, name)

    def features(self, lat, lon, elevation):
        key = (round(lat, 6), round(lon, 6), elevation)
        if key not in self.cache:
            self.cache[key] = self.session.features(lat, lon, elevation)
            while len(self.cache) > int(os.environ.get("SPRING_FEATURE_CACHE", "32")):
                self.cache.popitem(last=False)
        return self.cache[key]


class Terrain:
    """Map tiles of ground height for the 3D view (Terrarium encoding: height = R * 256 + G + B / 256 - 32768 m).

    Heights come from the Copernicus DEM tiles on this computer, the same files the modules use. Where those do not
    cover a map tile (outside the cached area, small voids, and every tile zoomed out below level 7), the gaps are
    filled from the public Terrarium elevation tiles, which are saved under <layer cache>/terrain_web so they also work
    offline later. Without internet the gaps take the nearest local height, so the 3D view never drops to sea level
    in a wall at the edge of the cached area."""

    SIZE = 256
    WEB = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
    WEB_TIMEOUT_S = 4
    WEB_RETRY_S = 300  # after a failed download, use local heights only for this long
    READERS = 4  # tiles cut at the same time; each reader has its own open files (rasterio files are not thread-safe)

    def __init__(self, folder):
        import queue
        self.lock = threading.Lock()
        self.files = sorted((Path(folder) / "dem").glob("*.tif"))
        self.readers = queue.Queue()
        for _ in range(max(1, int(os.environ.get("SPRING_TERRAIN_READERS", str(self.READERS))))):
            self.readers.put(self._open())
        self.cache = OrderedDict()
        self.web_dir = Path(folder) / "terrain_web"
        self.web_down_until = 0.0
        self.fill_level = None

    def _open(self):
        import rasterio
        return {f: rasterio.open(f) for f in self.files}

    def refresh(self):
        """Pick up DEM tiles downloaded for a newly assessed place (each reader opens them when it is next used)."""
        new = [f for f in sorted(self.files[0].parent.glob("*.tif"))] if self.files else []
        with self.lock:
            added = [f for f in new if f not in self.files]
            if added:
                self.files += added
                self.cache.clear()
                self.fill_level = None

    def tile(self, z, x, y):
        key = (z, x, y)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        heights, covered = self._heights(z, x, y)
        if not covered.all():
            heights = self._fill(z, x, y, heights, covered)
        png = self._png(heights)
        with self.lock:
            self.cache[key] = png
            while len(self.cache) > int(os.environ.get("SPRING_TERRAIN_CACHE", "600")):
                self.cache.popitem(last=False)
        return png

    def _fill(self, z, x, y, heights, covered):
        """Fill the cells no local DEM covers: from the public tile if it can be had, else the nearest local height."""
        import numpy as np
        web = self._web(z, x, y)
        if web is not None:
            return np.where(covered, heights, web)
        if covered.any():
            from scipy.ndimage import distance_transform_edt
            _, (rows, cols) = distance_transform_edt(~covered, return_indices=True)
            return heights[rows, cols]
        return np.full(heights.shape, self._fill_level(), np.float32)

    def _fill_level(self):
        """Median height of the local DEM, for map tiles with no local or public heights at all (offline, far away)."""
        import numpy as np
        if self.fill_level is None:
            datasets = self.readers.get()
            try:
                values = [ds.read(1, out_shape=(64, 64)).ravel() for ds in datasets.values()]
            finally:
                self.readers.put(datasets)
            values = np.concatenate(values) if values else np.zeros(1)
            values = values[values > -500]
            self.fill_level = float(np.median(values)) if values.size else 0.0
        return self.fill_level

    def _web(self, z, x, y):
        """The public Terrarium tile as heights (m), from the saved copy or downloaded once; None if not available."""
        import time
        import urllib.request
        import numpy as np
        from rasterio.io import MemoryFile
        path = self.web_dir / str(z) / str(x) / f"{y}.png"
        data = None
        if path.is_file():
            data = path.read_bytes()
        elif time.time() >= self.web_down_until:
            try:
                with urllib.request.urlopen(self.WEB.format(z=z, x=x, y=y), timeout=self.WEB_TIMEOUT_S) as reply:
                    data = reply.read()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            except Exception:
                self.web_down_until = time.time() + self.WEB_RETRY_S
                return None
        if not data:
            return None
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # a map tile has no geotransform; that is expected
                with MemoryFile(data) as mem, mem.open() as ds:
                    rgb = ds.read().astype(np.float32)
        except Exception:
            return None
        if rgb.shape[0] < 3 or rgb.shape[1:] != (self.SIZE, self.SIZE):
            return None
        return rgb[0] * 256 + rgb[1] + rgb[2] / 256 - 32768

    def _heights(self, z, x, y):
        """Local DEM heights at the tile's pixel centres, and which pixels the local DEM covers."""
        import numpy as np
        n, size = 2 ** z, self.SIZE
        frac = (np.arange(size) + 0.5) / size
        lons = (x + frac) / n * 360 - 180
        lats = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y + frac) / n))))
        heights = np.zeros((size, size), np.float32)
        covered = np.zeros((size, size), bool)
        if z < 7:  # a zoomed-out tile spans many DEM files: leave it to the public tile
            return heights, covered
        west, east, south, north = lons[0], lons[-1], lats[-1], lats[0]
        datasets = self.readers.get()
        try:
            for f in self.files:
                if f not in datasets:
                    import rasterio
                    datasets[f] = rasterio.open(f)
            self._read_into(datasets.values(), lons, lats, west, east, south, north, heights, covered)
        finally:
            self.readers.put(datasets)
        return heights, covered

    def _read_into(self, datasets, lons, lats, west, east, south, north, heights, covered):
        import numpy as np
        from rasterio.enums import Resampling
        from rasterio.windows import from_bounds
        size = self.SIZE
        for ds in datasets:
            b = ds.bounds
            if b.right < west or b.left > east or b.top < south or b.bottom > north:
                continue
            pad = 2 * abs(ds.transform.a)
            window = from_bounds(max(west - pad, b.left), max(south - pad, b.bottom), min(east + pad, b.right),
                                 min(north + pad, b.top), ds.transform).round_offsets().round_lengths()
            if window.width < 2 or window.height < 2:
                continue
            shape = (min(window.height, 2 * size), min(window.width, 2 * size))  # reads an overview when zoomed out
            data = ds.read(1, window=window, out_shape=shape, resampling=Resampling.bilinear).astype(np.float32)
            wt = ds.window_transform(window)
            sx, sy = window.width / shape[1], window.height / shape[0]
            # bilinear sampling at the tile's pixel centres
            fc = (lons - wt.c) / (wt.a * sx) - 0.5
            fr = (lats - wt.f) / (wt.e * sy) - 0.5
            inside_c = (lons >= b.left) & (lons < b.right)
            inside_r = (lats > b.bottom) & (lats <= b.top)
            c0 = np.clip(np.floor(fc).astype(int), 0, shape[1] - 2)
            r0 = np.clip(np.floor(fr).astype(int), 0, shape[0] - 2)
            dc = np.clip(fc - c0, 0, 1)[None, :]
            dr = np.clip(fr - r0, 0, 1)[:, None]
            R0, C0 = np.meshgrid(r0, c0, indexing="ij")
            v = (data[R0, C0] * (1 - dr) * (1 - dc) + data[R0, C0 + 1] * (1 - dr) * dc
                 + data[R0 + 1, C0] * dr * (1 - dc) + data[R0 + 1, C0 + 1] * dr * dc)
            use = inside_r[:, None] & inside_c[None, :] & (v > -500)
            heights[use] = v[use]
            covered |= use

    @staticmethod
    def _png(heights):
        import numpy as np
        v = np.clip(heights + 32768.0, 0, 65535.99)
        r = np.floor(v / 256)
        g = np.floor(v - r * 256)
        b = np.floor((v - np.floor(v)) * 256)
        rgb = np.dstack([r, g, b]).astype(np.uint8)
        h, w = heights.shape
        raw = b"".join(b"\x00" + rgb[i].tobytes() for i in range(h))

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def report_memory(stage):
    """Small Linux deployment diagnostic; no spring inputs or credentials are logged."""
    if os.environ.get('SPRING_LOG_MEMORY') != '1':
        return
    values = {}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, _ = line.split()
                values[key.rstrip(':') + '_MiB'] = round(int(value) / 1024, 1)
        values['container_MiB'] = round(int(Path('/sys/fs/cgroup/memory.current').read_text()) / 2**20, 1)
    except (OSError, ValueError):
        pass
    if values:
        print('Memory ' + stage + ': ' + json.dumps(values), flush=True)


def _leading_number(text):
    match = re.match(r"\s*(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else None


def existing_di_sites():
    """WATSAN's DI handpumps seen on the October 2026 field visit: position, depth, roof and state."""
    if not DI_SITES_CSV.exists():
        return []
    rows = []
    with DI_SITES_CSV.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except ValueError:
                continue
            roof = _leading_number(r["roof_area_m2"])
            if roof and "total for" in r["roof_area_m2"]:
                roof /= 2  # one roof figure given for a pair of handpumps
            rows.append({"id": r["di_site_id"], "name": r["name"], "latitude": lat, "longitude": lon,
                         "depth_m": _leading_number(r["bore_depth_m"]), "roof_area_m2": roof, "status": r["di_status"],
                         "linked_spring": r["linked_dataset_spring_id"] or None, "link_status": r["link_status"]})
    return rows


class Tool:
    def __init__(self):
        self.lock = threading.Lock()
        self.manifest = map_set.active()
        self.file_problems = map_set.check_files(self.manifest, fingerprints=False) if self.manifest else []
        places = map_set.roots()
        self.session = CachedSession(module_a.LayerSession(places["layer_cache"], places["local_layers"],
                                                           offline=self.manifest is not None))
        self.zones = OrderedDict()
        self._springs = None
        self.terrain = Terrain(places["layer_cache"])

    # ------------------------------------------------------------------ data
    def health(self):
        m = self.manifest
        return {"ok": True, "version": VERSION, "offline": m is not None,
                "map_set": None if m is None else {"snapshot_id": m["snapshot_id"], "approved_by": m.get("approved_by") or "",
                                                   "approved_at": m.get("approved_utc") or ""},
                "map_set_problems": len(self.file_problems)}

    def springs(self):
        if self._springs is None:
            rows = []
            with SPRINGS_CSV.open(encoding="utf-8", newline="") as handle:
                for r in csv.DictReader(handle):
                    if r.get("is_primary_record") != "Y" or not r.get("latitude") or not r.get("longitude"):
                        continue
                    try:
                        lat, lon = float(r["latitude"]), float(r["longitude"])
                    except ValueError:
                        continue
                    place = r["village"] or r["block"] or (r.get("area_name") or "").split(",")[0].strip()
                    label = r["spring_name"] or (f"Spring at {place}" if place else "Unnamed spring")
                    rows.append({"id": r["record_id"], "name": f"{label} ({r['record_id']})", "village": place,
                                 "district": r["district"], "latitude": lat, "longitude": lon,
                                 "elevation_m": float(r["elevation_m"]) if r.get("elevation_m") else None,
                                 "source": r["source_dataset"]})
            self._springs = rows
        return self._springs

    # ------------------------------------------------------------------ assessment
    def assess(self, request):
        spring, field, di = clean_request(request)
        lat, lon = spring["latitude"], spring["longitude"]
        name = spring.get("name") or f"{lat:.5f}, {lon:.5f}"
        problem = None
        if self.manifest and self.file_problems:
            problem = (f"The approved map set {self.manifest['snapshot_id']} is incomplete on this computer ({len(self.file_problems)} files "
                       "missing or changed). Run: python scripts/module_a_snapshot.py verify")
        elif self.manifest and not map_set.covers(self.manifest, lat, lon):
            problem = (f"This spring is outside the approved map set {self.manifest['snapshot_id']}. Add its area with "
                       "python scripts/module_a_snapshot.py prepare --bbox WEST SOUTH EAST NORTH, then approve the new set.")
        with self.lock:
            if problem:
                outputs = {m: failed(m, spring, problem, "unavailable") for m in "ABC"}
            else:
                outputs = self._run(spring, field, di)
        elevation = outputs["A"]["spring"].get("elevation_m") if outputs["A"].get("spring") else None
        if elevation is None and outputs["B"].get("result"):
            elevation = outputs["B"]["result"]["spring_cell"]["elevation_m"]
        run_id = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{slug(name)}"
        response = {"run_id": run_id, "created_at": datetime.now().isoformat(timespec="seconds"),
                    "map_set": self.manifest["snapshot_id"] if self.manifest else "none approved",
                    "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": elevation},
                    **{m: module_b.public(outputs[m]) for m in "ABC"}}
        response = finite(response)
        save_run(response, request)
        if not self.manifest:
            self.terrain.refresh()
        return response

    def _run(self, spring, field, di):
        report_memory('assessment start')
        out = {}
        inputs = {"spring": spring, "field": field}
        try:
            out["A"] = module_a.assess(inputs, self.session)
        except Exception as error:
            traceback.print_exc()
            out["A"] = failed("A", spring, f"The vulnerability score could not be computed: {error}")
        report_memory('after vulnerability')
        # B works from the map cell's elevation; C compares DI sites with that same elevation
        key = (round(spring["latitude"], 6), round(spring["longitude"], 6), spring.get("elevation_m"),
               *(field.get(k) for k in ("monsoon_flow_lpm", "lean_flow_lpm", "dip_direction_deg", "dip_angle_deg")))
        try:
            if key not in self.zones:
                self.zones[key] = module_b.delineate(inputs, self.session)
                while len(self.zones) > int(os.environ.get("SPRING_ZONE_CACHE", "8")):
                    self.zones.popitem(last=False)
            out["B"] = self.zones[key]
        except Exception as error:
            traceback.print_exc()
            out["B"] = failed("B", spring, f"The springshed could not be drawn: {error}")
        report_memory('after springshed')
        try:
            features = self.session.features(spring["latitude"], spring["longitude"], spring.get("elevation_m"))
        except Exception:
            features = {}
        try:
            out["C"] = module_c.estimate({**inputs, "di": di}, self.session, features, out["B"])
        except Exception as error:
            traceback.print_exc()
            out["C"] = failed("C", spring, f"The DI impact could not be estimated: {error}")
        report_memory('after DI')
        return out


TITLES = {"A": "Spring vulnerability", "B": "Springshed (recharge area)", "C": "Potential impact of DI recharge"}


def failed(module, spring, reason, status="failed"):
    return {"module": module, "title": TITLES[module], "version": "v1 draft", "status": status, "spring": spring,
            "result": None, "confidence": "Low", "validation": "Not run.", "rationale": [reason], "missing_inputs": [], "warnings": [],
            "report_markdown": f"# {TITLES[module]}\n\n{reason}\n"}


def number(value, label, low=None, high=None):
    if value in (None, ""):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(v) or (low is not None and v < low) or (high is not None and v > high):
        raise ValueError(f"{label} must be between {low} and {high}")
    return v


def clean_request(request):
    if not isinstance(request, dict) or not isinstance(request.get("spring"), dict):
        raise ValueError("Send {spring: {latitude, longitude}, field: {...}, di: {...}}")
    s = request["spring"]
    lat = number(s.get("latitude"), "Latitude", -90, 90)
    lon = number(s.get("longitude"), "Longitude", -180, 180)
    if lat is None or lon is None:
        raise ValueError("Latitude and longitude are needed")
    if not (STUDY_AREA["lat"][0] <= lat <= STUDY_AREA["lat"][1] and STUDY_AREA["lon"][0] <= lon <= STUDY_AREA["lon"][1]):
        raise ValueError("This tool covers the Uttarakhand and Himachal hills (latitude 28.5-33.5, longitude 75.5-81.5)")
    spring = {"name": str(s.get("name") or "").strip()[:120] or None, "latitude": lat, "longitude": lon,
              "elevation_m": number(s.get("elevation_m"), "Elevation", -100, 8000)}
    field = request.get("field") or {}
    if not isinstance(field, dict):
        raise ValueError("field must be an object")
    field = {k: v for k, v in field.items() if v not in (None, "")}
    for key, label, low, high in (("dip_direction_deg", "Dip direction", 0, 360), ("dip_angle_deg", "Dip angle", 0, 90)):
        if key in field:
            field[key] = number(field[key], label, low, high)
    di = request.get("di") or {}
    if not isinstance(di, dict) or not isinstance(di.get("sites", []), list):
        raise ValueError("di must be {sites: [...], assumptions: {...}}")
    if len(di.get("sites", [])) > MAX_SITES:
        raise ValueError(f"At most {MAX_SITES} DI sites at a time")
    return spring, field, di


def finite(value):
    """Replace NaN and infinity (which JSON cannot carry) with null."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    if hasattr(value, "item"):  # numpy scalars
        return finite(value.item())
    return value


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "spring"


def save_run(response, request):
    folder = RUNS / response["run_id"]
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
        (folder / "result.json").write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        report = [f"# Spring assessment: {response['spring']['name']}", "",
                  f"Run {response['run_id']}; map set {response['map_set']}; tool {VERSION}.", ""]
        for m in "ABC":
            report += [response[m]["report_markdown"].replace("\n# ", "\n## ").replace("# ", "## ", 1), ""]
        (folder / "report.md").write_text("\n".join(report), encoding="utf-8")
    except OSError as error:
        print(f"Run not saved: {error}", file=sys.stderr)


# ---------------------------------------------------------------------- web
class Handler(BaseHTTPRequestHandler):
    server_version = "SpringTool/1.0"
    tool: Tool = None

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self._json(HTTPStatus.OK, self.tool.health())
        if path == "/api/springs":
            return self._json(HTTPStatus.OK, self.tool.springs())
        if path == "/api/di_sites":
            return self._json(HTTPStatus.OK, existing_di_sites())
        tile = TERRAIN_PATH.fullmatch(path)
        if tile:
            z, x, y = (int(v) for v in tile.groups())
            if not (0 <= z <= 16 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
                return self._json(HTTPStatus.NOT_FOUND, {"error": "No such tile"})
            body = self.tool.terrain.tile(z, x, y)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            return
        if not (DIST / "index.html").is_file():
            return self._send(HTTPStatus.OK, b"The page is not built. In app/, run: npm ci, then npm run build.", "text/plain; charset=utf-8")
        file = (DIST / path.lstrip("/")).resolve()
        if path == "/" or DIST.resolve() not in file.parents or not file.is_file():
            file = DIST / "index.html"
        content_type = TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self._send(HTTPStatus.OK, file.read_bytes(), content_type)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/assess":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown address"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "Send the request as JSON (up to 1 MB)"})
        try:
            request = json.loads(self.rfile.read(length))
            response = self.tool.assess(request)
        except ValueError as error:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:  # report, keep the server running
            traceback.print_exc()
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Assessment failed: {error}"})
        self._json(HTTPStatus.OK, response)

    def log_message(self, fmt, *args):
        if args and "/api/" in str(args[0]):
            sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the page in the browser")
    args = parser.parse_args()
    print("Starting the spring tool...")
    Handler.tool = Tool()
    health = Handler.tool.health()
    if health["map_set"]:
        print(f"Map set {health['map_set']['snapshot_id']} (approved by {health['map_set']['approved_by']}): reading only its files.")
        if Handler.tool.file_problems:
            print(f"WARNING: {len(Handler.tool.file_problems)} map-set files are missing or changed; run module_a_snapshot.py verify")
    else:
        print("No approved map set: missing map tiles are downloaded as needed. See docs/spring-tool-guide.md.")
    # Read the Bhukosh map layers now (15-40 s) rather than during the first assessment
    threading.Thread(target=lambda: Handler.tool.session.secondary.vectors, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Spring tool running at {url}  (keep this window open; Ctrl+C to stop)")
    if not (DIST / "index.html").is_file():
        print("The page is not built yet: run `npm ci` and `npm run build` in app/.")
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
