import { memo, useCallback, useMemo, useState } from 'react'
import { AnalysisWarnings } from './components/AnalysisWarnings/AnalysisWarnings'
import { CheckpointDetails } from './components/CheckpointDetails/CheckpointDetails'
import { ForecastTimeline } from './components/ForecastTimeline/ForecastTimeline'
import { RiskLegend } from './components/RiskLegend/RiskLegend'
import { RouteComparison } from './components/RouteCard/RouteComparison'
import { RouteMap } from './components/RouteMap/RouteMap'
import { TripForm } from './components/TripForm/TripForm'
import { type ApiHealth, useApiHealth } from './hooks/useApiHealth'
import { useCorridorForecast } from './hooks/useCorridorForecast'
import { useTripAnalysis } from './hooks/useTripAnalysis'
import { hourTime, truckPositionAt } from './lib/corridor'
import type { TripAnalyzeRequest } from './types/trip'

const HEALTH_LABEL: Record<ApiHealth, string> = {
  checking: 'Checking API…',
  online: 'API online',
  offline: 'API offline',
}

const HEALTH_DOT: Record<ApiHealth, string> = {
  checking: 'bg-slate-400',
  online: 'bg-emerald-500',
  offline: 'bg-red-500',
}

const HOUR_MS = 3_600_000

// The side panels don't depend on the forecast hour, so slider movement skips re-rendering them.
const MemoRouteComparison = memo(RouteComparison)
const MemoCheckpointDetails = memo(CheckpointDetails)
const MemoWarnings = memo(AnalysisWarnings)

function App() {
  const health = useApiHealth()
  const { state, analyze } = useTripAnalysis()
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<number | null>(null)
  const [forecastHour, setForecastHour] = useState(0)
  const [showCorridor, setShowCorridor] = useState(true)

  const analysis = state.data
  const routes = useMemo(() => analysis?.routes ?? [], [analysis])
  const selectedRoute = routes.find((r) => r.id === selectedRouteId)
  const { state: corridorState, retry: retryCorridor } = useCorridorForecast(analysis?.analysis_id ?? null)
  const corridor = corridorState.data

  const truck = useMemo(() => {
    if (!corridor || !selectedRoute || !analysis) return null
    return truckPositionAt(selectedRoute, analysis.departure_at, hourTime(corridor, forecastHour))
  }, [corridor, selectedRoute, analysis, forecastHour])

  // Hours (on the slider) during which the selected route's truck is on the road.
  const tripHours = useMemo(() => {
    if (!corridor || !selectedRoute || !analysis) return null
    const start = new Date(corridor.start_at).getTime()
    return {
      from: Math.max(0, Math.floor((new Date(analysis.departure_at).getTime() - start) / HOUR_MS)),
      to: Math.floor((new Date(selectedRoute.arrival_at).getTime() - start) / HOUR_MS),
    }
  }, [corridor, selectedRoute, analysis])

  const handleSubmit = useCallback(
    async (request: TripAnalyzeRequest) => {
      const result = await analyze(request)
      if (result) {
        setSelectedRouteId(result.recommendation.recommended_route_id ?? result.routes[0]?.id ?? null)
        setSelectedCheckpoint(null)
        setForecastHour(0)
      }
    },
    [analyze],
  )

  const selectRoute = useCallback((routeId: string) => {
    setSelectedRouteId(routeId)
    setSelectedCheckpoint(null)
  }, [])

  return (
    // Desktop: fixed-height three-column dashboard with scrolling side panels.
    // Narrow screens: panels stack and the whole page scrolls normally.
    <div className="flex min-h-full flex-col bg-slate-50 text-slate-900 lg:h-full">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">Spotter Route Planner</h1>
        <span className="flex items-center gap-2 text-sm text-slate-600" role="status">
          <span className={`h-2 w-2 rounded-full ${HEALTH_DOT[health]}`} aria-hidden="true" />
          {HEALTH_LABEL[health]}
        </span>
      </header>

      <main className="grid flex-1 grid-cols-1 lg:min-h-0 lg:grid-cols-[320px_1fr_380px]">
        <aside className="space-y-4 border-b border-slate-200 bg-white p-4 lg:overflow-y-auto lg:border-r lg:border-b-0">
          <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Trip</h2>
          <TripForm onSubmit={handleSubmit} loading={state.status === 'loading'} />
          {state.error && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
              {state.error}
            </p>
          )}
        </aside>

        <section
          className="relative flex flex-col lg:min-h-0"
          aria-label="Route map"
          aria-busy={state.status === 'loading'}
        >
          {analysis?.weather_source === 'demo' && (
            <p
              role="note"
              className="bg-amber-400 px-3 py-1.5 text-center text-xs font-semibold text-amber-950"
            >
              Demo weather: synthetic storms for this walkthrough, not a real forecast. Routes are real.
            </p>
          )}
          <div className="relative min-h-[55vh] flex-1 lg:min-h-0">
            <RouteMap
              routes={routes}
              selectedRouteId={selectedRouteId}
              recommendedRouteId={analysis?.recommendation.recommended_route_id ?? null}
              selectedCheckpointIndex={selectedCheckpoint}
              onSelectRoute={selectRoute}
              onSelectCheckpoint={setSelectedCheckpoint}
              corridor={corridor}
              corridorHour={forecastHour}
              showCorridor={showCorridor}
              truck={truck?.lngLat ?? null}
            />
            {analysis && (
              <div className="absolute top-2 left-2">
                <RiskLegend corridor={showCorridor && corridor !== null} />
              </div>
            )}
            {state.status === 'loading' && (
              <div className="absolute inset-x-0 top-2 flex justify-center">
                <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white shadow">
                  Fetching routes and forecasts…
                </span>
              </div>
            )}
          </div>
          {analysis && (
            <div className="border-t border-slate-200 bg-slate-50 p-2 lg:absolute lg:inset-x-3 lg:bottom-8 lg:mx-auto lg:max-w-2xl lg:border-0 lg:bg-transparent lg:p-0">
              <ForecastTimeline
                status={corridorState.status}
                forecast={corridor}
                error={corridorState.error}
                onRetry={retryCorridor}
                hour={forecastHour}
                onHourChange={setForecastHour}
                visible={showCorridor}
                onVisibleChange={setShowCorridor}
                truck={truck}
                routeLabel={selectedRoute?.label ?? null}
                tripHours={tripHours}
                timeZone={analysis.origin.timezone}
              />
            </div>
          )}
        </section>

        <aside className="space-y-4 border-t border-slate-200 bg-white p-4 lg:overflow-y-auto lg:border-t-0 lg:border-l">
          {analysis ? (
            <>
              <MemoWarnings warnings={analysis.warnings} />
              <MemoRouteComparison
                analysis={analysis}
                selectedRouteId={selectedRouteId}
                onSelectRoute={selectRoute}
              />
              {selectedRoute && (
                <MemoCheckpointDetails
                  route={selectedRoute}
                  selectedIndex={selectedCheckpoint}
                  onSelect={setSelectedCheckpoint}
                  timeZone={analysis.origin.timezone}
                />
              )}
            </>
          ) : (
            <div className="text-sm text-slate-600">
              <h2 className="mb-1 text-sm font-semibold tracking-wide text-slate-500 uppercase">Routes</h2>
              <p>Enter a trip to compare up to three routes by weather risk at the truck's arrival time.</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}

export default App
