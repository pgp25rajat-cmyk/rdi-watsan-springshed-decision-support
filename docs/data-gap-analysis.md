# Data gap analysis and public-layer enrichment (v1)

Date: 2026-10-10. Input: `data/01_staged/common/csv/spring_records_common_v1.csv`, which has 1,842 records. Output: `data/02_processed/spring_features/`.

## 1. What the common file was missing

The table shows the share of records with a value, by source.

| Field | WATSAN (299) | Atlas annexure (948) | Himmotthan (542) | Literature (53) | Gap |
|---|---|---|---|---|---|
| Coordinates | 100% | 100% | 100% | 17 of 53 | Rathi (35) and Mathamali have none; 3 Atlas coordinates are typing errors |
| Elevation | 100% | 100% | 92% | 17 of 53 | Small |
| Discharge | 100% (text estimates) | **0%** | 99% (one-off) | 53 of 53 | No dated, repeated measurements anywhere except 10 Atlas profiles and Mathamali |
| Slope / aspect | 100% | **0%** | 92-99% | 7 of 53 | Atlas has none |
| Land use | 100% (code mislabelled) | **0%** | 92% | 0 | Mostly missing or unreliable |
| Rainfall | 100% | **0%** | **0%** | 17 of 53 | Mostly missing |
| Lithology / rock type | 100% (text) | **0%** | 92% | 17 of 53 | Atlas has none; now filled from the GSI map for all Uttarakhand springs (section 2) |
| Geological structure / lineaments | 100% (text) | **0%** | **0%** | 16 of 53 | No distance-to-lineament for any record (now filled from DEM lineaments; see section 2) |
| Soil | **0%** | **0%** | **0%** | 0 | Missing everywhere |
| Recharge / springshed area | 100% (estimates) | **0%** | **0%** | 52 of 53 | Only the Atlas profiles, Rathi and Chamba have delineated areas |
| Water quality (pH, TDS) | **0%** | **0%** | 99% | 10 of 53 | WATSAN and Atlas have none |
| Seasonality / variability | 100% (text labels) | **0%** | **0%** | 11 of 53 | No discharge time series except 10 Atlas profiles and Mathamali |
| Dependency (households, use) | **0%** | **0%** | **0%** | 0 | Not in any source |
| DI / recharge interventions | 0% | 0% | 0% | 18 of 53 | Only Chamba, Mathamali and the Atlas profiles |

Two problems are about data quality rather than gaps:
- **Duplicates across sources.** 217 groups of 448 records sit within 30 m of each other. 150 of these groups pair an Atlas row with a Himmotthan row, so the file probably holds about 1,570 distinct springs, not 1,803.
- **WATSAN values.** WATSAN elevations match the DEM to within about 5 m, which suggests they were themselves taken from a DEM. 9 WATSAN points fall on water pixels in WorldCover. Recharge areas and discharge are text estimates such as "55–65" or "~2–8 lpm dry".

## 2. What public layers could fill, and what was reached

| Layer asked for | Status | What was used |
|---|---|---|
| 30 m DEM | **Done** with Copernicus GLO-30 (AWS open data) | Elevation, slope, aspect, 500 m mean slope, 1 km relief, upslope relief, topographic position; drainage area, wetness index, distance to stream, stream order, height above stream (`scripts/spring_hydrology.py`) |
| CartoDEM (NRSC Bhoonidhi) | **Done** with 14 tiles Rajat downloaded by hand | Elevation and slope as a cross-check on Copernicus |
| Land use | **Done** with ESA WorldCover 2021 v200, 10 m (AWS open data) | Class at the spring, majority class and class shares within 500 m |
| Bhuvan LULC 1:50k | Not reached: Bhuvan is blocked from this environment and download needs a request | — |
| Rainfall | **Done** with CHIRPS v2 annual and monthly 2018-2025, as republished by FAO WaPOR v3 (~5 km) | Mean, minimum, maximum, year-to-year variation, monsoon share, dry-season rain, plus FAO reference ET0 and an aridity index |
| IMD 0.25° gridded rainfall | **Done** for 2021-2025, from the files Rajat downloaded | Five-year mean, driest and wettest year, year-to-year variation, monsoon share, rainy days, wettest day, and each year's total |
| Soil | **Done** with the FAO/IIASA Harmonized World Soil Database v2.0 (~1 km) | Dominant soil (WRB), drainage, available water capacity, topsoil sand/silt/clay, texture, coarse fragments, organic carbon |
| ISRIC SoilGrids 250 m | **Done** for 0-5, 5-15 and 15-30 cm, from 17 exports Rajat downloaded | Clay, silt, sand, coarse fragments, bulk density, organic carbon density per depth, and 0-30 cm depth-weighted means |
| Lineaments | **Done** as DEM-derived candidates (`scripts/extract_dem_lineaments.py`) | Distance to nearest lineament and lineament density within 1 km |
| Geology, faults and folds (GSI Bhukosh / NGDR) | **Done** from the Uttarakhand lithology, fault and fold layers the team added to `data/00_raw/ngdr_geology/` | Rock unit (description, group, formation, age), distance to the unit edge, distance to the nearest fault and thrust, fault type and name, fault density within 1 km, distance to the nearest fold axis, anticline and syncline, fold type, fold axes within 2 km |

