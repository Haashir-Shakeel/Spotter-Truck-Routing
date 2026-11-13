import { type KeyboardEvent, useEffect, useId, useState } from 'react'
import { searchPlaces } from '../../api/trips'
import type { LocationInput, Place } from '../../types/trip'

const MIN_QUERY_LENGTH = 3
const DEBOUNCE_MS = 300

interface PlaceInputProps {
  label: string
  value: LocationInput
  onChange: (value: LocationInput) => void
  placeholder?: string
  error?: string
}

/** Text input with place suggestions. Picking one attaches coordinates; typing clears them. */
export function PlaceInput({ label, value, onChange, placeholder, error }: PlaceInputProps) {
  const id = useId()
  const listId = `${id}-list`
  const [suggestions, setSuggestions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [unavailable, setUnavailable] = useState(false)

  const query = value.name.trim()
  const isPicked = value.lon !== undefined && value.lat !== undefined
  const searchable = !isPicked && query.length >= MIN_QUERY_LENGTH

  useEffect(() => {
    if (!searchable) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(query, controller.signal)
        .then((places) => {
          setSuggestions(places)
          setActive(-1)
          setUnavailable(false)
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setSuggestions([])
            setUnavailable(true)
          }
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query, searchable])

  // Stale results are hidden (not cleared in an effect) once the text is too short or picked.
  const visible = searchable ? suggestions : []

  const pick = (place: Place) => {
    onChange({ name: place.name, lon: place.lon, lat: place.lat })
    setOpen(false)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open || visible.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (i + 1) % visible.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (i <= 0 ? visible.length - 1 : i - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      pick(visible[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && visible.length > 0

  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-slate-400 focus:outline-none ${
          error ? 'border-red-500' : 'border-slate-300'
        }`}
        placeholder={placeholder}
        value={value.name}
        maxLength={200}
        onChange={(e) => {
          onChange({ name: e.target.value })
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg"
        >
          {visible.map((place, i) => (
            <li
              key={`${place.name}-${place.lon}-${place.lat}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`cursor-pointer px-3 py-2 ${i === active ? 'bg-slate-100' : 'hover:bg-slate-50'}`}
              // mousedown keeps focus in the input so blur doesn't close the list before the click
              onMouseDown={(e) => {
                e.preventDefault()
                pick(place)
              }}
            >
              {place.name}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
      {!error && unavailable && !isPicked && (
        <p className="mt-1 text-xs text-slate-500">Suggestions unavailable — a full address still works.</p>
      )}
    </div>
  )
}
