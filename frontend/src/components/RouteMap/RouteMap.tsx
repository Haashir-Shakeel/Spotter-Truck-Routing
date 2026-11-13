import type { Point } from 'geojson'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  corridorCenterLatitude,
  type CorridorProps,
  corridorFeatures,
  hourProperty,
  pixelsPerMile,
  UNAVAILABLE_VALUE,
} from '../../lib/corridor'
import { boundsOf } from '../../lib/geometry'
import {
  type ExpressionSpecification,
  type GeoJSONSource,
  MapLibreMap,
  type MapMouseEvent,
  NavigationControl,
} from '../../lib/maplibre'
import { checkpointPoints, emptyCollection, riskSegments, routeBadges, routeLines } from '../../lib/mapData'
import { RISK_ORDER, RISK_STYLE } from '../../lib/risk'
import type { CorridorForecast, LngLat, RouteResult } from '../../types/trip'

const MAP_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/liberty'

// Continental US default view until a trip is analyzed.
const DEFAULT_CENTER: [number, number] = [-96, 38.5]
const DEFAULT_ZOOM = 3.6
// Heatmap kernels stop growing past this zoom; sample dots carry the detail when zoomed in.
const HEAT_MAX_ZOOM = 9
// Calibrated so a uniform area of one level reaches density ≈ level / 4 (see lib/corridor.ts).
const HEAT_INTENSITY = 1.2
const FIT_BOTTOM_PADDING_DESKTOP = 230

const SOURCES = {
  corridor: 'corridor',
  routes: 'routes',
  segments: 'risk-segments',
  checkpoints: 'checkpoints',
  badges: 'route-badges',
  truck: 'truck',
} as const
const LAYERS = {
  corridorHeat: 'corridor-heat',
  corridorSamples: 'corridor-samples',
  routes: 'route-lines',
  segments: 'risk-segments',
  checkpoints: 'checkpoints',
  badges: 'route-badges',
  badgeLabels: 'route-badge-labels',
  truck: 'truck',
} as const
const CORRIDOR_LAYERS = [LAYERS.corridorHeat, LAYERS.corridorSamples]

const riskColor: ExpressionSpecification = [
  'match',
  ['get', 'risk'],
  'LOW',
  RISK_STYLE.LOW.color,
  'MODERATE',
  RISK_STYLE.MODERATE.color,
  'HIGH',
  RISK_STYLE.HIGH.color,
  'SEVERE',
  RISK_STYLE.SEVERE.color,
  'NO_TRAVEL',
  RISK_STYLE.NO_TRAVEL.color,
  RISK_STYLE.UNAVAILABLE.color,
]

const withAlpha = (hex: string, alpha: number) => {
  const n = Number.parseInt(hex.slice(1), 16)
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

// Density ≈ level / 4 in a uniform area, so the ramp stops line up with the risk levels.
const HEAT_COLOR: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0,
  'rgba(0, 0, 0, 0)',
  0.1,
  withAlpha(RISK_STYLE.MODERATE.color, 0),
  0.25,
  withAlpha(RISK_STYLE.MODERATE.color, 0.75),
  0.5,
  withAlpha(RISK_STYLE.HIGH.color, 0.85),
  0.75,
  withAlpha(RISK_STYLE.SEVERE.color, 0.9),
  1,
  withAlpha(RISK_STYLE.NO_TRAVEL.color, 0.95),
]

// --- per-hour expressions: the slider only swaps which `h<N>` property these read -------------

const hourValue = (hour: number): ExpressionSpecification => ['get', hourProperty(hour)]

const heatWeight = (hour: number): ExpressionSpecification => [
  '/',
  ['max', 0, hourValue(hour)],
  RISK_ORDER.length - 1,
]

const sampleColor = (hour: number): ExpressionSpecification => [
  'match',
  hourValue(hour),
  ...RISK_ORDER.flatMap((level, i) => [i, RISK_STYLE[level].color]),
  RISK_STYLE.UNAVAILABLE.color,
] as ExpressionSpecification

const sampleRadius = (hour: number): ExpressionSpecification => [
  'case',
  ['>=', hourValue(hour), 3],
  5.5,
  ['>=', hourValue(hour), 1],
  3.5,
  ['==', hourValue(hour), UNAVAILABLE_VALUE],
  3,
  2,
]

