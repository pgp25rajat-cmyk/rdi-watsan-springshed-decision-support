import { useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { AssessResponse, DatasetSpring, DiSite, DiSiteResult, Feature, FeatureCollection, Overlay } from '../api';
import { ZONE_RANK_COLORS, linkLabel, locationClass, num } from '../format';

// MapLibre 6 ships a separate module worker. Vite must bundle it and its imports;
// otherwise it looks beside the app bundle for a worker file that was never copied.
maplibregl.setWorkerUrl(mapWorkerUrl);

export type Tab = 'A' | 'B' | 'C';
export type Placing = 'none' | 'spring' | 'site';
export type Focus = { lat: number; lon: number; zoom: number; n: number };
type Base = 'sat' | 'topo' | 'osm';

type Props = {
  springs: DatasetSpring[];
  point: { lat: number; lon: number } | null;
  springName: string;
  result: AssessResponse | null;
  tab: Tab;
  sites: DiSite[];
  placing: Placing;
  canCancel: boolean;
  focus: Focus | null;
  terrainUrl: string; // Terrarium-encoded elevation tiles for the 3D view
  onPlace: (lat: number, lon: number) => void;
  onCancelPlacing: () => void;
  onSpringDrag: (lat: number, lon: number) => void;
  onSiteMove: (id: string, lat: number, lon: number) => void;
  onUseSpring: (s: DatasetSpring) => void;
};

const UTTARAKHAND: [[number, number], [number, number]] = [[77.6, 28.7], [81.1, 31.4]];
const BASES: { id: Base; label: string }[] = [
  { id: 'sat', label: 'Satellite' },
  { id: 'topo', label: 'Topo map' },
  { id: 'osm', label: 'Streets' },
];
const ZONE_LINE = '#14532d';
const LINK = '#8e5bb5';
const FLOW = '#0b5fa5';
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };
const PITCH_3D = 58;

function fc(features: (Feature | null | undefined)[]): FeatureCollection {
  return { type: 'FeatureCollection', features: features.filter((f): f is Feature => !!f) };
}

/** A circle of radius_m around a point, as a closed line. */
function ring(lat: number, lon: number, radiusM: number, props: Record<string, unknown>): Feature {
  const coords: [number, number][] = [];
  const dLat = radiusM / 111_132;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= 96; i += 1) {
    const a = (i / 96) * 2 * Math.PI;
    coords.push([lon + dLon * Math.sin(a), lat + dLat * Math.cos(a)]);
  }
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: coords }, properties: props };
}

/** [[west, south], [east, north]] of everything given, or null. */
function bboxOf(features: (Feature | null | undefined)[], points: [number, number][] = []) {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const add = (c: any) => {
    if (typeof c[0] === 'number') {
      w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
    } else for (const x of c) add(x);
  };
  for (const f of features) if (f?.geometry?.coordinates) add(f.geometry.coordinates);
  for (const p of points) add(p);
  return Number.isFinite(w) ? ([[w, s], [e, n]] as [[number, number], [number, number]]) : null;
}

/** Assumed groundwater path from each assessed handpump to the spring: a line and an arrow head near the spring. */
function flowPaths(sites: DiSiteResult[], spring: { latitude: number; longitude: number }): FeatureCollection {
  const out: Feature[] = [];
  const kx = Math.cos((spring.latitude * Math.PI) / 180);
  for (const s of sites) {
    const a: [number, number] = [s.longitude, s.latitude], b: [number, number] = [spring.longitude, spring.latitude];
    const dx = (b[0] - a[0]) * kx, dy = b[1] - a[1];
    const len = Math.hypot(dx, dy);
    if (len === 0) continue;
    const reach = s.share_reaching_spring.mid;
    out.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [a, b] }, properties: { kind: 'path', name: s.name, reach } });
    // arrow head 85% of the way along, sized to the path but at least ~12 m and at most ~40 m
    const size = Math.min(Math.max(len * 0.12, 0.00011), 0.00036);
    const ux = dx / len, uy = dy / len;
    const tip: [number, number] = [a[0] + (b[0] - a[0]) * 0.85, a[1] + (b[1] - a[1]) * 0.85];
    const back = (f: number, side: number): [number, number] => [tip[0] + (-ux * size * f - uy * size * 0.55 * side) / kx, tip[1] + (-uy * size * f + ux * size * 0.55 * side)];
    out.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[tip, back(1, 1), back(1, -1), tip]] }, properties: { kind: 'head', name: s.name, reach } });
  }
  return { type: 'FeatureCollection', features: out };
}

