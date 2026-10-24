# DI Dashboard

A local application for tracking spring, DI handpump and village outcomes through occasional field visits. Its code does not call, import or write to the spring planner's modules. No authentication is included; the service binds to this computer only.

## Run

The spring tool runs the dashboard for you: start it with `start_tool.bat` (or `python scripts/spring_tool_server.py`) and click **Open dashboard** on the opening page, or go to http://127.0.0.1:8765/dashboard/.

To run the dashboard on its own, double-click **Open DI Dashboard.cmd**, or with Python 3.11 or newer:

```sh
cd "DI Dashboard"
python server.py --port 8769
```

Open http://127.0.0.1:8769/dashboard/. Built frontend assets are included, so Node is not needed to run the app. To rebuild, install Node 22.12+ (or 20.19+) and run `npm ci` then `npm run build` in this folder. The server uses Python's standard library; there is no pip installation step.

## One platform

The opening page, the Spring Health & Recharge Planner and this dashboard are served by one server (`scripts/spring_tool_server.py`, port 8765). The page is built for `/dashboard/` (vite `base`), and the API stays at `/api/v2/`. The dashboard keeps its own frontend and SQLite database (`runtime/di-dashboard.sqlite`), so the same data opens whether it is run inside the spring tool or on its own (not both at once). `--no-dashboard` runs the planner without it; `--no-weather` stops the rainfall requests.

## WATSAN DI sites data

On start, the server loads the WATSAN DI sites data file from `../data/02_processed/watsan_di/` (use `--data` for another folder). It is built by `python scripts/build_watsan_di_sites.py` from the same field-visit, report and spring-master tables as the planner:

- 8 WATSAN DI springs (Makhdet/Dungsi left out until its DI is installed).
- 8 DI handpumps. Arakot 1 and 2 link to Balench; Arakot 2 may also feed Paniyar Dhar, so it is listed under both sites and its water is counted once in totals.
- 88 values, each labelled before or after DI, with its record (before-DI recall, WATSAN report, field visit Oct 2026), basis (measured, estimate, report, recall, observed) and source.

The October 2026 field visit appears as saved visits; every value also appears under **Source records**. The import runs again only when the files change. Sites edited and visits entered in the portal are kept.

Photos, scanned forms and people's names are not included.

## Workflow and methodology

- Record setup once, then collect repeat observations through three short visit steps. Save incomplete work as a draft.
- Record three bucket-and-stopwatch readings for measured spring flow. Keep missing measurements, dry conditions and estimates distinct.
- Track spring response, handpump performance, DI maintenance and village changes separately. Accounts of livelihood, school, collection effort, hygiene and sanitation remain dated accounts.
- **Impact is shown before vs after DI first**, then between the last two records, as charts (Overview, site page, Track impact). Values are ranges; change = after − before, with a range of (after low − before high) to (after high − before low), and % from the midpoints. A dry spring that now flows is shown as "dry to flowing". Handpumps are counted as restored when they were defunct or dry before DI and work now.
- **Water DI can put into the ground** = roof area × annual rain × 0.8 × 0.85 / 1000 (the planner's defaults). Divided by the spring gain, it gives the most of that gain DI could explain.
- **How it works** documents 16 indicators, formulas, equal repeat-reading weights, denominators and missing-data rules. There is no invented composite impact score. Comparable changes require matching season, point and procedure; a before/after difference does not identify DI's causal contribution.
- Supporting photos/PDFs are stored unchanged with a checksum. No OCR or extraction runs. Source evidence and notes must be entered explicitly in the portal.

## External services

Maps use locally bundled Leaflet and OpenStreetMap tiles. Viewing a map sends the requested tile area to OpenStreetMap, revealing its approximate location; labels, notes and files are not sent. Rainfall uses Open-Meteo ERA5 with site coordinates, model, date range and timezone. After saving coordinates, the background worker retrieves and caches rainfall automatically. Pump GPS is preferred; a spring-location proxy is labelled. Use `--no-weather` to disable rainfall requests. Internet is needed for basemaps and rainfall retrieval.

Rainfall is area context, not measured injection or recharge. Provider terms and licences apply: [Open-Meteo](https://open-meteo.com/en/terms), [OpenStreetMap](https://www.openstreetmap.org/copyright). No browser storage, cookies or analytics are used.

## Storage and backup

`runtime/di-dashboard.sqlite` holds sites, visits, drafts, evidence metadata and rainfall. Original uploaded files are under `runtime/attachments/`. Use **Back up database** and copy the attachment folder together; stop the server before restoring a database. CSV and JSON exports are also available. Keep backups outside Git. Unsaved page text is not retained; use Save draft.

## Checks and modules

```sh
python -m unittest discover -s tests -v
```

25 tests cover validation, SI conversions, history, missing data, independent asset comparisons, before/after DI results, the data-file import and rainfall handling. `backend/rules.py` validates records, `assessment.py` calculates results, `store.py` owns SQLite, `weather.py` owns rainfall and `server.py` serves the API/UI. Frontend modules separate forms, controls, maps, graphics and evidence views. See `docs/backend.design.md` and `docs/backend.design.packet.json`.

For future multi-user hosting, add authentication, permissions, managed persistence and backups before exposing the service. This branch is a local application, with no deployment change to the original app.
