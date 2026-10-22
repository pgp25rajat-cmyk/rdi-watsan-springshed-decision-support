# Secondary data inventory

Date: 2026-10-22. This page lists every map layer the project holds, where it is kept and whether the tool uses it.
Laptop paths are under `C:\Users\rajat\Downloads\DOCC\Data\Secondary data\` unless shown otherwise.
Source IDs (SRC-nnn) point to `docs/source-register/source-register.csv`.

Status:
- **In use**: read today by the dataset build (`scripts/build_spring_features.py`) or by Module A, B or C.
- **Data only**: collected and checked, but not used by the model. Rajat (2026-10-22): finalise the data first; model changes come later.
- **Pending**: not yet in hand.

## Terrain, land and climate

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| Copernicus DEM 30 m | SRC-018 | downloaded to `MapCache` by the tool | All springs | In use | Slope, catchments, relief |
| CartoDEM v3 30 m | SRC-022 | `Bhoonidhi` | 14 tiles, Uttarakhand | In use (cross-check) | |
| ESA WorldCover 2021, 10 m | SRC-019 | `MapCache` | All springs | In use | Tree cover is one class: no dense/open split |
| Sentinel-2 NDVI, Oct-Nov 2025, 20 m | SRC-033 | `Sentinel2` | Tehri district | Data only | Forest density. Provisional cut-offs: dense >= 0.70, open 0.50-0.70. `scripts/build_sentinel2_ndvi.py` |
| IMD 0.25 degree rainfall 2001-2025 | SRC-023 | `IMD` | India | In use | 2012 file now present but not yet used |
| CHIRPS rainfall and ET0 (WaPOR) | SRC-020 | `MapCache` | All springs | In use | |

## Soil

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| SoilGrids 2.0, 0-30 cm texture, carbon, gravel, bulk density | SRC-024 | `SoilGrids` | lon 76-81.1, lat 28.7-32.4 | In use | |
| HWSD v2.0 | SRC-021 | `MapCache` | All springs | In use | |
| Infiltration (Ksat 0-30 cm, Saxton-Rawls) | SRC-024 via TRN-018 | `Infiltration` | Same as SoilGrids | Data only | Median 15 mm/h; varies little between nearby sites. `scripts/build_soil_infiltration.py` |
| Depth to bedrock (SoilGrids 2017 BDRICM) | AQ-013 | `SoilGrids` (to come) | | Pending | Rajat downloading |

## Geology and structure

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| Lithology | SRC-014 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| Faults | SRC-013 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| Folds | SRC-015 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| DEM lineament candidates | TRN-008 | in the repo | Spring tiles | In use | Automatic, unverified |
| Mapped lineaments 1:250k (joints, faults, shear zones) | SRC-030 | `NGDR(Bhukosh)` | Uttarakhand | Data only | 345 joints/fractures mapped by geologists |
| Geomorphology 1:250k | SRC-029 | `NGDR(Bhukosh)` | Uttarakhand | Data only | Too coarse: most hill springs fall in one class |
| Landslide polygons | SRC-031 | `NGDR(Bhukosh)` | Uttarakhand | Data only | 281 springs have one within about 500 m |
| Dip and dip direction (oriented structure planes) | SRC-032 | `NGDR(Bhukosh)` | Kumaon sheets 53O, 62C, 53N only | Data only | Nothing near Tehri; take a compass reading in the field (AQ-014) |
| Geomorphology and lineament 1:50k (NRSC) | AQ-015 | | | Dropped for now | Bhuvan offers no download |

## Springsheds drawn by geologists

| Layer | Source | Where | Status | Notes |
|---|---|---|---|---|
| Badeda and Makhdet report catchments | SRC-027, SRC-028 via TRN-019 | `Report catchments` and `data/01_staged/literature/geojson/report_catchments_v1.geojson` | Data only | Traced from the report maps: Badeda 12.4 ha (report says 40.51), Makhdet 94.3 ha (report 91.07). Both springs are in the test set: use for the final check only, never for tuning |

WATSAN has no catchment boundary files (Rajat, 2026-10-22).
