import { useEffect, useState } from 'react'
import logo from '../../assets/logo.png'
import { fetchWeatherForecast, type LguUser, type WeatherForecast } from '../../lib/api'
import StatusPage from './StatusPage'
import IpmPage from './IpmPage'
import ClimateDriversPage from './ClimateDriversPage'
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

type PageKey = 'status' | 'forecast' | 'ipm' | 'climate'

const navItems: { key: PageKey; label: string }[] = [
  { key: 'status', label: 'Status' },
  { key: 'forecast', label: 'Pest Forecast' },
  { key: 'ipm', label: 'IPM Recommendation' },
  { key: 'climate', label: 'Climate Drivers' },
]

const navIcons: Record<PageKey, React.ReactNode> = {
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

function Dashboard({ user, onLogout }: DashboardProps) {
  const [activePage, setActivePage] = useState<PageKey>('status')
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
  const activeLabel = navItems.find((item) => item.key === activePage)?.label ?? 'Status'

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
                onClick={(e) => {
                  e.preventDefault()
                  setActivePage(item.key)
                }}
                className={`sidebar-nav-item${activePage === item.key ? ' active' : ''}`}
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
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path
                  d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path d="M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Logout
            </button>
          </div>
        </aside>

        <main className="dashboard-main">
          <header className="dashboard-header">
            <h1>{activeLabel}</h1>
            <div className="dashboard-user">
              <span className="dashboard-user-label">{user.roleLevel}</span>
              <span className="dashboard-user-name">{user.username}</span>
            </div>
          </header>

          {activePage === 'status' && (
            <StatusPage
              user={user}
              weather={weather}
              weatherError={weatherError}
              climateMetrics={climateMetrics}
            />
          )}

          {activePage === 'ipm' && <IpmPage user={user} />}

          {activePage === 'climate' && (
            <ClimateDriversPage
              user={user}
              weather={weather}
              weatherError={weatherError}
              climateMetrics={climateMetrics}
            />
          )}

          {activePage === 'forecast' && (
            <section className="panel coming-soon-panel">
              <div className="panel-title">{activeLabel}</div>
              <p className="panel-subtitle">This section hasn't been built yet.</p>
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default Dashboard
