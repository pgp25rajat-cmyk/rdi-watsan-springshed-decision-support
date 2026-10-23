"""The tool's map set: prepare it once, check it, approve it. Assessments then read only these files, never the internet.

It began as Module A's set and now also holds what Modules B (springshed) and C (DI impact) read: the GSI geology,
the DEM lineaments, the recharge-factor table and the Rathi (2021) springsheds used to size the zone.

    python scripts/module_a_snapshot.py prepare [--bbox W S E N] [--rebuild-reference] [--by NAME]
    python scripts/module_a_snapshot.py verify [SNAPSHOT_ID]
    python scripts/module_a_snapshot.py approve SNAPSHOT_ID --by NAME
    python scripts/module_a_snapshot.py status

prepare   Downloads every map tile Module A needs for all dataset springs (plus an optional extra box), then writes a
          manifest: each file's source ID, place, size and SHA-256 fingerprint. The set starts as "pending_review".
          --rebuild-reference first rebuilds the comparison table (scripts/build_spring_features.py), which is needed
          after adding new data such as another IMD year. It needs the data-build packages in requirements.txt.
verify    Re-reads every file and checks it against the manifest (default: the approved set).
approve   Verifies, records who approved it and when, and makes it the set assessments use.
status    Shows the approved set.

Manifests are kept in data/02_processed/snapshots/module_a/. File places are stored relative to three roots, so no
personal folder names are recorded: layer_cache (SPRING_LAYER_CACHE), local_layers (SPRING_LOCAL_LAYERS) and repo.
Building growth (Google Open Buildings, SRC-025) is read over the internet for each spring, so it is not in the set:
assessments that use an approved set leave it out, and its 3 points are shared among the other indicators.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = Path(os.environ.get("SPRING_SNAPSHOT_DIR", str(ROOT / "data" / "02_processed" / "snapshots" / "module_a")))
ACTIVE = SNAPSHOTS / "active.json"
FEATURES_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_features_v1.csv"
REPO_FILES = [  # Module A: the comparison table, the weights and the input/test split
    ("derived", "data/02_processed/spring_features/spring_features_v1.csv"),
    ("derived", "data/02_processed/spring_master/spring_master_v1_input.csv"),
    ("derived", "config/module_a_indicators_v1.csv"),
    # Module B: geology, fractures, factor weights, the springsheds that size the zone; the tool's spring list
    ("SRC-014", "data/00_raw/ngdr_geology/lithology/LITHOLOGY_STATE_UTTARAKHAND.geojson"),
    ("SRC-013", "data/00_raw/ngdr_geology/faults/FAULT_STATE_UTTARAKHAND.geojson"),
    ("SRC-015", "data/00_raw/ngdr_geology/folds/FOLD_STATE_UTTARAKHAND.geojson"),
    ("derived", "data/02_processed/lineaments/dem_lineament_candidates_v1.geojson"),
    ("derived", "config/module_b_recharge_factors_v1.csv"),
    ("SRC-011", "data/01_staged/literature/csv/literature_spring_records_common_v1.csv"),
    ("derived", "data/02_processed/spring_master/spring_master_v1_clean.csv"),
    # secondary layers: per-spring comparison values and the ERA5 winter snowfall grid
    ("derived", "data/02_processed/spring_features/spring_secondary_features_v1.csv"),
    ("SRC-035", "data/02_processed/climate/era5_snowfall_winter_mean_v1.tif"),
    ("SRC-035", "data/02_processed/climate/era5_snowfall_winter_mean_v1_curve.csv"),
]
LOCAL_FILES = [("SRC-023", "IMD", "*.nc"), ("SRC-024", "SoilGrids", "*.tif"), ("SRC-022", "Bhoonidhi", "*.zip"),
               # secondary layers (scripts/secondary_layers.py): Bhukosh lineaments, landslides and dips; forest density; infiltration
               ("SRC-029", "NGDR(Bhukosh)", "*.zip"), ("SRC-033", "Sentinel2", "*.tif"), ("TRN-018", "Infiltration", "*.tif")]
NOT_INCLUDED = [{"source_id": "SRC-025", "indicator": "building_growth",
                 "reason": "Google Open Buildings is read over the internet for each spring; left out when this set is used"}]


def roots() -> dict[str, Path]:
    return {"layer_cache": Path(os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache"))),
            "local_layers": Path(os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers"))),
            "repo": ROOT}


def layers_module():
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import build_spring_features
    return build_spring_features


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- coverage
def dem_cells(lat, lon):
    """1-degree DEM cells the layer reader opens for a spring (same rule as build_spring_features.dem_tiles_for)."""
    return {f"N{math.floor(lat + dy):02d}E{math.floor(lon + dx):03d}" for dy in (-0.02, 0, 0.02) for dx in (-0.02, 0, 0.02)}


def worldcover_tiles(lat, lon):
    """3-degree WorldCover tiles the layer reader opens for a spring (same rule as worldcover_tiles_for)."""
    return {f"N{math.floor((lat + dy) / 3) * 3:02d}E{math.floor((lon + dx) / 3) * 3:03d}"
            for dy in (-0.01, 0, 0.01) for dx in (-0.01, 0, 0.01)}


def covers(manifest: dict, lat: float, lon: float) -> bool:
    coverage = manifest["coverage"]
    return dem_cells(lat, lon) <= set(coverage["dem_cells"]) and worldcover_tiles(lat, lon) <= set(coverage["worldcover_tiles"])


# --------------------------------------------------------------------------- manifests
def load(snapshot_id: str | None = None) -> dict | None:
    path = ACTIVE if snapshot_id is None else SNAPSHOTS / f"{snapshot_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def active() -> dict | None:
    """The approved set assessments use, or None."""
    manifest = load()
    return manifest if manifest and manifest.get("approval_status") == "approved" else None


def save(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def check_files(manifest: dict, fingerprints: bool = True) -> list[str]:
    """Problems with the files on this computer: missing, changed size, or (with fingerprints) changed content."""
    places, problems = roots(), []
    for item in manifest["files"]:
        path = places[item["root"]] / item["path"]
        if not path.is_file():
            problems.append(f"missing: {item['root']}/{item['path']}")
        elif path.stat().st_size != item["bytes"]:
            problems.append(f"size changed: {item['root']}/{item['path']}")
        elif fingerprints and sha256(path) != item["sha256"]:
            problems.append(f"content changed: {item['root']}/{item['path']}")
    return problems


def entry(source_id: str, root: str, path: Path) -> dict:
    relative = path.resolve().relative_to(roots()[root].resolve()).as_posix()
    return {"source_id": source_id, "root": root, "path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}


def code_version() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


# --------------------------------------------------------------------------- commands
def prepare(bbox=None, rebuild_reference=False, by=None) -> dict:
    places = roots()
    cache, local = places["layer_cache"], places["local_layers"]
    if rebuild_reference:
        missing = [folder for _, folder, pattern in LOCAL_FILES[:3] if not list((local / folder).glob(pattern))]
        if missing:
            raise SystemExit(f"Not rebuilt: {', '.join(missing)} not found under SPRING_LOCAL_LAYERS ({local}). Without them "
                             "the comparison table would lose its IMD, SoilGrids and CartoDEM values.")
        print("Rebuilding the comparison table (all dataset springs); this can take an hour")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_spring_features.py"),
                        "--cache", str(cache), "--local-layers", str(local), "--keep-hwsd"], check=True)
    mod = layers_module()
    mod.set_offline(False)
    points = [(float(r["latitude_dd"]), float(r["longitude_dd"])) for r in csv.DictReader(FEATURES_CSV.open(encoding="utf-8"))
              if r.get("latitude_dd") and r.get("longitude_dd")]
    if bbox:
        west, south, east, north = bbox
        steps = lambda lo, hi: [lo + i * 0.25 for i in range(int((hi - lo) / 0.25) + 1)]  # noqa: E731
        points += [(lat, lon) for lat in steps(south, north) for lon in steps(west, east)]
    print(f"Fetching map tiles for {len(points)} points (only missing tiles are downloaded)")
    dem = mod.dem_tiles_for(points, cache)
    wc = mod.worldcover_tiles_for(points, cache)
    for code, periods in (("L1-PCP-A", [str(y) for y in mod.YEARS]),
                          ("L1-PCP-M", [f"{y}-{m:02d}" for y in mod.YEARS for m in range(1, 13)]),
                          ("L1-RET-A", [str(y) for y in mod.YEARS])):
        mod.WaporStack(code, periods, cache=cache)
    files = [entry("SRC-018", "layer_cache", p) for p in dem] + [entry("SRC-019", "layer_cache", p) for p in wc]
    files += [entry("SRC-020", "layer_cache", p) for p in sorted((cache / "wapor").glob("*.npz"))]
    for source_id, folder, pattern in LOCAL_FILES:
        found = sorted((local / folder).glob(pattern))
        if not found:
            print(f"Note: no {pattern} files in {folder}/ under SPRING_LOCAL_LAYERS; {source_id} is left out of the set")
        files += [entry(source_id, "local_layers", p) for p in found]
    files += [entry(source_id, "repo", ROOT / path) for source_id, path in REPO_FILES]
    fingerprint = hashlib.sha256("".join(sorted(f["sha256"] for f in files)).encode()).hexdigest()[:8]
    present_dem = {p.name.split("_")[4] + p.name.split("_")[6] for p in dem}  # N30 + E078 from the Copernicus name
    manifest = {
        "snapshot_id": f"MA-{datetime.now(timezone.utc):%Y%m%d}-{fingerprint}",
        "kind": "Spring tool map set (Modules A, B and C)",
        "approval_status": "pending_review",
        "prepared_utc": now(), "prepared_by": by, "code_version": code_version(),
        "approved_utc": None, "approved_by": None,
        "coverage": {"dem_cells": sorted(present_dem),
                     "worldcover_tiles": sorted(p.name.split("_")[5] for p in wc),
                     "points": len(points), "extra_bbox_wgs84": list(bbox) if bbox else None},
        "files": files,
        "not_included": NOT_INCLUDED,
    }
    save(manifest, SNAPSHOTS / f"{manifest['snapshot_id']}.json")
    size = sum(f["bytes"] for f in files) / 1e9
    print(f"Prepared {manifest['snapshot_id']}: {len(files)} files, {size:.2f} GB, "
          f"{len(present_dem)} elevation cells, {len(wc)} land-cover tiles.")
    print(f"Next: check it, then approve it with:\n  python scripts/module_a_snapshot.py approve {manifest['snapshot_id']} --by \"Your name\"")
    return manifest


def verify(snapshot_id=None) -> int:
    manifest = load(snapshot_id)
    if manifest is None:
        print("No such map set." if snapshot_id else "No approved map set yet. Run prepare, then approve.")
        return 1
    problems = check_files(manifest)
    for line in problems:
        print(line)
    print(f"{manifest['snapshot_id']}: {len(manifest['files']) - len(problems)} of {len(manifest['files'])} files match"
          + ("" if problems else " - all good"))
    return 1 if problems else 0


def approve(snapshot_id, by) -> int:
    manifest = load(snapshot_id)
    if manifest is None:
        print(f"No map set called {snapshot_id}.")
        return 1
    problems = check_files(manifest)
    if problems:
        print("Not approved; these files do not match the manifest:\n" + "\n".join(problems))
        return 1
    manifest.update(approval_status="approved", approved_by=by, approved_utc=now())
    save(manifest, SNAPSHOTS / f"{snapshot_id}.json")
    save(manifest, ACTIVE)
    print(f"Approved {snapshot_id} (by {by}). Assessments now use this set and download nothing.")
    return 0


def status() -> int:
    manifest = active()
    if manifest is None:
        print("No approved map set: assessments read Module A's layer cache and may download tiles.")
        return 1
    size = sum(f["bytes"] for f in manifest["files"]) / 1e9
    print(f"Approved map set {manifest['snapshot_id']}: {len(manifest['files'])} files, {size:.2f} GB; "
          f"approved by {manifest['approved_by']} on {manifest['approved_utc'][:10]}.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--rebuild-reference", action="store_true")
    p.add_argument("--by")
    p = sub.add_parser("verify")
    p.add_argument("snapshot_id", nargs="?")
    p = sub.add_parser("approve")
    p.add_argument("snapshot_id")
    p.add_argument("--by", required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.bbox, args.rebuild_reference, args.by)
        return 0
    if args.command == "verify":
        return verify(args.snapshot_id)
    if args.command == "approve":
        return approve(args.snapshot_id, args.by)
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
