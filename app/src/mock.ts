// Demo data used when the local tool server is not running.
// The shapes follow api.ts exactly. Numbers are illustrative, not results.
import type {
  AResult, AssessRequest, AssessResponse, BResult, CResult, DatasetSpring, DiSite, DiSiteResult, Feature,
  FeatureCollection, FlowPath, Health, Indicator, Range, RechargeZone,
} from './api';
import { DEFAULT_ASSUMPTIONS } from './api';

export const DEMO_SPRING = { name: 'Nauli Dhara', latitude: 29.91903, longitude: 78.55647, elevation_m: 1481 };

export const MOCK_HEALTH: Health = { ok: true, version: 'demo', map_set: null, offline: false };

// ------------------------------------------------------------------ geometry helpers
const M_PER_DEG_LAT = 111320;
type LonLat = [number, number];

function offset(lat: number, lon: number, east: number, north: number): LonLat {
  const dLat = north / M_PER_DEG_LAT;
  const dLon = east / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  return [round6(lon + dLon), round6(lat + dLat)];
}
const round6 = (n: number) => Math.round(n * 1e6) / 1e6;

/** A wobbly ellipse whose long axis points along `bearingDeg`; the spring sits inside, near the downhill end. */
function blob(lat: number, lon: number, areaHa: number, aspect: number, bearingDeg: number, wobble: (t: number) => number): Feature {
  const a = Math.sqrt((areaHa * 10000 * aspect) / Math.PI);
  const b = a / aspect;
  const br = (bearingDeg * Math.PI) / 180;
  const ax = [Math.sin(br), Math.cos(br)]; // east, north of the long axis
  const px = [ax[1], -ax[0]];
  const cx = 0.78 * a;
  const ring: LonLat[] = [];
  for (let i = 0; i < 48; i++) {
    const t = (i / 48) * Math.PI * 2;
    const w = wobble(t);
    const u = cx + a * Math.cos(t) * w;
    const v = b * Math.sin(t) * w;
    ring.push(offset(lat, lon, u * ax[0] + v * px[0], u * ax[1] + v * px[1]));
  }
  ring.push(ring[0]);
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
}

/** A rough oval of areaHa centred east/north metres from the spring. */
function patch(lat: number, lon: number, east: number, north: number, areaHa: number): Feature {
  const a = Math.sqrt((areaHa * 10000 * 1.5) / Math.PI), b = a / 1.5;
  const ring: LonLat[] = [];
  for (let i = 0; i < 40; i++) {
    const t = (i / 40) * Math.PI * 2, w = 1 + 0.08 * Math.sin(3 * t);
    ring.push(offset(lat, lon, east + a * Math.cos(t) * w * 0.8 - b * Math.sin(t) * w * 0.6, north + a * Math.cos(t) * w * 0.6 + b * Math.sin(t) * w * 0.8));
  }
  ring.push(ring[0]);
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
}

function line(lat: number, lon: number, pts: [number, number][], properties: Record<string, any>): Feature {
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: pts.map(([e, n]) => offset(lat, lon, e, n)) }, properties };
}

const fc = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features });

