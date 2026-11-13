import { type FormEvent, useId, useState } from 'react'
import { localInputToOffsetIso, nextWholeHourLocal, toLocalInputValue } from '../../lib/format'
import type { CheckpointInterval, LocationInput, TripAnalyzeRequest } from '../../types/trip'
import { PlaceInput } from './PlaceInput'

const INTERVALS: CheckpointInterval[] = [10, 25, 50]
const MAX_LOAD_LB = 150_000
const MAX_DAYS_AHEAD = 14 // matches the backend forecast window
const PAST_GRACE_MS = 60 * 60 * 1000

type Errors = Partial<Record<'origin' | 'destination' | 'departure' | 'load', string>>

interface TripFormProps {
  onSubmit: (request: TripAnalyzeRequest) => void
  loading: boolean
  now?: () => Date
}

export function TripForm({ onSubmit, loading, now = () => new Date() }: TripFormProps) {
  const ids = { departure: useId(), load: useId() }
  const [origin, setOrigin] = useState<LocationInput>({ name: '' })
  const [destination, setDestination] = useState<LocationInput>({ name: '' })
  const [departure, setDeparture] = useState(() => nextWholeHourLocal(now()))
  const [load, setLoad] = useState('')
  const [interval, setCheckpointInterval] = useState<CheckpointInterval>(25)
  const [errors, setErrors] = useState<Errors>({})

  const validate = (): Errors => {
    const found: Errors = {}
    if (!origin.name.trim()) found.origin = 'Enter an origin.'
    if (!destination.name.trim()) found.destination = 'Enter a destination.'

    const departureMs = new Date(departure).getTime()
    const nowMs = now().getTime()
    if (!departure || Number.isNaN(departureMs)) found.departure = 'Choose a departure date and time.'
    else if (departureMs < nowMs - PAST_GRACE_MS) found.departure = 'Departure is in the past.'
    else if (departureMs > nowMs + MAX_DAYS_AHEAD * 86_400_000)
      found.departure = `Forecasts only cover the next ${MAX_DAYS_AHEAD} days.`

    const weight = Number(load)
    if (!load.trim() || !Number.isFinite(weight) || weight <= 0) found.load = 'Enter the load weight in pounds.'
    else if (weight > MAX_LOAD_LB) found.load = `Load must be at most ${MAX_LOAD_LB.toLocaleString()} lb.`
    return found
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return
    onSubmit({
      origin: { ...origin, name: origin.name.trim() },
      destination: { ...destination, name: destination.name.trim() },
      departure_at: localInputToOffsetIso(departure),
      load_weight_lb: Number(load),
      checkpoint_interval_miles: interval,
    })
  }

  const minDeparture = toLocalInputValue(new Date(now().getTime() - PAST_GRACE_MS))

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="Trip details">
      <PlaceInput
        label="Origin"
        value={origin}
        onChange={setOrigin}
        placeholder="e.g. Chicago, IL"
        error={errors.origin}
      />
      <PlaceInput
        label="Destination"
        value={destination}
        onChange={setDestination}
        placeholder="e.g. Detroit, MI"
        error={errors.destination}
      />

      <div>
        <label htmlFor={ids.departure} className="mb-1 block text-sm font-medium text-slate-700">
          Departure <span className="font-normal text-slate-500">(your local time)</span>
        </label>
        <input
          id={ids.departure}
          type="datetime-local"
          value={departure}
          min={minDeparture}
          onChange={(e) => setDeparture(e.target.value)}
          aria-invalid={errors.departure ? true : undefined}
          aria-describedby={errors.departure ? `${ids.departure}-error` : undefined}
          className={`w-full rounded-md border px-3 py-2 text-sm shadow-sm ${errors.departure ? 'border-red-500' : 'border-slate-300'}`}
        />
        {errors.departure && (
          <p id={`${ids.departure}-error`} className="mt-1 text-xs text-red-600">
            {errors.departure}
          </p>
        )}
      </div>

      <div>
        <label htmlFor={ids.load} className="mb-1 block text-sm font-medium text-slate-700">
          Load weight <span className="font-normal text-slate-500">(lb)</span>
        </label>
        <input
          id={ids.load}
          type="number"
          inputMode="numeric"
          min={1}
          max={MAX_LOAD_LB}
          step={1}
          placeholder="e.g. 35000"
          value={load}
          onChange={(e) => setLoad(e.target.value)}
          aria-invalid={errors.load ? true : undefined}
          aria-describedby={errors.load ? `${ids.load}-error` : undefined}
          className={`w-full rounded-md border px-3 py-2 text-sm shadow-sm ${errors.load ? 'border-red-500' : 'border-slate-300'}`}
        />
        {errors.load && (
          <p id={`${ids.load}-error`} className="mt-1 text-xs text-red-600">
            {errors.load}
          </p>
        )}
      </div>

      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Weather checkpoint every</legend>
        <div className="grid grid-cols-3 gap-1 rounded-md bg-slate-100 p-1">
          {INTERVALS.map((miles) => (
            <label
              key={miles}
              className={`cursor-pointer rounded px-2 py-1.5 text-center text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-slate-400 ${
                interval === miles ? 'bg-white font-semibold shadow-sm' : 'text-slate-600'
              }`}
            >
              <input
                type="radio"
                name="checkpoint-interval"
                value={miles}
                checked={interval === miles}
                onChange={() => setCheckpointInterval(miles)}
                className="sr-only"
              />
              {miles} mi
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-wait disabled:opacity-60"
      >
        {loading ? 'Analyzing routes…' : 'Analyze routes'}
      </button>
    </form>
  )
}
