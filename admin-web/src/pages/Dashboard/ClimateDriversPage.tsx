import type { LguUser, WeatherForecast } from '../../lib/api'
import './ClimateDriversPage.css'

interface ClimateMetrics {
  gdd: number
  sevenDayRainfall: number
  humidityPersistence: number
}

interface ClimateDriversPageProps {
  user: LguUser
  weather: WeatherForecast | null
  weatherError: string
  climateMetrics: ClimateMetrics | null
}

const GDD_BASE_TEMP_C = 10

// Static placeholder — SHAP values require a trained model, not weather data.
const shapFeatures = [
  { label: 'Day -4 High Humidity Persistence', value: 0.34 },
  { label: 'Day -7 GDD Spike', value: 0.22 },
  { label: 'Day -2 Night Temperature > 25°C', value: 0.18 },
  { label: 'Day -10 CRF Surge (>30mm)', value: 0.12 },
  { label: 'Day -1 Wind Speed > 15 km/h', value: -0.08 },
  { label: 'Day -5 Solar Radiation Drop', value: -0.15 },
  { label: 'Day -3 Rainfall Break (dry spell)', value: -0.19 },
]
const maxShap = Math.max(...shapFeatures.map((f) => Math.abs(f.value)))

const CHART_WIDTH = 340
const CHART_HEIGHT = 130
const PAD_LEFT = 32
const PAD_RIGHT = 8
const PAD_TOP = 10
const PAD_BOTTOM = 20

function niceMax(value: number) {
  if (value <= 0) return 10
  const magnitude = 10 ** Math.floor(Math.log10(value))
  return Math.ceil((value * 1.15) / magnitude) * magnitude
}

