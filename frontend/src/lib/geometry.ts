import type { LngLat } from '../types/trip'

const EARTH_RADIUS_MILES = 3958.7613
const toRad = (deg: number) => (deg * Math.PI) / 180

export function haversineMiles([lon1, lat1]: LngLat, [lon2, lat2]: LngLat): number {
  const h =
    Math.sin(toRad(lat2 - lat1) / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(toRad(lon2 - lon1) / 2) ** 2
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** Distance from the first vertex to each vertex, optionally scaled to a known road distance. */
export function cumulativeMiles(coords: LngLat[], totalMiles?: number): number[] {
  const cumulative = [0]
  for (let i = 1; i < coords.length; i++) {
    cumulative.push(cumulative[i - 1] + haversineMiles(coords[i - 1], coords[i]))
  }
  const geometryMiles = cumulative[cumulative.length - 1]
  if (totalMiles === undefined || geometryMiles === 0) return cumulative
  const scale = totalMiles / geometryMiles
  return cumulative.map((d) => d * scale)
}

function segmentIndex(cumulative: number[], target: number): number {
  let lo = 0
  let hi = cumulative.length - 2
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (cumulative[mid] <= target) lo = mid
    else hi = mid - 1
  }
  return lo
}

export function pointAtDistance(coords: LngLat[], cumulative: number[], target: number): LngLat {
  const i = segmentIndex(cumulative, target)
  const length = cumulative[i + 1] - cumulative[i]
  const t = length > 0 ? Math.min(Math.max((target - cumulative[i]) / length, 0), 1) : 0
  const [lon1, lat1] = coords[i]
  const [lon2, lat2] = coords[i + 1]
  return [lon1 + t * (lon2 - lon1), lat1 + t * (lat2 - lat1)]
}

/** The part of a polyline between two along-route distances, following every vertex in between. */
export function sliceLine(coords: LngLat[], cumulative: number[], from: number, to: number): LngLat[] {
  const line: LngLat[] = [pointAtDistance(coords, cumulative, from)]
  for (let i = 0; i < coords.length; i++) {
    if (cumulative[i] > from && cumulative[i] < to) line.push(coords[i])
  }
  line.push(pointAtDistance(coords, cumulative, to))
  return line
}

export function boundsOf(lines: LngLat[][]): [LngLat, LngLat] | null {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity
  for (const line of lines) {
    for (const [lon, lat] of line) {
      minLon = Math.min(minLon, lon)
      minLat = Math.min(minLat, lat)
      maxLon = Math.max(maxLon, lon)
      maxLat = Math.max(maxLat, lat)
    }
  }
  return Number.isFinite(minLon) ? [[minLon, minLat], [maxLon, maxLat]] : null
}
