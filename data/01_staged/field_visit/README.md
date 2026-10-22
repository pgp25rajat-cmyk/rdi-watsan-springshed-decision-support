# Field visit, October 2026 (Tehri Garhwal)

DoCC team field visit with RDI/WATSAN: Kokhliyal on 13 Oct 2026 and the Chamba–Kanatal DI sites on 18–21 Oct 2026. Values are transcribed by hand from the scanned field forms (Field_Form_Spring_DI_v1), the team's site summary table and visit summaries. Photos, scanned forms and people's names are kept off this repository.

| File | One row per | What it holds |
| --- | --- | --- |
| `csv/field_visit_springs_2026-10.csv` | spring (8) | Location, flow today and recalled flows, users, water quality, surroundings, rock, DI link, community notes, WATSAN DTR reference values |
| `csv/field_visit_discharge_readings_2026-10.csv` | bucket reading | Litres and seconds for the 3 springs measured with a bucket and stopwatch |
| `csv/field_visit_di_sites_2026-10.csv` | DI handpump (8) | Location, linked spring and how sure the link is, bore depth, roof area, first flush, filter, pump and DI condition |
| `csv/field_visit_screen_scores_2026-10.csv` | spring x indicator | The team's quick vulnerability screen scores, and a recomputed score with the reason wherever it differs |

Decisions agreed with Rajat on 2026-10-22:

- Field form values are the primary reference. WATSAN DTR values (`dtr_*`, `elevation_dtr_m`) are kept for reference only.
- Coordinates follow the site summary table, which matches the photo GPS stamps. The form latitudes for Chorghadna and Rasanulikhal were copy errors.
- Elevation is taken from the Copernicus DEM at the field coordinate (`scripts/build_field_visit.py`). Several form altitudes had been copied from the dataset's map value at the old rounded coordinate.
- Measured flow is the mean of the bucket readings. Balench, Paniyar Dhar, Ganjrkhanal and Kokhliyal flows are estimates made by looking at the source; Chorghadna was not measured (solar pump).
- Kokhliyal lean flow is 10–15 L/min (recall), not the margin note of about 4 L/min.
- No handpump feeds Paniyar Dhar directly. Arakot 2 is the nearest, but the link is not established; WATSAN links both Arakot 1 and 2 to Balench.
- The Uniyal Gaon handpump at Kaddukhal is the broken school handpump near Surkanda Devi. The geologist found no link to the Ganjrkhanal naula.
- Quick screen bands (sum of 10 scores, 10–30): below 15 Low, 15–20 Medium, above 20 High. Household counts behind the households-per-flow score are Rajat's approximate guess where the form is blank.
- All field springs are test data and must not be used to build or tune the model.

Rebuild the processed tables with `python scripts/build_field_visit.py`. They are written to `data/02_processed/field_visit/`.

How the visit reaches the spring master (2026-10-22):

- RDI-SPR-0001 to 0007 move to the field GPS: `scripts/build_spring_features.py` reads this table and names the fix in `coordinate_correction`. The staged report coordinates are not edited.
- Field springs without a dataset record become FLD-SPR-nnnn rows of the common file (`scripts/field_visit_spring_records.py`; Kokhliyal is FLD-SPR-0001).
- `scripts/build_spring_master.py` uses the form flow (bucket mean, or the form's estimate range) for the linked RDI springs. Chorghadna was not measured and keeps the report value.
- Only these 8 records' map values were rebuilt, with `python scripts/build_spring_features.py --only field-visit` and the hand-downloaded layers from DOCC\Data\Secondary data. Every other row is unchanged.
