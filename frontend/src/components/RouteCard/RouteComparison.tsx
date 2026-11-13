import type { TripAnalysis } from '../../types/trip'
import { RouteCard } from './RouteCard'

interface RouteComparisonProps {
  analysis: TripAnalysis
  selectedRouteId: string | null
  onSelectRoute: (routeId: string) => void
}

export function RouteComparison({ analysis, selectedRouteId, onSelectRoute }: RouteComparisonProps) {
  const { recommendation, routes } = analysis
  const noSafeRoute = recommendation.status === 'no_safe_route'

  return (
    <section aria-labelledby="route-comparison-heading" className="space-y-3">
      <h2 id="route-comparison-heading" className="text-sm font-semibold tracking-wide text-slate-500 uppercase">
        Routes
      </h2>

      <div
        role="status"
        className={`rounded-lg p-3 text-sm ${
          noSafeRoute ? 'bg-red-50 text-red-900 ring-1 ring-red-200' : 'bg-emerald-50 text-emerald-950 ring-1 ring-emerald-200'
        }`}
      >
        <p className="font-semibold">{noSafeRoute ? 'No safe route' : 'Recommendation'}</p>
        <p className="mt-1">{recommendation.explanation}</p>
      </div>

      <ul className="space-y-2">
        {routes.map((route) => (
          <li key={route.id}>
            <RouteCard
              route={route}
              selected={route.id === selectedRouteId}
              recommended={route.id === recommendation.recommended_route_id}
              ineligible={recommendation.ineligible[route.id]}
              timeZone={analysis.destination.timezone}
              onSelect={() => onSelectRoute(route.id)}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}
