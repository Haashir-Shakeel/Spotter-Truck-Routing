import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/health'

export type ApiHealth = 'checking' | 'online' | 'offline'

export function useApiHealth(): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>('checking')

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then(() => setHealth('online'))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error('API health check failed', error)
          setHealth('offline')
        }
      })
    return () => controller.abort()
  }, [])

  return health
}
