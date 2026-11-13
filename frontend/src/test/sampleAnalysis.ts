/** SAMPLE response for tests only. Not real route or weather data. */
import type { Checkpoint, CorridorForecast, RiskLevel, RouteResult, TripAnalysis } from '../types/trip'

function checkpoint(index: number, miles: number, risk: RiskLevel | null, lon: number): Checkpoint {
  return {
    index,
    lon,
    lat: 40,
    distance_miles: miles,
    elapsed_seconds: miles * 60,
    arrival_at: new Date(Date.UTC(2026, 10, 13, 13, 0) + miles * 60_000).toISOString(),
    weather: risk
      ? { wind_mph: risk === 'NO_TRAVEL' ? 60 : 10, rain_in_per_hour: 0, snow_in_per_hour: 0 }
      : null,
    risk,
    risk_detail: risk ? { wind: risk, rain: 'LOW', snow: 'LOW' } : null,
    load_override: null,
  }
}

function route(
  id: string,
  risks: (RiskLevel | null)[],
  summary: Partial<RouteResult['risk_summary']>,
): RouteResult {
  return {
    id,
    label: `Route ${id}`,
    source: 'provider',
    geometry: {
      type: 'LineString',
      coordinates: [
        [-90, 40],
        [-89, 40],
        [-88, 40],
      ],
    },
    distance_miles: 50,
    duration_seconds: 3000,
    arrival_at: '2026-11-13T13:50:00Z',
    eta_method: 'segment_durations',
    risk_summary: {
      low_miles: 50,
      moderate_miles: 0,
      high_miles: 0,
      severe_miles: 0,
      no_travel_miles: 0,
      unavailable_miles: 0,
      average_risk: 0,
      max_risk: 'LOW',
      complete: true,
      ...summary,
    },
    checkpoints: risks.map((risk, i) => checkpoint(i, i * 25, risk, -90 + i)),
  }
}

export const sampleAnalysis: TripAnalysis = {
  analysis_id: '00000000-0000-0000-0000-000000000001',
  status: 'complete',
  weather_source: 'live',
  generated_at: '2026-11-13T12:00:00Z',
  departure_at: '2026-11-13T13:00:00Z',
  load_weight_lb: 35000,
  checkpoint_interval_miles: 25,
  origin: { name: 'Origin City', lon: -90, lat: 40, timezone: 'America/Chicago' },
  destination: { name: 'Destination City', lon: -88, lat: 40, timezone: 'America/Chicago' },
  recommendation: {
    status: 'route_available',
    recommended_route_id: 'B',
    ranked_route_ids: ['B', 'A'],
    ineligible: { A: 'no_travel' },
    explanation:
      'Route B is recommended with 0.0 Severe and 0.0 High-risk miles. Route A was excluded: 25.0 No Travel miles.',
  },
  routes: [
    route('A', ['LOW', 'NO_TRAVEL', 'LOW'], {
      low_miles: 0,
      no_travel_miles: 50,
      max_risk: 'NO_TRAVEL',
      average_risk: 4,
    }),
    route('B', ['LOW', 'LOW', null], { low_miles: 25, unavailable_miles: 25, complete: false }),
  ],
  warnings: [
    { code: 'FEWER_ROUTES', message: 'The routing service returned 2 distinct routes for this trip, not 3.' },
  ],
}

/** SAMPLE corridor: 3 points x 3 hours. Hour 1 mixes levels and a gap; hour 2 has no data. */
export const sampleCorridor: CorridorForecast = {
  analysis_id: sampleAnalysis.analysis_id,
  start_at: '2026-11-13T13:00:00+00:00',
  hour_count: 3,
  spacing_miles: 15,
  buffer_miles: 20,
  levels: ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL'],
  points: [
    [-90, 40],
    [-89, 40],
    [-88, 40],
  ],
  risk: [
    [0, 0, 0],
    [1, 3, null],
    [null, null, null],
  ],
}
