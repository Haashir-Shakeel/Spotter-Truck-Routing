import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { mockFetch } from './test/mockFetch'
import { sampleAnalysis } from './test/sampleAnalysis'

const health = () => ({ body: { status: 'ok', time: '' } })
const noPlaces = () => ({ body: { results: [] } })

async function fillAndSubmit() {
  const user = userEvent.setup()
  await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Origin')
  await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'Destination')
  await user.type(screen.getByLabelText(/Load weight/), '35000')
  await user.click(screen.getByRole('button', { name: 'Analyze routes' }))
  return user
}

describe('App', () => {
  it('renders the shell and reports API health', async () => {
    mockFetch({ '/api/v1/health/': health })
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Spotter Route Planner' })).toBeInTheDocument()
    expect(screen.getByTestId('route-map')).toBeInTheDocument()
    expect(await screen.findByText('API online')).toBeInTheDocument()
  })

  it('reports API offline when health fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockFetch({ '/api/v1/health/': () => ({ status: 503, body: null }) })
    render(<App />)

    expect(await screen.findByText('API offline')).toBeInTheDocument()
  })

  it('analyzes a trip and selects the recommended route', async () => {
    let posted: unknown
    mockFetch({
      '/api/v1/health/': health,
      '/api/v1/places/': noPlaces,
      '/api/v1/trips/analyze/': (init) => {
        posted = JSON.parse(String(init?.body))
        return { status: 201, body: sampleAnalysis }
      },
    })
    render(<App />)

    const user = await fillAndSubmit()

    expect(await screen.findByText(sampleAnalysis.recommendation.explanation)).toBeInTheDocument()
    expect(posted).toMatchObject({ origin: { name: 'Origin' }, load_weight_lb: 35000 })
    expect(screen.getByRole('button', { name: /Route B/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { name: 'Route B checkpoints' })).toBeInTheDocument()
    expect(screen.getByText(/2 distinct routes/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Route A/ }))
    expect(screen.getByRole('heading', { name: 'Route A checkpoints' })).toBeInTheDocument()
  })

  it('shows API errors from the error contract', async () => {
    mockFetch({
      '/api/v1/health/': health,
      '/api/v1/places/': noPlaces,
      '/api/v1/trips/analyze/': () => ({
        status: 400,
        body: {
          error: { code: 'LOCATION_NOT_FOUND', message: "Could not find the destination 'Destination'.", details: {} },
        },
      }),
    })
    render(<App />)

    await fillAndSubmit()

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText(/Could not find the destination/)).toBeInTheDocument()
  })
})
