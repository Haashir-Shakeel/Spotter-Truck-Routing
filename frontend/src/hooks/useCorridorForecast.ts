import { useCallback, useEffect, useState } from 'react'
import { getCorridorForecast } from '../api/trips'
import { describeError } from '../lib/errors'
import type { CorridorForecast } from '../types/trip'

export interface CorridorState {
  status: 'idle' | 'loading' | 'success' | 'error'
  data: CorridorForecast | null
  error: string | null
}

const IDLE: CorridorState = { status: 'idle', data: null, error: null }

/**
 * Loads the corridor forecast once per analysis, after the route analysis has rendered, so the
 * main result never waits on it. The slider then works entirely on this one response.
 */
export function useCorridorForecast(analysisId: string | null) {
  const [state, setState] = useState<CorridorState>(IDLE)
  const [attempt, setAttempt] = useState(0)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)

  // Reset during render when the analysis changes, so an old corridor is never drawn over new routes.
  if (loadedFor !== analysisId) {
    setLoadedFor(analysisId)
    setState(analysisId ? { status: 'loading', data: null, error: null } : IDLE)
  }

  useEffect(() => {
    if (!analysisId) return
    const controller = new AbortController()
    getCorridorForecast(analysisId, controller.signal)
      .then((data) => setState({ status: 'success', data, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ status: 'error', data: null, error: describeError(error) })
      })
    return () => controller.abort()
  }, [analysisId, attempt])

  const retry = useCallback(() => {
    setState({ status: 'loading', data: null, error: null })
    setAttempt((n) => n + 1)
  }, [])

  return { state, retry }
}