After this step, 1,803 of 1,842 records (98%) have every terrain, land-cover, rainfall and soil value. The other 39 records have no usable coordinates.

### GSI geology (added later on 2026-10-10)

The team downloaded the NGDR Uttarakhand lithology (4,554 polygons) and fault (2,605 lines) layers from Bhukosh into the repo. `build_spring_features.py` overlays them on each spring:
- **1,761 springs** fall inside the Uttarakhand map and get a rock unit and fault distances. The other 42 (Kangra and Sirmaur in Himachal) stay blank.
- Springs sit mostly in the Garhwal (537), Jaunsar (353) and Almora (343) groups.
- The median spring is 2.5 km from a mapped fault and 4.7 km from a mapped thrust; 230 springs are within 500 m of a fault. The North Almora Thrust is the nearest named fault for 302 springs.
- **Field vs map rock type:** where a spring has both, the field description shares at least one rock class with the GSI polygon for 677 of 980 records (69%). The rest are likely small outcrops the state map does not show, or springs near a contact.
- **DEM lineaments vs GSI faults:** distance to the nearest DEM lineament has almost no relation to distance to the nearest GSI fault (rank correlation 0.03). The DEM lineaments mostly pick up ridges and valleys at a finer scale than the mapped faults. Use the GSI faults for structure and treat the DEM lineaments as a separate, unvalidated fracture signal.
- **Folds (added 2026-10-12):** the NGDR fold layer has 290 fold axes. They are sparse at state scale: the median spring is 8.8 km from the nearest axis (10-90%: 1.8-21.6 km), so fold distance will mostly separate regions rather than individual springs.

### Hand-downloaded layers (added later on 2026-10-10)

Rajat downloaded CartoDEM, IMD 2025 rainfall and SoilGrids by hand. The raw files stay in `DOCC/Data/` and are not committed; `build_spring_features.py --local-layers DIR` reads them. What they show:
- **CartoDEM** covers 1,780 springs (no tile for the 23 Kangra springs). It sits a steady ~44 m below Copernicus (middle 90%: 26-58 m). That matches the geoid height in this region, so the tiles are most likely ellipsoidal heights, not sea-level heights. Slopes agree with Copernicus (median 20.8 vs 21.4 degrees). Use Copernicus as the main DEM.
- **IMD 2025** is a single year at ~25 km. Median 1,436 mm against a CHIRPS 2018-2025 mean of 1,817 mm, and some hill cells fall to ~560 mm. IMD grids are thin on hill stations, so treat these as a cross-check, not a replacement.
- **SoilGrids** 0-5 cm files arrived unnamed (`out.tif` to `out (4).tif`). They were first identified from their value ranges, and three of those labels turned out wrong (corrected on 2026-10-12, see below). At 250 m they separate springs much better than HWSD: 82 distinct clay values against 4.
- **IMD 2021-2025 (added 2026-10-12):** the five-year mean at the median spring is 1,245 mm against 1,817 mm from CHIRPS, and year-to-year variation is 15%. IMD stays well below CHIRPS in the hills, so keep CHIRPS as the main rainfall and IMD as the check. (The earlier single-year 2025 median was 1,436 mm; 2025 was a wet year.)
- **SoilGrids 5-15 and 15-30 cm (added 2026-10-12):** these files came named by property, which exposed a mistake in the 0-5 cm labels. Matching each unnamed 0-5 cm file to the named 5-15 cm file it tracks pixel by pixel (rank correlation 0.95-0.99) shows `out (2)` is coarse fragments (not organic carbon), `out (3)` is sand (not silt) and `out (4)` is organic carbon (not sand). The 2026-10-10 build had those three columns wrong; they are fixed. There is no 0-5 cm silt file, so 0-5 cm silt is 100 - clay - sand (it matches the 5-15 cm silt closely). The master file now uses 0-30 cm depth-weighted means. Organic carbon is read as density (kg/m3), as Rajat described the download; if it was the content layer (soc) the unit is g/kg instead.
- **DEM lineaments**: 26,672 straight terrain lines of at least ~0.9 km from the Copernicus DEM. Median distance from a spring to the nearest is 618 m; median density within 1 km is 0.3 km/km2. These are unvalidated candidates: some are faults or fracture-controlled valleys, others are ordinary ridges. Copernicus was used rather than CartoDEM because it covers all spring tiles and has fewer artefacts.

