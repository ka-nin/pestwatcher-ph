from datetime import datetime, timedelta, timezone

import requests
import openmeteo_requests
from fastapi import APIRouter, HTTPException
from retry_requests import retry

from app.schemas.weather import (
    CurrentWeather,
    DailyWeather,
    HourlyWeather,
    WeatherForecastResponse,
    WeatherLocation,
)

router = APIRouter(prefix="/api/weather", tags=["weather"])

# Plain session + retry (no response caching — requests-cache's serializer has a
# known incompatibility with newer cattrs/typing versions, so keep this simple).
_retry_session = retry(requests.Session(), retries=5, backoff_factor=0.2)
_client = openmeteo_requests.Client(session=_retry_session)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_recent_daily_weather(latitude: float, longitude: float, days: int) -> list[dict]:
    """Past `days` days of daily weather ending today, for feeding the
    BiLSTM's input window (see app/routers/inference.py). Uses the forecast
    API's `past_days` parameter rather than the separate historical/archive
    API — the archive API's ERA5 reanalysis data lags several days behind
    real time, which would make "today" unavailable; `past_days` returns
    near-real-time GFS-based data instead, at the cost of not being the
    same reanalysis dataset used for older historical training data.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "relative_humidity_2m_mean",
        ],
        "timezone": "auto",
        "past_days": days - 1,
        "forecast_days": 1,
    }

    try:
        responses = _client.weather_api(FORECAST_URL, params=params)
        response = responses[0]
    except Exception as exc:  # noqa: BLE001 - surface upstream failure as a 502
        raise HTTPException(status_code=502, detail="Failed to fetch weather data") from exc

    utc_offset = response.UtcOffsetSeconds()
    daily = response.Daily()
    daily_times = _time_range(daily.Time() + utc_offset, daily.TimeEnd() + utc_offset, daily.Interval())

    tmax = list(daily.Variables(0).ValuesAsNumpy())
    tmin = list(daily.Variables(1).ValuesAsNumpy())
    rainfall = list(daily.Variables(2).ValuesAsNumpy())
    humidity = list(daily.Variables(3).ValuesAsNumpy())

    return [
        {
            "date": date.split("T")[0],
            "tmax": float(tmax[i]),
            "tmin": float(tmin[i]),
            "relative_humidity": float(humidity[i]),
            "rainfall": float(rainfall[i]),
        }
        for i, date in enumerate(daily_times)
    ]


def _time_range(start_epoch: int, end_epoch: int, interval_seconds: int) -> list[str]:
    start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    end = datetime.fromtimestamp(end_epoch, tz=timezone.utc)
    step = timedelta(seconds=interval_seconds)

    times = []
    current = start
    while current < end:
        times.append(current.isoformat().replace("+00:00", "Z"))
        current += step
    return times


@router.get("/forecast", response_model=WeatherForecastResponse)
def get_forecast(latitude: float = 15.58, longitude: float = 120.97) -> WeatherForecastResponse:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m"],
        "current": ["temperature_2m", "relative_humidity_2m", "precipitation", "rain"],
        "timezone": "auto",
        "forecast_days": 14,
    }

    try:
        responses = _client.weather_api(FORECAST_URL, params=params)
        response = responses[0]
    except Exception as exc:  # noqa: BLE001 - surface upstream failure as a 502
        raise HTTPException(status_code=502, detail="Failed to fetch weather data") from exc

    utc_offset = response.UtcOffsetSeconds()

    current = response.Current()
    current_time = datetime.fromtimestamp(
        current.Time() + utc_offset, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    hourly = response.Hourly()
    hourly_times = _time_range(
        hourly.Time() + utc_offset, hourly.TimeEnd() + utc_offset, hourly.Interval()
    )

    daily = response.Daily()
    daily_times = _time_range(
        daily.Time() + utc_offset, daily.TimeEnd() + utc_offset, daily.Interval()
    )

    return WeatherForecastResponse(
        location=WeatherLocation(
            latitude=response.Latitude(),
            longitude=response.Longitude(),
            elevation=response.Elevation(),
            timezone=response.Timezone(),
            timezone_abbreviation=response.TimezoneAbbreviation(),
        ),
        current=CurrentWeather(
            time=current_time,
            temperature_2m=current.Variables(0).Value(),
            relative_humidity_2m=current.Variables(1).Value(),
            precipitation=current.Variables(2).Value(),
            rain=current.Variables(3).Value(),
        ),
        hourly=HourlyWeather(
            time=hourly_times,
            temperature_2m=list(hourly.Variables(0).ValuesAsNumpy()),
            relative_humidity_2m=list(hourly.Variables(1).ValuesAsNumpy()),
            dew_point_2m=list(hourly.Variables(2).ValuesAsNumpy()),
        ),
        daily=DailyWeather(
            time=daily_times,
            temperature_2m_max=list(daily.Variables(0).ValuesAsNumpy()),
            temperature_2m_min=list(daily.Variables(1).ValuesAsNumpy()),
            precipitation_sum=list(daily.Variables(2).ValuesAsNumpy()),
        ),
    )
