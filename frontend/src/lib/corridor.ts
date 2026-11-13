/**
 * Pure helpers for the corridor forecast (0-48 h slider).
 *
 * The GeoJSON is built once per forecast with every hour stored as a feature property
 * (`h0`..`h48`). Moving the slider only swaps which property the map layers read, so dragging
 * never refetches, re-uploads data, or rebuilds features.
 */
import type { FeatureCollection, Point } from 'geojson'
import type { CorridorForecast, LngLat, RiskLevel, RouteResult } from '../types/trip'
import { cumulativeMiles, pointAtDistance } from './geometry'
import { RISK_ORDER, type RiskOrUnavailable } from './risk'

/** Stored in place of null so map expressions stay numeric. */
export const UNAVAILABLE_VALUE = -1
const EQUATOR_MILES = 24901.46
const TILE_SIZE = 512
const HOUR_MS = 3_600_000

export type CorridorProps = Record<string, number>

export const hourProperty = (hour: number) => `h${hour}`

export function corridorFeatures(forecast: CorridorForecast): FeatureCollection<Point, CorridorProps> {
  return {
    type: 'FeatureCollection',
    features: forecast.points.map((coordinates, point) => {
      const properties: CorridorProps = {}
      forecast.risk.forEach((hour, h) => {
        properties[hourProperty(h)] = hour[point] ?? UNAVAILABLE_VALUE
      })
      return { type: 'Feature', geometry: { type: 'Point', coordinates }, properties }
    }),
  }
}

export function levelName(forecast: CorridorForecast, value: number | null): RiskOrUnavailable {
  if (value === null || value === UNAVAILABLE_VALUE) return 'UNAVAILABLE'
  return forecast.levels[value] ?? 'UNAVAILABLE'
}

export interface HourSummary {
  counts: Record<RiskOrUnavailable, number>
  /** Worst level among points that have data, or null when no point has data this hour. */
  worst: RiskLevel | null
  total: number
}

export function summarizeHour(forecast: CorridorForecast, hour: number): HourSummary {
  const counts: Record<RiskOrUnavailable, number> = {
    LOW: 0,
    MODERATE: 0,
    HIGH: 0,
    SEVERE: 0,
    NO_TRAVEL: 0,
    UNAVAILABLE: 0,
  }
  let worst: RiskLevel | null = null
  for (const value of forecast.risk[hour] ?? []) {
    const level = levelName(forecast, value)
    counts[level] += 1
    if (level !== 'UNAVAILABLE' && (worst === null || RISK_ORDER.indexOf(level) > RISK_ORDER.indexOf(worst))) {
      worst = level
    }
  }
  return { counts, worst, total: forecast.points.length }
}

/** Worst corridor level for every hour, for the strip above the slider. */
export function hourlyWorst(forecast: CorridorForecast): (RiskLevel | null)[] {
  return forecast.risk.map((_, hour) => summarizeHour(forecast, hour).worst)
}

export function hourTime(forecast: CorridorForecast, hour: number): Date {
  return new Date(new Date(forecast.start_at).getTime() + hour * HOUR_MS)
}

/**
 * Map pixels per ground mile at a zoom and latitude (Web Mercator, 512 px tiles). Used to size
 * the heatmap kernel to the grid spacing: with radius = spacing, overlapping kernels on the
 * regular grid sum to an even density, so colour reflects risk rather than sample count.
 */
export function pixelsPerMile(zoom: number, latitude: number): number {
  return (TILE_SIZE * 2 ** zoom) / (EQUATOR_MILES * Math.cos((latitude * Math.PI) / 180))
}

export function corridorCenterLatitude(forecast: CorridorForecast): number {
  if (forecast.points.length === 0) return 0
  return forecast.points.reduce((sum, [, lat]) => sum + lat, 0) / forecast.points.length
}

export type TruckStatus = 'not_departed' | 'en_route' | 'arrived'

export interface TruckPosition {
  status: TruckStatus
  lngLat: LngLat
  distanceMiles: number
}

/** Where the truck is on `route` at `when`, from the checkpoint ETAs (same timing as the risk). */
export function truckPositionAt(route: RouteResult, departureIso: string, when: Date): TruckPosition | null {
  const checkpoints = route.checkpoints
  if (checkpoints.length === 0) return null
  const first = checkpoints[0]
  const last = checkpoints[checkpoints.length - 1]
  const elapsed = (when.getTime() - new Date(departureIso).getTime()) / 1000

  if (elapsed < 0) return { status: 'not_departed', lngLat: [first.lon, first.lat], distanceMiles: 0 }
  if (elapsed >= last.elapsed_seconds) {
    return { status: 'arrived', lngLat: [last.lon, last.lat], distanceMiles: last.distance_miles }
  }

  let i = 0
  while (i < checkpoints.length - 2 && checkpoints[i + 1].elapsed_seconds <= elapsed) i++
  const a = checkpoints[i]
  const b = checkpoints[i + 1]
  const span = b.elapsed_seconds - a.elapsed_seconds
  const t = span > 0 ? (elapsed - a.elapsed_seconds) / span : 0
  const distanceMiles = a.distance_miles + t * (b.distance_miles - a.distance_miles)
  const coords = route.geometry.coordinates
  const lngLat = pointAtDistance(coords, cumulativeMiles(coords, route.distance_miles), distanceMiles)
  return { status: 'en_route', lngLat, distanceMiles }
}
