from datetime import date as date_type
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
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_archive_daily_weather_range(latitude: float, longitude: float, start, end) -> list[dict]:
    """Daily weather for every day from `start` to `end` inclusive (both
    datetime.date), from the ERA5 reanalysis archive rather than the
    near-real-time forecast API's past_days — the same dataset
    ml.config.CLEAN_DAILY_CSV's historical rows came from. Used for dates
    too old for fetch_recent_daily_weather's ~92-day past_days ceiling, or
    where matching the historical dataset's own weather source matters more
    than low-latency recent data (see ml/bilstm/ingest_reports.py and
    GET /api/reports/{report_id}/gap-analysis, both of which analyze a
    report that's typically already days-to-weeks old by the time this runs).

    Returns [] on a fetch failure rather than raising — callers already
    treat "weather missing for this date" as a normal, handleable case
    (see app/routers/inference.py's _window_for_target), not worth a 502.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "relative_humidity_2m_mean",
        ],
        "timezone": "auto",
    }

    try:
        responses = _client.weather_api(ARCHIVE_URL, params=params)
        response = responses[0]
    except Exception:  # noqa: BLE001 - one bad archive fetch shouldn't crash the caller
        return []

    utc_offset = response.UtcOffsetSeconds()
    daily = response.Daily()
    daily_times = _time_range(daily.Time() + utc_offset, daily.TimeEnd() + utc_offset, daily.Interval())

    tmax = list(daily.Variables(0).ValuesAsNumpy())
    tmin = list(daily.Variables(1).ValuesAsNumpy())
    rainfall = list(daily.Variables(2).ValuesAsNumpy())
    humidity = list(daily.Variables(3).ValuesAsNumpy())

    return [
        {
            "date": date_str.split("T")[0],
            "tmax": float(tmax[i]),
            "tmin": float(tmin[i]),
            "relative_humidity": float(humidity[i]),
            "rainfall": float(rainfall[i]),
        }
        for i, date_str in enumerate(daily_times)
    ]


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


def fetch_daily_weather_range(latitude: float, longitude: float, start: date_type, end: date_type) -> list[dict]:
    """Daily weather for every day from `start` to `end` inclusive, for a
    range that may span past, today, and near-future dates — unlike
    fetch_archive_daily_weather_range, which silently returns [] for the
    WHOLE range the moment `end` extends past what the archive API has
    (its ERA5 reanalysis isn't available for future dates, and a future
    end_date makes it reject the request outright, past dates included).

    Used by GET /api/reports/{report_id}/gap-analysis, where a report
    verified recently needs a window reaching ANCHOR_DAYS into the future
    relative to the report's own (near-today) date — exactly the case the
    plain archive range-fetch can't handle. Splits the request at today:
    the past/today portion comes from the forecast API's `past_days`
    (near-real-time, not reanalysis — see fetch_recent_daily_weather's
    docstring for that tradeoff), the future portion from the same API's
    `forecast_days`, then stitches both into one list.
    """
    today = date_type.today()
    if end < today:
        # Fully in the past — the forecast API's past_days only reaches
        # back ~92 days and wouldn't match the archive data training used
        # anyway, so prefer the archive for a fully-historical range.
        return fetch_archive_daily_weather_range(latitude, longitude, start, end)

    past_days = max((today - start).days, 0)
    forecast_days = max((end - today).days + 1, 1)

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
        "past_days": past_days,
        "forecast_days": forecast_days,
    }

    try:
        responses = _client.weather_api(FORECAST_URL, params=params)
        response = responses[0]
    except Exception:  # noqa: BLE001 - treat a fetch failure as "no weather for this range"
        return []

    utc_offset = response.UtcOffsetSeconds()
    daily = response.Daily()
    daily_times = _time_range(daily.Time() + utc_offset, daily.TimeEnd() + utc_offset, daily.Interval())

    tmax = list(daily.Variables(0).ValuesAsNumpy())
    tmin = list(daily.Variables(1).ValuesAsNumpy())
    rainfall = list(daily.Variables(2).ValuesAsNumpy())
    humidity = list(daily.Variables(3).ValuesAsNumpy())

    return [
        {
            "date": date_str.split("T")[0],
            "tmax": float(tmax[i]),
            "tmin": float(tmin[i]),
            "relative_humidity": float(humidity[i]),
            "rainfall": float(rainfall[i]),
        }
        for i, date_str in enumerate(daily_times)
        if start.isoformat() <= date_str.split("T")[0] <= end.isoformat()
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
