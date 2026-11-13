import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// jsdom has no WebGL, so MapLibre is replaced with an inert map in unit tests. Map data is built
// by pure functions in src/lib/mapData.ts, which are tested directly.
vi.mock('maplibre-gl', () => {
  class Map {
    addControl() {}
    on() {}
    remove() {}
    addSource() {}
    addLayer() {}
    getSource() {
      return { setData() {} }
    }
    fitBounds() {}
    queryRenderedFeatures() {
      return []
    }
    getCanvas() {
      return { style: {} }
    }
  }
  class NavigationControl {}
  return { Map, NavigationControl, setWorkerUrl() {} }
})
