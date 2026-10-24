# Spring Health & Recharge Planner (web page)

The page the team uses to assess one spring. You choose the spring (from the dataset list, by clicking the map or by typing its position), add optional field observations and planned DI sites (defunct handpumps that take rooftop rainwater), and get three results drawn on a map:

1. **Vulnerability**: a 0-100 score with its class, the signs behind it and what would improve the answer.
2. **Springshed**: surface catchment, small / likely / large recharge zones, faults, lineaments, streams and suggested recharge spots.
3. **DI impact**: water put into the ground, added dry-season flow, per-site estimates, a monthly chart and a monitoring plan.

**Print report** prints a two-to-three page summary (the map is left out).

## Pages

- `#/` opening page: two doors (dashboard, planner), about, team. Code in `src/home/`.
- `#/planner` the planner described above. Its title in the top bar goes back home.
- `#/dashboard` slot for the WATSAN intervention dashboard (Abhishek). For now a "coming soon" page that lists the WATSAN DI sites from `/api/di_sites`. When the dashboard arrives, either add it as React components in `src/home/Dashboard.tsx`, or drop its built files in `public/dashboard/` and show `/dashboard/index.html` in that page. It should read the same data as the planner (`/api/springs`, `/api/di_sites`).
- The SRHU logo is `public/brand/srhu-logo.png` (cropped from the high-resolution file).

## Everyday use (no Node.js needed)

The built page in `dist/` is committed. Start the tool with `start_tool.bat` (or `python scripts/spring_tool_server.py`) and open http://127.0.0.1:8765. The Python server serves `dist/` and the API (`/api/health`, `/api/springs`, `/api/assess`) together.

If the page cannot reach `/api/health`, it switches to **demo data** (see `src/mock.ts`) and says so in an amber banner. Demo numbers are illustrative only.

Map backgrounds (Esri satellite, OpenTopoMap, OpenStreetMap) need internet. Without it the page shows a note and draws the spring and the results on a blank map.

## Changing the page (needs Node.js 18 or newer)

```powershell
cd app
npm ci            # once, installs the exact versions in package-lock.json
npm run dev       # live page at http://127.0.0.1:5173; /api calls go to the Python server on port 8765
npm run build     # type-checks, then writes dist/ (commit dist/ afterwards)
npm run typecheck # type-check only
```

For `npm run dev`, run `python scripts/spring_tool_server.py` in a second terminal. Without it the dev page uses the demo data.

## Files

- `src/api.ts`: the request and response shapes shared with the Python server (change both sides together).
- `src/questions.ts`: the scored field questions. A Python test checks its ids and values against Module A, so keep its line format.
- `src/questionExtras.ts`: form grouping, the geology text questions and the rock-dip questions.
- `src/mock.ts`: demo answer for "Nauli Dhara" and a demo spring list.
- `src/form.ts`: form state, conversion to the request, and remembering the last form in the browser.
- `src/components/`: the map (`MapView.tsx`, Leaflet via react-leaflet), the form, the result tabs, hand-drawn SVG charts and the print report.

Stack: React 18, Leaflet 1.9 with react-leaflet 4, TypeScript, Vite. No chart or CSS library; system fonts only, so the page works offline.
