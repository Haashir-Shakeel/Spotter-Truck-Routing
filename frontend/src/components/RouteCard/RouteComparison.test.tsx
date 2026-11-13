import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { sampleAnalysis } from '../../test/sampleAnalysis'
import { RouteComparison } from './RouteComparison'

describe('RouteComparison', () => {
  it('shows the recommendation, badges and the selected route', () => {
    render(<RouteComparison analysis={sampleAnalysis} selectedRouteId="B" onSelectRoute={() => {}} />)

    expect(screen.getByText(sampleAnalysis.recommendation.explanation)).toBeInTheDocument()
    const cardA = screen.getByRole('button', { name: /Route A/ })
    const cardB = screen.getByRole('button', { name: /Route B/ })
    expect(within(cardB).getByText('Recommended')).toBeInTheDocument()
    expect(within(cardA).getByText('Has No Travel conditions')).toBeInTheDocument()
    expect(within(cardA).getByText('Max: No Travel')).toBeInTheDocument()
    expect(cardB).toHaveAttribute('aria-pressed', 'true')
    expect(cardA).toHaveAttribute('aria-pressed', 'false')
    expect(within(cardB).getByText(/Forecast unavailable for 25 mi/)).toBeInTheDocument()
  })

  it('selects a route when its card is clicked', async () => {
    const onSelect = vi.fn()
    render(<RouteComparison analysis={sampleAnalysis} selectedRouteId="B" onSelectRoute={onSelect} />)

    await userEvent.click(screen.getByRole('button', { name: /Route A/ }))

    expect(onSelect).toHaveBeenCalledWith('A')
  })

  it('makes a no-safe-route result obvious', () => {
    const analysis = {
      ...sampleAnalysis,
      recommendation: {
        ...sampleAnalysis.recommendation,
        status: 'no_safe_route' as const,
        recommended_route_id: null,
        explanation: 'No route can be recommended as safe.',
      },
    }
    render(<RouteComparison analysis={analysis} selectedRouteId={null} onSelectRoute={() => {}} />)

    expect(screen.getByText('No safe route')).toBeInTheDocument()
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument()
  })
})
