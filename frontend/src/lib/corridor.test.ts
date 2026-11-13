import { describe, expect, it } from 'vitest'
import { sampleAnalysis, sampleCorridor } from '../test/sampleAnalysis'
import {
  corridorFeatures,
  hourlyWorst,
  hourTime,
  pixelsPerMile,
  summarizeHour,
  truckPositionAt,
  UNAVAILABLE_VALUE,
} from './corridor'

const routeA = sampleAnalysis.routes[0]
const at = (iso: string) => new Date(iso)

describe('corridor features', () => {
  it('stores every hour as a property so the slider never rebuilds data', () => {
    const features = corridorFeatures(sampleCorridor).features

    expect(features).toHaveLength(3)
    expect(features[0].geometry.coordinates).toEqual([-90, 40])
    expect(Object.keys(features[0].properties)).toEqual(['h0', 'h1', 'h2'])
    expect(features.map((f) => f.properties.h1)).toEqual([1, 3, UNAVAILABLE_VALUE])
  })
})

describe('hour summaries', () => {
  it('counts levels and keeps missing data separate from Low', () => {
    const summary = summarizeHour(sampleCorridor, 1)

    expect(summary.worst).toBe('SEVERE')
    expect(summary.counts).toMatchObject({ MODERATE: 1, SEVERE: 1, UNAVAILABLE: 1, LOW: 0 })
    expect(summary.total).toBe(3)
  })

  it('reports no worst level for an hour without any data', () => {
    expect(summarizeHour(sampleCorridor, 2).worst).toBeNull()
    expect(hourlyWorst(sampleCorridor)).toEqual(['LOW', 'SEVERE', null])
  })

  it('maps slider hours to absolute times from the forecast start', () => {
    expect(hourTime(sampleCorridor, 0).toISOString()).toBe('2026-11-13T13:00:00.000Z')
    expect(hourTime(sampleCorridor, 2).toISOString()).toBe('2026-11-13T15:00:00.000Z')
  })
})

describe('heatmap sizing', () => {
  it('doubles pixels per mile with each zoom level and grows with latitude', () => {
    expect(pixelsPerMile(5, 40)).toBeCloseTo(pixelsPerMile(4, 40) * 2)
    expect(pixelsPerMile(5, 45)).toBeGreaterThan(pixelsPerMile(5, 30))
  })
})

describe('truck position', () => {
  it('is at the origin before departure and at the destination after arrival', () => {
    expect(truckPositionAt(routeA, sampleAnalysis.departure_at, at('2026-11-13T12:00:00Z'))).toMatchObject({
      status: 'not_departed',
      lngLat: [-90, 40],
    })
    expect(truckPositionAt(routeA, sampleAnalysis.departure_at, at('2026-11-13T15:00:00Z'))).toMatchObject({
      status: 'arrived',
      distanceMiles: 50,
    })
  })

  it('interpolates between checkpoint ETAs along the road geometry', () => {
    // Checkpoints: 0 mi at +0 s, 25 mi at +1500 s. Halfway in time is 12.5 mi.
    const truck = truckPositionAt(routeA, sampleAnalysis.departure_at, at('2026-11-13T13:12:30Z'))

    expect(truck?.status).toBe('en_route')
    expect(truck?.distanceMiles).toBeCloseTo(12.5)
    expect(truck?.lngLat[0]).toBeCloseTo(-89.5, 1)
  })
})
