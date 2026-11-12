import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// jsdom has no WebGL, so MapLibre is replaced with a no-op map in unit tests.
vi.mock('maplibre-gl', () => {
  class Map {
    addControl() {}
    remove() {}
  }
  class NavigationControl {}
  return { Map, NavigationControl }
})
