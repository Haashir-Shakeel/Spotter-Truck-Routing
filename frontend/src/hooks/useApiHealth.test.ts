import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockFetch } from '../test/mockFetch'
import { useApiHealth } from './useApiHealth'

describe('useApiHealth', () => {
  it('keeps retrying while a sleeping API wakes up, then reports online', async () => {
    let calls = 0
    mockFetch({
      '/api/v1/health/': () => (++calls < 3 ? { status: 503, body: null } : { body: { status: 'ok' } }),
    })

    const seen: string[] = []
    renderHook(() => {
      const health = useApiHealth({ retryMs: 5, wakeTimeoutMs: 5_000 })
      if (seen.at(-1) !== health) seen.push(health)
      return health
    })

    await waitFor(() => expect(seen.at(-1)).toBe('online'))
    expect(seen).toEqual(['checking', 'waking', 'online'])
    expect(calls).toBe(3)
  })

  it('gives up and reports offline after the wake timeout', async () => {
    mockFetch({ '/api/v1/health/': () => ({ status: 503, body: null }) })

    const { result } = renderHook(() => useApiHealth({ retryMs: 5, wakeTimeoutMs: 30 }))

    await waitFor(() => expect(result.current).toBe('offline'))
  })
})