/** Ray casting; ring is [lon, lat][] */
export function insidePolygon(lat: number, lon: number, f: Feature | null | undefined): boolean {
  if (!f || f.geometry?.type !== 'Polygon') return false;
  const ring: LonLat[] = f.geometry.coordinates[0];
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function distanceM(lat1: number, lon1: number, lat2: number, lon2: number) {
  const dy = (lat2 - lat1) * M_PER_DEG_LAT;
  const dx = (lon2 - lon1) * M_PER_DEG_LAT * Math.cos((lat1 * Math.PI) / 180);
  return Math.hypot(dx, dy);
}

// ------------------------------------------------------------------ overlay image (tiny gradient)
const POTENTIAL_LEGEND = [
  { label: 'Low', color: '#f2efc7' },
  { label: 'Moderate', color: '#b9dc8f' },
  { label: 'High', color: '#4fae5a' },
  { label: 'Very high', color: '#17723f' },
];

function potentialImage(): string | null {
  try {
    const size = 48;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const rgb = POTENTIAL_LEGEND.map((l) => [1, 3, 5].map((i) => parseInt(l.color.slice(i, i + 2), 16)));
    const img = ctx.createImageData(size, size);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        // highest towards the north-west, with some ridges
        const nx = x / size, ny = y / size;
        let p = 0.55 * (1 - nx) + 0.45 * (1 - ny);
        p += 0.12 * Math.sin(nx * 9 + ny * 4) + 0.08 * Math.cos(ny * 11 - nx * 3);
        p = Math.max(0, Math.min(0.999, p));
        const c = rgb[Math.floor(p * rgb.length)];
        const k = (y * size + x) * 4;
        img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2]; img.data[k + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL('image/png');
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ Module A
function moduleA(req: AssessRequest, elevation: number): AssessResponse['A'] {
  const f = req.field;
  const ind = (id: string, group: string, indicator: string, value: string, score: number, weight: number, comparison: string, why: string): Indicator => ({
    id, group, indicator, value, score, weight_used_pct: weight, points: Math.round(score * weight) / 100, comparison, why,
  });
  const indicators: Indicator[] = [
    ind('flow_vs_past', 'State (field)', 'Flow now vs 10-20 years ago', 'A bit less', 55, 12, 'Most springs in the dataset: same or a bit less', 'People report the flow has dropped a little.'),
    ind('lean_flow_lpm', 'State (field)', 'Lean-season flow', '4 L/min', 50, 12, 'Median of dataset springs: 5 L/min', 'Lean flow is close to the typical spring.'),
    ind('low_flow_months', 'State (field)', 'Months with low or no flow', '3 months', 45, 8, 'Typical: 2-4 months', 'A normal dry spell for a mid-hill spring.'),
    ind('seasonality', 'State (field)', 'Seasonality', 'Seasonal-perennial', 40, 6, '', 'Flows all year but drops a lot before the monsoon.'),
    ind('households', 'Impact (field)', 'Households using the spring', '35 households', 55, 10, 'Median: 22 households', 'More families than usual depend on it.'),
    ind('water_quality', 'Impact (field)', 'Water quality', 'Muddy after rain', 45, 6, '', 'Fast flow paths: surface water reaches the outlet quickly.'),
    ind('users_vs_past', 'Stressor (field)', 'Users now vs 10-20 years ago', 'More', 55, 7, '', 'Demand is growing.'),
    ind('disturbance_uphill', 'Stressor (field)', 'Roads, fire, grazing or landslides uphill', 'Some', 45, 8, '', 'A village road cuts the slope above the spring.'),
    ind('dry_season_rain', 'Stressor (location)', 'Dry-season rain (Nov-May)', '182 mm', 40, 9, 'Dataset range 90-310 mm', 'Average winter and pre-monsoon rain for the area.'),
    ind('slope', 'Stressor (location)', 'Slope around the spring', '24°', 25, 6, 'Dataset median 27°', 'Gentler slopes let more rain soak in.'),
    ind('protection', 'Response (field)', 'Outlet protected and an active user committee', 'One of them', 50, 8, '', 'The outlet is protected but there is no active committee.'),
    ind('recharge_works', 'Response (field)', 'Recharge works uphill', 'None', 25, 8, '', 'No trenches, pits or plantation yet: room to act.'),
  ];
  const total = indicators.reduce((s, i) => s + i.points, 0);
  const weight = indicators.reduce((s, i) => s + i.weight_used_pct, 0);
  const score = Math.round((total / weight) * 100);
  const result: AResult = {
    score,
    class: score < 35 ? 'Low' : score < 60 ? 'Medium' : 'High',
    kind: 'vulnerability score',
    coverage_pct: 86,
    indicators,
    context: [
      `Elevation used: ${elevation} m (field value; the map says ${elevation - 9} m)`,
      'Rock: Lansdowne granite / quartzite with phyllite bands (GSI 1:2M)',
      'Nearest mapped fault: 0.4 km (Main Boundary Thrust)',
      'Soil 0-30 cm (SoilGrids): clay 21%, sand 44%',
      'Yearly rain (CHIRPS 2018-2025): 1,600 mm (IMD 2001-2025: 1,540 mm)',
    ],
    nearest_dataset_spring: { record_id: 'SPR-0417', spring_name: 'Nauli Dhara', distance_m: 38 },
    elevation_gap_m: 9,
    map: {
      rings: [
        { radius_m: 500, label: '500 m: disturbed land and slope' },
        { radius_m: 1000, label: '1 km: buildings and land rising above the spring' },
      ],
      land_cover: null,
    },
  };
  const missing = [
    { id: 'monsoon_flow_lpm', indicator: 'Monsoon flow', weight: 6, needs: 'Time how long a bucket takes to fill in August.' },
    { id: 'pollution_30m', indicator: 'Pollution sources within 30 m', weight: 5, needs: 'Walk 30 m around the outlet and count latrines, drains and cattle sheds.' },
    { id: 'spring_type', indicator: 'Spring type', needs: 'Note where the water comes out: a crack, a contact of two rocks, or a hollow.' },
  ].filter((m) => !(m.id in f) || (f as any)[m.id] === undefined || (f as any)[m.id] === '');
  return {
    module: 'A', title: 'Vulnerability assessment', version: '0.4-demo', status: 'complete', confidence: 'Medium',
    summary: [`This spring has a medium vulnerability score (${score} out of 100) mainly because many households share a small flow and people say the flow is a bit less than 10-20 years ago.`,
      'Keeping it from being higher: the land uphill is little disturbed.'],
    validation: 'Not yet validated: the score has not been checked against springs known to be declining or steady. Weights and cut-offs are a draft for WATSAN to review.',
    rationale: [
      `Score ${score} of 100, a Medium vulnerability: the spring is under some pressure but not in crisis.`,
      'The biggest contributors are the many households using it and the drop in flow people report.',
      'No recharge work uphill yet, which is also the clearest thing to change.',
      'Location factors (rain, slope) are close to the middle of the dataset.',
    ],
    missing_inputs: missing,
    warnings: ['Demo data: these numbers are illustrative only.', 'Lean flow was given once; one reading can be off by 30% or more.'],
    result,
    report_markdown: '',
  };
}

// ------------------------------------------------------------------ Module B
function moduleB(lat: number, lon: number, elev: number): AssessResponse['B'] {
  const w2 = (t: number) => 1 + 0.1 * Math.sin(2 * t + 1.1) + 0.06 * Math.cos(4 * t + 0.3);
  const catchment = blob(lat, lon, 8, 2.4, 335, w2);
  const zone = (id: string, rank: number, geojson: Feature, extra: Partial<RechargeZone>): RechargeZone => ({
    id, rank, area_ha: 3.0, geojson, link: { kind: 'Surface slope', name: 'The slope that drains to the spring', geojson: null },
    in_catchment_pct: 100, distance_m: 0, height_above_spring_m: { min: 2, mean: 45, max: 95 }, mean_potential: 0.74,
    mean_slope_deg: 18, land_cover_pct: { 'Tree cover': 70, Grassland: 22, Cropland: 8 },
    soil: { class: 'Loam or silt loam (clay under 27%)', clay_pct: 21, sand_pct: 44 }, rock_unit: 'Quartzite with phyllite bands',
    valley_between_m: 0, crosses_fault: false, score: 0.7, why: '', ...extra,
  });
  const zones: RechargeZone[] = [
    zone('R1', 1, patch(lat, lon, -150, 190, 3.0), {
      score: 0.74,
      why: '3.0 ha, starting at the spring and on average 45 m above it; on the slope that drains to the spring; recharge potential 0.74; 70% tree cover, 22% grassland; loam or silt loam soil.',
    }),
    zone('R2', 2, patch(lat, lon, -760, 1230, 3.0), {
      link: { kind: 'GSI fault', name: 'Unnamed fault', geojson: line(lat, lon, [[-150, -100], [-500, 700], [-760, 1230]], {}) },
      in_catchment_pct: 0, distance_m: 1350, height_above_spring_m: { min: 70, mean: 140, max: 190 }, mean_potential: 0.81,
      land_cover_pct: { 'Tree cover': 64, Grassland: 30, Cropland: 6 }, soil: { class: 'Sandy loam (sand 50-70%, clay under 20%)', clay_pct: 16, sand_pct: 58 },
      valley_between_m: 0, score: 0.62,
      why: '3.0 ha, 1350 m from the spring and on average 140 m above it, beyond the ridge; linked to the spring by a mapped fault (Unnamed fault); recharge potential 0.81; 64% tree cover, 30% grassland; sandy loam soil.',
    }),
    zone('R3', 3, patch(lat, lon, -330, 440, 3.0), {
      distance_m: 320, height_above_spring_m: { min: 60, mean: 110, max: 160 }, mean_potential: 0.66, mean_slope_deg: 24,
      land_cover_pct: { Cropland: 48, 'Tree cover': 40, 'Built-up': 12 }, score: 0.58,
      why: '3.0 ha, 320 m from the spring and on average 110 m above it; on the slope that drains to the spring; recharge potential 0.66; 48% cropland, 40% tree cover; loam or silt loam soil.',
    }),
  ];
  const ring = zones.flatMap((z) => (z.geojson?.geometry.coordinates[0] ?? []) as LonLat[]);
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const image = potentialImage();
  const pad = 0.0006;
  const result: BResult = {
    spring_cell: { latitude: lat, longitude: lon, elevation_m: elev - 9, moved_m: 14, note: 'The spring was moved 14 m to the nearest elevation-map cell on the slope line.' },
    surface_catchment: { area_ha: 8.0, geojson: catchment },
    exact_cell_catchment: { area_ha: 2.1, geojson: blob(lat, lon, 2.1, 2.0, 335, w2) },
    target_area_ha: { low: 1.2, mid: 3.0, high: 7.5, kind: 'lean flow', basis: 'Sized from the lean-season flow (4 L/min) times 3.3, the median monsoon/lean ratio, with the Rathi (2021) area-flow relation.' },
    streams_block_zones: true,
    recharge_zones: zones,
    search: {
      searched: 'Searched all ground within 4 km that can send water to the spring: the slope that drains to it, and ground at least 20 m higher beyond it along 2 faults or lineaments passing within 200 m of the spring.',
      links: 2,
      checks: [
        'Walk each zone with a geologist before spending money: look for deep soil, open cracks in the rock, and seepage between the zone and the spring.',
        'Walk the fault line between the spring and R2: seeps, wet patches or green strips along it support a link.',
        'Measure the water temperature and EC every month: water from higher up is a little cooler.',
      ],
    },
    potential_overlay: image ? {
      image,
      bounds: [[Math.min(...lats) - pad, Math.min(...lons) - pad], [Math.max(...lats) + pad, Math.max(...lons) + pad]],
      legend: POTENTIAL_LEGEND,
    } : null,
    factors: [
      { id: 'slope', name: 'Slope', weight_pct: 25, how: 'Gentle slopes keep water longer so more soaks in.' },
      { id: 'land_cover', name: 'Land cover', weight_pct: 20, how: 'Forest and grass score higher than bare ground or roofs.' },
      { id: 'rock', name: 'Rock type', weight_pct: 20, how: 'Fractured quartzite scores higher than shale or phyllite.' },
      { id: 'structure', name: 'Faults, cracks and rock tilt', weight_pct: 20, how: 'Ground near faults and lineaments, and up the tilt of the rock layers, scores higher.' },
      { id: 'soil', name: 'Soil texture', weight_pct: 15, how: 'Sandy loam lets water in faster than clay; stony soil is scored low.' },
    ],
    geology: { rock_class: 'Hard rock, fractured', unit: 'Lansdowne granite / quartzite', nearest_fault_m: 410, nearest_fault_name: 'Main Boundary Thrust' },
    faults: fc([
      line(lat, lon, [[-1600, 120], [-700, 330], [0, 410], [800, 560], [1700, 690]], { name: 'Main Boundary Thrust', type: 'thrust' }),
      line(lat, lon, [[-900, 1500], [-500, 700], [-150, -100], [200, -900]], { name: 'Unnamed fault', type: 'fault' }),
    ]),
    lineaments: fc([
      line(lat, lon, [[-700, 50], [-120, 620]], { length_m: 820 }),
      line(lat, lon, [[-420, -220], [-460, 420]], { length_m: 640 }),
      line(lat, lon, [[150, 200], [600, 900]], { length_m: 830 }),
    ]),
    streams: fc([
      line(lat, lon, [[-520, 760], [-330, 430], [-120, 150], [60, -60], [300, -330], [700, -650]], { order: 2 }),
      line(lat, lon, [[-860, 300], [-560, 230], [-330, 430]], { order: 1 }),
      line(lat, lon, [[-80, 900], [-200, 560], [-120, 150]], { order: 1 }),
      line(lat, lon, [[1300, 400], [1000, -200], [700, -650], [500, -1200]], { order: 3 }),
      line(lat, lon, [[1400, -300], [1000, -200]], { order: 1 }),
    ]),
  };
  return {
    module: 'B', title: 'Springshed (recharge area)', version: '0.3-demo', status: 'provisional', confidence: 'Low',
    summary: ['The catchment of this spring is the valley above it, up to the surrounding ridges. Rain falling here runs or seeps towards the spring.',
      'R1 (just above the outlet, on the spring\'s own slope) was picked because it has gentle slopes and forest cover.',
      'R2 lies beyond the ridge, connected through a fault; check that link in the field.'],
    validation: 'Not yet validated: no field-walked springshed boundary has been compared with these zones. They are candidate places to inspect, not delineated springsheds.',
    rationale: [
      'All ground within 4 km that can send water to the spring was scored on recharge potential, how strong its link to the spring is, and how close it is.',
      'R1, the best place to recharge this spring, is just above the outlet on its own slope.',
      'R2 lies beyond the ridge, linked by a fault that passes 180 m from the spring. Check that link in the field before relying on it.',
    ],
    missing_inputs: [{ id: 'dip_direction_deg', indicator: 'Tilt of the rock layers', weight: 10, needs: 'Measure the dip direction and angle of rock layers near the outlet.' }],
    warnings: ['Demo data: these shapes are illustrative only.', 'Rock-layer tilt was not measured, so the up-dip direction was not searched.'],
    result,
    report_markdown: '',
  };
}

function pt(lat: number, lon: number, east: number, north: number) {
  const [lo, la] = offset(lat, lon, east, north);
  return { latitude: la, longitude: lo };
}

// ------------------------------------------------------------------ Module C
const MONTHLY_RAIN = [45, 50, 40, 25, 45, 190, 450, 440, 230, 55, 10, 20];

function moduleC(req: AssessRequest, lat: number, lon: number, elev: number, b: BResult): AssessResponse['C'] {
  const a = { ...DEFAULT_ASSUMPTIONS, ...(req.di.assumptions ?? {}) };
  const rain = a.annual_rain_mm ?? 1600;
  const leanFlow = req.field.lean_flow_lpm ?? 4;
  const minutesYear = 365 * 24 * 60;
  const minutesLean = a.lean_season_months * 30.4 * 24 * 60;
  const shares: Record<DiSiteResult['location_class'], Range> = {
    in_zone_slope: { low: 0.3, mid: 0.6, high: 1.0 },
    in_zone_linked: { low: 0.1, mid: 0.3, high: 0.6 },
    in_zone_crack: { low: 0.05, mid: 0.2, high: 0.5 },
    in_catchment: { low: 0.08, mid: 0.18, high: 0.3 },
    outside: { low: 0, mid: 0.03, high: 0.08 },
    below_spring: { low: 0, mid: 0, high: 0 },
  };
  const notes: Record<DiSiteResult['location_class'], string> = {
    in_zone_slope: 'Inside recharge zone {zone}, on the slope that drains to the spring: most of the injected water can reach it.',
    in_zone_linked: 'Inside recharge zone {zone}, linked to the spring by a mapped fault or tilted rock layers: some water may reach it if that link is real.',
    in_zone_crack: 'Inside recharge zone {zone}, linked to the spring by a lineament (a likely crack): some water may reach it.',
    in_catchment: 'In the surface catchment but outside the recharge zones.',
    outside: 'Outside the recharge zones: little of this water is expected at the spring.',
    below_spring: 'Lower than the spring: water injected here cannot flow up to it.',
  };
  const scale = (r: Range, k: number): Range => ({ low: r.low * k, mid: r.mid * k, high: r.high * k });
  const sites: DiSiteResult[] = req.di.sites.map((s: DiSite, i) => {
    const d = distanceM(lat, lon, s.latitude, s.longitude);
    // pretend the ground rises north-west of the spring
    const dy = (s.latitude - lat) * M_PER_DEG_LAT;
    const dx = (s.longitude - lon) * M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
    const height = Math.round((dy - dx) * 0.35);
    let cls: DiSiteResult['location_class'] = 'outside';
    let zone: RechargeZone | null = null;
    if (height < -5) cls = 'below_spring';
    else if ((zone = b.recharge_zones.find((z) => insidePolygon(s.latitude, s.longitude, z.geojson)) ?? null)) {
      cls = zone.link.kind === 'Surface slope' ? 'in_zone_slope' : zone.link.kind === 'DEM lineament' ? 'in_zone_crack' : 'in_zone_linked';
    } else if (insidePolygon(s.latitude, s.longitude, b.surface_catchment.geojson)) cls = 'in_catchment';
    const eff = (s.first_flush ? 1 : 0.92) * (s.filter ? 1 : 0.9);
    const vol = (s.roof_area_m2 * rain) / 1000 * a.collection_coefficient * a.injection_efficiency * eff;
    const share = shares[cls];
    const flags: string[] = [];
    if (!s.first_flush) flags.push('No first-flush diverter: dirty first rain goes into the aquifer.');
    if (!s.filter) flags.push('No filter: silt may clog the handpump.');
    if (cls === 'below_spring') flags.push('Below the spring.');
    if (d > 600) flags.push('Far from the spring: slow and uncertain.');
    const mound = (sy: number) => (vol * share.mid) / (sy * Math.PI * a.radius_of_influence_m ** 2);
    const depth = s.depth_m ?? 70;
    const top = elev + height;
    const flowPath: FlowPath = {
      profile: Array.from({ length: 21 }, (_, k) => [Math.round((d * k) / 20), Math.round(top - (height * k) / 20 + 6 * Math.sin((k / 20) * Math.PI))] as [number, number]),
      length_m: Math.round(d), ground_at_handpump_m: top, depth_m: depth, injection_elevation_m: top - depth, spring_elevation_m: elev,
      water_level_m: s.water_level_m ?? null, head_at_handpump_m: s.water_level_m != null ? top - s.water_level_m : null,
      hydraulic_gradient: d > 0 ? Math.round((height / d) * 100) / 100 : 0,
      gradient_basis: 'water table assumed to follow the ground slope, as in the SRHU reports (no water level given)',
      travel_time_days: null, valley_between_m: null,
    };
    return {
      id: s.id,
      name: s.name || `DI site ${i + 1}`,
      latitude: s.latitude,
      longitude: s.longitude,
      elevation_m: elev + height,
      roof_area_m2: s.roof_area_m2,
      runoff_m3_per_year: Math.round((s.roof_area_m2 * rain) / 1000 * a.collection_coefficient * 10) / 10,
      volume_m3_per_year: Math.round(vol * 10) / 10,
      location_class: cls,
      location_note: notes[cls].replace('{zone}', zone?.id ?? ''),
      zone_id: zone?.id ?? null,
      share_reaching_spring: share,
      reaching_m3_per_year: scale(share, vol),
      depth_m: depth,
      depth_given: s.depth_m != null,
      flow_path: flowPath,
      added_flow_lpm_annual: scale(share, (vol * 1000) / minutesYear),
      added_flow_lpm_lean: scale(share, (vol * 1000) / minutesLean),
      water_level_rise_m: { low: Math.round(mound(0.05) * 100) / 100, high: Math.round(mound(0.02) * 100) / 100 },
      travel_time_days: cls === 'below_spring' || cls === 'outside' ? null : { low: Math.round(d / 5), high: Math.round(d / 0.8) },
      distance_to_spring_m: Math.round(d),
      height_above_spring_m: height,
      flags,
    };
  });
  const sum = (k: 'added_flow_lpm_annual' | 'added_flow_lpm_lean'): Range => ({
    low: sites.reduce((t, s) => t + s[k].low, 0),
    mid: sites.reduce((t, s) => t + s[k].mid, 0),
    high: sites.reduce((t, s) => t + s[k].high, 0),
  });
  const volume = sites.reduce((t, s) => t + s.volume_m3_per_year, 0);
  const lean = sum('added_flow_lpm_lean');
  const perRoofLean = ((100 * rain) / 1000 * a.collection_coefficient * a.injection_efficiency * 1000 * 0.5) / minutesLean;
  const rainTotal = MONTHLY_RAIN.reduce((s, v) => s + v, 0);
  const result: CResult = {
    rain: { annual_mm: rain, source: a.annual_rain_mm == null ? 'CHIRPS 2018-2025 mean at the spring' : 'Entered by you', monthly_mm: MONTHLY_RAIN.map((v) => Math.round((v * rain) / rainTotal)) },
    sites,
    totals: {
      volume_m3_per_year: Math.round(volume * 10) / 10,
      added_flow_lpm_annual: sum('added_flow_lpm_annual'),
      added_flow_lpm_lean: lean,
      lean_flow_lpm: leanFlow,
      pct_of_lean_flow: leanFlow > 0 ? scale(lean, 100 / leanFlow) : null,
    },
    monthly_injection_m3: sites.length ? MONTHLY_RAIN.map((v) => Math.round((v / rainTotal) * volume * 10) / 10) : null,
    roofs_for_10pct: leanFlow > 0 ? Math.ceil((0.1 * leanFlow) / perRoofLean) : null,
    safety: {
      ready: sites.length > 0 && sites.every((s) => !s.flags.some((f) => f.startsWith('No first-flush') || f.startsWith('No filter'))),
      actions: sites.length ? [
        ...sites.filter((s) => s.flags.some((f) => f.startsWith('No first-flush'))).map((s) => `Fit a first-flush diverter at ${s.name}`),
        ...sites.filter((s) => s.flags.some((f) => f.startsWith('No filter'))).map((s) => `Fit a filter at ${s.name}`),
        'Test the roof water and the spring water (turbidity, coliform, iron) before the first injection',
        'Check each handpump for clogging and overflow after the first heavy rain, and clean the filter each season',
      ] : [],
    },
    assumptions: [
      { id: 'annual_rain_mm', label: 'Yearly rain', value: rain, unit: 'mm', note: a.annual_rain_mm == null ? 'From rainfall maps at the spring' : 'Entered by you' },
      { id: 'collection_coefficient', label: 'Share of roof rain reaching the handpump', value: a.collection_coefficient, unit: '', note: 'Losses from splashing, gutters and evaporation' },
      { id: 'injection_efficiency', label: 'Share left after first flush and overflow', value: a.injection_efficiency, unit: '', note: 'Heavy storms overflow the pipe' },
      { id: 'lean_season_months', label: 'Months the extra water comes out in', value: a.lean_season_months, unit: 'months', note: 'Best case: all of it in the dry season' },
      { id: 'radius_of_influence_m', label: 'Radius of the water mound', value: a.radius_of_influence_m, unit: 'm', note: 'Used for the water-level rise' },
      { id: 'specific_yield', label: 'Share of rock that holds water', value: '0.02-0.05', unit: '', note: 'Fractured hard rock' },
    ],
    benchmarks: [
      'A 100 m² roof in 1,600 mm of rain catches about 160 m³ (1.6 lakh litres) a year before losses.',
      'ICIMOD reports +23% and +48% spring flow after full springshed treatment (not DI alone), so this is context only.',
      'Springs in the dataset give a median lean flow of 5 L/min.',
    ],
    monitoring_plan: [
      'Measure the spring flow with a bucket and stopwatch on the 1st of every month, starting now, before any work.',
      'Keep the same record for one nearby spring that gets no recharge work, to compare.',
      'Note rain on the day of each reading and any cleaning of first-flush diverters and filters.',
      'Check water in the DI handpumps once a month after the monsoon (a dip-meter or a rope with a weight).',
      'Compare May-June flows over at least two years before judging the result.',
    ],
  };
  return {
    module: 'C', title: 'Potential impact of DI recharging', version: '0.2-demo', status: sites.length ? 'provisional' : 'complete',
    summary: sites.map((x) => `${x.name}: about ${Math.round(x.volume_m3_per_year)} m3 a year goes in at ${x.depth_m} m depth. Of that, about ${Math.round(x.reaching_m3_per_year?.mid ?? 0)} m3 a year may reach the spring, if the handpump is connected to it.`),
    confidence: 'Low',
    validation: 'Not yet validated: no monitored DI site has been compared with these estimates. They are planning scenarios that depend on the assumed shares; the real gain could be zero.',
    rationale: sites.length ? [
      `${sites.length} DI site${sites.length > 1 ? 's' : ''} could put about ${Math.round(volume)} m³ of roof water into the ground each year.`,
      'Only part of it reaches this spring; the share depends on whether the handpump sits inside the recharge zone.',
      'The added flow is a best case: it assumes the extra water comes out evenly in the dry months.',
      'If a site turns out not to be connected to the spring, which only monitoring can show, its gain is zero.',
    ] : ['No DI sites were given. Add handpumps on the map to see how much water they could add.'],
    missing_inputs: [],
    warnings: ['Demo data: these numbers are illustrative only.', 'Check each handpump is truly defunct and its bore is open before planning.'],
    result,
    report_markdown: '',
  };
}

// ------------------------------------------------------------------ public
export function mockAssess(req: AssessRequest): AssessResponse {
  const { latitude: lat, longitude: lon } = req.spring;
  const elev = Math.round(req.spring.elevation_m ?? DEMO_SPRING.elevation_m);
  const B = moduleB(lat, lon, elev);
  return {
    run_id: `demo-${Date.now().toString(36)}`,
    created_at: new Date().toISOString(),
    map_set: 'none approved',
    spring: { name: req.spring.name || 'Unnamed spring', latitude: lat, longitude: lon, elevation_m: elev },
    A: moduleA(req, elev),
    B,
    C: moduleC(req, lat, lon, elev, B.result!),
  };
}

/** Two example DI sites for the demo spring: one inside a recharge zone, one further out. */
export function demoDiSites(): DiSite[] {
  const { latitude: lat, longitude: lon } = DEMO_SPRING;
  const a = pt(lat, lon, -95, 120);
  const b = pt(lat, lon, -260, 360);
  return [
    { id: 'di-demo-1', name: 'School handpump', ...a, roof_area_m2: 180, first_flush: true, filter: true },
    { id: 'di-demo-2', name: 'Panchayat bhawan', ...b, roof_area_m2: 120, first_flush: true, filter: false },
  ];
}

/** A ready-made answer for the demo spring, with two DI sites. */
export const mockResponse = (): AssessResponse => mockAssess({
  spring: DEMO_SPRING,
  field: { flow_vs_past: 'a_bit_less', lean_flow_lpm: 4, low_flow_months: 3, households: 35, seasonality: 'seasonal_perennial' },
  di: { sites: demoDiSites(), assumptions: { annual_rain_mm: 1600 } },
});

// ------------------------------------------------------------------ spring list
const NAMES = [
  'Bhatwari Dhara', 'Kaflani Naula', 'Gadhera Srot', 'Chandi Dhara', 'Mala Naula', 'Pipal Pani', 'Thala Dhara',
  'Banj Naula', 'Kholi Dhara', 'Sera Srot', 'Gaon Dhara', 'Devi Naula', 'Ghatti Pani', 'Upli Dhara', 'Bagar Naula',
  'Simli Dhara', 'Kunj Srot', 'Hariyali Pani', 'Talla Naula', 'Malla Dhara', 'Jamun Dhara', 'Chir Naula', 'Patal Pani',
  'Gwar Dhara', 'Dungri Naula', 'Bakhli Srot', 'Kapkot Dhara', 'Ranikhet Naula', 'Saknoli Dhara',
];
const VILLAGES = ['Bhatwari', 'Kaflani', 'Thalisain', 'Chandpur', 'Malari', 'Pipalkoti', 'Thal', 'Banjgaon', 'Kholi', 'Seraghat',
  'Gaon', 'Devidhura', 'Ghat', 'Upli', 'Bagar', 'Simli', 'Kunjapuri', 'Hariyali', 'Talla Ramgarh', 'Malla Ramgarh',
  'Jamunda', 'Chirbatiya', 'Patalbhuvaneshwar', 'Gwaldam', 'Dungri', 'Bakhli', 'Kapkot', 'Ranikhet', 'Saknoli'];
const DISTRICTS: [string, number, number][] = [
  ['Uttarkashi', 30.75, 78.4], ['Tehri Garhwal', 30.35, 78.45], ['Dehradun', 30.45, 77.95], ['Pauri Garhwal', 29.95, 78.75],
  ['Rudraprayag', 30.4, 79.05], ['Chamoli', 30.35, 79.45], ['Almora', 29.65, 79.6], ['Nainital', 29.35, 79.45],
  ['Bageshwar', 29.9, 79.75], ['Champawat', 29.3, 79.95], ['Pithoragarh', 29.65, 79.95],
];

export function mockSprings(): DatasetSpring[] {
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const list: DatasetSpring[] = [{
    id: 'SPR-0417', name: DEMO_SPRING.name, village: 'Nauli', district: 'Pauri Garhwal',
    latitude: DEMO_SPRING.latitude, longitude: DEMO_SPRING.longitude, elevation_m: DEMO_SPRING.elevation_m, source: 'Demo list',
  }];
  NAMES.forEach((name, i) => {
    const [district, dlat, dlon] = DISTRICTS[i % DISTRICTS.length];
    const lat = Math.min(30.9, Math.max(29.2, dlat + (rand() - 0.5) * 0.4));
    const lon = Math.min(80.0, Math.max(77.8, dlon + (rand() - 0.5) * 0.4));
    list.push({
      id: `SPR-${String(500 + i * 13).padStart(4, '0')}`, name, village: VILLAGES[i], district,
      latitude: round6(lat), longitude: round6(lon), elevation_m: Math.round(900 + rand() * 1500), source: 'Demo list',
    });
  });
  return list;
}
