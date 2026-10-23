# Secondary data inventory

Date: 2026-10-23 (model changes: several layers moved from data only to In use). This page lists every map layer the project holds, where it is kept and whether the tool uses it.
Laptop paths are under `C:\Users\rajat\Downloads\DOCC\Data\Secondary data\` unless shown otherwise.
Source IDs (SRC-nnn) point to `docs/source-register/source-register.csv`.

Status:
- **In use**: read today by the dataset build (`scripts/build_spring_features.py`) or by Module A, B or C.
- **In master (data only)**: a value for every spring is in the master file (`scripts/build_spring_secondary_features.py`), but no module reads it yet.

Since 2026-10-23 the tool reads the secondary layers through `scripts/secondary_layers.py`, the same reader the dataset build uses.
- **Pending**: not yet in hand.

## Terrain, land and climate

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| Copernicus DEM 30 m | SRC-018 | downloaded to `MapCache` by the tool | All springs | In use | Slope, catchments, relief |
| CartoDEM v3 30 m | SRC-022 | `Bhoonidhi` | 14 tiles, Uttarakhand | In use (cross-check) | |
| ESA WorldCover 2021, 10 m | SRC-019 | `MapCache` | All springs | In use | Tree cover is one class: no dense/open split |
| Sentinel-2 NDVI, Oct-Nov 2025, 20 m | SRC-033 | `Sentinel2` | Tehri district | In use (Module B) | Forest density: splits tree cover into dense, open and sparse in the recharge-zone score. Provisional cut-offs: dense >= 0.70, open 0.50-0.70. `scripts/build_sentinel2_ndvi.py` |
| IMD 0.25 degree rainfall 2001-2025 | SRC-023 | `IMD` | India | In use | 2012 file now present but not yet used |
| CHIRPS rainfall and ET0 (WaPOR) | SRC-020 | `MapCache` | All springs | In use | |
| ERA5 winter snowfall 2019-20 to 2024-25 (water equivalent) and ERA5 ground height | SRC-035 via TRN-021 | in the repo: `data/02_processed/climate/` (2 KB grid + snow-height curve) | lon 76-81.1, lat 28.7-32.4 | In use (Module C; context in A) | 27 km cells average lower ground than the springs, so the model reads the snow-height curve at the spring's elevation. Snow matters only above about 1,900 m (44 mm at 1,875 m, 162 mm at 2,375 m). `scripts/build_era5_snowfall.py` |

## Soil

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| SoilGrids 2.0, 0-30 cm texture, carbon, gravel, bulk density | SRC-024 | `SoilGrids` | lon 76-81.1, lat 28.7-32.4 | In use | |
| HWSD v2.0 | SRC-021 | `MapCache` | All springs | In use | |
| Infiltration (Ksat 0-30 cm, Saxton-Rawls) | SRC-024 via TRN-018 | `Infiltration` | Same as SoilGrids | In master (data only) | Median 15 mm/h; varies little between nearby sites. `scripts/build_soil_infiltration.py` |
| Depth to bedrock (SoilGrids 2017 BDRICM) | SRC-034 | `SoilGrids` (`BDRICM_M_250m_Uttarakhand.tif`) | lon 76-81.1, lat 28.7-32.4 | In use (Module A shallow soil; Module B soil depth) | cm, capped at 200 (about 10% of springs at the cap). Median 150 cm |

## Geology and structure

| Layer | Source | Laptop folder | Coverage | Status | Notes |
|---|---|---|---|---|---|
| Lithology | SRC-014 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| Faults | SRC-013 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| Folds | SRC-015 | `NGDR(Bhukosh)` | Uttarakhand | In use | |
| DEM lineament candidates | TRN-008 | in the repo | Spring tiles | In use | Automatic, unverified |
| Mapped lineaments 1:250k (joints, faults, shear zones) | SRC-030 | `NGDR(Bhukosh)` | Uttarakhand | In use (Module B: distance to structure, links to the spring) | 345 joints/fractures mapped by geologists |
| Geomorphology 1:250k | SRC-029 | `NGDR(Bhukosh)` | Uttarakhand | In master (data only) | Too coarse: most hill springs fall in one class |
| Landslide polygons | SRC-031 | `NGDR(Bhukosh)` | Uttarakhand | In use (Module A) | 281 springs have one within about 500 m |
| Dip and dip direction (oriented structure planes) | SRC-032 | `NGDR(Bhukosh)` | Kumaon sheets 53O, 62C, 53N only | In use (Module B, when no field dip; within 2 km) | Nothing near Tehri; take a compass reading in the field (AQ-014) |
| Geomorphology and lineament 1:50k (NRSC) | AQ-015 | | | Dropped for now | Bhuvan offers no download |

## Springsheds drawn by geologists

| Layer | Source | Where | Status | Notes |
|---|---|---|---|---|
| Badeda and Makhdet report catchments | SRC-027, SRC-028 via TRN-019 | `Report catchments` and `data/01_staged/literature/geojson/report_catchments_v1.geojson` | In master (data only) | Traced from the report maps: Badeda 12.4 ha (report says 40.51), Makhdet 94.3 ha (report 91.07). Both springs are in the test set: use for the final check only, never for tuning |

WATSAN has no catchment boundary files (Rajat, 2026-10-22).

## New columns in the master file

21 columns, placed after the GSI structure columns. Values are blank where a layer does not cover the spring.

| Columns | Springs with a value (of 1,845 records) |
|---|---|
| `bhukosh_geomorphology_250k`, `bhukosh_lineament_*`, `bhukosh_joint_distance_m`, `landslide_*` | 1,766 (Uttarakhand) |
| `gsi_dip_*` (nearest measurement within 5 km, median dip) | 1,159 (Kumaon) |
| `ndvi_s2_2025`, `forest_dense_500m_pct`, `forest_open_500m_pct` | 344 (Tehri) |
| `soil_ksat_0_30cm_mm_h` | 1,799 |
| `soil_depth_to_bedrock_cm` | 1,807 |
| `era5_snowfall_winter_mm`, `snow_at_elevation_mm` | 1,808 |
| `report_catchment_ha` | 2 (Badeda, Makhdet; test springs) |

## Still missing

- Rock dip for Tehri: a compass reading at each spring on the next field visit (AQ-014).
- Dated dry-season flows and before/after DI readings (AQ-003).
- Forest density outside Tehri: rerun `scripts/build_sentinel2_ndvi.py` with a wider area if the model needs it.
