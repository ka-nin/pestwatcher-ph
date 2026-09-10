import { useEffect, useState } from 'react'
import logo from '../../assets/logo.png'
import { fetchWeatherForecast, type LguUser, type WeatherForecast } from '../../lib/api'
import ProvinceMap from './ProvinceMap'
import './Dashboard.css'

interface DashboardProps {
  user: LguUser
  onLogout: () => void
}

const GDD_BASE_TEMP_C = 10
const HUMIDITY_PERSISTENCE_THRESHOLD = 80

function deriveClimateMetrics(weather: WeatherForecast) {
  const gdd = weather.daily.temperature_2m_max.reduce((total, tMax, i) => {
    const tMin = weather.daily.temperature_2m_min[i]
    const meanTemp = (tMax + tMin) / 2
    return total + Math.max(meanTemp - GDD_BASE_TEMP_C, 0)
  }, 0)

  const sevenDayRainfall = weather.daily.precipitation_sum
    .slice(0, 7)
    .reduce((total, mm) => total + mm, 0)

  const nextWeekHumidity = weather.hourly.relative_humidity_2m.slice(0, 24 * 7)
  const humidityPersistence =
    (nextWeekHumidity.filter((rh) => rh >= HUMIDITY_PERSISTENCE_THRESHOLD).length /
      nextWeekHumidity.length) *
    100

  return {
    gdd: Math.round(gdd),
    sevenDayRainfall: Math.round(sevenDayRainfall),
    humidityPersistence: Math.round(humidityPersistence),
  }
}

const navItems = [
  { key: 'status', label: 'Status', active: true },
  { key: 'forecast', label: 'Pest Forecast' },
  { key: 'ipm', label: 'IPM Recommendation' },
  { key: 'climate', label: 'Climate Drivers' },
]

