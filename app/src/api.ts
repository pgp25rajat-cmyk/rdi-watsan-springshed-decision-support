// What the page sends to and gets back from the local server (scripts/spring_tool_server.py).
// The Python side builds exactly these shapes; change both together.

export type Status = 'complete' | 'provisional' | 'unavailable' | 'failed';
export type Confidence = 'Low' | 'Medium' | 'High';
export type Range = { low: number; mid: number; high: number };
export type Feature = { type: 'Feature'; geometry: any; properties: Record<string, any> };
export type FeatureCollection = { type: 'FeatureCollection'; features: Feature[] };

// ------------------------------------------------------------------ request
export type FieldAnswers = {
  // Module A questions (ids and allowed values match OPTIONAL in scripts/module_a_vulnerability.py)
  flow_vs_past?: 'more' | 'same' | 'a_bit_less' | 'much_less' | 'dries_at_times';
  lean_flow_lpm?: number;
  monsoon_flow_lpm?: number;
  low_flow_months?: number;
  dry_months?: number; // months with no flow at all
  households?: number;
  users_vs_past?: 'fewer' | 'same' | 'more' | 'much_more';
  water_quality?: 'no_issue' | 'muddy_after_rain' | 'contamination';
  pollution_30m?: 'none' | 'one' | 'two_or_more' | 'latrine';
  disturbance_uphill?: 'little' | 'some' | 'major';
  disaster_prone?: 'no' | 'minor' | 'major';
  existing_interventions?: string[]; // check_dams, trenches, pits, ponds, plantation, di_handpumps, other, none
  protection?: 'both' | 'one' | 'neither';
  recharge_works?: 'maintained' | 'neglected' | 'none';
  seasonality?: 'perennial' | 'seasonal_perennial' | 'seasonal' | 'highly_seasonal' | 'ephemeral';
  spring_type?: string;
  rock_at_outlet?: string;
  // Module B extras
  dip_direction_deg?: number; // direction the rock layers tilt down towards, 0-360 from north
  dip_angle_deg?: number;
  streams_block_zones?: boolean; // false: recharge zones may grow across stream channels (default: streams stop them)
};

export type DiSite = {
  id: string;
  name?: string;
  latitude: number;
  longitude: number;
  roof_area_m2: number;
  first_flush: boolean;
  filter: boolean;
  depth_m?: number | null; // handpump depth; 70 m when not given
  water_level_m?: number | null; // water level in the handpump, m below ground (optional)
};

export type DiAssumptions = {
  annual_rain_mm: number | null; // null = read from the rainfall maps at the spring
  collection_coefficient: number; // share of roof rain that reaches the handpump (0.7-0.9)
  injection_efficiency: number; // share left after first flush and overflow (0.7-0.95)
  lean_season_months: number; // months the extra water is assumed to come out in (best case)
  radius_of_influence_m: number; // mound radius for the water-level estimate
};

export type AssessRequest = {
  spring: { name?: string; latitude: number; longitude: number; elevation_m?: number | null };
  field: FieldAnswers;
  di: { sites: DiSite[]; assumptions?: Partial<DiAssumptions> };
};

// ------------------------------------------------------------------ response
export type MissingInput = { id: string; indicator: string; weight?: number; needs: string };

export type ModuleOutput<R> = {
  module: 'A' | 'B' | 'C';
  title: string;
  version: string;
  status: Status;
  confidence: Confidence; // how complete the inputs were ("Evidence" on the page), not whether the answer is right
  validation?: string; // whether the module has been checked against field evidence yet
  summary?: string[]; // the result in everyday words, shown first
  rationale: string[];
  missing_inputs: MissingInput[];
  warnings: string[];
  result: R | null;
  report_markdown: string;
};

export type Indicator = {
  id: string;
  group: string; // e.g. 'State (field)', 'Stressor (location)'
  indicator: string;
  value: string;
  score: number; // 0-100
  weight_used_pct: number;
  points: number;
  comparison: string;
  why: string;
};

export type AResult = {
  score: number;
  class: 'Low' | 'Medium' | 'High';
  kind: 'vulnerability score' | 'exposure score';
  coverage_pct: number;
  indicators: Indicator[];
  context: string[];
  nearest_dataset_spring: { record_id: string; spring_name: string; distance_m: number } | null;
  elevation_gap_m: number | null;
  // what the vulnerability tab draws: the circles the map indicators use, and land cover within 1 km
  map?: {
    rings: { radius_m: number; label: string }[];
    land_cover: Overlay & { legend: { label: string; color: string; disturbed: boolean }[] } | null;
  };
};

export type Overlay = {
  image: string; // data:image/png;base64,...
  bounds: [[number, number], [number, number]]; // [[south, west], [north, east]]
  legend: { label: string; color: string }[];
};

export type SoilSummary = { class: string; clay_pct: number; sand_pct: number };

export type LinkKind = 'Surface slope' | 'GSI fault' | 'Rock layers (up-dip)' | 'DEM lineament' | 'Mapped lineament';

// One of the top recharge zones (R1-R3), ranked by recharge potential x link to the spring x closeness.
// It may lie on the spring's own slope or beyond the ridge, linked by a fault, a crack (lineament) or tilted rock layers.
export type RechargeZone = {
  id: string; // R1, R2, R3
  rank: number;
  area_ha: number;
  geojson: Feature | null; // Polygon or MultiPolygon, WGS84
  link: { kind: LinkKind; name: string; geojson: Feature | null }; // geojson: the fault or lineament line, if any
  in_catchment_pct: number;
  distance_m: number;
  height_above_spring_m: { min: number; mean: number; max: number };
  mean_potential: number; // 0-1
  mean_slope_deg: number;
  land_cover_pct: Record<string, number>;
  soil: SoilSummary | null;
  soil_depth_cm?: number | null;
  rock_unit: string;
  valley_between_m: number;
  crosses_fault: boolean;
  score: number;
  why: string;
};