### DEM hydrology (added 2026-10-12)

`scripts/spring_hydrology.py` works on the Copernicus DEM in a window around each spring (±5 km, widened to ±20 km when the catchment reaches the edge). It fills depressions, routes flow (single-direction D8 and multiple-direction MFD), and takes cells draining at least 0.5 km2 as streams. For the 1,572 distinct springs with a coordinate:
- **Drainage area** at the spring cell: median 1.6 ha (10-90%: 0.2-17 ha). Within about 30 m of the point it rises to a median 4.2 ha, so many springs sit right next to a hollow the 30 m DEM puts one cell over. Both columns are kept.
- **Wetness index (TWI):** median 7.4 (10-90%: 5.3-10.1), so most springs plot as ordinary hillslope, not as wet hollows. That is what a 30 m DEM shows for springs fed by fractures rather than by the surface catchment.
- **Distance to stream:** median 304 m; 343 springs are within 100 m of a DEM stream. Height above that stream (HAND): median 109 m. 73% drain to a first-order stream.
- **Drainage area is not recharge area.** For the 309 springs with a field or estimated recharge area, the DEM drainage area does not rise with it (rank correlation -0.16). TWI does not track discharge either (0.03, 831 springs). The surface catchment is a useful input for the springshed module, but the recharge zone has to come from geology (rock type, dip, faults) and not from the DEM alone.

## 3. What the processed file is (and isn't)

`spring_features_v1.csv` has one row per common-file record, with 132 columns:
- Cleaned identity: district spellings unified, coordinates parsed, coordinate status and precision, and a co-located group id for likely duplicates.
- Numbers parsed from the source text: elevation, discharge low/high, recharge-area low/high, rainfall, slope, TDS, pH. There are also two clearly named unit conversions: Rathi m3/day to L/min, and km2 to ha.
- Layer values for terrain, DEM hydrology, land cover, rainfall/ET0, soil, GSI geology, faults and folds, and DEM lineaments.
- `processing_notes` per row, for example a rounded coordinate or a DEM vs source elevation gap of more than 150 m (77 records).

Every column is defined in `spring_features_v1_data_dictionary.csv`. Fill rates by source are in `spring_features_v1_coverage_pct.csv`.

Limits to keep in mind:
- **Buffers are not recharge zones.** Layer values describe the pixel at the coordinate or a circle around it. They are not values for the spring's real recharge area, which is usually upslope. Module B should replace the 500 m circle with the delineated zone once it exists.
- **Rainfall is coarse.** CHIRPS (~5 km) and ET0 (~30 km) smooth out local differences. Source rainfall figures are on average 77 mm (WATSAN), 298 mm (Atlas profiles) and 431 mm (Chamba) below CHIRPS.
- **Soil varies little.** At HWSD's ~1 km scale, most springs fall in the same soil unit: 78% are Dystric Cambisols with loam topsoil and about 20% clay. Treat soil as context, not as a variable that tells springs apart.
- **Non-commercial licences.** WaPOR (CC BY-NC-SA 4.0) and HWSD (CC BY-NC-SA 3.0 IGO) allow only non-commercial use. That is fine for this project, but it needs attribution in reports.

## 4. Gaps that remain and how to close them

| Gap | Best route | Who |
|---|---|---|
| Geology for the 42 Himachal springs | Himachal lithology, fault and fold layers from Bhukosh if those springs stay in scope | Team |
| Check DEM lineaments | They do not follow GSI faults (section 2); spot-check against imagery or field mapping at pilot springs | Team |
| Repeated, dated discharge (dry and wet season) | Field survey (SRC-017 protocol), plus RDI/WATSAN monitoring records and Himmotthan MIS (AQ-003, AQ-012) | Team with WATSAN |
| Household dependency and use | Field survey / RDI village records (for example, the Malan table) | Team with WATSAN |
| DI before/after data | RDI monitoring records for the Chamba and Gairsain handpumps | WATSAN |
| Real recharge areas | Field hydrogeology at pilot springs, or Module B estimates checked against the 10 Atlas profiles, Rathi and Chamba | Team |
| Duplicates | Decide the 22 pairs on the master workbook's Duplicate review sheet (14 groups); the other 203 groups were settled by rule (section 7) | Team / WATSAN |
| Elevation gaps | Re-take GPS at the 12 springs where no point within 2 km has the source elevation (section 7) | Field team |
| Rathi and Mathamali coordinates | Ask NIH Roorkee or the authors | Team |

