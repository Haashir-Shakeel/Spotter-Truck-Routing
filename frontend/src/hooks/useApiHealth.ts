import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/health'

export type ApiHealth = 'checking' | 'waking' | 'online' | 'offline'

const RETRY_MS = 3_000
// Free hosting stops idle services; the first request can take up to about a minute to wake one.
const WAKE_TIMEOUT_MS = 90_000

/** Polls the API until it answers, showing "waking" meanwhile instead of declaring it offline. */
export function useApiHealth({ retryMs = RETRY_MS, wakeTimeoutMs = WAKE_TIMEOUT_MS } = {}): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>('checking')

  useEffect(() => {
    const controller = new AbortController()
    const started = Date.now()
    let timer: ReturnType<typeof setTimeout> | undefined

    const check = () => {
      fetchHealth(controller.signal)
        .then(() => setHealth('online'))
        .catch(() => {
          if (controller.signal.aborted) return
          if (Date.now() - started >= wakeTimeoutMs) {
            setHealth('offline')
            return
          }
          setHealth('waking')
          timer = setTimeout(check, retryMs)
        })
    }
    check()

    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [retryMs, wakeTimeoutMs])

  return health
}
