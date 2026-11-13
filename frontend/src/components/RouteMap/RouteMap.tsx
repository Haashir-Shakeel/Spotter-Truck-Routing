import { useEffect, useRef, useState } from 'react'
import { boundsOf } from '../../lib/geometry'
import {
  type ExpressionSpecification,
  type GeoJSONSource,
  MapLibreMap,
  type MapMouseEvent,
  NavigationControl,
} from '../../lib/maplibre'
import { checkpointPoints, emptyCollection, riskSegments, routeLines } from '../../lib/mapData'
import { RISK_STYLE } from '../../lib/risk'
import type { RouteResult } from '../../types/trip'

const MAP_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/liberty'

// Continental US default view until a trip is analyzed.
const DEFAULT_CENTER: [number, number] = [-96, 38.5]
const DEFAULT_ZOOM = 3.6

const SOURCES = { routes: 'routes', segments: 'risk-segments', checkpoints: 'checkpoints' } as const
const LAYERS = {
  routes: 'route-lines',
  routeLabels: 'route-labels',
  segments: 'risk-segments',
  checkpoints: 'checkpoints',
} as const

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

function addLayers(map: MapLibreMap) {
  map.addSource(SOURCES.routes, { type: 'geojson', data: emptyCollection() })
  map.addSource(SOURCES.segments, { type: 'geojson', data: emptyCollection() })
  map.addSource(SOURCES.checkpoints, { type: 'geojson', data: emptyCollection() })

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
    id: LAYERS.routeLabels,
    type: 'symbol',
    source: SOURCES.routes,
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'label'],
      'text-font': ['Noto Sans Regular'],
      'text-size': 12,
      'symbol-spacing': 400,
    },
    paint: { 'text-color': '#0f172a', 'text-halo-color': '#ffffff', 'text-halo-width': 2 },
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
}

interface RouteMapProps {
  routes: RouteResult[]
  selectedRouteId: string | null
  recommendedRouteId: string | null
  selectedCheckpointIndex: number | null
  onSelectRoute: (routeId: string) => void
  onSelectCheckpoint: (index: number) => void
}

export function RouteMap({
  routes,
  selectedRouteId,
  recommendedRouteId,
  selectedCheckpointIndex,
  onSelectRoute,
  onSelectCheckpoint,
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

    const interactive = [LAYERS.checkpoints, LAYERS.routes]
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
    if (bounds) map.fitBounds(bounds, { padding: 48, duration: 600 })
  }, [ready, routes])

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      data-testid="route-map"
      role="region"
      aria-label="Map of route alternatives and weather checkpoints"
    />
  )
}
