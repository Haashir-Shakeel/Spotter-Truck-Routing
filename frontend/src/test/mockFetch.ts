import { vi } from 'vitest'

type Handler = (init: RequestInit | undefined, url: URL) => { status?: number; body: unknown }

/** Route fetch calls by URL path prefix. Unmatched paths fail loudly. */
export function mockFetch(routes: Record<string, Handler>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    const match = Object.keys(routes).find((prefix) => url.pathname.startsWith(prefix))
    if (!match) throw new Error(`Unexpected fetch: ${url.pathname}`)
    const { status = 200, body } = routes[match](init, url)
    return {
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    } as Response
  })
}
