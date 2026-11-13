import { useCallback, useEffect, useRef, useState } from 'react'
import { analyzeTrip } from '../api/trips'
import { describeError } from '../lib/errors'
import type { TripAnalysis, TripAnalyzeRequest } from '../types/trip'

export interface TripAnalysisState {
  status: 'idle' | 'loading' | 'success' | 'error'
  /** Last successful analysis; kept while a new one loads so the map doesn't go blank. */
  data: TripAnalysis | null
  error: string | null
}

export function useTripAnalysis() {
  const [state, setState] = useState<TripAnalysisState>({ status: 'idle', data: null, error: null })
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const analyze = useCallback(async (request: TripAnalyzeRequest): Promise<TripAnalysis | null> => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setState((prev) => ({ ...prev, status: 'loading', error: null }))

    try {
      const data = await analyzeTrip(request, controller.signal)
      if (controller.signal.aborted) return null
      setState({ status: 'success', data, error: null })
      return data
    } catch (error) {
      if (controller.signal.aborted) return null
      setState((prev) => ({ ...prev, status: 'error', error: describeError(error) }))
      return null
    }
  }, [])

  return { state, analyze }
}
