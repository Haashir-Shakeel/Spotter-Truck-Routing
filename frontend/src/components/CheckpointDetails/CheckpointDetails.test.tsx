import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { sampleAnalysis } from '../../test/sampleAnalysis'
import { CheckpointDetails } from './CheckpointDetails'

const [routeA, routeB] = sampleAnalysis.routes

describe('CheckpointDetails', () => {
  it('lists checkpoints and selects one', async () => {
    const onSelect = vi.fn()
    render(<CheckpointDetails route={routeA} selectedIndex={null} onSelect={onSelect} />)

    await userEvent.click(screen.getByRole('button', { name: 'Mile 25, No Travel' }))

    expect(onSelect).toHaveBeenCalledWith(1)
    expect(screen.getByText(/Select a checkpoint/)).toBeInTheDocument()
  })

  it('shows weather and per-condition risk for the selected checkpoint', () => {
    render(<CheckpointDetails route={routeA} selectedIndex={1} onSelect={() => {}} />)

    expect(screen.getByText('60 mph')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /Weather and risk/ })).toBeInTheDocument()
  })

  it('says when a forecast is unavailable instead of showing Low', () => {
    render(<CheckpointDetails route={routeB} selectedIndex={2} onSelect={() => {}} />)

    expect(screen.getByText(/Forecast unavailable for this time and place/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