function GddLineChart({ points }: { points: number[] }) {
  const yMax = niceMax(Math.max(...points, 1))
  const plotW = CHART_WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = CHART_HEIGHT - PAD_TOP - PAD_BOTTOM
  const xFor = (i: number) => PAD_LEFT + (i / (points.length - 1)) * plotW
  const yFor = (v: number) => PAD_TOP + plotH - (v / yMax) * plotH

  const path = points.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xFor(i)} ${yFor(v)}`).join(' ')
  const ticks = [0, yMax / 2, yMax]

  return (
    <svg
      className="climate-chart-svg"
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label="Cumulative growing degree days over the 14-day forecast"
    >
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={PAD_LEFT}
            x2={CHART_WIDTH - PAD_RIGHT}
            y1={yFor(t)}
            y2={yFor(t)}
            className="climate-chart-gridline"
          />
          <text x={PAD_LEFT - 6} y={yFor(t) + 3} textAnchor="end" className="climate-chart-axis-label">
            {Math.round(t)}
          </text>
        </g>
      ))}

      <path d={path} className="climate-chart-line" />
      {points.map((v, i) => (
        <circle key={i} cx={xFor(i)} cy={yFor(v)} r={2.5} className="climate-chart-dot" />
      ))}

      <text x={xFor(0)} y={yFor(points[0]) - 8} textAnchor="start" className="climate-chart-value-label">
        {points[0].toFixed(0)}
      </text>
      <text
        x={xFor(points.length - 1)}
        y={yFor(points[points.length - 1]) - 8}
        textAnchor="end"
        className="climate-chart-value-label"
      >
        {points[points.length - 1].toFixed(0)}
      </text>

      <text x={xFor(0)} y={CHART_HEIGHT - 4} textAnchor="start" className="climate-chart-axis-label">
        Day 1
      </text>
      <text
        x={xFor(points.length - 1)}
        y={CHART_HEIGHT - 4}
        textAnchor="end"
        className="climate-chart-axis-label"
      >
        Day {points.length}
      </text>
    </svg>
  )
}

function CrfBarChart({ points }: { points: number[] }) {
  const yMax = niceMax(Math.max(...points, 1))
  const plotW = CHART_WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = CHART_HEIGHT - PAD_TOP - PAD_BOTTOM
  const slot = plotW / points.length
  const barW = Math.max(slot - 6, 3)
  const yFor = (v: number) => PAD_TOP + plotH - (v / yMax) * plotH
  const ticks = [0, yMax / 2, yMax]

  return (
    <svg
      className="climate-chart-svg"
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label="Daily rainfall over the 14-day forecast"
    >
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={PAD_LEFT}
            x2={CHART_WIDTH - PAD_RIGHT}
            y1={yFor(t)}
            y2={yFor(t)}
            className="climate-chart-gridline"
          />
          <text x={PAD_LEFT - 6} y={yFor(t) + 3} textAnchor="end" className="climate-chart-axis-label">
            {Math.round(t)}
          </text>
        </g>
      ))}

      {points.map((v, i) => {
        const x = PAD_LEFT + i * slot + (slot - barW) / 2
        const y = yFor(v)
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barW}
            height={PAD_TOP + plotH - y}
            rx={2}
            className="climate-chart-bar"
          >
            <title>{`Day ${i + 1}: ${v.toFixed(1)}mm`}</title>
          </rect>
        )
      })}

      <text x={PAD_LEFT} y={CHART_HEIGHT - 4} textAnchor="start" className="climate-chart-axis-label">
        Day 1
      </text>
      <text x={CHART_WIDTH - PAD_RIGHT} y={CHART_HEIGHT - 4} textAnchor="end" className="climate-chart-axis-label">
        Day {points.length}
      </text>
    </svg>
  )
}

function ClimateDriversPage({ user, weather, weatherError, climateMetrics }: ClimateDriversPageProps) {
  const dailyGdd = weather
    ? weather.daily.temperature_2m_max.map((tMax, i) => {
        const tMin = weather.daily.temperature_2m_min[i]
        return Math.max((tMax + tMin) / 2 - GDD_BASE_TEMP_C, 0)
      })
    : []
  const cumulativeGdd = dailyGdd.reduce<number[]>((acc, v, i) => {
    acc.push((acc[i - 1] ?? 0) + v)
    return acc
  }, [])
  const dailyCrf = weather?.daily.precipitation_sum ?? []

  return (
    <>
      <section className="stat-row">
        <div className="stat-card">
          <div className="stat-card-head">
            <div>
              <div className="stat-card-title">Growing Degree Days (GDD)</div>
            </div>
            <span className="badge badge-green">14-DAY</span>
          </div>
          {weatherError ? (
            <p className="stat-card-error">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="stat-card-big">
                <span className="stat-card-big-value">{climateMetrics.gdd}</span>
                <span className="stat-card-big-unit">°C-days</span>
              </div>
              <div className="stat-card-footer">Cumulative over the next 14 days</div>
            </>
          ) : (
            <p className="stat-card-loading">Loading live weather data…</p>
          )}
        </div>

        <div className="stat-card">
          <div className="stat-card-head">
            <div>
              <div className="stat-card-title">Cumulative Rainfall Factor (CRF)</div>
            </div>
            <span className="badge badge-green">7D</span>
          </div>
          {weatherError ? (
            <p className="stat-card-error">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="stat-card-big">
                <span className="stat-card-big-value">{climateMetrics.sevenDayRainfall}</span>
                <span className="stat-card-big-unit">mm</span>
              </div>
              <div className="stat-card-footer">
                7-day accumulated volume — tracks waterlogging / larval habitat risk
              </div>
            </>
          ) : (
            <p className="stat-card-loading">Loading live weather data…</p>
          )}
        </div>

        <div className="stat-card">
          <div className="stat-card-head">
            <div>
              <div className="stat-card-title">Humidity Persistence (HP)</div>
            </div>
            <span className="badge badge-green">RH</span>
          </div>
          {weatherError ? (
            <p className="stat-card-error">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="stat-card-big">
                <span className="stat-card-big-value">{climateMetrics.humidityPersistence}</span>
                <span className="stat-card-big-unit">%</span>
              </div>
              <div className="stat-card-footer">
                Sustained hours ≥80% RH — favorable to pest reproduction above 70%
              </div>
            </>
          ) : (
            <p className="stat-card-loading">Loading live weather data…</p>
          )}
        </div>
      </section>

      <section className="row-2">
        <div className="panel climate-chart-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">14-Day Climate Feature Forecast</div>
              <div className="panel-subtitle">
                Daily GDD accumulation and rainfall, live from Open-Meteo for {user.municipality}
              </div>
            </div>
          </div>

          {weatherError ? (
            <p className="stat-card-error">{weatherError}</p>
          ) : weather ? (
            <div className="climate-chart-stack">
              <div className="climate-chart-block">
                <div className="climate-chart-block-title">
                  <span className="climate-chart-swatch climate-chart-swatch-line" />
                  Cumulative GDD (°C-days)
                </div>
                <GddLineChart points={cumulativeGdd} />
              </div>
              <div className="climate-chart-block">
                <div className="climate-chart-block-title">
                  <span className="climate-chart-swatch climate-chart-swatch-bar" />
                  Daily Rainfall / CRF (mm)
                </div>
                <CrfBarChart points={dailyCrf} />
              </div>
            </div>
          ) : (
            <p className="stat-card-loading">Loading live weather data…</p>
          )}
        </div>
      </section>

      <section className="row-2">
        <div className="panel shap-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">Feature Influence on Current Risk (SHAP Explanations)</div>
              <div className="panel-subtitle">
                Which time-lagged climate variables drive the current BPH outbreak prediction
              </div>
            </div>
          </div>

          <div className="feature-bars">
            {shapFeatures.map((f) => (
              <div className="feature-bar-row" key={f.label}>
                <div className="feature-bar-label">{f.label}</div>
                <div className="feature-bar-track">
                  <div
                    className={`feature-bar-fill ${f.value >= 0 ? 'feature-bar-up' : 'feature-bar-down'}`}
                    style={{ width: `${(Math.abs(f.value) / maxShap) * 100}%` }}
                  />
                </div>
                <div className={`feature-bar-value ${f.value >= 0 ? 'feature-bar-up-text' : 'feature-bar-down-text'}`}>
                  {f.value >= 0 ? '+' : ''}
                  {f.value.toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          <p className="ipm-footnote">Placeholder SHAP values — not yet wired to a trained model.</p>
        </div>
      </section>
    </>
  )
}

export default ClimateDriversPage
