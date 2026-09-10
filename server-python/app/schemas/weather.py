from pydantic import BaseModel, ConfigDict, Field


class WeatherLocation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latitude: float
    longitude: float
    elevation: float
    timezone: str
    timezone_abbreviation: str = Field(alias="timezoneAbbreviation")


class CurrentWeather(BaseModel):
    time: str
    temperature_2m: float
    relative_humidity_2m: float
    precipitation: float
    rain: float


class HourlyWeather(BaseModel):
    time: list[str]
    temperature_2m: list[float]
    relative_humidity_2m: list[float]
    dew_point_2m: list[float]


class DailyWeather(BaseModel):
    time: list[str]
    temperature_2m_max: list[float]
    temperature_2m_min: list[float]
    precipitation_sum: list[float]


class WeatherForecastResponse(BaseModel):
    location: WeatherLocation
    current: CurrentWeather
    hourly: HourlyWeather
    daily: DailyWeather
