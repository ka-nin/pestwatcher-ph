import logo from '../../assets/logo.png'
import type { LguUser } from '../../lib/api'
import './Dashboard.css'

interface DashboardProps {
  user: LguUser
  onLogout: () => void
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
    title: 'Crop Context & Climate Drivers',
    subtitle: 'Current conditions and growth stage',
    badge: { label: 'Vegetative', tone: 'green' as const },
    metrics: [
      { label: 'GDD', value: '485°C-days' },
      { label: '7-Day Rainfall', value: '42mm' },
      { label: 'Humidity Persistence', value: '78%' },
    ],
  },
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
  return (
    <div className="dashboard">
      <div className="dashboard-topbar">Dashboard - Status</div>

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

          <section className="stat-row">
            {statCards.map((card) => (
              <div className="stat-card" key={card.title}>
                <div className="stat-card-head">
                  <div>
                    <div className="stat-card-title">{card.title}</div>
                    <div className="stat-card-subtitle">{card.subtitle}</div>
                  </div>
                  <span className={`badge badge-${card.badge.tone}`}>{card.badge.label}</span>
                </div>

                {'metrics' in card && card.metrics ? (
                  <div className="stat-card-metrics">
                    {card.metrics.map((m) => (
                      <div className="stat-metric" key={m.label}>
                        <div className="stat-metric-label">{m.label}</div>
                        <div className="stat-metric-value">{m.value}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="stat-card-big">
                      <span className="stat-card-big-value">{card.big!.value}</span>
                      <span className="stat-card-big-unit">{card.big!.unit}</span>
                    </div>
                    <div className="stat-card-etl">
                      ETL: <strong>{card.etl}</strong>
                    </div>
                    <div className="stat-card-risk-row">
                      <span className="stat-card-risk-label">Risk</span>
                      <span className="badge badge-red">{card.risk}</span>
                    </div>
                    <div className="stat-card-footer">{card.footer}</div>
                  </>
                )}
              </div>
            ))}
          </section>

          <section className="row-2">
            <div className="panel map-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-title">{user.province} Province Map</div>
                  <div className="panel-subtitle">Risk zones by region (API map placeholder)</div>
                </div>
                <span className="badge badge-green">LIVE</span>
              </div>

              <div className="map-placeholder">
                Map placeholder
                <span className="map-marker map-marker-low" style={{ top: '38%', left: '18%' }}>
                  L
                </span>
                <span className="map-marker map-marker-mid" style={{ top: '48%', left: '46%' }}>
                  M
                </span>
                <span className="map-marker map-marker-high" style={{ top: '68%', left: '68%' }}>
                  H
                </span>
              </div>

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
