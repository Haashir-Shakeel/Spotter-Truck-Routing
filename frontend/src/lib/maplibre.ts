/**
 * MapLibre, configured for Vite.
 *
 * MapLibre loads its tile/GeoJSON worker from a file next to its own module. Vite pre-bundles
 * (dev) and bundles (prod) the library, so that sibling file is no longer there and the worker
 * fails to load: no vector tiles, no GeoJSON layers, and the map's `load` event never fires.
 * Pointing MapLibre at the worker as a Vite asset fixes it in both dev and production builds.
 *
 * Import MapLibre through this module, never directly from 'maplibre-gl'.
 */
import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

setWorkerUrl(workerUrl)

export { Map as MapLibreMap, NavigationControl } from 'maplibre-gl'
export type { ExpressionSpecification, GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
