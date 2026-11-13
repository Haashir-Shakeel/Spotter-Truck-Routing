import type { AnalysisWarning } from '../../types/trip'

export function AnalysisWarnings({ warnings }: { warnings: AnalysisWarning[] }) {
  if (warnings.length === 0) return null
  return (
    <section
      aria-label="Analysis warnings"
      className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950 ring-1 ring-amber-200"
    >
      <ul className="list-disc space-y-1 pl-4">
        {warnings.map((w) => (
          <li key={`${w.code}-${w.message}`}>{w.message}</li>
        ))}
      </ul>
    </section>
  )
}