const navIcons: Record<string, React.ReactNode> = {
  status: (
    <path d="M3 12h4l2 6 4-14 2 8h6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  forecast: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20V8" strokeLinecap="round" />
    </>
  ),
  ipm: <circle cx="12" cy="12" r="8" />,
  climate: (
    <path
      d="M6 14a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A4.5 4.5 0 0 1 18 14H6Z"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
}

const statCards = [
  {
    title: 'Peak Pest Day - BPH',
    subtitle: 'Projected peak intensity',
    badge: { label: 'Day 11', tone: 'blue' as const },
    big: { value: '65', unit: 'hoppers/hill' },
    etl: '20 hoppers/hill',
    risk: 'CRITICAL',
    footer: 'May 25 · Projected BPH',
  },
  {
    title: 'Peak Pest Day - RSB',
    subtitle: 'Projected peak intensity',
    badge: { label: 'Day 13', tone: 'blue' as const },
    big: { value: '12%', unit: '% Dead Hearts' },
    etl: '5%',
    risk: 'CRITICAL',
    footer: 'May 27 · Projected RSB',
  },
]

const bphForecast = {
  title: 'Brown Planthopper',
  note: '(Date as of 6:00 am)',
  rows: [
    { range: 'May 17-23', values: [12, 15, 19, 24, 31, 38, 44] },
    { range: 'May 24-30', values: [51, 58, 62, 61, 54, 47, null] },
  ],
}

const rsbForecast = {
  title: 'Rice Stem Borer',
  note: 'ETL: 5% Dead Hearts',
  rows: [
    { range: 'May 17-23', values: [8, 9, 11, 13, 16, 20, 25] },
    { range: 'May 24-30', values: [29, 33, 37, 38, 35, 31, null] },
  ],
}

const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function riskTone(value: number | null) {
  if (value === null) return 'empty'
  if (value < 20) return 'low'
  if (value < 40) return 'mid'
  if (value < 55) return 'high'
  return 'critical'
}

const surveillance = [
  { label: 'BPH Detected', confidence: '89% conf', box: 'teal' },
  { label: 'Healthy', confidence: '97% conf', box: 'teal' },
  { label: 'Dead Hearts', confidence: '82% conf', box: 'red' },
  { label: 'BPH Detected', confidence: '76% conf', box: 'teal' },
]

const riskFactors = [
  { label: 'Humidity', value: 25, direction: 'up' as const },
  { label: 'Visual Symptoms', value: 18, direction: 'up' as const },
  { label: 'GDD', value: 12, direction: 'up' as const },
  { label: 'Rainfall', value: 8, direction: 'up' as const },
  { label: 'Wind Speed', value: -5, direction: 'down' as const },
  { label: 'Natural Predators', value: -3, direction: 'down' as const },
]

const maxRiskFactor = Math.max(...riskFactors.map((f) => Math.abs(f.value)))

function Dashboard({ user, onLogout }: DashboardProps) {
  const [weather, setWeather] = useState<WeatherForecast | null>(null)
  const [weatherError, setWeatherError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchWeatherForecast(user.latitude, user.longitude)
      .then((data) => {
        if (!cancelled) setWeather(data)
      })
      .catch(() => {
        if (!cancelled) setWeatherError('Unable to load live weather data')
      })

    return () => {
      cancelled = true
    }
  }, [user.latitude, user.longitude])

  const climateMetrics = weather ? deriveClimateMetrics(weather) : null

  return (
    <div className="dashboard">
      <div className="dashboard-body">
        <aside className="dashboard-sidebar">
          <div className="sidebar-brand">
            <img src={logo} alt="PestWatcher PH Logo" className="sidebar-logo" />
            <div>
              <div className="sidebar-brand-name">PestWatcher PH</div>
              <div className="sidebar-brand-tagline">Early Warning System</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <a
                key={item.key}
                href="#"
                className={`sidebar-nav-item${item.active ? ' active' : ''}`}
              >
                <svg
                  className="sidebar-nav-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  {navIcons[item.key]}
                </svg>
                {item.label}
              </a>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-province">
              <span className="sidebar-province-label">PROVINCE</span>
              <div className="sidebar-province-value">{user.province}</div>
            </div>
            <div className="sidebar-province">
              <span className="sidebar-province-label">MUNICIPALITY / CITY</span>
              <div className="sidebar-province-value">{user.municipality}</div>
            </div>
            <button type="button" onClick={onLogout} className="sidebar-logout">
              Logout
            </button>
          </div>
        </aside>

        <main className="dashboard-main">
          <header className="dashboard-header">
            <h1>Status</h1>
            <div className="dashboard-user">
              <span className="dashboard-user-label">{user.roleLevel}</span>
              <span className="dashboard-user-name">{user.username}</span>
            </div>
          </header>

          <section className="panel weather-now-panel">
            <div className="panel-head">
              <div>
                <div className="panel-title">Live Weather</div>
                <div className="panel-subtitle">
                  {weather
                    ? `As of ${new Date(weather.current.time).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        timeZone: 'UTC',
                      })} (${weather.location.timezoneAbbreviation})`
                    : `${user.municipality}, ${user.province}`}
                </div>
              </div>
              <span className="badge badge-live">● LIVE</span>
            </div>

            {weatherError ? (
              <p className="stat-card-error">{weatherError}</p>
            ) : weather ? (
              <div className="weather-now-grid">
                <div className="weather-now-item">
                  <svg className="weather-now-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="4" />
                    <path
                      d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
                      strokeLinecap="round"
                    />
                  </svg>
                  <div>
                    <div className="weather-now-label">Temperature</div>
                    <div className="weather-now-value">
                      {Math.round(weather.current.temperature_2m)}°C
                    </div>
                  </div>
                </div>
                <div className="weather-now-item">
                  <svg className="weather-now-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path
                      d="M8 13a4 4 0 0 1 8 0c0 3-4 7-4 7s-4-4-4-7Z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path d="M12 6V2" strokeLinecap="round" />
                  </svg>
                  <div>
                    <div className="weather-now-label">Rainfall</div>
                    <div className="weather-now-value">
                      {weather.current.rain.toFixed(1)}mm
                    </div>
                  </div>
                </div>
                <div className="weather-now-item">
                  <svg className="weather-now-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path
                      d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div>
                    <div className="weather-now-label">Relative Humidity</div>
                    <div className="weather-now-value">
                      {Math.round(weather.current.relative_humidity_2m)}%
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="stat-card-loading">Loading live weather data…</p>
            )}
          </section>

          <section className="stat-row">
            <div className="stat-card">
              <div className="stat-card-head">
                <div>
                  <div className="stat-card-title">Crop Context & Climate Drivers</div>
                  <div className="stat-card-subtitle">Current conditions and growth stage</div>
                </div>
                <span className="badge badge-green">Vegetative</span>
              </div>

              {weatherError ? (
                <p className="stat-card-error">{weatherError}</p>
              ) : climateMetrics ? (
                <div className="stat-card-metrics">
                  <div className="stat-metric">
                    <div className="stat-metric-label">GDD</div>
                    <div className="stat-metric-value">{climateMetrics.gdd}°C-days</div>
                  </div>
                  <div className="stat-metric">
                    <div className="stat-metric-label">7-Day Rainfall</div>
                    <div className="stat-metric-value">{climateMetrics.sevenDayRainfall}mm</div>
                  </div>
                  <div className="stat-metric">
                    <div className="stat-metric-label">Humidity Persistence</div>
                    <div className="stat-metric-value">{climateMetrics.humidityPersistence}%</div>
                  </div>
                </div>
              ) : (
                <p className="stat-card-loading">Loading live weather data…</p>
              )}
            </div>

            {statCards.map((card) => (
              <div className="stat-card" key={card.title}>
                <div className="stat-card-head">
                  <div>
                    <div className="stat-card-title">{card.title}</div>
                    <div className="stat-card-subtitle">{card.subtitle}</div>
                  </div>
                  <span className={`badge badge-${card.badge.tone}`}>{card.badge.label}</span>
                </div>

                <div className="stat-card-big">
                  <span className="stat-card-big-value">{card.big.value}</span>
                  <span className="stat-card-big-unit">{card.big.unit}</span>
                </div>
                <div className="stat-card-etl">
                  ETL: <strong>{card.etl}</strong>
                </div>
                <div className="stat-card-risk-row">
                  <span className="stat-card-risk-label">Risk</span>
                  <span className="badge badge-red">{card.risk}</span>
                </div>
                <div className="stat-card-footer">{card.footer}</div>
              </div>
            ))}
          </section>

          <section className="map-row">
            <div className="panel map-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-title">{user.province} Province Map</div>
                  <div className="panel-subtitle">Risk zones by region (API map placeholder)</div>
                </div>
                <span className="badge badge-green">LIVE</span>
              </div>

              <ProvinceMap
                latitude={user.latitude}
                longitude={user.longitude}
                label={`${user.municipality}, ${user.province}`}
              />

              <div className="map-legend">
                <span className="legend-item">
                  <span className="legend-dot legend-dot-low" /> Low risk
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-dot-mid" /> Medium risk
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-dot-high" /> High risk
                </span>
              </div>
            </div>
          </section>

          <section className="row-2">
            <div className="panel heatmap-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-title">14-Day Forecasting Heatmap</div>
                  <div className="panel-subtitle">
                    Aggregated {user.municipality} forecast · Source: DOST-PAGASA CLSU + BPI-CPMD
                  </div>
                </div>
                <span className="badge badge-neutral">ETL: 50/hill</span>
              </div>

              {[bphForecast, rsbForecast].map((forecast) => (
                <div className="heatmap-block" key={forecast.title}>
                  <div className="heatmap-block-head">
                    <span className="heatmap-block-title">{forecast.title}</span>
                    <span className="heatmap-block-note">{forecast.note}</span>
                  </div>
                  <table className="heatmap-table">
                    <thead>
                      <tr>
                        <th />
                        {days.map((d) => (
                          <th key={d}>{d}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.rows.map((row) => (
                        <tr key={row.range}>
                          <td className="heatmap-range">{row.range}</td>
                          {row.values.map((v, i) => (
                            <td key={i} className={`heatmap-cell heatmap-${riskTone(v)}`}>
                              {v === null ? '-' : `${v}${forecast === rsbForecast ? '%' : ''}`}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          </section>

          <section className="row-3">
            <div className="panel surveillance-panel">
              <div className="panel-head">
                <div className="panel-title">Optical Field Surveillance (ResNet-50)</div>
                <span className="panel-hint">Farmer uploads</span>
              </div>

              <div className="surveillance-grid">
                {surveillance.map((item, i) => (
                  <div className="surveillance-item" key={i}>
                    <div className="surveillance-thumb">
                      <span className={`surveillance-box surveillance-box-${item.box}`} />
                    </div>
                    <div className="surveillance-caption">
                      {item.label} · {item.confidence}
                    </div>
                  </div>
                ))}
              </div>

              <div className="surveillance-footer">
                <span>Last synced: 10:30 AM (PST)</span>
                <a href="#">View All Reports</a>
              </div>
            </div>

            <div className="panel risk-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-title">Risk Factor Attribution - Current Alert</div>
                  <div className="panel-subtitle">SHAP values for the active BPH peak</div>
                </div>
              </div>

              <div className="risk-bars">
                {riskFactors.map((f) => (
                  <div className="risk-bar-row" key={f.label}>
                    <div className="risk-bar-label">
                      {f.direction === 'up' ? '+' : ''}
                      {f.value}% {f.label}
                    </div>
                    <div className="risk-bar-track">
                      <div
                        className={`risk-bar-fill risk-bar-${f.direction}`}
                        style={{ width: `${(Math.abs(f.value) / maxRiskFactor) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

export default Dashboard
