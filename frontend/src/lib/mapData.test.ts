import { describe, expect, it } from 'vitest'
import { sampleAnalysis } from '../test/sampleAnalysis'
import { checkpointPoints, riskSegments, routeLines } from './mapData'
import { segmentRisk } from './risk'

const [routeA, routeB] = sampleAnalysis.routes

describe('segmentRisk', () => {
  it('uses the worse endpoint, like the backend', () => {
    expect(segmentRisk('LOW', 'HIGH')).toBe('HIGH')
    expect(segmentRisk('SEVERE', 'MODERATE')).toBe('SEVERE')
  })

  it('treats a missing endpoint as unavailable, never Low', () => {
    expect(segmentRisk('LOW', null)).toBe('UNAVAILABLE')
    expect(segmentRisk(null, 'LOW')).toBe('UNAVAILABLE')
  })
})

describe('map data', () => {
  it('flags the selected and recommended route lines', () => {
    const lines = routeLines(sampleAnalysis.routes, 'A', 'B')

    expect(lines.features.map((f) => f.properties)).toEqual([
      { id: 'A', label: 'Route A', selected: true, recommended: false },
      { id: 'B', label: 'Route B', selected: false, recommended: true },
    ])
  })

  it('splits the selected route into one segment per checkpoint gap', () => {
    const segments = riskSegments(routeA)

    expect(segments.features.map((f) => f.properties.risk)).toEqual(['NO_TRAVEL', 'NO_TRAVEL'])
    expect(riskSegments(routeB).features.map((f) => f.properties.risk)).toEqual(['LOW', 'UNAVAILABLE'])
  })

  it('returns no segments or points without a selected route', () => {
    expect(riskSegments(undefined).features).toEqual([])
    expect(checkpointPoints(undefined, null).features).toEqual([])
  })

  it('marks the selected checkpoint and missing risk as unavailable', () => {
    const points = checkpointPoints(routeB, 1)

    expect(points.features.map((f) => f.properties)).toEqual([
      { index: 0, risk: 'LOW', selected: false },
      { index: 1, risk: 'LOW', selected: true },
      { index: 2, risk: 'UNAVAILABLE', selected: false },
    ])
  })
})
