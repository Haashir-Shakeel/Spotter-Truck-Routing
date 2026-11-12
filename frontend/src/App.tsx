import { RouteMap } from './components/RouteMap/RouteMap'
import { useApiHealth, type ApiHealth } from './hooks/useApiHealth'

const HEALTH_LABEL: Record<ApiHealth, string> = {
  checking: 'Checking API…',
  online: 'API online',
  offline: 'API offline',
}

const HEALTH_DOT: Record<ApiHealth, string> = {
  checking: 'bg-slate-400',
  online: 'bg-emerald-500',
  offline: 'bg-red-500',
}

function App() {
  const health = useApiHealth()

  return (
    <div className="flex h-full flex-col bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">Spotter Route Planner</h1>
        <span className="flex items-center gap-2 text-sm text-slate-600" role="status">
          <span className={`h-2 w-2 rounded-full ${HEALTH_DOT[health]}`} aria-hidden="true" />
          {HEALTH_LABEL[health]}
        </span>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[320px_1fr_340px]">
        <aside className="border-b border-slate-200 bg-white p-4 lg:border-r lg:border-b-0">
          <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Trip</h2>
        </aside>

        <section className="relative min-h-[50vh] lg:min-h-0" aria-label="Route map">
          <RouteMap />
        </section>

        <aside className="border-t border-slate-200 bg-white p-4 lg:border-t-0 lg:border-l">
          <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Routes</h2>
        </aside>
      </main>
    </div>
  )
}

export default App
