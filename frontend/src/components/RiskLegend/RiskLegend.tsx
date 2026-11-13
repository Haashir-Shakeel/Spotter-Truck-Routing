import { RISK_STYLE, type RiskOrUnavailable } from '../../lib/risk'

const ENTRIES: RiskOrUnavailable[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNAVAILABLE']

/** Compact so it covers little of the map; the reading guide folds open on demand. */
export function RiskLegend({ corridor = false }: { corridor?: boolean }) {
  return (
    <div className="max-w-56 rounded-md bg-white/95 p-2 text-xs shadow ring-1 ring-slate-200">
      <ul className="grid grid-cols-2 gap-x-3 gap-y-0.5" aria-label="Risk levels">
        {ENTRIES.map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: RISK_STYLE[level].color }}
              aria-hidden="true"
            />
            {RISK_STYLE[level].label}
          </li>
        ))}
      </ul>
      <details className="mt-1 text-slate-600">
        <summary className="cursor-pointer font-medium text-slate-700">What am I seeing?</summary>
        <ul className="mt-1 space-y-0.5">
          <li>Selected route line: risk at the truck's arrival time at each checkpoint.</li>
          <li>Grey lines: other routes. Letters mark each route.</li>
          {corridor && (
            <>
              <li>Shading and small dots: corridor forecast at the slider hour.</li>
              <li className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-blue-600 ring-2 ring-white" aria-hidden="true" />
                Truck position at the slider hour.
              </li>
            </>
          )}
        </ul>
      </details>
    </div>
  )
}
