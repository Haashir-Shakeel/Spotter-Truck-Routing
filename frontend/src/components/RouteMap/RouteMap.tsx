import { Map as MapLibreMap, NavigationControl } from 'maplibre-gl'
import { useEffect, useRef } from 'react'

const MAP_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/liberty'

// Continental US default view until a trip is analyzed.
const DEFAULT_CENTER: [number, number] = [-96, 38.5]
const DEFAULT_ZOOM = 3.6

export function RouteMap() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    })
    map.addControl(new NavigationControl(), 'top-right')

    return () => map.remove()
  }, [])

  return <div ref={containerRef} className="h-full w-full" data-testid="route-map" />
}