export type BResult = {
  spring_cell: { latitude: number; longitude: number; elevation_m: number; moved_m: number; note: string };
  surface_catchment: { area_ha: number; geojson: Feature | null; note?: string; snapped_m?: number; snapped_drainage_ha?: number }; // the valley up to the ridges
  outlet_catchment?: { area_ha: number; geojson: Feature | null; note?: string }; // land running off straight to the outlet (30 m GPS allowance)
  exact_cell_catchment?: { area_ha: number; geojson: Feature | null; note?: string }; // the map cell at the exact coordinate
  target_area_ha: Range & { basis: string; kind?: 'monsoon flow' | 'lean flow' | 'default' }; // recharge area the flow needs
  streams_block_zones?: boolean;
  recharge_zones: RechargeZone[]; // best first
  search: { searched: string; links: number; checks: string[] };
  potential_overlay: Overlay | null;
  factors: { id: string; name: string; weight_pct: number; how: string }[];
  geology: { rock_class: string; unit: string; nearest_fault_m: number | null; nearest_fault_name: string } | null;
  faults: FeatureCollection; // GSI faults and thrusts in the window (properties.name, properties.type)
  lineaments: FeatureCollection; // DEM lineament candidates in the window
  mapped_lineaments?: FeatureCollection; // GSI Bhukosh 1:250k lineaments in the window (properties.type)
  streams: FeatureCollection; // DEM streams in the window (properties.order)
};

export type DiSiteResult = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  elevation_m: number | null;
  roof_area_m2: number;
  runoff_m3_per_year?: number; // roof rain reaching the handpump
  volume_m3_per_year: number; // of that, actually injected
  location_class: 'in_zone_slope' | 'in_zone_linked' | 'in_zone_crack' | 'in_catchment' | 'outside' | 'below_spring';
  zone_id?: string | null;
  location_note: string;
  share_reaching_spring: Range;
  reaching_m3_per_year?: Range;
  depth_m?: number;
  depth_given?: boolean;
  water_level_m?: number | null;
  flow_path?: FlowPath | null;
  added_flow_lpm_annual: Range;
  added_flow_lpm_lean: Range;
  water_level_rise_m: { low: number; high: number };
  travel_time_days: { low: number; high: number } | null;
  distance_to_spring_m: number;
  height_above_spring_m: number | null;
  flags: string[];
};

// Ground profile from a handpump to the spring, for the cross-section drawing
export type FlowPath = {
  profile: [number, number][]; // [distance from the handpump m, ground height m]
  length_m: number;
  ground_at_handpump_m: number;
  depth_m: number;
  injection_elevation_m: number;
  spring_elevation_m: number;
  water_level_m: number | null;
  head_at_handpump_m: number | null;
  hydraulic_gradient: number;
  gradient_basis: string;
  travel_time_days: { low: number; high: number } | null;
  valley_between_m: number | null;
  depth_factor?: number;
  depth_words?: string;
};

export type CResult = {
  rain: { annual_mm: number; source: string; monthly_mm: number[] | null; snow_mm?: number; snow_used_mm?: number }; // monthly: Jan..Dec
  sites: DiSiteResult[];
  totals: {
    volume_m3_per_year: number;
    reaching_m3_per_year?: Range;
    added_flow_lpm_annual: Range;
    added_flow_lpm_lean: Range;
    lean_flow_lpm: number | null;
    pct_of_lean_flow: Range | null;
  };
  monthly_injection_m3: number[] | null; // Jan..Dec, all sites
  roofs_for_10pct: number | null; // 100 m2 roofs in a slope recharge zone needed for +10% lean flow (mid case, conditional)
  safety?: { ready: boolean; actions: string[] }; // missing safeguards make the plan "not ready"
  assumptions: { id: string; label: string; value: number | string; unit: string; note: string }[];
  benchmarks: string[];
  monitoring_plan: string[];
};

export type AssessResponse = {
  persistence?: { durable: boolean; reason?: string; archive_key?: string };
  run_id: string;
  created_at: string;
  map_set: string; // approved map set id, or 'none approved'
  spring: { name: string; latitude: number; longitude: number; elevation_m: number };
  A: ModuleOutput<AResult>;
  B: ModuleOutput<BResult>;
  C: ModuleOutput<CResult>;
};

export type DatasetSpring = {
  id: string;
  name: string;
  village: string;
  district: string;
  latitude: number;
  longitude: number;
  elevation_m: number | null;
  source: string;
};

export type Health = {
  ok: boolean;
  version: string;
  map_set: { snapshot_id: string; approved_by: string; approved_at: string } | null;
  offline: boolean; // true when only the approved map set is read (nothing downloaded)
};

export const DEFAULT_ASSUMPTIONS: DiAssumptions = {
  annual_rain_mm: null,
  collection_coefficient: 0.8,
  injection_efficiency: 0.85,
  lean_season_months: 5,
  radius_of_influence_m: 50,
};

export async function getHealth(): Promise<Health> {
  const r = await fetch('/api/health');
  if (!r.ok) throw new Error(`Server answered ${r.status}`);
  const health = await r.json();
  if (health.hosted) {
    const status = await fetch('/api/status');
    if (!status.ok) throw new Error(`Server answered ${status.status}`);
    return status.json();
  }
  return health;
}

export async function getSprings(): Promise<DatasetSpring[]> {
  const r = await fetch('/api/springs');
  if (!r.ok) throw new Error(`Server answered ${r.status}`);
  return r.json();
}

export async function assess(request: AssessRequest): Promise<AssessResponse> {
  const r = await fetch('/api/assess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Server answered ${r.status}`);
  return body;
}
