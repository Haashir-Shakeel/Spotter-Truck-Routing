const pad = (n: number) => String(n).padStart(2, '0')

export function formatMiles(miles: number): string {
  return `${miles.toLocaleString(undefined, { maximumFractionDigits: miles < 10 ? 1 : 0 })} mi`
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`
}

const DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
}

/**
 * Time with its zone name, e.g. "Fri 8:00 AM CST". Pass the trip's IANA zone to show trip-local
 * time; without one (or with an unknown one) the viewer's own zone is used.
 */
export function formatDateTime(iso: string, timeZone?: string | null): string {
  const date = new Date(iso)
  if (timeZone) {
    try {
      return new Intl.DateTimeFormat(undefined, { ...DATE_TIME_OPTIONS, timeZone }).format(date)
    } catch {
      // RangeError for a zone this browser doesn't know: fall through to the viewer's zone.
    }
  }
  return new Intl.DateTimeFormat(undefined, DATE_TIME_OPTIONS).format(date)
}

/** Value for <input type="datetime-local">: the next whole hour in local time. */
export function nextWholeHourLocal(now: Date = new Date()): string {
  const d = new Date(now)
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  return toLocalInputValue(d)
}

export function toLocalInputValue(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** "2026-11-13T08:00" (browser local) -> "2026-11-13T08:00:00-06:00", so the API gets an exact instant. */
export function localInputToOffsetIso(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) throw new Error(`Invalid date-time: ${value}`)
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  return `${toLocalInputValue(date)}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}
