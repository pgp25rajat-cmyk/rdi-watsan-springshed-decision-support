"""Mean winter snowfall (mm water equivalent) over the study area from ERA5, for the spring tool.

IMD and CHIRPS are rain products: snow that falls on the hills is not counted, or counted poorly. ERA5 (ECMWF
reanalysis, 0.25 degree, about 27 km) has snowfall as its own field. The NSF NCAR copy on AWS (nsf-ncar-era5,
open, no account) is read over HTTP: field 128_144 SF (snowfall, m of water equivalent, hourly accumulations),
two files a month. Only the window over the study area is kept.

Winters November-April, 2019-20 to 2024-25 (6 winters; snow outside these months is negligible at spring
elevations). Output: a GeoTIFF of mean snowfall per winter (mm water equivalent), EPSG:4326, 0.25 degree.

Limits: a 27 km cell averages valleys and ridges, so it says how snowy the area is, not how much snow falls on the
spring's own slope. ERA5 cells over the hills sit near 1,500 m on average, so a spring at 2,300 m gets the snow of a
1,500 m cell (almost none). The script therefore also writes ERA5's own snow-height curve: the median winter snowfall of
the cells in each 250 m band of ERA5 ground height (ERA5 orography, field 128_129 Z), using only cells below 4,000 m so
the dry Tibetan plateau is left out. Reading that curve at the spring's own height gives the snow a cell at that height
receives in ERA5. Output: OUT.tif plus OUT_curve.csv (elevation_m, snow_mm).

Usage: python scripts/build_era5_snowfall.py OUT.tif [--cache DIR] [--workers 3]
"""

import argparse
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from rasterio.windows import from_bounds

BUCKET = "https://nsf-ncar-era5.s3.amazonaws.com"
PREFIX = "e5.oper.fc.sfc.accumu"
BBOX = (75.5, 28.5, 81.5, 33.5)  # W S E N, the tool's study area
WINTERS = range(2019, 2025)  # 2019 = November 2019 to April 2020
WINTER_MONTHS = (11, 12, 1, 2, 3, 4)


def month_files(year, month):
    listing = urllib.request.urlopen(f"{BUCKET}/?list-type=2&prefix={PREFIX}/{year}{month:02d}/", timeout=60).read().decode()
    import re
    return sorted(k for k in re.findall(r"<Key>([^<]*)</Key>", listing) if "128_144_sf" in k)


def window_sum(key, cache):
    cached = os.path.join(cache, os.path.basename(key) + ".npy")
    if os.path.exists(cached):
        return np.load(cached), None
    # Download the whole file (about 155 MB) and read it locally: reading it over HTTP with GDAL re-fetches the same
    # chunks for every one of its 360 hourly bands and is about 50 times slower.
    local = os.path.join(cache, os.path.basename(key))
    for attempt in range(4):
        try:
            urllib.request.urlretrieve(f"{BUCKET}/{key}", local)
            with rasterio.open(f'netcdf:"{local}":SF') as src:
                window = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
                total = src.read(window=window).sum(axis=0) * 1000  # m -> mm water equivalent
                transform = src.window_transform(window)
            np.save(cached, total)
            print("done", os.path.basename(key), flush=True)
            return total, transform
        except Exception as error:  # network hiccups through proxies
            if attempt == 3:
                raise
            print("retry", key, error, flush=True)
            time.sleep(10 * (attempt + 1))
        finally:
            if os.path.exists(local):
                os.remove(local)


OROGRAPHY = "e5.oper.invariant/197901/e5.oper.invariant.128_129_z.ll025sc.1979010100_1979010100.nc"
CURVE_MAX_M = 4000  # higher cells are mostly the dry Tibetan plateau
CURVE_STEP_M = 250


def snow_curve(mean, cache):
    """[(band centre m, median snow mm)] from ERA5 cells below CURVE_MAX_M, by their ERA5 ground height."""
    local = os.path.join(cache, "orography.nc")
    if not os.path.exists(local):
        urllib.request.urlretrieve(f"{BUCKET}/{OROGRAPHY}", local)
    with rasterio.open(f'netcdf:"{local}":Z') as src:
        window = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
        height = src.read(1, window=window) / 9.80665  # geopotential -> m
    curve = []
    for low in range(0, CURVE_MAX_M, CURVE_STEP_M):
        cells = mean[(height >= low) & (height < low + CURVE_STEP_M)]
        if cells.size >= 3:
            curve.append((low + CURVE_STEP_M / 2, float(np.median(cells))))
    return curve


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("--cache", default=".layer_cache/era5_snowfall")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    os.makedirs(args.cache, exist_ok=True)
    keys = []
    for winter in WINTERS:
        for month in WINTER_MONTHS:
            year = winter if month >= 11 else winter + 1
            keys += month_files(year, month)
    print(len(keys), "files", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda k: (k, *window_sum(k, args.cache)), keys))
    total = sum(r[1] for r in results)
    mean = (total / len(WINTERS)).astype("float32")
    transform = next((r[2] for r in results if r[2] is not None), None)
    if transform is None:  # every file came from the cache: work the grid out from the bounding box (0.25 degree cells)
        from rasterio.transform import from_origin
        transform = from_origin(round((BBOX[0] + 0.125) * 4) / 4 - 0.125, round((BBOX[3] - 0.125) * 4) / 4 + 0.125, 0.25, 0.25)
    with rasterio.open(args.out, "w", driver="GTiff", width=mean.shape[1], height=mean.shape[0], count=1, dtype="float32",
                       crs="EPSG:4326", transform=transform, compress="deflate") as dst:
        dst.write(mean, 1)
        dst.update_tags(description="ERA5 mean snowfall per winter (Nov-Apr), mm water equivalent, winters 2019-20 to 2024-25",
                        source="NSF NCAR ERA5 on AWS, e5.oper.fc.sfc.accumu 128_144_sf", files=str(len(keys)))
    curve = snow_curve(mean, args.cache)
    with open(os.path.splitext(args.out)[0] + "_curve.csv", "w", encoding="utf-8") as handle:
        handle.write("elevation_m,snow_mm\n" + "".join(f"{e:.0f},{v:.1f}\n" for e, v in curve))
    print("written", args.out, "max", float(mean.max()), "mm; curve", curve)


if __name__ == "__main__":
    main()
