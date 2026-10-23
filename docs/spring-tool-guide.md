# Spring Health & Recharge Planner: user guide (v1.1 draft, 16 October 2026)

One spring goes in. Three results come out, on a map:

1. **Vulnerability assessment** (Module A). Is the spring at risk of declining? This gives a 0-100 score, a Low, Medium or High class, and the reasons.
2. **Springshed and recharge zone** (Module B). Where does the spring's water soak in? This gives the surface catchment, the top three recharge zones (R1-R3) wherever they lie, on the spring's own slope or beyond the ridge, and a recharge-potential map.
3. **Potential impact of DI recharging** (Module C). What could rooftop water injected into defunct handpumps add to the spring? This gives the water injected, the added lean-season flow, the water-level rise, a travel time and a monitoring plan.

Everything runs on your laptop. The tool calls no paid service and uses no AI model. Each method is plain arithmetic on map layers and field answers, and every number comes with its reason.

## 1. Start it

**Windows (Rajat's laptop):** double-click **`start_tool.bat`** in the `Tool` folder.

- A black window opens and the page opens in your browser at http://127.0.0.1:8765.
- Keep the black window open while you use the tool. Close it to stop.

The start file looks for its map folders next to the `Tool` folder:

| Folder | What it holds |
|---|---|
| `DOCC\MapCache` | Map tiles |
| `DOCC\Data\Secondary data` (else `DOCC\Data`) | IMD, SoilGrids and CartoDEM files |

SoilGrids files can sit either as `SoilGrids\clay_0-5cm_mean.tif` or in depth folders such as `SoilGrids\0-5 soilgrids\clay.tif` (the laptop's layout). Both are read.

If your folders are elsewhere, set `SPRING_LAYER_CACHE` and `SPRING_LOCAL_LAYERS` before starting (see [run-module-a-locally.md](run-module-a-locally.md)).

**Any computer with Python set up:** run `python scripts/spring_tool_server.py --open`.

**Run times:**

| Run | Time |
|---|---|
| First run after starting | Up to a minute (it opens the maps) |
| Later runs | A few seconds |

Every run is saved in `data/03_outputs/tool_runs/<date-time>-<spring>/`:

- `request.json`: what was entered
- `result.json`: everything the page shows
- `report.md`: the three reports

## 2. Use it

1. **Spring.** Pick the spring in one of three ways:
   - Search the 1,643 springs in the dataset by name, village or district.
   - Click the map.
   - Type the latitude and longitude.

   The GPS elevation is optional. If you leave it blank, the tool uses the map elevation.
2. **Field observations** (optional). Every answer improves the result:
   - Flow now vs 10-20 years ago matters most for vulnerability. It is the only direct sign of decline.
   - Monsoon flow sizes the recharge zone.
   - Months with no flow at all: even one dry month counts strongly.
   - Whether the area is prone to landslides, cloudbursts or flash floods, and which recharge works are already there (check dams, trenches, pits, ponds, plantation, DI).
   - The rock tilt (dip direction and angle) lets the tool look for recharge ground up-dip of the spring, even beyond the ridge.
3. **DI plan** (optional). Click **Add DI site** and click the map where the handpump is, or type its latitude and longitude. Enter the roof area and the handpump depth (70 m if left blank; most are 50-80 m), and the water level in the handpump if you know it. You can open **Assumptions** to change:
   - the rainfall;
   - the share of roof rain collected;
   - the length of the lean season.
4. Click **Assess this spring**. The three results appear as tabs. The map shows only the layers for the tab you are on:

   | Tab | What the map shows |
   |---|---|
   | Vulnerability | The 500 m and 1 km circles the map indicators are measured in, land cover inside 1 km (disturbed land drawn strong), and nearby dataset springs |
   | Springshed | Catchment to the ridge, the land running off straight to the outlet, the top recharge zones R1-R3 and the fault or crack that links each one to the spring, faults, GSI and DEM lineaments, streams, and the heat map switch |
   | DI impact | DI sites coloured by where they sit, an arrow for the assumed groundwater path from each handpump to the spring, and the recharge zones and catchment drawn faintly for context |

   The map is 3D by default: right-drag (or Ctrl + drag) to tilt and turn it. Heights are drawn 1.5 times. The **2D** button flattens it, and the background can be satellite, a topo map or streets. The 3D hills come from the tool's own elevation tiles, so they show even when the background cannot download. Beyond the area those tiles cover, and when zoomed far out, the hills come from public elevation tiles (AWS Terrain Tiles), which are saved under `MapCache\terrain_web` so they also show offline next time. With no internet and no saved copy, the ground there continues at the nearest known height instead of dropping to sea level.
5. **Print report** prints the three sections.

## 3. What each section does

Every section shows two separate labels:

- **Evidence** (Low, Medium or High) says how complete the inputs were. It does not say the answer is right.
- **Not validated yet** says the section has not been checked against field evidence: known declining springs for A, walked springsheds for B, monitored DI sites for C. Hover over it for the detail.

Every number Modules B and C use, and Module A's rules, is listed in [`config/assumption_register_v1.csv`](../config/assumption_register_v1.csv) with its source, where it applies, and whether it is sourced, fitted or an assumption. A test checks that the register matches the code. WATSAN can review from that one file.

Each tab opens with a short plain-language box ("Why this score", "How this area was mapped", "Where the water goes").

### Vulnerability (Module A)

The method follows [module-a-vulnerability.md](module-a-vulnerability.md), with Rajat's changes of 23 October 2026:

- There are 23 indicators in four groups (state, impact, stressor, response). Field weights: flow now vs 10-20 years ago 10, lean-season flow 10, months of low or no flow 13, households per L/min 10, disturbance uphill 5, ratio 3, pollution 3, protection 3, recharge works 3, disaster-prone area 2, water quality 2, seasonality 2, users vs past 2 (68 in all).
- Months of low or no flow: 0 = 0, 1 = 25, 2-3 = 50, 4 or more = 100; any month with no flow at all scores at least 75 (3 or more: 100).
- Two map indicators were added: soil depth to bedrock (SoilGrids, 3) and mapped GSI landslides within 500 m (2; read with the disaster question). Disturbed land, slope, land above the spring, building growth and rain variability each lost 1 point.
- Map indicators are scored as percentiles among the input springs.
- With location only, the result is an **exposure score**: it shows how exposed the setting is, not whether the spring is declining.
- The lean-season flow reading feeds three indicators, so on 16 October 2026 the monsoon/lean ratio went from 6 to 3 and months of low flow from 5 to 8. The result notes the combined share when more than one is used.
- `python scripts/module_a_checks.py --sensitivity` also compares equal weights with the draft weights: 12% of the input springs change class.

### Springshed and recharge zone (Module B)

`scripts/module_b_springshed.py`, with weights in `config/module_b_recharge_factors_v1.csv`.

1. **Catchment to the ridge.** The geologists' reports draw the whole valley above the spring up to the ridges, which is much larger than the land that runs off straight to the outlet. The tool now does the same, by standard GIS practice: it moves the outlet onto the main drainage line within 90 m of the spring (never onto a channel draining more than 5 km², which is a river), and takes all the land upslope of it that is no lower than the spring. It then adds the side slopes: it follows the water down from the spring until just before it joins a stream (a channel draining 0.5 km², the size the tool already treats as a stream; at most 1.5 km), and takes all the ground in that valley that is above the spring and joined to it, ridge to ridge. This is the dashed blue line. The land running off straight to the outlet (allowing 30 m for GPS error) is drawn dotted inside it. The rule was fixed from GIS practice, not fitted to the two report catchments, which belong to test springs. If the catchment reaches the edge of the map window, it is reported as incomplete.
2. **Search area.** The tool looks for recharge ground in one search, on the spring's own slope and beyond it:
   - up to 4 km from the spring;
   - every cell must be linked to the spring in one of four ways (see step 5);
   - cells linked only by a fault, a crack or rock tilt must be at least 20 m above the spring.
3. **Recharge potential.** Each 30 m cell gets a score from 0 to 1:

   | Factor | Weight | What scores high |
   |---|---|---|
   | Slope | 20% | Gentle ground |
   | Land cover | 20% | Forest; built-up land scores low. In Tehri, Sentinel-2 NDVI splits tree cover into dense (1.0), open (0.8) and sparse (0.65); elsewhere tree cover scores 0.9 |
   | Rock type (GSI map) | 20% | Fractured or porous rock such as carbonate and quartzite; shale and phyllite score low |
   | Distance to a fault or lineament | 20% | Within 100 m of a GSI fault, a GSI Bhukosh mapped lineament or a DEM lineament |
   | Soil texture, top 30 cm (SoilGrids) | 10% | Sandy and sandy-loam soil; clay scores low; stony soil gets a small bonus |
   | Soil depth to bedrock (SoilGrids) | 10% | 150 cm or more; under 50 cm scores low |

   Without SoilGrids files the soil factor is left out and the other weights are scaled up.

4. **Recharge area needed.** This comes from the monsoon flow, using the area-flow relation of 35 delineated springsheds (Rathi 2021): area ≈ 0.20 × flow^0.68 ha. With no flow reading, the typical 1.5 / 3 / 8 ha of hill springsheds is used. Each zone is grown to about the middle value (at least 1 ha).
5. **Link to the spring.** A cell can only feed the spring if water has a way to get there:

   | Link | Strength | Which cells |
   |---|---|---|
   | Spring slope | 1.0 | Inside the catchment to the ridge (plus a 60 m ridge margin), not below the spring |
   | GSI fault | 0.9 | Within 250 m of a mapped fault that passes within 200 m of the spring |
   | GSI mapped lineament | 0.9 | Within 250 m of a Bhukosh lineament (joint, fracture, shear zone) that passes within 200 m of the spring |
   | Rock tilt (up-dip) | 0.9 | Up-dip of the spring (±40°) in the same rock unit, when the dip is entered |
   | DEM lineament (crack) | 0.7 | Within 250 m of a lineament that passes within 200 m of the spring |

   When the dip is entered, slope cells that are not up-dip count a little less (×0.6). With no field dip, a GSI bedding or foliation measurement within 2 km is used instead and the tab says so (these exist for Kumaon only).
6. **Top three zones.** Each cell gets: recharge potential × link strength × closeness (falls off over about 4 km). The tool then:
   - starts a zone at the best cell and grows it through neighbouring cells with the same link, best first, up to the size needed;
   - for zones linked by a fault, crack or tilt, checks the ground in between: if it dips more than 30 m below the spring, a stream there may catch the water first, so the zone is ranked lower; more than 100 m rules it out;
   - keeps a 90 m gap and repeats, then keeps the best three as **R1, R2, R3**.

   Only ground with a recharge potential of 0.5 or more is used (0.35 with a warning if there is none).

   Streams (channels draining 0.5 km² or more) stop a zone from growing, because a stream usually takes the water first. Where the rock may carry water under a stream, for example along a fault, untick **Streams stop a recharge zone** under Geology.

   Zones are grown to the size the flow needs, so a zone's area matching that size is by design, not a check that it is right. The area-flow relation uses Rathi's long-term maximum flows; one monsoon bucket reading is not the same, so treat the size as a rough guide. With no flow reading, the 3 ha is a default and is marked so.

   There is no rule that a zone must be near the spring or far from it. For a spring with good ground on its own slope, all three can be on the slope. For a spring with poor ground above it but a fault to a better slope, R1 can be in the next valley. Each zone card says what links it, how far and how high it is, its land cover, soil and rock, and why it ranked where it did.

   Zones beyond the surface catchment are hypotheses, not findings. The tab lists field checks: walk the fault or crack line for seeps, track water temperature and EC monthly, note how slowly the spring rises after rain, and (with budget) an oxygen-18 test of the recharge height.

The map shows the **surface catchment** (dashed blue: where rain runs off towards the spring) and the **recharge zones** R1-R3 (green, darkest is best: where rain soaks in and feeds it) as separate layers, because the two are not the same area.

**Evidence** is Low by default. It is Medium when both the monsoon flow and the rock tilt are given and the GSI geology covers the spring.

**Limits:**

- The GSI geology covers Uttarakhand only.
- The zones have not yet been checked against field-delineated springsheds. The 10 Spring Atlas profile springs are kept aside for that one-time check.
- Walk the zone with a geologist before spending money on works.

### Potential impact of DI recharging (Module C)

`scripts/module_c_di_impact.py`.

**Water injected** is worked out in two steps, which cover different losses, so nothing is counted twice:

- roof runoff reaching the handpump = roof area × yearly rain × 0.8 (gutter, pipe and splash losses);
- water injected = that runoff × 0.85 (first flush, overflow, downtime and clogging).

Both factors can be changed under Assumptions.

**Rain source:**

- The IMD gauge mean is used when the IMD files are present.
- Otherwise the CHIRPS satellite estimate is used. At the dataset springs it read about 45% above IMD; that is a comparison, not a correction factor.
- You can type in a local value instead.

**Snow.** Snowfall comes from ERA5 (winters 2019-20 to 2024-25, as water). ERA5 cells are 27 km wide and average lower ground than most springs, so the tool reads the snow at the spring's own height off an ERA5 snow-height curve: almost none below 1,500 m, about 45 mm at 1,900 m, 160 mm at 2,400 m and 290 mm at 2,900 m a winter. Half of it is counted as melting off the roof into the gutters in January-March.

**Handpump depth.** The water goes in at the bottom of the handpump (70 m unless given), not at the surface. The share reaching the spring is multiplied by a depth factor that compares that injection point with the spring outlet: 1.0 if it is 10 m or more above the outlet, 0.7 within 10 m, 0.4 up to 50 m below, 0.2 deeper. Water put in below the outlet has to rise to come out there; most of it flows on deeper, towards the valley. These factors are judgement.

**Flow path.** For each handpump the tab draws a cross-section like the reports' groundwater flow path figure: the ground along the straight line from the handpump to the spring, the borehole down to the injection point, the spring outlet level and the assumed path of the water. The map shows the same path as an arrow. The hydraulic gradient is the fall of the assumed water table over that distance: the ground slope, as in the reports, or the handpump water level when it is given. If the ground on the way dips below the spring (more than 90 m from it), the tab warns that water may come out in that valley first.

**Share reaching the spring** depends on where the handpump sits. These shares are judgement, not measured connection, and should be replaced by monitoring. Being inside a zone does not show the handpump is connected to the spring: if it is not, the gain is zero, and the tab says so next to every range.

| Where the handpump is | Share reaching the spring (low, mid, best) |
|---|---|
| Inside a recharge zone on the spring slope | 30%, 60%, 100% |
| Inside a recharge zone linked by a fault or rock tilt | 10%, 30%, 60% |
| Inside a recharge zone linked by a crack (lineament) | 5%, 20%, 50% |
| Elsewhere in the catchment | 5%, 15%, 30% |
| Outside the catchment | 0%, 2%, 10% |
| Below the spring | None |

**Added flow** is shown two ways:

- spread over the year;
- as a **dry-season water equivalent**: all of it coming out in the lean season (5 months by default). This is a timing assumption, so it is a water-volume equivalent, not an expected gain.

When the lean flow is known, the tool also shows this as a % of today's lean flow and the number of 100 m² roofs needed for +10%. Both carry the same two assumptions (60% reaching the spring, all of it in the dry months).

**Storage rise (illustration)** shows how much water the rock would have to hold after the wettest month: that month's volume ÷ (circle of 50 m radius × specific yield). It is not a predicted water-level rise, which would need the recharge rate, the aquifer properties and its boundaries. Specific yield is 0.5-3% for hard rock and 8-16% for alluvium or debris, taken from the rock at the spring, which may not be the rock at the injection depth.

**Water reaching the spring** is shown as m³ a year next to the water injected: injected × share × depth factor.

**Travel time** is distance ÷ (permeability × gradient ÷ porosity), using wide hard-rock ranges. Specific yield stands in for effective porosity, and the gradient is the one in the cross-section (at least 0.02). Treat it as an order of magnitude only; it does not show that a flow path exists.

**Safety gate.** If any site has no first-flush diverter or no filter, the tab opens with **Not ready for DI yet** and the actions to take. Every plan also lists the checks before the first injection: water-quality tests, clogging and overflow checks, and WATSAN's site check. Sites outside the zones or below the spring keep their record and the reason, because surface position alone does not prove they are cut off.

The section also lists benchmarks (ICIMOD: +23% and +48% after full springshed treatment, which is context only, not evidence for DI alone) and a monitoring plan. The monitoring plan is how these estimates will be replaced by real numbers.

## 4. Working offline with an approved map set

Without an approved map set, the tool downloads missing map tiles as needed. That needs internet the first time for a new area.

To make results repeatable and offline, prepare and approve a map set once:

```
python scripts\module_a_snapshot.py prepare --by "Rajat"
python scripts\module_a_snapshot.py approve <name it prints> --by "Rajat"
```

After that, the tool reads only those files. The header shows the map set name, and every saved run records it.

- After adding new data (another IMD year, say), run `prepare --rebuild-reference` and approve the new set.
- For a new area, add `--bbox WEST SOUTH EAST NORTH`.

## 5. Change the page

The built page is in `app/dist/` and is committed, so the laptop needs no Node.js. To change the page, edit `app/src/` and rebuild with Node.js (`npm ci`, then `npm run build` in `app/`). The data passed between the page and the modules is defined once, in `app/src/api.ts`.
