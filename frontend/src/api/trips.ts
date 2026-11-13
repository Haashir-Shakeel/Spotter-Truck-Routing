import type { CorridorForecast, Place, TripAnalysis, TripAnalyzeRequest } from '../types/trip'
import { apiRequest } from './client'

export function analyzeTrip(request: TripAnalyzeRequest, signal?: AbortSignal): Promise<TripAnalysis> {
  return apiRequest<TripAnalysis>('/api/v1/trips/analyze/', {
    method: 'POST',
    body: JSON.stringify(request),
    signal,
  })
}

export function getTrip(analysisId: string, signal?: AbortSignal): Promise<TripAnalysis> {
  return apiRequest<TripAnalysis>(`/api/v1/trips/${encodeURIComponent(analysisId)}/`, { signal })
}

export function getCorridorForecast(analysisId: string, signal?: AbortSignal): Promise<CorridorForecast> {
  return apiRequest<CorridorForecast>(
    `/api/v1/trips/${encodeURIComponent(analysisId)}/corridor-forecast/`,
    { signal },
  )
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const params = new URLSearchParams({ q: query, limit: '5' })
  const body = await apiRequest<{ results: Place[] }>(`/api/v1/places/?${params}`, { signal })
  return body.results
}
