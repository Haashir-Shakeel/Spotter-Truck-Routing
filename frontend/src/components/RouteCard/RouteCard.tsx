import { formatDateTime, formatDuration, formatMiles } from '../../lib/format'
import { INELIGIBLE_LABEL, RISK_STYLE, type RiskOrUnavailable } from '../../lib/risk'
import type { IneligibilityReason, RouteResult } from '../../types/trip'

interface RouteCardProps {
  route: RouteResult
  selected: boolean
  recommended: boolean
  ineligible?: IneligibilityReason
  /** Destination's zone, so arrival shows in local time where the truck arrives. */
  timeZone?: string | null
  onSelect: () => void
}

function RiskBar({ route }: { route: RouteResult }) {
  const s = route.risk_summary
  const parts: [RiskOrUnavailable, number][] = [
    ['LOW', s.low_miles],
    ['MODERATE', s.moderate_miles],
    ['HIGH', s.high_miles],
    ['SEVERE', s.severe_miles],
    ['NO_TRAVEL', s.no_travel_miles],
    ['UNAVAILABLE', s.unavailable_miles],
  ]
  const total = parts.reduce((sum, [, miles]) => sum + miles, 0) || 1
  const description = parts
    .filter(([, miles]) => miles > 0)
    .map(([level, miles]) => `${RISK_STYLE[level].label} ${formatMiles(miles)}`)
    .join(', ')

  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
        {parts.map(([level, miles]) =>
          miles > 0 ? (
            <div
              key={level}
              style={{ width: `${(miles / total) * 100}%`, backgroundColor: RISK_STYLE[level].color }}
            />
          ) : null,
        )}
      </div>
      <p className="sr-only">Risk miles: {description}</p>
    </div>
  )
}

export function RouteCard({ route, selected, recommended, ineligible, timeZone, onSelect }: RouteCardProps) {
  const s = route.risk_summary
  const maxRisk = s.max_risk ?? 'UNAVAILABLE'

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-lg border p-3 text-left transition ${
        selected ? 'border-slate-900 ring-1 ring-slate-900' : 'border-slate-200 hover:border-slate-400'
      }`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold">{route.label}</span>
        {recommended && (
          <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-xs font-semibold text-white">
            Recommended
          </span>
        )}
        {route.source === 'via_waypoint' && (
          <span
            className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
            title="Requested through a waypoint beside the trip because the routing service offered fewer than three routes."
          >
            Via waypoint
          </span>
        )}
        {ineligible && (
          <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700">
            {INELIGIBLE_LABEL[ineligible]}
          </span>
        )}
        <span className={`ml-auto rounded px-1.5 py-0.5 text-xs font-medium ${RISK_STYLE[maxRisk].badge}`}>
          Max: {RISK_STYLE[maxRisk].label}
        </span>
      </div>

      <dl className="mb-2 grid grid-cols-3 gap-2 text-xs">
        <div>
          <dt className="text-slate-500">Distance</dt>
          <dd className="font-medium">{formatMiles(route.distance_miles)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Drive time</dt>
          <dd className="font-medium">{formatDuration(route.duration_seconds)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Arrives</dt>
          <dd className="font-medium">{formatDateTime(route.arrival_at, timeZone)}</dd>
        </div>
      </dl>

      <RiskBar route={route} />

      <dl className="mt-2 grid grid-cols-4 gap-2 text-xs">
        <div>
          <dt className="text-slate-500">Severe</dt>
          <dd className="font-medium">{formatMiles(s.severe_miles)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">High</dt>
          <dd className="font-medium">{formatMiles(s.high_miles)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">No Travel</dt>
          <dd className="font-medium">{formatMiles(s.no_travel_miles)}</dd>
        </div>
        <div>
          <dt className="text-slate-500" title="Mile-weighted score: Low 0 to No Travel 4">
            Avg risk
          </dt>
          <dd className="font-medium">{s.average_risk.toFixed(2)}</dd>
        </div>
      </dl>
      {s.unavailable_miles > 0 && (
        <p className="mt-2 text-xs text-slate-600">
          Forecast unavailable for {formatMiles(s.unavailable_miles)}.
        </p>
      )}
    </button>
  )
}
