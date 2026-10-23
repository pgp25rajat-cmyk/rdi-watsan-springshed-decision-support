# DI Dashboard

A separate local application for tracking spring, DI handpump and village outcomes through occasional field visits. This module does not call, import or write to the original spring-planning app. No authentication is included; the service binds to this computer only.

## Run

On Windows, double-click **Open DI Dashboard.cmd**. Alternatively, with Python 3.11 or newer:

```sh
cd "DI Dashboard"
python server.py --port 8769
```

Open http://127.0.0.1:8769/. Built frontend assets are included, so Node is not needed to run the app. To rebuild, install Node 22.12+ (or 20.19+) and run `npm ci` then `npm run build` in this folder. The server uses Python's standard library; there is no pip installation step.

## Separate applications

The original Spring Health & Recharge Planner remains at the repository root with its existing launcher and API. DI Dashboard has its own server, frontend and SQLite database. Run each with its own launcher; use different ports if needed. No shared runtime or integration is introduced by this branch.

## Public source package

This checkout starts with an empty database. Add sites through **Sites → Add a site**, then enter field visits. Spring and handpump locations are separate and can be chosen on a map or entered as coordinates. Site photos are added through the portal.

Field records, exact site locations, source PDFs, photographs, local drafts, databases, weather caches, source registers, screenshots and private intake files are deliberately excluded. The full field-data copy remains on the project computer. Do not copy that local data into Git. The original app's existing tracked contents are inherited unchanged from main.

## Workflow and methodology

- Record setup once, then collect repeat observations through three short visit steps. Save incomplete work as a draft.
- Record three bucket-and-stopwatch readings for measured spring flow. Keep missing measurements, dry conditions and estimates distinct.
- Track spring response, handpump performance, DI maintenance and village changes separately. Accounts of livelihood, school, collection effort, hygiene and sanitation remain dated accounts.
- **How it works** documents 11 indicators, formulas, equal repeat-reading weights, denominators and missing-data rules. There is no invented composite impact score. Comparable changes require matching season, point and procedure; a before/after difference does not identify DI's causal contribution.
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

18 tests cover validation, SI conversions, history, missing data, independent asset comparisons and rainfall handling. `backend/rules.py` validates records, `assessment.py` calculates results, `store.py` owns SQLite, `weather.py` owns rainfall and `server.py` serves the API/UI. Frontend modules separate forms, controls, maps, graphics and evidence views. See `docs/backend.design.md` and `docs/backend.design.packet.json`.

For future multi-user hosting, add authentication, permissions, managed persistence and backups before exposing the service. This branch is a local application, with no deployment change to the original app.
