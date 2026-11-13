/** Mirrors the backend contract for POST /api/v1/trips/analyze/ and GET /api/v1/trips/{id}/. */

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL'
export type CheckpointInterval = 10 | 25 | 50
export type LngLat = [number, number]

export interface LocationInput {
  name: string
  lon?: number
  lat?: number
}

export interface Place {
  name: string
  lon: number
  lat: number
}

export interface TripAnalyzeRequest {
  origin: LocationInput
  destination: LocationInput
  departure_at: string // ISO 8601 with UTC offset
  load_weight_lb: number
  checkpoint_interval_miles: CheckpointInterval
}

export interface CheckpointWeather {
  wind_mph: number
  rain_in_per_hour: number
  snow_in_per_hour: number
}

export interface Checkpoint {
  index: number
  lon: number
  lat: number
  distance_miles: number
  elapsed_seconds: number
  arrival_at: string
  weather: CheckpointWeather | null
  risk: RiskLevel | null
  risk_detail: { wind: RiskLevel; rain: RiskLevel; snow: RiskLevel } | null
  load_override: string | null
}

export interface RiskSummary {
  low_miles: number
  moderate_miles: number
  high_miles: number
  severe_miles: number
  no_travel_miles: number
  unavailable_miles: number
  average_risk: number
  max_risk: RiskLevel | null
  complete: boolean
}

export interface RouteResult {
  id: string
  label: string
  geometry: { type: 'LineString'; coordinates: LngLat[] }
  distance_miles: number
  duration_seconds: number
  arrival_at: string
  eta_method: 'segment_durations' | 'proportional'
  risk_summary: RiskSummary
  checkpoints: Checkpoint[]
}

export type IneligibilityReason = 'no_travel' | 'incomplete_forecast'

export interface Recommendation {
  status: 'route_available' | 'no_safe_route'
  recommended_route_id: string | null
  ranked_route_ids: string[]
  ineligible: Record<string, IneligibilityReason>
  explanation: string
}

export interface AnalysisWarning {
  code: string
  message: string
}

export interface TripAnalysis {
  analysis_id: string
  status: 'complete'
  generated_at: string
  departure_at: string
  load_weight_lb: number
  checkpoint_interval_miles: CheckpointInterval
  origin: Place
  destination: Place
  recommendation: Recommendation
  routes: RouteResult[]
  warnings: AnalysisWarning[]
}

/** GET /api/v1/trips/{id}/corridor-forecast/: risk across the corridor for each forecast hour. */
export interface CorridorForecast {
  analysis_id: string
  start_at: string // departure, floored to the hour (UTC)
  hour_count: number // 49: hours 0..48
  spacing_miles: number
  buffer_miles: number
  levels: RiskLevel[] // index -> level name
  points: LngLat[]
  /** risk[hour][point]: index into `levels`, or null when the forecast is unavailable */
  risk: (number | null)[][]
}