## 5. Final comprehensive file

`data/02_processed/spring_master/spring_master_v1.csv` (and `.xlsx`, with a Guide, Data dictionary and Fill summary sheet) brings everything into one table of 102 columns, one row per record:
- **Mapped values** (terrain, land cover, rainfall, soil, lineaments) come from the same layer for every spring, so springs can be compared. Each source's own value sits beside it.
- **Field values** (discharge, pH, TDS, spring type, lithology, recharge area) come from the record itself, or else from a record of another source within 30 m. That filled about 160 records per field, mostly Atlas annexure rows matched to Himmotthan. The `*_from` column names the record used.
- **`is_primary_record = Y`** keeps one row per spring: 1,679 distinct springs after the 2026-10-12 cleanup (section 7).
- **`duplicate_status` and `duplicate_group`** (added 2026-10-12) say, for the 448 records in the 217 groups within 30 m, which records are the same spring, which are separate springs and why, and which still need a person. See section 7.
- **Springshed inputs** (added 2026-10-12): drainage area, wetness index, distance to stream, stream order, height above stream, IMD 2021-2025 rainfall, 0-30 cm soil with coarse fragments, and fold distances.
- **Rock type:** `rock_class` uses the field description where there is one (980 records) and the GSI map otherwise (781), so 95% of distinct springs now have a rock class. Both the field and GSI versions stay in their own columns.
- **Spring type and lithology classes** group the free text (with spelling fixes) into Fracture, Depression, Contact, Karst, ... and Carbonate, Quartzite, Phyllite, Schist, Mixed, ...
- **`gaps_remaining`** lists what is still blank for each record.
- **Final check (2026-10-10):** district filled for 294 WATSAN springs from their area labels; WATSAN's dry and monsoon discharge figures added; WATSAN land-use codes decoded as ESA WorldCover classes (WATSAN's own class names do not fit the codes); pH 0 and TDS 0 removed as blanks coded as zero (2 Himmotthan records); values to check listed in `notes` (5 discharges above 300 L/min, 15 recharge areas above 1,000 ha, 77 elevation gaps above 150 m).

What it still cannot fill: 729 Atlas annexure springs have no discharge, water quality, spring type or lithology from any source, and no spring has household dependency or before/after DI data. Those need field work or WATSAN records.

## 6. Rebuilding

```
pip install rasterio numpy access-parser
pip install scipy scikit-image shapely pyproj pyflwdir          # lineament and DEM hydrology steps
python scripts/build_spring_features.py --cache .layer_cache   # downloads about 1.3 GB of layers on first run
python scripts/extract_dem_lineaments.py --cache .layer_cache  # needs the DEM tiles from the step above
python scripts/build_spring_features.py --cache .layer_cache --local-layers .local_layers
python scripts/build_spring_master.py
python scripts/export_hwsd_tables.py .layer_cache/hwsd/HWSD2.mdb  # only if the HWSD CSV tables are missing
```

`.local_layers/` holds the hand downloads: `Bhoonidhi/*.zip`, `IMD/*.nc` (one file per year) and `SoilGrids/{clay,silt,sand,cfvo,bdod,ocd}_{0-5,5-15,15-30}cm_mean.tif` (the SoilGrids exports renamed; see the metadata JSON for which `out (n).tif` is which). Without it those columns stay blank. Layers were accessed on 2026-10-10 and 2026-10-12. The feature build takes about 25 minutes because of the hydrology step. URLs, versions, resolutions and licences are in `spring_features_v1_metadata.json`.

## 7. Cleanup round (2026-10-12)

**Duplicates.** `scripts/spring_duplicates.py` compares every pair of records within 30 m of each other (249 pairs in 217 groups):
- **Same spring (165 pairs):** the names match after removing generic words (naula, dhara, spring) and the source elevations agree within 60 m, or the pair was matched during transcription (an Atlas profile and its annexure row). Most are the Spring Atlas listing a Himmotthan spring again.
- **Different springs (62 pairs):** the source elevations differ by more than 100 m; the same base name carries a different position word (Talla / Malla, I / II, 2); or both names are specific and clearly different. These are separate springs sharing one coordinate, often a coordinate copied in the source. Before, they were all treated as one spring.
- **Needs review (22 pairs, 14 groups):** one name is generic ("Dhara", "Naula") or the names are only partly alike ("Gairigar Naula" / "Gaderigad", 52 m apart). These are on the workbook's Duplicate review sheet. Until decided they count as separate springs and share no values.

