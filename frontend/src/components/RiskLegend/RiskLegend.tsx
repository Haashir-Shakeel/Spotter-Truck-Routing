import { RISK_STYLE, type RiskOrUnavailable } from '../../lib/risk'

const ENTRIES: RiskOrUnavailable[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNAVAILABLE']

export function RiskLegend() {
  return (
    <div className="rounded-md bg-white/95 p-2 text-xs shadow ring-1 ring-slate-200">
      <p className="mb-1 font-semibold text-slate-700">Risk at truck's ETA</p>
      <ul className="space-y-0.5">
        {ENTRIES.map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-4 rounded-sm"
              style={{ backgroundColor: RISK_STYLE[level].color }}
              aria-hidden="true"
            />
            {RISK_STYLE[level].label}
          </li>
        ))}
      </ul>
      <p className="mt-1 text-slate-500">Grey lines: other routes</p>
    </div>
  )
}
