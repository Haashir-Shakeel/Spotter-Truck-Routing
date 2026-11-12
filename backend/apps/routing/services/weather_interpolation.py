"""Pick the weather a truck meets at a checkpoint, at its estimated arrival time.

Policy (see docs/scoring-assumptions.md):
- Wind is an instantaneous value at each hour, so it is linearly interpolated between the two
  forecast hours around the arrival time.
- Rain and snow are totals for the hour *ending* at each timestamp. We use the hour whose window
  contains the arrival time (the next timestamp at or after it). Totals are never interpolated.
- Outside the forecast range, or when any needed value is missing, the result is None
  (unavailable). We never extrapolate and never fall back to "Low".
"""

from bisect import bisect_left
from datetime import datetime

from apps.routing.domain.types import HourlyForecast, WeatherConditions


def conditions_at(forecast: HourlyForecast, when: datetime) -> WeatherConditions | None:
    if when.tzinfo is None:
        raise ValueError("Arrival time must be timezone-aware.")
    times = forecast.times
    if not times or when < times[0] or when > times[-1]:
        return None

    upper = bisect_left(times, when)  # first timestamp >= when
    lower = upper if times[upper] == when else upper - 1

    rain = forecast.rain_in_per_hour[upper]
    snow = forecast.snow_in_per_hour[upper]
    wind_low, wind_high = forecast.wind_mph[lower], forecast.wind_mph[upper]
    if rain is None or snow is None or wind_low is None or wind_high is None:
        return None

    if lower == upper:
        wind = wind_low
    else:
        span = (times[upper] - times[lower]).total_seconds()
        fraction = (when - times[lower]).total_seconds() / span
        wind = wind_low + fraction * (wind_high - wind_low)

    return WeatherConditions(wind_mph=wind, rain_in_per_hour=rain, snow_in_per_hour=snow)
