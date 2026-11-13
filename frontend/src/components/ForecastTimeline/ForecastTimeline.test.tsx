import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { type ComponentProps, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { sampleCorridor } from '../../test/sampleAnalysis'
import { ForecastTimeline } from './ForecastTimeline'

type Props = ComponentProps<typeof ForecastTimeline>

const base: Props = {
  status: 'success',
  forecast: sampleCorridor,
  error: null,
  onRetry: () => {},
  hour: 0,
  onHourChange: () => {},
  visible: true,
  onVisibleChange: () => {},
  truck: null,
  routeLabel: null,
  tripHours: null,
}

/** Controlled like in App, so slider changes re-render with the new hour. */
function Harness(props: Partial<Props>) {
  const [hour, setHour] = useState(props.hour ?? 0)
  return (
    <ForecastTimeline
      {...base}
      {...props}
      hour={hour}
      onHourChange={(h) => {
        setHour(h)
        props.onHourChange?.(h)
      }}
    />
  )
}

describe('ForecastTimeline', () => {
  it('moves through forecast hours and summarizes the corridor at each', async () => {
    const onHourChange = vi.fn()
    render(<Harness onHourChange={onHourChange} />)
    const slider = screen.getByRole('slider', { name: 'Forecast hour' })

    expect(slider).toHaveAttribute('max', '2')
    expect(screen.getByText(/Worst in corridor/)).toHaveTextContent('Low')

    fireEvent.change(slider, { target: { value: '1' } })
    await waitFor(() => expect(onHourChange).toHaveBeenLastCalledWith(1))
    expect(screen.getByText(/Worst in corridor/)).toHaveTextContent('Severe')
    expect(screen.getByText(/1 of 3 points without data/)).toBeInTheDocument()

    fireEvent.change(slider, { target: { value: '2' } })
    await waitFor(() => expect(screen.getByText('No forecast data for this hour.')).toBeInTheDocument())
  })

  it('labels the selected hour with its absolute time', () => {
    render(<Harness hour={2} />)

    expect(screen.getByText(/Forecast hour \+2 h/)).toBeInTheDocument()
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', expect.stringMatching(/^\+2 h, /))
  })

  it('toggles the corridor layer', async () => {
    const onVisibleChange = vi.fn()
    render(<Harness onVisibleChange={onVisibleChange} />)

    await userEvent.click(screen.getByRole('checkbox', { name: 'Weather corridor' }))

    expect(onVisibleChange).toHaveBeenCalledWith(false)
  })

  it('shows loading and a retryable error', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(<ForecastTimeline {...base} status="loading" forecast={null} />)
    expect(screen.getByText(/Loading 48-hour corridor forecast/)).toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()

    rerender(<ForecastTimeline {...base} status="error" forecast={null} error="Timed out" onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Corridor forecast unavailable: Timed out')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('explains where the truck is at the slider hour', () => {
    render(
      <Harness
        truck={{ status: 'en_route', lngLat: [-89.5, 40], distanceMiles: 12.5 }}
        routeLabel="Route A"
        tripHours={{ from: 0, to: 1 }}
      />,
    )

    expect(screen.getByText(/Truck ≈ 13 mi along Route A/)).toBeInTheDocument()
  })
})
