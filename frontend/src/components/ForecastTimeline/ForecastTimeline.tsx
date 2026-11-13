import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { hourlyWorst, hourTime, summarizeHour, type TruckPosition } from '../../lib/corridor'
import { formatDateTime, formatMiles } from '../../lib/format'
import { RISK_STYLE } from '../../lib/risk'
import type { CorridorForecast } from '../../types/trip'

const PLAY_STEP_MS = 600
const TICKS = [0, 12, 24, 36, 48]

interface ForecastTimelineProps {
  status: 'idle' | 'loading' | 'success' | 'error'
  forecast: CorridorForecast | null
  error: string | null
  onRetry: () => void
  hour: number
  onHourChange: (hour: number) => void
  visible: boolean
  onVisibleChange: (visible: boolean) => void
  /** Selected route's truck position at the slider hour, and the hours it is on the road. */
  truck: TruckPosition | null
  routeLabel: string | null
  tripHours: { from: number; to: number } | null
  /** Trip's (origin) zone for the hour labels. */
  timeZone?: string | null
}

function truckText(truck: TruckPosition | null, routeLabel: string | null): string | null {
  if (!truck || !routeLabel) return null
  if (truck.status === 'not_departed') return `Truck not yet departed on ${routeLabel}`
  if (truck.status === 'arrived') return `Truck has arrived (${routeLabel})`
  if (truck.distanceMiles < 0.5) return `Truck departing on ${routeLabel}`
  return `Truck ≈ ${formatMiles(truck.distanceMiles)} along ${routeLabel}`
}

export function ForecastTimeline({
  status,
  forecast,
  error,
  onRetry,
  hour,
  onHourChange,
  visible,
  onVisibleChange,
  truck,
  routeLabel,
  tripHours,
  timeZone,
}: ForecastTimelineProps) {
  const [playing, setPlaying] = useState(false)
  const frame = useRef<number | null>(null)
  const pending = useRef(hour)
  const maxHour = forecast ? forecast.hour_count - 1 : 48

  const worstByHour = useMemo(() => (forecast ? hourlyWorst(forecast) : []), [forecast])
  const summary = useMemo(() => (forecast ? summarizeHour(forecast, hour) : null), [forecast, hour])

  // Coalesce slider input to one map update per animation frame.
  const onInput = (event: ChangeEvent<HTMLInputElement>) => {
    pending.current = Number(event.target.value)
    setPlaying(false)
    if (frame.current !== null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      onHourChange(pending.current)
    })
  }
  useEffect(
    () => () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current)
    },
    [],
  )

  // Playback stops by itself at the last hour.
  const isPlaying = playing && hour < maxHour
  useEffect(() => {
    if (!isPlaying) return
    const timer = setTimeout(() => onHourChange(hour + 1), PLAY_STEP_MS)
    return () => clearTimeout(timer)
  }, [isPlaying, hour, onHourChange])

  if (status === 'idle') return null

  const at = forecast ? hourTime(forecast, hour) : null
  const atText = at ? formatDateTime(at.toISOString(), timeZone) : ''
  const noData = summary !== null && summary.worst === null
  const truckLine = truckText(truck, routeLabel)

  return (
    <section
      aria-label="Corridor forecast timeline"
      className="space-y-1.5 rounded-md bg-white/95 p-3 text-xs shadow ring-1 ring-slate-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-1.5 font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={visible}
            onChange={(e) => onVisibleChange(e.target.checked)}
            className="h-3.5 w-3.5 accent-slate-900"
          />
          Weather corridor
        </label>
        {forecast && (
          <span className="font-medium text-slate-900">
            Forecast hour +{hour} h · {atText}
          </span>
        )}
        {forecast && (
          <button
            type="button"
            onClick={() => {
              if (!isPlaying && hour >= maxHour) onHourChange(0)
              setPlaying(!isPlaying)
            }}
            className="rounded bg-slate-900 px-2 py-0.5 font-semibold text-white hover:bg-slate-700"
            aria-pressed={isPlaying}
          >
            {isPlaying ? 'Pause' : 'Play'}
          </button>
        )}
      </div>

      {status === 'loading' && <p className="text-slate-600">Loading 48-hour corridor forecast…</p>}
      {status === 'error' && (
        <p role="alert" className="text-red-700">
          Corridor forecast unavailable: {error}{' '}
          <button type="button" onClick={onRetry} className="font-semibold underline">
            Retry
          </button>
        </p>
      )}

      {forecast && (
        <>
          {/* Worst corridor risk per hour; the outlined span is when the truck is on the road. */}
          <div className="relative flex h-2.5 overflow-hidden rounded-sm" aria-hidden="true">
            {worstByHour.map((level, h) => (
              <span
                key={h}
                className="flex-1"
                style={{ backgroundColor: RISK_STYLE[level ?? 'UNAVAILABLE'].color, opacity: level ? 1 : 0.5 }}
              />
            ))}
            {tripHours && tripHours.from <= maxHour && (
              <span
                className="absolute inset-y-0 rounded-sm ring-2 ring-slate-900 ring-inset"
                style={{
                  left: `${(tripHours.from / (maxHour + 1)) * 100}%`,
                  width: `${((Math.min(tripHours.to, maxHour) - tripHours.from + 1) / (maxHour + 1)) * 100}%`,
                }}
              />
            )}
          </div>
          <input
            type="range"
            min={0}
            max={maxHour}
            step={1}
            value={hour}
            onChange={onInput}
            aria-label="Forecast hour"
            aria-valuetext={`+${hour} h, ${atText}`}
            className="w-full accent-slate-900"
          />
          <div className="flex justify-between text-slate-500" aria-hidden="true">
            {TICKS.filter((t) => t <= maxHour).map((t) => (
              <span key={t}>{t} h</span>
            ))}
          </div>
          <p className="text-slate-700" aria-live="polite">
            {noData ? (
              'No forecast data for this hour.'
            ) : (
              <>
                Worst in corridor:{' '}
                <span className="font-semibold">{RISK_STYLE[summary?.worst ?? 'UNAVAILABLE'].label}</span>
                {summary && summary.counts.UNAVAILABLE > 0 && (
                  <>
                    {' '}
                    · {summary.counts.UNAVAILABLE} of {summary.total} points without data
                  </>
                )}
              </>
            )}
            {truckLine && <> · {truckLine}</>}
          </p>
          <p className="text-slate-500">
            One forecast hour across the whole corridor, blended between sample points every{' '}
            {Math.round(forecast.spacing_miles)} mi. Route colors use each checkpoint's arrival time instead.
          </p>
        </>
      )}
    </section>
  )
}
