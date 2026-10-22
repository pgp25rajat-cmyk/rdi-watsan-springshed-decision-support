"""Post-monsoon Sentinel-2 NDVI for Tehri Garhwal, as a forest-density layer.

For each Sentinel-2 tile over the district, the 4 clearest L2A scenes from 10 October to 30 November 2025 are
read from the public AWS bucket (sentinel-cogs, Element 84). Cloud, shadow, snow and saturated pixels are masked
with the scene classification (SCL). NDVI is computed at 20 m, reprojected to EPSG:4326 and the median of all
clear scenes is kept. Early October is skipped (monsoon tail, more cloud).

Output: one GeoTIFF, NDVI x 100 as int8, nodata -128 (about 2% of the district has no clear view).
Provisional forest classes (not used by the model yet): dense forest NDVI >= 0.70, open forest 0.50-0.70.

Usage: python scripts/build_sentinel2_ndvi.py OUT.tif [--cache DIR]
The per-scene cache lets an interrupted run restart where it stopped. Set GDAL_HTTP_TIMEOUT=60 on slow links.
"""

import argparse
import json
import os
import re
import time
import urllib.request

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
TILES = ["43/R/GP", "43/R/GQ", "44/R/KU", "44/R/KV", "44/R/LU", "44/R/LV"]
MONTHS = [("2025", "10"), ("2025", "11")]
N_SCENES = 4
BBOX = (77.9, 29.95, 79.05, 30.9)  # W S E N, Tehri Garhwal
RES = 0.0002  # about 20 m
BAD_SCL = {0, 1, 3, 8, 9, 10, 11}  # no data, saturated, shadow, cloud medium/high, cirrus, snow


def retry(fn, *args):
    for attempt in range(5):
        try:
            return fn(*args)
        except Exception as error:  # network errors through proxies vary in type
            if attempt == 4:
                raise
            print("retry", error, flush=True)
            time.sleep(2 ** attempt * 3)


def fetch_text(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode()


def read_band(url, band):
    """B04/B08 are 10 m: read at half size (20 m) by averaging. SCL is already 20 m."""
    factor = 1 if band == "SCL" else 2
    with rasterio.open(url) as src:
        shape = (src.height // factor, src.width // factor)
        data = src.read(1, out_shape=shape, resampling=Resampling.nearest if band == "SCL" else Resampling.average)
        return data, src.transform * src.transform.scale(src.width / shape[1], src.height / shape[0]), src.crs


def clearest_scenes(tile):
    found = []
    for year, month in MONTHS:
        listing = retry(fetch_text, f"{BUCKET}/?list-type=2&prefix=sentinel-s2-l2a-cogs/{tile}/{year}/{month}/&delimiter=/")
        for prefix in re.findall(r"<Prefix>([^<]*_L2A/)</Prefix>", listing):
            name = prefix.rstrip("/").split("/")[-1]
            if month == "10" and int(name.split("_")[2][6:8]) < 10:
                continue
            try:
                props = json.loads(retry(fetch_text, f"{BUCKET}/{prefix}{name}.json"))["properties"]
            except Exception:
                continue
            found.append((props.get("eo:cloud_cover", 100), prefix, props))
    return sorted(found, key=lambda item: item[0])[:N_SCENES]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("--cache", default=".layer_cache/sentinel2")
    args = parser.parse_args()
    os.makedirs(args.cache, exist_ok=True)

    west, south, east, north = BBOX
    width, height = int(round((east - west) / RES)), int(round((north - south) / RES))
    dst_transform = from_origin(west, north, RES, RES)
    stack = []
    for tile in TILES:
        for cloud, prefix, props in clearest_scenes(tile):
            cached = os.path.join(args.cache, prefix.split("/")[-2] + ".npy")
            if os.path.exists(cached):
                stack.append(np.load(cached))
                continue
            # Processing baseline 04.00+ adds 1000 to reflectance unless the offset was already applied
            offset = 0 if props.get("earthsearch:boa_offset_applied") else (1000 if float(props.get("s2:processing_baseline", "0")) >= 4 else 0)
            bands = {band: retry(read_band, f"{BUCKET}/{prefix}{band}.tif", band) for band in ("B04", "B08", "SCL")}
            red = (bands["B04"][0].astype("float32") - offset) / 10000
            nir = (bands["B08"][0].astype("float32") - offset) / 10000
            ndvi = (nir - red) / np.maximum(nir + red, 1e-6)
            ndvi[np.isin(bands["SCL"][0], list(BAD_SCL)) | (bands["B04"][0] == 0)] = np.nan
            grid = np.full((height, width), np.nan, "float32")
            reproject(ndvi, grid, src_transform=bands["B04"][1], src_crs=bands["B04"][2], dst_transform=dst_transform,
                      dst_crs="EPSG:4326", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
            if np.isfinite(grid).any():
                stack.append(grid.astype("float16"))
                np.save(cached, stack[-1])
            print(tile, prefix.split("/")[-2], f"cloud {cloud:.1f}%", flush=True)

    scenes = np.stack(stack)
    median = np.full((height, width), np.nan, "float32")
    for row in range(0, height, 500):
        median[row:row + 500] = np.nanmedian(scenes[:, row:row + 500].astype("float32"), axis=0)
    code = np.where(np.isfinite(median), np.clip(np.round(median * 100), -100, 100), -128).astype("int8")
    with rasterio.open(args.out, "w", driver="GTiff", width=width, height=height, count=1, dtype="int8",
                       crs="EPSG:4326", transform=dst_transform, nodata=-128, compress="deflate", tiled=True) as dst:
        dst.write(code, 1)
        dst.update_tags(description="Sentinel-2 L2A NDVI x 100, median of the clearest scenes 10 Oct - 30 Nov 2025, "
                                    "cloud/shadow/snow masked (SCL)", scenes=str(len(stack)))
    print("written", args.out, "scenes", len(stack), "no-data share", round(float(np.isnan(median).mean()), 3))


if __name__ == "__main__":
    main()