const heatRadius = (spacingMiles: number, latitude: number): ExpressionSpecification => [
  'interpolate',
  ['exponential', 2],
  ['zoom'],
  0,
  spacingMiles * pixelsPerMile(0, latitude),
  HEAT_MAX_ZOOM,
  spacingMiles * pixelsPerMile(HEAT_MAX_ZOOM, latitude),
]

function addLayers(map: MapLibreMap) {
  for (const id of Object.values(SOURCES)) map.addSource(id, { type: 'geojson', data: emptyCollection() })

  // Corridor forecast sits under the routes so route identity and ETA risk stay on top.
  map.addLayer({
    id: LAYERS.corridorHeat,
    type: 'heatmap',
    source: SOURCES.corridor,
    paint: {
      'heatmap-weight': heatWeight(0),
      'heatmap-intensity': HEAT_INTENSITY,
      'heatmap-radius': 20,
      'heatmap-color': HEAT_COLOR,
      'heatmap-opacity': 0.7,
    },
  })
  map.addLayer({
    id: LAYERS.corridorSamples,
    type: 'circle',
    source: SOURCES.corridor,
    paint: {
      'circle-radius': sampleRadius(0),
      'circle-color': sampleColor(0),
      'circle-opacity': 0.75,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 0.5,
    },
  })

  // Route identity: neutral slate lines (never risk colors). The selected route is a dark casing.
  map.addLayer({
    id: LAYERS.routes,
    type: 'line',
    source: SOURCES.routes,
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
      'line-sort-key': ['case', ['get', 'selected'], 1, 0],
    },
    paint: {
      'line-color': ['case', ['get', 'selected'], '#0f172a', '#64748b'],
      'line-width': ['case', ['get', 'selected'], 11, 5],
      'line-opacity': ['case', ['get', 'selected'], 1, 0.6],
    },
  })
  map.addLayer({
    id: LAYERS.segments,
    type: 'line',
    source: SOURCES.segments,
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: { 'line-color': riskColor, 'line-width': 6 },
  })
  map.addLayer({
    id: LAYERS.checkpoints,
    type: 'circle',
    source: SOURCES.checkpoints,
    paint: {
      'circle-radius': ['case', ['get', 'selected'], 9, 6],
      'circle-color': riskColor,
      'circle-stroke-color': ['case', ['get', 'selected'], '#0f172a', '#ffffff'],
      'circle-stroke-width': ['case', ['get', 'selected'], 3, 2],
    },
  })
  map.addLayer({
    id: LAYERS.badges,
    type: 'circle',
    source: SOURCES.badges,
    paint: {
      'circle-radius': 11,
      'circle-color': ['case', ['get', 'selected'], '#0f172a', '#ffffff'],
      'circle-stroke-color': '#0f172a',
      'circle-stroke-width': 2,
    },
  })
  map.addLayer({
    id: LAYERS.badgeLabels,
    type: 'symbol',
    source: SOURCES.badges,
    layout: {
      'text-field': ['get', 'id'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 13,
      // Always draw: basemap labels must never hide which line is which route.
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: { 'text-color': ['case', ['get', 'selected'], '#ffffff', '#0f172a'] },
  })
  map.addLayer({
    id: LAYERS.truck,
    type: 'circle',
    source: SOURCES.truck,
    paint: {
      'circle-radius': 8,
      'circle-color': '#2563eb',
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 3,
    },
  })
}

interface RouteMapProps {
  routes: RouteResult[]
  selectedRouteId: string | null
  recommendedRouteId: string | null
  selectedCheckpointIndex: number | null
  onSelectRoute: (routeId: string) => void
  onSelectCheckpoint: (index: number) => void
  corridor?: CorridorForecast | null
  corridorHour?: number
  showCorridor?: boolean
  /** Selected route's truck position at the corridor hour. */
  truck?: LngLat | null
}

export function RouteMap({
  routes,
  selectedRouteId,
  recommendedRouteId,
  selectedCheckpointIndex,
  onSelectRoute,
  onSelectCheckpoint,
  corridor = null,
  corridorHour = 0,
  showCorridor = true,
  truck = null,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  // Latest callbacks, so map event handlers registered once never go stale.
  const handlers = useRef({ onSelectRoute, onSelectCheckpoint })
  useEffect(() => {
    handlers.current = { onSelectRoute, onSelectCheckpoint }
  }, [onSelectRoute, onSelectCheckpoint])

  useEffect(() => {
    if (!containerRef.current) return
    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    })
    mapRef.current = map
    map.addControl(new NavigationControl(), 'top-right')

    map.on('load', () => {
      addLayers(map)
      setReady(true)
    })

    const interactive = [LAYERS.checkpoints, LAYERS.badges, LAYERS.routes]
    map.on('click', (event: MapMouseEvent) => {
      const [hit] = map.queryRenderedFeatures(event.point, { layers: interactive })
      if (!hit) return
      if (hit.layer.id === LAYERS.checkpoints) handlers.current.onSelectCheckpoint(Number(hit.properties.index))
      else handlers.current.onSelectRoute(String(hit.properties.id))
    })
    for (const layer of interactive) {
      map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
    }

    return () => {
      mapRef.current = null
      map.remove()
    }
  }, [])

  const selectedRoute = routes.find((r) => r.id === selectedRouteId)

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    ;(map.getSource(SOURCES.routes) as GeoJSONSource).setData(
      routeLines(routes, selectedRouteId, recommendedRouteId),
    )
    ;(map.getSource(SOURCES.badges) as GeoJSONSource).setData(routeBadges(routes, selectedRouteId))
    ;(map.getSource(SOURCES.segments) as GeoJSONSource).setData(riskSegments(selectedRoute))
    ;(map.getSource(SOURCES.checkpoints) as GeoJSONSource).setData(
      checkpointPoints(selectedRoute, selectedCheckpointIndex),
    )
  }, [ready, routes, selectedRoute, selectedRouteId, recommendedRouteId, selectedCheckpointIndex])

  // Fit the view only when a new set of routes arrives, not on every selection change.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const bounds = boundsOf(routes.map((r) => r.geometry.coordinates))
    // On desktop the forecast timeline overlays the bottom of the map; keep routes clear of it.
    const bottom = window.matchMedia('(min-width: 1024px)').matches ? FIT_BOTTOM_PADDING_DESKTOP : 48
    if (bounds) map.fitBounds(bounds, { padding: { top: 48, left: 48, right: 48, bottom }, duration: 600 })
  }, [ready, routes])

  // Corridor data is uploaded once per forecast; every hour lives in the feature properties.
  const corridorData = useMemo(() => (corridor ? corridorFeatures(corridor) : emptyCollection<Point, CorridorProps>()), [corridor])
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    ;(map.getSource(SOURCES.corridor) as GeoJSONSource).setData(corridorData)
    if (corridor) {
      map.setPaintProperty(
        LAYERS.corridorHeat,
        'heatmap-radius',
        heatRadius(corridor.spacing_miles, corridorCenterLatitude(corridor)),
      )
    }
  }, [ready, corridor, corridorData])

  // Slider movement: swap the hour the layers read. No data upload, no refetch.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    map.setPaintProperty(LAYERS.corridorHeat, 'heatmap-weight', heatWeight(corridorHour))
    map.setPaintProperty(LAYERS.corridorSamples, 'circle-color', sampleColor(corridorHour))
    map.setPaintProperty(LAYERS.corridorSamples, 'circle-radius', sampleRadius(corridorHour))
  }, [ready, corridorHour])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    for (const layer of CORRIDOR_LAYERS) {
      map.setLayoutProperty(layer, 'visibility', showCorridor ? 'visible' : 'none')
    }
  }, [ready, showCorridor])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    ;(map.getSource(SOURCES.truck) as GeoJSONSource).setData(
      truck
        ? {
            type: 'FeatureCollection',
            features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: truck }, properties: {} }],
          }
        : emptyCollection(),
    )
  }, [ready, truck])

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      data-testid="route-map"
      role="region"
      aria-label="Map of route alternatives, weather checkpoints and corridor forecast"
    />
  )
}
