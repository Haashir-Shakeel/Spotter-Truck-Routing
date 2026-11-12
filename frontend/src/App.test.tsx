import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

function mockFetch(response: Partial<Response>) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response as Response)
}

describe('App shell', () => {
  it('renders the layout and reports API online when health succeeds', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve({ status: 'ok', time: '' }) })

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Spotter Route Planner' })).toBeInTheDocument()
    expect(screen.getByTestId('route-map')).toBeInTheDocument()
    expect(await screen.findByText('API online')).toBeInTheDocument()
  })

  it('reports API offline when health fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockFetch({ ok: false, status: 503, json: () => Promise.resolve(null) })

    render(<App />)

    expect(await screen.findByText('API offline')).toBeInTheDocument()
  })
})
