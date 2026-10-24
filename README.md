# Project 1 — Spring vulnerability, recharge-zone and DI support

Private working repository for the SRHU/HIHT RDI WATSAN DoCC Project 1 team.

## What belongs here

This repository holds the reproducible project record: raw inputs, field records, source metadata, scripts, staged and processed data, and handover outputs. It supports three connected modules:

1. transparent spring-vulnerability scoring;
2. a provisional, field-verifiable candidate recharge-zone estimate; and
3. a best-case Direct Injection (DI) water-balance estimate.

The tool is decision support, not a substitute for hydrogeological verification. DI estimates are upper-bound planning calculations until monitoring permits calibration.

## The spring tool (start here)

**Spring Health & Recharge Planner** is one local, map-based tool. A spring's location, field answers and planned DI sites go in. Three results come out: vulnerability (Module A), springshed and recharge zone (Module B), and the potential impact of DI recharging (Module C). On Windows, double-click [`start_tool.bat`](start_tool.bat). Elsewhere, run `python scripts/spring_tool_server.py --open`. How to use it, and how each section works: [`docs/spring-tool-guide.md`](docs/spring-tool-guide.md).

- **Page:** [`app/`](app/) (React + Leaflet; built copy in `app/dist/`, so no Node.js is needed to run it)
- **Server:** [`scripts/spring_tool_server.py`](scripts/spring_tool_server.py)
- **Modules:** [`module_a_vulnerability.py`](scripts/module_a_vulnerability.py), [`module_b_springshed.py`](scripts/module_b_springshed.py) and [`module_c_di_impact.py`](scripts/module_c_di_impact.py)

## Other components

- **Module A vulnerability:** [`scripts/module_a_vulnerability.py`](scripts/module_a_vulnerability.py), with its own inputs, reports and checks. See [`docs/run-module-a-locally.md`](docs/run-module-a-locally.md).
- **Catchment/springshed agents:** [`agents/`](agents/README.md) defines the exact IDs and rules; [`spring_agents/`](spring_agents/README.md) runs the resolved checks and records unavailable results where delineation inputs or approved rules are missing.
- **Vulnerability agent:** [`agents/vulnerability.md`](agents/vulnerability.md) (`AG-VUL`) runs Module A inside the agent runtime when a request sets `include_vulnerability: true`.
- **Field interface:** [`interface/`](interface/README.md) is a mobile-friendly Preact map and form. With the local server [`scripts/serve_tool.py`](scripts/serve_tool.py) running, it sends the spring to the agent runtime and shows the vulnerability score and the recharge-zone status; without it, it falls back to an illustrative preview. The older [`app.py`](app.py) Streamlit prototype calls only the catchment/springshed runtime.

One field request now runs both: the agent runtime's request carries Module A's elevation and answers, and `AG-VUL` calls Module A unchanged. Module A's map layers follow the approved-local-snapshot policy: [`scripts/module_a_snapshot.py`](scripts/module_a_snapshot.py) prepares, verifies and approves a versioned map set, and assessments then read only those files (rule `R-VUL-03`).

## Data flow

`data/00_raw` → `data/01_staged` → `data/02_processed` → `data/03_outputs`

- **00_raw:** received or downloaded files, unchanged after intake. Add a register entry first.
- **01_staged:** standardised copies with source, date, units and transformations recorded.
- **02_processed:** reproducible analysis-ready files. Most are generated locally; the small per-spring tables (`spring_features/`, `spring_master/`) and the DEM lineament file are committed so the team can open them without rebuilding. Start with `data/02_processed/spring_master/spring_master_v1.xlsx`.
- **03_outputs:** maps, tables and tool exports; generate them from scripts and staged inputs. Module A (vulnerability score) results are in `data/03_outputs/module_a/`; method and how to run it: `docs/module-a-vulnerability.md`. For how Modules A, B and C fit together, see `docs/module-contract.md`. To run Module A on your own computer, see `docs/run-module-a-locally.md`.

Do not put credentials, personal contact details, consent-sensitive photos, or unapproved community data in the repository.

## Start here

1. Add every received/downloaded file to `docs/source-register/source-register.csv` before analysis.
2. Store it unchanged in `data/00_raw/<source-id>/`.
3. Record every cleaning or conversion in `docs/source-register/transformation-log.csv`.
4. Keep observed data, community recall, staff hypotheses and project calculations distinct.

The current register is an intake inventory, not an endorsement that each data source is suitable for modelling.

## Separate DI impact dashboard

This branch also contains [`DI Dashboard/`](DI%20Dashboard/README.md), an independent local application for repeat spring/handpump visits and impact tracking. Its launcher, frontend, API and database remain separate from the original planner. The public source package includes no DI field records, photos, exact site coordinates or runtime databases. Existing app behaviour and deployment are unchanged.
