# Staged data layout

Each source has a separate folder and the same structure:

- `csv/` - machine-readable staged tables.
- `xlsx/` - the matching review/share workbook.
- `metadata/` - generated extraction metadata where applicable.

`common/` contains the combined source-traceable master table. It is an append of source records, not a deduplicated spring inventory. `common/duplicate_review_decisions_v1.csv` holds the team's same-or-different decisions on records within 30 m of each other; `scripts/build_spring_master.py` applies them. Raw source files belong in `../00_raw/<source>/` and must not be edited.

`literature/` holds spring rows transcribed from papers and reports (Rathi et al. 2021, Daniel et al. 2021, the RDI Chamba Spring Assessment Report and the Spring Atlas representative-spring profiles). `literature_spring_values_long_v1.csv` gives the source page/table and measured-or-estimated status of every value. See `docs/literature-enrichment-notes.md`.

`field_visit/` holds the October 2026 Tehri field visit (8 springs, 8 DI handpumps, bucket readings, quick screen scores), transcribed from the field forms; `scripts/build_field_visit.py` adds map elevation, measured flow and screen bands into `data/02_processed/field_visit/`. See `field_visit/README.md`.

`ngdr_geology/` holds separate NGDR fault-line, fold-line, and lithology-polygon attribute extracts. Their original geometry remains unchanged in `data/00_raw/ngdr_geology/`; the staged CSV/XLSX rows preserve a GeoJSON feature locator and bounds only. They have not been spatially joined to spring records.

Rebuild order: `python scripts/stage_watsan_and_spring_atlas.py`, `python scripts/build_literature_workbooks.py`, then `python scripts/stage_ngdr_geology.py` and `node scripts/build_ngdr_geology_workbooks.mjs`.

Processed per-spring features (terrain, land cover, rainfall, soil, GSI geology and faults) are built from the common file by `scripts/build_spring_features.py` into `data/02_processed/spring_features/`, and the final table by `scripts/build_spring_master.py` into `data/02_processed/spring_master/`. The NGDR geology is spatially joined there, not in the staged tables. See `docs/data-gap-analysis.md`.
