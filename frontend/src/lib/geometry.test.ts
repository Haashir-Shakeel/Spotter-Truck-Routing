import { describe, expect, it } from 'vitest'
import type { LngLat } from '../types/trip'
import { boundsOf, cumulativeMiles, haversineMiles, pointAtDistance, sliceLine } from './geometry'

const MILES_PER_DEGREE = (3958.7613 * Math.PI) / 180

describe('geometry', () => {
  it('measures great-circle distance', () => {
    expect(haversineMiles([-87.6298, 41.8781], [-83.0458, 42.3314])).toBeCloseTo(237.5, -1)
  })

  it('accumulates and scales distance to the road distance', () => {
    const coords: LngLat[] = [
      [0, 0],
      [1, 0],
      [2, 0],
    ]
    expect(cumulativeMiles(coords)[2]).toBeCloseTo(2 * MILES_PER_DEGREE)
    expect(cumulativeMiles(coords, 200)).toEqual([0, 100, 200].map((v) => expect.closeTo(v)))
  })

  it('slices a line around a corner, keeping the corner vertex', () => {
    const coords: LngLat[] = [
      [0, 0],
      [1, 0],
      [1, 1],
    ]
    const cumulative = cumulativeMiles(coords, 100)
    const slice = sliceLine(coords, cumulative, 25, 75)

    expect(slice).toHaveLength(3)
    expect(slice[0][0]).toBeCloseTo(0.5)
    expect(slice[1]).toEqual([1, 0])
    expect(slice[2][1]).toBeCloseTo(0.5)
  })

  it('clamps points to the line ends', () => {
    const coords: LngLat[] = [
      [0, 0],
      [1, 0],
    ]
    const cumulative = cumulativeMiles(coords, 10)
    expect(pointAtDistance(coords, cumulative, 10)).toEqual([1, 0])
    expect(pointAtDistance(coords, cumulative, 0)).toEqual([0, 0])
  })

  it('computes bounds across lines, or null when empty', () => {
    expect(
      boundsOf([
        [
          [-90, 40],
          [-88, 41],
        ],
        [[-89, 39]],
      ]),
    ).toEqual([
      [-90, 39],
      [-88, 41],
    ])
    expect(boundsOf([])).toBeNull()
  })
})
