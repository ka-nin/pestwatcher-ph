import { Router } from 'express';
import { fetchWeatherApi } from 'openmeteo';

const router = Router();

router.get('/forecast', async (req, res) => {
  const latitude = Number(req.query.latitude ?? 15.58);
  const longitude = Number(req.query.longitude ?? 120.97);

  if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return res.status(400).json({ message: 'latitude and longitude must be numbers' });
  }

  const params = {
    latitude,
    longitude,
    daily: ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum'],
    hourly: ['temperature_2m', 'relative_humidity_2m', 'dew_point_2m'],
    current: ['temperature_2m', 'relative_humidity_2m', 'precipitation', 'rain'],
    timezone: 'auto',
    forecast_days: 14,
  };
  const url = 'https://api.open-meteo.com/v1/forecast';

  try {
    const responses = await fetchWeatherApi(url, params);
    const response = responses[0];

    const utcOffsetSeconds = response.utcOffsetSeconds();
    const current = response.current()!;
    const hourly = response.hourly()!;
    const daily = response.daily()!;

    const weatherData = {
      location: {
        latitude: response.latitude(),
        longitude: response.longitude(),
        elevation: response.elevation(),
        timezone: response.timezone(),
        timezoneAbbreviation: response.timezoneAbbreviation(),
      },
      current: {
        time: new Date((Number(current.time()) + utcOffsetSeconds) * 1000),
        temperature_2m: current.variables(0)!.value(),
        relative_humidity_2m: current.variables(1)!.value(),
        precipitation: current.variables(2)!.value(),
        rain: current.variables(3)!.value(),
      },
      hourly: {
        time: Array.from(
          { length: (Number(hourly.timeEnd()) - Number(hourly.time())) / hourly.interval() },
          (_, i) => new Date((Number(hourly.time()) + i * hourly.interval() + utcOffsetSeconds) * 1000),
        ),
        temperature_2m: Array.from(hourly.variables(0)!.valuesArray()!),
        relative_humidity_2m: Array.from(hourly.variables(1)!.valuesArray()!),
        dew_point_2m: Array.from(hourly.variables(2)!.valuesArray()!),
      },
      daily: {
        time: Array.from(
          { length: (Number(daily.timeEnd()) - Number(daily.time())) / daily.interval() },
          (_, i) => new Date((Number(daily.time()) + i * daily.interval() + utcOffsetSeconds) * 1000),
        ),
        temperature_2m_max: Array.from(daily.variables(0)!.valuesArray()!),
        temperature_2m_min: Array.from(daily.variables(1)!.valuesArray()!),
        precipitation_sum: Array.from(daily.variables(2)!.valuesArray()!),
      },
    };

    res.json(weatherData);
  } catch (err) {
    console.error('Open-Meteo request failed', err);
    res.status(502).json({ message: 'Failed to fetch weather data' });
  }
});

export default router;
