import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockFetch } from '../../test/mockFetch'
import { TripForm } from './TripForm'

const NOW = new Date(2026, 10, 13, 8, 20) // local time

function setup() {
  const onSubmit = vi.fn()
  render(<TripForm onSubmit={onSubmit} loading={false} now={() => NOW} />)
  return { onSubmit, user: userEvent.setup() }
}

describe('TripForm', () => {
  it('submits a complete request with an offset-aware departure', async () => {
    mockFetch({ '/api/v1/places/': () => ({ body: { results: [] } }) })
    const { onSubmit, user } = setup()

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Chicago, IL')
    await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'Detroit, MI')
    await user.type(screen.getByLabelText(/Load weight/), '35000')
    await user.click(screen.getByRole('radio', { name: '50 mi' }))
    await user.click(screen.getByRole('button', { name: 'Analyze routes' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const request = onSubmit.mock.calls[0][0]
    expect(request).toMatchObject({
      origin: { name: 'Chicago, IL' },
      destination: { name: 'Detroit, MI' },
      load_weight_lb: 35000,
      checkpoint_interval_miles: 50,
    })
    expect(request.departure_at).toMatch(/^2026-11-13T09:00:00[+-]\d{2}:\d{2}$/)
  })

  it('shows field errors and does not submit when incomplete', async () => {
    const { onSubmit, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Analyze routes' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Enter an origin.')).toBeInTheDocument()
    expect(screen.getByText('Enter a destination.')).toBeInTheDocument()
    expect(screen.getByText('Enter the load weight in pounds.')).toBeInTheDocument()
  })

  it('rejects an overweight load', async () => {
    mockFetch({ '/api/v1/places/': () => ({ body: { results: [] } }) })
    const { onSubmit, user } = setup()

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'A town')
    await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'B town')
    await user.type(screen.getByLabelText(/Load weight/), '200000')
    await user.click(screen.getByRole('button', { name: 'Analyze routes' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/Load must be at most/)).toBeInTheDocument()
  })

  it('sends coordinates when a suggestion is picked', async () => {
    const fetchSpy = mockFetch({
      '/api/v1/places/': () => ({
        body: { results: [{ name: 'Chicago, Illinois, United States', lon: -87.63, lat: 41.88 }] },
      }),
    })
    const { onSubmit, user } = setup()

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Chic')
    const option = await screen.findByRole('option', { name: 'Chicago, Illinois, United States' })
    await user.click(option)
    await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'Detroit, MI')
    await user.type(screen.getByLabelText(/Load weight/), '20000')
    await user.click(screen.getByRole('button', { name: 'Analyze routes' }))

    expect(onSubmit.mock.calls[0][0].origin).toEqual({
      name: 'Chicago, Illinois, United States',
      lon: -87.63,
      lat: 41.88,
    })
    const placeCalls = fetchSpy.mock.calls.filter(([url]) => String(url).includes('/places/'))
    expect(placeCalls.some(([url]) => String(url).includes('q=Chic'))).toBe(true)
  })

  it('keeps working when suggestions are unavailable', async () => {
    mockFetch({ '/api/v1/places/': () => ({ status: 503, body: null }) })
    const { user } = setup()

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Chicago')

    await waitFor(() => expect(screen.getByText(/Suggestions unavailable/)).toBeInTheDocument())
  })
})
