"""Topsoil infiltration capacity: saturated hydraulic conductivity (Ksat, mm/h) for 0-30 cm.

Saxton and Rawls (2006) pedotransfer equations from SoilGrids 2.0 sand, clay and organic carbon, with their
gravel correction from coarse fragments. The three depths (0-5, 5-15, 15-30 cm) are averaged by thickness.
Organic matter = organic carbon x 1.724, capped at 8% (the equations' range). The organic carbon export is
read as SOC in dg/kg; if it was OCD (density) instead, organic matter is only roughly right (SRC-024 note).

A texture-based estimate: it ignores cracks, roots and macropores, so real hillslope infiltration is often
higher. At 250 m it changes little between nearby slopes (13-15 mm/h across the Tehri field sites).

Usage: python scripts/build_soil_infiltration.py SOILGRIDS_DIR OUT.tif
SOILGRIDS_DIR holds the folders "0-5 soilgrids", "5-15 soilgrids" and "15-30 soilgrids" (DOCC/Data/Secondary data/SoilGrids).
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio

DEPTHS = [("0-5 soilgrids", 5), ("5-15 soilgrids", 10), ("15-30 soilgrids", 15)]


def read(folder, name):
    matches = [p for p in folder.glob("*.tif") if p.stem.lower() == name]
    with rasterio.open(matches[0]) as src:
        return src.read(1).astype("float32"), src.profile


def saxton_rawls_ksat(sand, clay, organic_matter, gravel):
    """Fractions for sand, clay and gravel (by volume); organic matter in %. Returns mm/h."""
    S, C, OM = sand, clay, organic_matter
    t1500 = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    wilting = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    field_capacity = t33 + (1.283 * t33 ** 2 - 0.374 * t33 - 0.015)
    ts33 = 0.278 * S + 0.034 * C + 0.022 * OM - 0.018 * S * OM - 0.027 * C * OM - 0.584 * S * C + 0.078
    saturated = field_capacity + ts33 + (0.636 * ts33 - 0.107) - 0.097 * S + 0.043
    lam = (np.log(field_capacity) - np.log(wilting)) / (np.log(1500) - np.log(33))
    ksat = 1930 * np.clip(saturated - field_capacity, 1e-4, None) ** (3 - lam)
    alpha = (1 - saturated)  # matric density / 2.65
    return ksat * (1 - gravel) / (1 - gravel * (1 - 1.5 * alpha))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("soilgrids_dir", type=Path)
    parser.add_argument("out")
    args = parser.parse_args()

    total, profile = None, None
    for folder, thickness in DEPTHS:
        path = args.soilgrids_dir / folder
        sand, profile = read(path, "sand")
        clay, _ = read(path, "clay")
        carbon, _ = read(path, "organic carbon")
        coarse, _ = read(path, "coarse")
        organic_matter = np.clip(carbon / 100 * 1.724, 0, 8)  # dg/kg -> % carbon -> % organic matter
        ksat = np.where((sand > 0) & (clay > 0),
                        saxton_rawls_ksat(sand / 1000, clay / 1000, organic_matter, np.clip(coarse / 1000, 0, 0.8)), np.nan)
        total = ksat * thickness if total is None else total + ksat * thickness
    result = (total / sum(t for _, t in DEPTHS)).astype("float32")
    profile.update(dtype="float32", nodata=np.nan, compress="deflate")
    with rasterio.open(args.out, "w", **profile) as dst:
        dst.write(result, 1)
        dst.update_tags(description="Saturated hydraulic conductivity mm/h, 0-30 cm, Saxton & Rawls 2006 from SoilGrids 2.0")
    values = result[np.isfinite(result)]
    print("Ksat mm/h, 5/25/50/75/95th percentile:", np.percentile(values, [5, 25, 50, 75, 95]).round(1))


if __name__ == "__main__":
    main()