Result: 151 groups are one spring, 48 are different springs, 4 are partly the same, 14 need review. Distinct springs (`is_primary_record = Y`) go from 1,611 to 1,679. Values borrowed from a neighbouring record now come only from a record confirmed as the same spring (151 discharges instead of 160). Every pair, its decision and the reason are in `spring_master_v1_duplicate_pairs.csv`. Team decisions go in `data/01_staged/common/duplicate_review_decisions_v1.csv` (record_id_a, record_id_b, same or different, who, when) and override the rules on the next build.

**Coordinates.** Two of the three coordinates outside the study area were typing slips with a certain fix, applied in `build_spring_features.py` and named in `coordinate_correction` (the staged value is not edited):
- ATL-SPR-0006 (Sunkiya Dhara): latitude 26.44050 is 29.44050. Its sister spring is at 29.44343, and the DEM at the corrected point is 2,049 m against 2,035 m in the source.
- ATL-SPR-0818 (Khatigaon): the longitude repeated the latitude. HIM-SPR-0204 has the same latitude and the same elevation (1,279 m), so its longitude was used.
- ATL-SPR-0792 (Gunagad, Simalkhet) stays out: the latitude repeats the longitude and cannot be recovered. It is probably ATL-SPR-0791 (same longitude, 1,613 m against 1,612 m).

**Elevation gaps.** For the 77 records whose source elevation is more than 150 m from the DEM, the build now searches the DEM within 2 km for the nearest point at the source elevation (±25 m). `elevation_check` says which side is probably wrong:
- 4 have a coordinate copied from another record at the same point whose elevation fits.
- 9 are a little off: the source elevation lies within 300 m, on a steep slope.
- 52 are off by 0.3-1.8 km (37 within 1 km). The coordinate is probably wrong, and the source elevation probably right.
- 12 have no point within 2 km at the source elevation. Either the coordinate or the elevation is badly wrong; these need a new GPS reading.

60 of the 77 are Spring Atlas annexure rows.

The 36 records with no coordinates stay unmapped. Placing them from a village name would add a precision the data does not have.

## 8. Input and test data (2026-10-14)

The master is split so the tool can be checked honestly. `dataset_split` is `input` (build and tune the tool) or `test` (keep aside; score the finished tool on it once). The test set is:
- every record in **Tehri Garhwal**, a whole held-out district where the field visit also takes place;
- the **10 Spring Atlas profile springs**, the only springs with both a delineated recharge area and a coordinate;
- every record in the same 30 m group as one of these;
- every spring **within 2 km** of one of these. Nearby springs share rainfall, rocks and sometimes a coordinate, so leaving a neighbour in the input data would make the test too easy.

That gave 216 distinct springs for testing and 1,463 for input (217 test springs since the October 2026 field visit added Kokhliyal). The test set holds 11 highly seasonal and 5 perennial springs, plus 130 with a discharge figure. The workbook's Input data and Test data sheets have one row per distinct spring, with duplicate copies removed. The All records sheet keeps all 1,842 source records so every value can be traced back. The same files are in CSV: `spring_master_v1_clean.csv` (all 1,679 distinct springs), `spring_master_v1_input.csv` and `spring_master_v1_test.csv`. `spring_master_v1.csv` has all records. Field-visit springs will be added to the test data. The October 2026 visit is in `data/02_processed/field_visit/` (8 Tehri springs, all test data). Seven of them are RDI-SPR-0001 to 0007. Their report coordinates were rounded and sat 400-800 m from the outlet; since 2026-10-22 the master uses the field GPS (named in `coordinate_correction`) and the form flow (`discharge_from` names the visit; the report value stays in `discharge_text`). Kokhliyal (Bhawani Khala) is a new spring, FLD-SPR-0001. Rasanulikhal is also HIM-SPR-0194 (Ludru Ka Pani, 64 m away) and Ganjrkhanal is probably HIM-SPR-0413 (191 m away); both pairs are further apart than the 30 m duplicate check, so they still count as separate test springs.

Vulnerability is judged by decline over time (less flow than before, drying earlier, perennial turned seasonal), not by seasonality alone. A spring that has always been seasonal is not vulnerable for that reason. Seasonality, especially "highly seasonal", is one sign among several. The best test labels will be field answers to "has this spring declined?".