function corners(o: Overlay): [[number, number], [number, number], [number, number], [number, number]] {
  const [[south, west], [north, east]] = o.bounds;
  return [[west, north], [east, north], [east, south], [west, south]];
}

function el(className: string, html = '') {
  const d = document.createElement('div');
  d.className = className;
  d.innerHTML = html;
  return d;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

function readPref<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = window.localStorage.getItem(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}
function writePref(key: string, value: string) {
  try { window.localStorage.setItem(key, value); } catch { /* private window */ }
}

export default function MapView(props: Props) {
  const { springs, point, result, tab, sites, placing } = props;
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const live = useRef(props);
  live.current = props;
  const [ready, setReady] = useState(false);
  const [base, setBase] = useState<Base>(() => readPref('spring-tool-base', ['sat', 'topo', 'osm'] as const, 'sat'));
  const [threeD, setThreeD] = useState(() => readPref('spring-tool-3d', ['on', 'off'] as const, 'on') === 'on');
  const [heightScale, setHeightScale] = useState(() => Number(readPref('spring-tool-height-scale', ['1', '1.5', '3'] as const, '1.5')));
  const [terrainState, setTerrainState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [tilesFailed, setTilesFailed] = useState(false);
  const [heatOn, setHeatOn] = useState(false);
  const [heatOpacity, setHeatOpacity] = useState(0.65);
  const [legendOpen, setLegendOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 900);

  const A = result?.A.result ?? null;
  const B = result?.B.result ?? null;
  const C = result?.C.result ?? null;
  const zones = B?.recharge_zones ?? [];
  const siteClass = useMemo(() => {
    const m = new Map<string, DiSiteResult>();
    for (const s of C?.sites ?? []) m.set(s.id, s);
    return m;
  }, [C]);
  // DI sites belong to the DI impact tab; before any result, or while placing one, they show everywhere.
  const showSites = !result || tab === 'C' || placing === 'site';
  const showDataset = springs.length > 0 && (!result || tab === 'A');

  // ------------------------------------------------------------------ the map, once
  useEffect(() => {
    if (!box.current) return;
    const map = new maplibregl.Map({
      container: box.current,
      bounds: UTTARAKHAND,
      maxPitch: 75,
      attributionControl: { compact: true },
      style: {
        version: 8,
        sources: {
          sat: { type: 'raster', tileSize: 256, maxzoom: 19, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
            tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'] },
          topo: { type: 'raster', tileSize: 256, maxzoom: 17,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | © <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
            tiles: ['a', 'b', 'c'].map((s) => `https://${s}.tile.opentopomap.org/{z}/{x}/{y}.png`) },
          osm: { type: 'raster', tileSize: 256, maxzoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] },
          dem: { type: 'raster-dem', tiles: [props.terrainUrl], tileSize: 256, encoding: 'terrarium', maxzoom: 14,
            attribution: 'Elevation: Copernicus GLO-30, AWS Terrain Tiles' },
          shade: { type: 'raster-dem', tiles: [props.terrainUrl], tileSize: 256, encoding: 'terrarium', maxzoom: 14 },
        },
        // a sky and haze at the horizon, so a tilted 3D view fades out instead of ending in a hard edge
        sky: { 'sky-color': '#bcd8ea', 'horizon-color': '#eef2ee', 'fog-color': '#eef2ee', 'sky-horizon-blend': 0.6,
          'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.85 },
        layers: [
          { id: 'bg', type: 'background', paint: { 'background-color': '#dfe5dc' } },
          ...BASES.map((b) => ({ id: `base-${b.id}`, type: 'raster' as const, source: b.id, layout: { visibility: (b.id === base ? 'visible' : 'none') as 'visible' | 'none' } })),
          { id: 'hillshade', type: 'hillshade', source: 'shade', paint: { 'hillshade-exaggeration': 0.3, 'hillshade-shadow-color': '#2d3a2d' } },
        ],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
    mapRef.current = map;

    let loaded = 0, failed = 0;
    map.on('data', (e: any) => { if (e.tile && BASES.some((b) => b.id === e.sourceId)) { loaded += 1; setTilesFailed(false); } });
    map.on('sourcedata', (e: any) => {
      if (e.sourceId === 'dem' && e.tile) setTerrainState('ready');
    });
    map.on('error', (e: any) => {
      if (e.sourceId === 'dem') setTerrainState('error');
      if (BASES.some((b) => b.id === e.sourceId)) {
        failed += 1;
        if (failed >= 4 && loaded === 0) setTilesFailed(true);
      }
    });

    // 'style.load', not 'load': 'load' waits for every background tile, and never comes when they cannot download
    map.once('style.load', () => {
      const geo = (id: string) => map.addSource(id, { type: 'geojson', data: EMPTY });
      ['zones', 'catchment', 'exact', 'links', 'faults', 'lineaments', 'mapped', 'streams', 'rings', 'dataset', 'flow'].forEach(geo);
      map.addLayer({ id: 'zones-fill', type: 'fill', source: 'zones', paint: {
        'fill-color': ['match', ['get', 'rank'], 1, ZONE_RANK_COLORS[0], 2, ZONE_RANK_COLORS[1], ZONE_RANK_COLORS[2]],
        'fill-opacity': 0.42 } });
      map.addLayer({ id: 'zones-line', type: 'line', source: 'zones', paint: {
        'line-color': ZONE_LINE, 'line-width': ['match', ['get', 'rank'], 1, 2.8, 1.8] } });
      map.addLayer({ id: 'catchment-line', type: 'line', source: 'catchment', paint: { 'line-color': '#1d5f99', 'line-width': 2.5, 'line-dasharray': [3, 2.5] } });
      map.addLayer({ id: 'exact-line', type: 'line', source: 'exact', paint: { 'line-color': '#1d5f99', 'line-width': 1.6, 'line-dasharray': [0.6, 1.6] } });
      map.addLayer({ id: 'streams', type: 'line', source: 'streams', paint: { 'line-color': '#2b7bbd', 'line-opacity': 0.85,
        'line-width': ['+', 0.8, ['*', 0.9, ['coalesce', ['get', 'order'], 1]]] } });
      map.addLayer({ id: 'lineaments', type: 'line', source: 'lineaments', paint: { 'line-color': '#e08a1e', 'line-width': 1.6, 'line-dasharray': [2.5, 2.5] } });
      map.addLayer({ id: 'mapped', type: 'line', source: 'mapped', paint: { 'line-color': '#b5651d', 'line-width': 2.2, 'line-dasharray': [4, 1.5] } });
      map.addLayer({ id: 'faults', type: 'line', source: 'faults', paint: { 'line-color': '#d1352b', 'line-width': 2.5 } });
      map.addLayer({ id: 'links-glow', type: 'line', source: 'links', paint: { 'line-color': '#ffffff', 'line-width': 7, 'line-opacity': 0.7 } });
      map.addLayer({ id: 'links', type: 'line', source: 'links', paint: { 'line-color': LINK, 'line-width': 3.5 } });
      map.addLayer({ id: 'rings', type: 'line', source: 'rings', paint: { 'line-color': '#0b6e8a', 'line-width': 2,
        'line-dasharray': [1, 2.5], 'line-opacity': ['match', ['get', 'radius_m'], 500, 1, 0.75] } });
      map.addLayer({ id: 'flow-glow', type: 'line', source: 'flow', filter: ['==', ['get', 'kind'], 'path'],
        paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.75 } });
      map.addLayer({ id: 'flow-line', type: 'line', source: 'flow', filter: ['==', ['get', 'kind'], 'path'],
        paint: { 'line-color': FLOW, 'line-width': 3, 'line-dasharray': [2, 1.2] } });
      map.addLayer({ id: 'flow-head', type: 'fill', source: 'flow', filter: ['==', ['get', 'kind'], 'head'], paint: { 'fill-color': FLOW } });
      map.addLayer({ id: 'dataset', type: 'circle', source: 'dataset', paint: { 'circle-radius': 4.5, 'circle-color': '#0b6e8a',
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.2 } });
      setReady(true);
    });

    // hover labels for lines and areas
    const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'hover-tip', offset: 10 });
    const hoverLayers = ['zones-fill', 'catchment-line', 'exact-line', 'faults', 'mapped', 'lineaments', 'links', 'rings', 'flow-line'];
    map.on('mousemove', (e) => {
      const layers = hoverLayers.filter((l) => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') !== 'none');
      const f = layers.length ? map.queryRenderedFeatures(e.point, { layers })[0] : undefined;
      if (!f || live.current.placing !== 'none') { tip.remove(); return; }
      const p = f.properties as Record<string, any>;
      const text = f.layer.id === 'zones-fill' ? `Recharge zone ${p.id}: ${(linkLabel[p.link] ?? '').toLowerCase()}, ${num(p.area_ha, 1)} ha`
        : f.layer.id === 'catchment-line' ? `Catchment to the ridge: ${num(p.area_ha, 1)} ha (the valley above the spring, as geologists draw it)`
        : f.layer.id === 'exact-line' ? `Land running off straight to the outlet: ${num(p.area_ha, 1)} ha`
        : f.layer.id === 'mapped' ? `${p.type}`
        : f.layer.id === 'flow-line' ? `Assumed groundwater path from ${p.name} to the spring (about ${Math.round(Number(p.reach) * 100)}% of its water may arrive)`
        : f.layer.id === 'faults' ? `${p.name || 'Fault'}${p.type ? ` (${p.type})` : ''}`
        : f.layer.id === 'links' ? `Possible water path to the spring: ${p.name}`
        : f.layer.id === 'rings' ? p.label
        : 'Lineament: a straight line on the elevation map that may follow a crack in the rock';
      tip.setLngLat(e.lngLat).setText(text).addTo(map);
    });
    map.on('mouseout', () => tip.remove());

    map.on('click', (e) => {
      const p = live.current;
      if (p.placing !== 'none') { p.onPlace(e.lngLat.lat, e.lngLat.lng); return; }
      if (!map.getLayer('dataset') || map.getLayoutProperty('dataset', 'visibility') === 'none') return;
      const hit = map.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: ['dataset'] })[0];
      if (!hit) return;
      const s = p.springs.find((x) => x.id === hit.properties?.id);
      if (!s) return;
      const body = el('pop', `<strong>${escapeHtml(s.name)}</strong><div>${escapeHtml([s.village, s.district].filter(Boolean).join(', '))}</div>
        <div class="muted">${s.elevation_m != null ? `${num(s.elevation_m)} m · ` : ''}${escapeHtml(s.source)}</div>`);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-small btn-primary';
      btn.textContent = 'Use this spring';
      const popup = new maplibregl.Popup({ offset: 8 }).setLngLat([s.longitude, s.latitude]).setDOMContent(body).addTo(map);
      btn.onclick = () => { popup.remove(); live.current.onUseSpring(s); };
      body.appendChild(btn);
    });
    map.on('mouseenter', 'dataset', () => { if (live.current.placing === 'none') map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'dataset', () => { if (live.current.placing === 'none') map.getCanvas().style.cursor = ''; });

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(box.current);
    return () => { ro.disconnect(); map.remove(); mapRef.current = null; };
    // the map is made once; later changes go through the effects below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------ base map and 3D
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const b of BASES) map.setLayoutProperty(`base-${b.id}`, 'visibility', b.id === base ? 'visible' : 'none');
    setTilesFailed(false);
    writePref('spring-tool-base', base);
  }, [base, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (threeD) {
      map.setTerrain({ source: 'dem', exaggeration: heightScale });
      if (map.getPitch() < 20) map.easeTo({ pitch: PITCH_3D, duration: 700, freezeElevation: true });
    } else {
      map.setTerrain(null);
      map.easeTo({ pitch: 0, bearing: 0, duration: 600, freezeElevation: true });
    }
    writePref('spring-tool-3d', threeD ? 'on' : 'off');
    writePref('spring-tool-height-scale', String(heightScale));
  }, [threeD, heightScale, ready]);

  // the elevation tiles come from the local tool, or from a public copy in the demo
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of ['dem', 'shade']) {
      const src = map.getSource(id) as maplibregl.RasterDEMTileSource | undefined;
      if (src && src.tiles?.[0] !== props.terrainUrl) {
        setTerrainState('loading');
        src.setTiles([props.terrainUrl]);
      }
    }
  }, [props.terrainUrl, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = placing !== 'none' ? 'crosshair' : '';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') live.current.onCancelPlacing(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [placing]);

  // ------------------------------------------------------------------ what each tab shows
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const set = (id: string, data: FeatureCollection) => (map.getSource(id) as maplibregl.GeoJSONSource).setData(data as any);
    const show = (ids: string[], on: boolean) => ids.forEach((id) => map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'));

    set('dataset', showDataset ? fc(springs.map((s) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [s.longitude, s.latitude] }, properties: { id: s.id } }))) : EMPTY);
    show(['dataset'], showDataset);

    set('zones', fc([...zones].reverse().map((z) => z.geojson && { ...z.geojson, properties: { id: z.id, rank: z.rank, link: z.link.kind, area_ha: z.area_ha } })));
    set('catchment', B?.surface_catchment.geojson ? fc([{ ...B.surface_catchment.geojson, properties: { area_ha: B.surface_catchment.area_ha } }]) : EMPTY);
    const outlet = B?.outlet_catchment ?? B?.exact_cell_catchment;
    set('exact', outlet?.geojson && outlet.area_ha < (B?.surface_catchment.area_ha ?? 0) - 0.05 ? fc([{ ...outlet.geojson, properties: { area_ha: outlet.area_ha } }]) : EMPTY);
    set('links', fc(zones.map((z) => z.link.geojson && { ...z.link.geojson, properties: { name: `${z.link.name} (to ${z.id})` } })));
    set('faults', B ? B.faults : EMPTY);
    set('lineaments', B ? B.lineaments : EMPTY);
    set('mapped', B?.mapped_lineaments ?? EMPTY);
    set('flow', C && result ? flowPaths(C.sites, result.spring) : EMPTY);
    set('streams', B ? B.streams : EMPTY);
    const s = result?.spring;
    set('rings', s && A?.map ? fc(A.map.rings.map((r) => ring(s.latitude, s.longitude, r.radius_m, { radius_m: r.radius_m, label: r.label }))) : EMPTY);

    const onA = !!result && tab === 'A', onB = !!result && tab === 'B', onC = !!result && tab === 'C';
    show(['rings'], onA);
    show(['zones-fill', 'zones-line', 'catchment-line'], onB || onC);
    show(['faults', 'lineaments', 'mapped', 'streams', 'links-glow', 'links', 'exact-line'], onB);
    show(['flow-glow', 'flow-line', 'flow-head'], onC);
    // on the DI tab the zones are context for where each handpump sits, so they are drawn lighter
    map.setPaintProperty('zones-fill', 'fill-opacity', onC ? 0.2 : 0.42);
    map.setPaintProperty('catchment-line', 'line-opacity', onC ? 0.6 : 1);

    const image = (id: string, overlay: Overlay | null | undefined, visible: boolean, opacity: number, before: string) => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
      if (!overlay || !visible) return;
      map.addSource(id, { type: 'image', url: overlay.image, coordinates: corners(overlay) });
      map.addLayer({ id, type: 'raster', source: id, paint: { 'raster-opacity': opacity, 'raster-fade-duration': 0 } }, before);
    };
    image('potential-img', B?.potential_overlay, onB && heatOn, heatOpacity, 'zones-fill');
    image('landcover-img', A?.map?.land_cover, onA, 0.85, 'zones-fill');
  }, [ready, result, tab, springs, showDataset, heatOn, heatOpacity, A, B, C, zones]);

  // ------------------------------------------------------------------ markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const made: maplibregl.Marker[] = [];
    const add = (m: maplibregl.Marker) => { m.addTo(map); made.push(m); return m; };

    if (point) {
      const node = el('pin pin-spring', '<span></span>');
      node.title = props.springName || 'Your spring';
      const m = add(new maplibregl.Marker({ element: node, anchor: 'bottom', draggable: true }).setLngLat([point.lon, point.lat]));
      m.on('dragend', () => { const ll = m.getLngLat(); live.current.onSpringDrag(ll.lat, ll.lng); });
    }
    if (B && (tab === 'B' || tab === 'C')) {
      for (const z of zones) {
        const box = bboxOf([z.geojson]);
        if (!box) continue;
        const node = el(`zone-tag zone-tag-${z.rank}`, z.id);
        add(new maplibregl.Marker({ element: node }).setLngLat([(box[0][0] + box[1][0]) / 2, (box[0][1] + box[1][1]) / 2])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setDOMContent(el('pop', `<strong>Recharge zone ${z.id}</strong><div>${escapeHtml(z.why)}</div>`))));
      }
    }
    if (showSites) {
      sites.forEach((s, i) => {
        const r = siteClass.get(s.id);
        const moved = r && (Math.abs(r.latitude - s.latitude) > 1e-6 || Math.abs(r.longitude - s.longitude) > 1e-6);
        const cls = r && !moved ? r.location_class : null;
        const size = tab === 'C' ? 30 : 24;
        const node = el(`site-icon${cls ? '' : ' site-new'}`, String(i + 1));
        node.style.background = cls ? locationClass[cls].color : '#ffffff';
        node.style.width = node.style.height = `${size}px`;
        const name = escapeHtml(s.name || `DI site ${i + 1}`);
        const body = cls && r
          ? `<div><span class="badge" style="background:${locationClass[cls].color}">${locationClass[cls].label}</span><div>${escapeHtml(r.location_note)}</div></div>`
          : '<div class="muted">Not assessed yet. Run the assessment again to see its effect.</div>';
        const m = add(new maplibregl.Marker({ element: node, draggable: true }).setLngLat([s.longitude, s.latitude])
          .setPopup(new maplibregl.Popup({ offset: size / 2 }).setDOMContent(el('pop', `<strong>${name}</strong><div>Roof ${num(s.roof_area_m2)} m²</div>${body}<div class="muted">Drag the marker to move it.</div>`))));
        m.on('dragend', () => { const ll = m.getLngLat(); live.current.onSiteMove(s.id, ll.lat, ll.lng); });
      });
    }
    return () => made.forEach((m) => m.remove());
  }, [ready, point?.lat, point?.lon, props.springName, B, tab, zones, showSites, sites, siteClass]);

  // ------------------------------------------------------------------ where the camera goes
  const lastFocus = useRef(0);
  useEffect(() => {
    const map = mapRef.current;
    const focus = props.focus;
    if (!map || !ready || !focus || focus.n === lastFocus.current) return;
    lastFocus.current = focus.n;
    map.flyTo({ center: [focus.lon, focus.lat], zoom: focus.zoom, pitch: threeD ? PITCH_3D : 0, duration: 900, freezeElevation: true });
  }, [props.focus, ready, threeD]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (!result) {
      if (point && !props.focus) map.jumpTo({ center: [point.lon, point.lat], zoom: 14, pitch: threeD ? PITCH_3D : 0 });
      return;
    }
    const s = result.spring;
    const near = ring(s.latitude, s.longitude, tab === 'A' ? 1100 : 600, {});
    const features: (Feature | null | undefined)[] = [near];
    if (tab !== 'A' && B) features.push(B.surface_catchment.geojson, ...zones.map((z) => z.geojson));
    const pts: [number, number][] = tab === 'C' ? sites.map((x) => [x.longitude, x.latitude]) : [];
    const b = bboxOf(features, pts);
    if (b) map.fitBounds(b, { padding: 60, maxZoom: 16.5, pitch: threeD ? PITCH_3D : 0, duration: 900, freezeElevation: true });
    // only when the result or the tab changes, not on every edit
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result?.run_id, tab, ready]);

  // ------------------------------------------------------------------ legend
  const legend: { key: string; label: string; swatch: JSX.Element }[] = [];
  legend.push({ key: 'spring', label: 'Your spring', swatch: <i className="lg-pin" /> });
  if (showDataset) legend.push({ key: 'ds', label: 'Springs in the dataset', swatch: <i className="lg-dot" /> });
  if (result && tab === 'A' && A?.map) {
    legend.push({ key: 'r', label: 'Circles of 500 m and 1 km the map indicators use', swatch: <i className="lg-ring" /> });
    for (const l of A.map.land_cover?.legend ?? []) {
      legend.push({ key: `lc-${l.label}`, label: l.label, swatch: <i className="lg-fill" style={{ background: l.color, opacity: l.disturbed ? 1 : 0.45 }} /> });
    }
  }
  if (B && (tab === 'B' || tab === 'C')) {
    if (B.surface_catchment.geojson) legend.push({ key: 'c', label: 'Catchment to the ridge (the valley above the spring)', swatch: <i className="lg-dash" /> });
    const outlet = B.outlet_catchment ?? B.exact_cell_catchment;
    if (tab === 'B' && outlet?.geojson && outlet.area_ha < B.surface_catchment.area_ha - 0.05) legend.push({ key: 'ce', label: 'Land running off straight to the outlet', swatch: <i className="lg-dotted" /> });
    if (zones.length) legend.push({ key: 'z', label: `Top recharge zones ${zones.map((z) => z.id).join(', ')} (darkest is best)`, swatch: (
      <span className="lg-zones">{zones.map((z) => <i key={z.id} className="lg-fill" style={{ background: ZONE_RANK_COLORS[z.rank - 1] }} />)}</span>
    ) });
  }
  if (B && tab === 'B') {
    if (zones.some((z) => z.link.geojson)) legend.push({ key: 'lk', label: 'Fault or crack linking a zone to the spring', swatch: <i className="lg-line" style={{ background: LINK }} /> });
    if (B.faults.features.length) legend.push({ key: 'f', label: 'Fault or thrust', swatch: <i className="lg-line" style={{ background: '#d1352b' }} /> });
    if (B.mapped_lineaments?.features.length) legend.push({ key: 'ml', label: 'Lineament mapped by GSI (joint, fracture, shear zone)', swatch: <i className="lg-line" style={{ background: '#b5651d' }} /> });
    if (B.lineaments.features.length) legend.push({ key: 'l', label: 'Lineament from the elevation map (possible crack line)', swatch: <i className="lg-line lg-dashed" /> });
    if (B.streams.features.length) legend.push({ key: 's', label: 'Stream', swatch: <i className="lg-line" style={{ background: '#2b7bbd' }} /> });
  }
  if (C && tab === 'C' && C.sites.length) legend.push({ key: 'fp', label: 'Assumed groundwater path from a handpump to the spring', swatch: <i className="lg-line" style={{ background: FLOW }} /> });
  if (showSites && sites.length) {
    const classes = new Set<DiSiteResult['location_class'] | null>();
    for (const s of sites) {
      const r = siteClass.get(s.id);
      classes.add(r && r.latitude === s.latitude && r.longitude === s.longitude ? r.location_class : null);
    }
    for (const c of Object.keys(locationClass) as DiSiteResult['location_class'][]) {
      if (classes.has(c)) legend.push({ key: `di-${c}`, label: `DI site: ${locationClass[c].label.toLowerCase()}`, swatch: <i className="lg-site" style={{ background: locationClass[c].color }} /> });
    }
    if (classes.has(null)) legend.push({ key: 'di-new', label: 'DI site (not assessed yet)', swatch: <i className="lg-site lg-site-new" /> });
  }
  const overlay = B?.potential_overlay ?? null;

  return (
    <div className={`map-wrap${placing !== 'none' ? ' placing' : ''}`}>
      <div ref={box} className="map" />

      <div className="map-switch" role="group" aria-label="Map view">
        <button type="button" className={`seg${threeD ? ' on' : ''}`} aria-pressed={threeD} onClick={() => setThreeD(true)}>3D</button>
        <button type="button" className={`seg${threeD ? '' : ' on'}`} aria-pressed={!threeD} onClick={() => setThreeD(false)}>2D</button>
        <select value={base} onChange={(e) => setBase(e.target.value as Base)} aria-label="Background map">
          {BASES.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
        </select>
      </div>
      {threeD && <div className="map-tip" role="status">
        <label>Hill height display <select aria-label="Hill height display" value={heightScale}
          onChange={(e) => setHeightScale(Number(e.target.value))}>
          <option value="1">True scale (1×)</option>
          <option value="1.5">1.5×</option>
          <option value="3">Stronger relief (3×)</option>
        </select></label>
        <div>{terrainState === 'ready' ? 'Elevation tiles loaded. Right-drag (or Ctrl + drag) to tilt and turn.'
          : terrainState === 'error' ? 'Some hill heights could not load. Refresh to retry.' : 'Loading hill heights…'}</div>
        {heightScale !== 1 && <div>Heights are visually enlarged; assessment calculations are unchanged.</div>}
      </div>}

      {placing !== 'none' && (
        <div className={`map-hint${props.canCancel ? '' : ' map-hint-soft'}`} role="status">
          <span>
            {placing === 'site' ? 'Click on the map where the defunct handpump is.'
              : props.canCancel ? 'Click on the map where the spring comes out.'
              : 'Click the map where the spring comes out, click a teal dot, or search on the left.'}
          </span>
          {props.canCancel && <button type="button" className="btn btn-small" onClick={props.onCancelPlacing}>Cancel</button>}
        </div>
      )}
      {tilesFailed && (
        <div className="map-note" role="status">The map background could not load (no internet?). The hills are still drawn from the elevation map, with your spring and the results on top.</div>
      )}

      <div className="map-legend" aria-label="Map legend">
        <details open={legendOpen} onToggle={(e) => setLegendOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Legend</summary>
          <ul>
            {legend.map((l) => <li key={l.key}>{l.swatch}<span>{l.label}</span></li>)}
          </ul>
          {overlay && tab === 'B' && (
            <div className="heat-ctl">
              <label className="check">
                <input type="checkbox" checked={heatOn} onChange={(e) => setHeatOn(e.target.checked)} />
                Recharge potential heat map
              </label>
              {heatOn && (
                <>
                  <label className="slider-row">
                    <span>See-through</span>
                    <input type="range" min={0.1} max={1} step={0.05} value={heatOpacity} onChange={(e) => setHeatOpacity(Number(e.target.value))} aria-label="Heat map opacity" />
                  </label>
                  <div className="heat-legend">
                    {overlay.legend.map((l) => <span key={l.label}><i style={{ background: l.color }} />{l.label}</span>)}
                  </div>
                </>
              )}
            </div>
          )}
        </details>
      </div>
    </div>
  );
}
