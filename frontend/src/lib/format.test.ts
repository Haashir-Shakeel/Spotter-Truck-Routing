import { describe, expect, it } from 'vitest'
import { formatDateTime, formatDuration, formatMiles, localInputToOffsetIso, nextWholeHourLocal } from './format'

describe('format', () => {
  it('formats durations', () => {
    expect(formatDuration(45 * 60)).toBe('45 min')
    expect(formatDuration(5 * 3600 + 12 * 60)).toBe('5 h 12 min')
  })

  it('formats miles', () => {
    expect(formatMiles(4.25)).toBe('4.3 mi')
    expect(formatMiles(285.7)).toBe('286 mi')
  })

  it('rounds the default departure up to the next whole local hour', () => {
    expect(nextWholeHourLocal(new Date(2026, 10, 13, 8, 20))).toBe('2026-11-13T09:00')
  })

  it('turns a local input value into the same instant with an explicit offset', () => {
    const iso = localInputToOffsetIso('2026-11-13T08:00')

    expect(iso).toMatch(/^2026-11-13T08:00:00[+-]\d{2}:\d{2}$/)
    expect(new Date(iso).getTime()).toBe(new Date(2026, 10, 13, 8, 0).getTime())
  })

  it('shows times in the trip time zone when one is known', () => {
    const iso = '2026-11-13T14:00:00Z' // 8:00 AM in Chicago, 7:00 AM in Phoenix

    expect(formatDateTime(iso, 'America/Chicago')).toMatch(/8:00/)
    expect(formatDateTime(iso, 'America/Phoenix')).toMatch(/7:00/)
  })

  it("falls back to the viewer's zone for a missing or unknown zone", () => {
    const iso = '2026-11-13T14:00:00Z'
    const viewer = formatDateTime(iso)

    expect(formatDateTime(iso, null)).toBe(viewer)
    expect(formatDateTime(iso, 'Mars/Olympus_Mons')).toBe(viewer)
  })

  it('rejects an invalid value', () => {
    expect(() => localInputToOffsetIso('')).toThrow()
  })
})
