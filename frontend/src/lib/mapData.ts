/** Pure builders for the GeoJSON the map renders. Kept out of React so they are cheap to test. */
import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { RouteResult } from '../types/trip'
import { cumulativeMiles, sliceLine } from './geometry'
import { type RiskOrUnavailable, segmentRisk } from './risk'

export interface RouteLineProps {
  id: string
  label: string
  selected: boolean
  recommended: boolean
}

export interface RiskSegmentProps {
  risk: RiskOrUnavailable
}

export interface CheckpointProps {
  index: number
  risk: RiskOrUnavailable
  selected: boolean
}

const EMPTY = { type: 'FeatureCollection', features: [] } as const

export function emptyCollection<G extends LineString | Point, P>(): FeatureCollection<G, P> {
  return { ...EMPTY, features: [] }
}

export function routeLines(
  routes: RouteResult[],
  selectedId: string | null,
  recommendedId: string | null,
): FeatureCollection<LineString, RouteLineProps> {
  return {
    type: 'FeatureCollection',
    features: routes.map((route) => ({
      type: 'Feature',
      geometry: route.geometry,
      properties: {
        id: route.id,
        label: route.label,
        selected: route.id === selectedId,
        recommended: route.id === recommendedId,
      },
    })),
  }
}

/** The selected route split at its checkpoints, each stretch colored by its assigned risk. */
export function riskSegments(route: RouteResult | undefined): FeatureCollection<LineString, RiskSegmentProps> {
  if (!route || route.checkpoints.length < 2) return emptyCollection()
  const coords = route.geometry.coordinates
  const cumulative = cumulativeMiles(coords, route.distance_miles)

  const features: Feature<LineString, RiskSegmentProps>[] = []
  for (let i = 0; i < route.checkpoints.length - 1; i++) {
    const start = route.checkpoints[i]
    const end = route.checkpoints[i + 1]
    features.push({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: sliceLine(coords, cumulative, start.distance_miles, end.distance_miles),
      },
      properties: { risk: segmentRisk(start.risk, end.risk) },
    })
  }
  return { type: 'FeatureCollection', features }
}

export function checkpointPoints(
  route: RouteResult | undefined,
  selectedIndex: number | null,
): FeatureCollection<Point, CheckpointProps> {
  if (!route) return emptyCollection()
  return {
    type: 'FeatureCollection',
    features: route.checkpoints.map((cp) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [cp.lon, cp.lat] },
      properties: { index: cp.index, risk: cp.risk ?? 'UNAVAILABLE', selected: cp.index === selectedIndex },
    })),
  }
}
