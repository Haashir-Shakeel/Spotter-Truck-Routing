from datetime import UTC, datetime, timedelta

import pytest

from apps.routing.domain.types import HourlyForecast
from apps.routing.services.weather_interpolation import conditions_at

T0 = datetime(2026, 11, 13, 12, tzinfo=UTC)


def forecast(
    wind: list[float | None],
    rain: list[float | None] | None = None,
    snow: list[float | None] | None = None,
) -> HourlyForecast:
    n = len(wind)
    return HourlyForecast(
        lon=0.0,
        lat=0.0,
        times=tuple(T0 + timedelta(hours=i) for i in range(n)),
        wind_mph=tuple(wind),
        rain_in_per_hour=tuple(rain or [0.0] * n),
        snow_in_per_hour=tuple(snow or [0.0] * n),
    )


def test_exact_hour_uses_that_hour() -> None:
    result = conditions_at(forecast([10, 20, 30], rain=[0.0, 0.2, 0.4]), T0 + timedelta(hours=1))

    assert result is not None
    assert result.wind_mph == 20
    assert result.rain_in_per_hour == 0.2


def test_wind_is_interpolated_between_hours() -> None:
    result = conditions_at(forecast([10, 30]), T0 + timedelta(minutes=15))
    assert result is not None
    assert result.wind_mph == pytest.approx(15)


def test_precipitation_uses_the_hour_window_containing_arrival() -> None:
    # Value at 13:00 is the total for 12:00-13:00, so a 12:40 arrival gets it (not interpolated).
    result = conditions_at(
        forecast([0, 0], rain=[0.05, 0.6], snow=[0.0, 1.2]), T0 + timedelta(minutes=40)
    )

    assert result is not None
    assert result.rain_in_per_hour == 0.6
    assert result.snow_in_per_hour == 1.2


def test_each_checkpoint_gets_weather_for_its_own_eta() -> None:
    series = forecast([5, 15, 25, 35, 45])
    early = conditions_at(series, T0)
    late = conditions_at(series, T0 + timedelta(hours=4))

    assert early is not None and late is not None
    assert (early.wind_mph, late.wind_mph) == (5, 45)


@pytest.mark.parametrize(
    "offset", [timedelta(minutes=-1), timedelta(hours=2, minutes=1)], ids=["before", "after"]
)
def test_outside_forecast_range_is_unavailable(offset: timedelta) -> None:
    assert conditions_at(forecast([10, 20, 30]), T0 + offset) is None


@pytest.mark.parametrize(
    "series",
    [
        forecast([10, None]),
        forecast([None, 10]),
        forecast([10, 10], rain=[0.0, None]),
        forecast([10, 10], snow=[0.0, None]),
    ],
)
def test_missing_values_are_unavailable_never_low(series: HourlyForecast) -> None:
    assert conditions_at(series, T0 + timedelta(minutes=30)) is None


def test_empty_forecast_is_unavailable() -> None:
    assert conditions_at(forecast([]), T0) is None


def test_naive_time_rejected() -> None:
    with pytest.raises(ValueError):
        conditions_at(forecast([10]), datetime(2026, 11, 13, 12))
