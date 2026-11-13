import { formatDateTime } from '../../lib/format'
import { RISK_STYLE } from '../../lib/risk'
import type { Checkpoint, RiskLevel, RouteResult } from '../../types/trip'

interface CheckpointDetailsProps {
  route: RouteResult
  selectedIndex: number | null
  onSelect: (index: number) => void
}

function RiskBadge({ level }: { level: RiskLevel | null }) {
  const style = RISK_STYLE[level ?? 'UNAVAILABLE']
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${style.badge}`}>{style.label}</span>
}

function WeatherRow({ name, value, level }: { name: string; value: string; level: RiskLevel }) {
  return (
    <tr>
      <th scope="row" className="py-0.5 text-left font-normal text-slate-500">
        {name}
      </th>
      <td>{value}</td>
      <td className="text-right">
        <RiskBadge level={level} />
      </td>
    </tr>
  )
}

function Detail({ checkpoint }: { checkpoint: Checkpoint }) {
  const { weather, risk_detail: detail } = checkpoint
  return (
    <div className="rounded-lg border border-slate-200 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="font-semibold">Mile {checkpoint.distance_miles.toFixed(0)}</p>
        <RiskBadge level={checkpoint.risk} />
      </div>
      <p className="text-xs text-slate-600">
        Truck arrives {formatDateTime(checkpoint.arrival_at)} · {checkpoint.lat.toFixed(3)},{' '}
        {checkpoint.lon.toFixed(3)}
      </p>

      {weather && detail ? (
        <table className="mt-2 w-full text-xs">
          <caption className="sr-only">Weather and risk at this checkpoint</caption>
          <tbody>
            <WeatherRow name="Wind" value={`${weather.wind_mph.toFixed(0)} mph`} level={detail.wind} />
            <WeatherRow name="Rain" value={`${weather.rain_in_per_hour.toFixed(2)} in/hr`} level={detail.rain} />
            <WeatherRow name="Snow" value={`${weather.snow_in_per_hour.toFixed(2)} in/hr`} level={detail.snow} />
          </tbody>
        </table>
      ) : (
        <p className="mt-2 text-xs text-slate-700">
          Forecast unavailable for this time and place, so this point is not rated.
        </p>
      )}
      {checkpoint.load_override && (
        <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-900">{checkpoint.load_override}</p>
      )}
    </div>
  )
}

export function CheckpointDetails({ route, selectedIndex, onSelect }: CheckpointDetailsProps) {
  const selected = route.checkpoints.find((cp) => cp.index === selectedIndex)

  return (
    <section aria-labelledby="checkpoint-heading" className="space-y-2">
      <h2 id="checkpoint-heading" className="text-sm font-semibold tracking-wide text-slate-500 uppercase">
        {route.label} checkpoints
      </h2>
      <p className="text-xs text-slate-500">Weather at the truck's estimated arrival time at each point.</p>
      <div className="flex flex-wrap gap-1">
        {route.checkpoints.map((cp) => {
          const style = RISK_STYLE[cp.risk ?? 'UNAVAILABLE']
          const active = cp.index === selectedIndex
          return (
            <button
              key={cp.index}
              type="button"
              onClick={() => onSelect(cp.index)}
              aria-pressed={active}
              aria-label={`Mile ${cp.distance_miles.toFixed(0)}, ${style.label}`}
              className={`flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs ${
                active ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200'
              }`}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: style.color }} aria-hidden="true" />
              {cp.distance_miles.toFixed(0)}
            </button>
          )
        })}
      </div>
      {selected ? (
        <Detail checkpoint={selected} />
      ) : (
        <p className="text-xs text-slate-500">Select a checkpoint on the map or above to see its weather.</p>
      )}
    </section>
  )
}
