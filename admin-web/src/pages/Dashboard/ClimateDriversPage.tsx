import { useEffect, useState } from 'react'
import {
  fetchPestForecastExplanation,
  type ExplanationFeature,
  type GrowthStage,
  type LguUser,
  type WeatherForecast,
} from '../../lib/api'
import { ASSUMED_GROWTH_STAGE } from '../../lib/etl'
import { GDD_BASE_TEMP_C } from '../../lib/climate'
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

const SHAP_PESTS = ['BPH', 'RSB'] as const
const SHAP_GROWTH_STAGE: GrowthStage = ASSUMED_GROWTH_STAGE

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

function formatDay(iso: string | undefined) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

interface ClimateChartProps {
  points: number[]
  dates: string[]
  hoverDay: number | null
  onHover: (day: number | null) => void
}

/** x position (in viewBox units) of a pointer event over the svg. */
function pointerX(e: React.PointerEvent<SVGSVGElement>) {
  const rect = e.currentTarget.getBoundingClientRect()
  return ((e.clientX - rect.left) / rect.width) * CHART_WIDTH
}

function onChartKey(
  e: React.KeyboardEvent<SVGSVGElement>,
  count: number,
  hoverDay: number | null,
  onHover: (day: number | null) => void,
) {
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    onHover(hoverDay === null ? 0 : Math.min(count - 1, hoverDay + 1))
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    onHover(hoverDay === null ? count - 1 : Math.max(0, hoverDay - 1))
  } else if (e.key === 'Escape') {
    onHover(null)
  }
}

function ChartTooltip({ x, y, children }: { x: number; y: number; children: React.ReactNode }) {
  const left = Math.min(88, Math.max(12, (x / CHART_WIDTH) * 100))
  return (
    <div className="climate-tooltip" style={{ left: `${left}%`, top: `${(y / CHART_HEIGHT) * 100}%` }}>
      {children}
    </div>
  )
}

function GddLineChart({
  points,
  dailyGdd,
  dates,
  hoverDay,
  onHover,
}: ClimateChartProps & { dailyGdd: number[] }) {
  const yMax = niceMax(Math.max(...points, 1))
  const plotW = CHART_WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = CHART_HEIGHT - PAD_TOP - PAD_BOTTOM
  const xFor = (i: number) => PAD_LEFT + (i / (points.length - 1)) * plotW
  const yFor = (v: number) => PAD_TOP + plotH - (v / yMax) * plotH

  const path = points.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xFor(i)} ${yFor(v)}`).join(' ')
  const ticks = [0, yMax / 2, yMax]

  const handlePointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const i = Math.round(((pointerX(e) - PAD_LEFT) / plotW) * (points.length - 1))
    onHover(Math.min(points.length - 1, Math.max(0, i)))
  }

  return (
    <div className="climate-chart-wrap">
      <svg
        className="climate-chart-svg climate-chart-interactive"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        tabIndex={0}
        aria-label="Cumulative growing degree days over the 14-day forecast. Use the left and right arrow keys to inspect each day."
        onPointerMove={handlePointer}
        onPointerDown={handlePointer}
        onPointerLeave={() => onHover(null)}
        onBlur={() => onHover(null)}
        onKeyDown={(e) => onChartKey(e, points.length, hoverDay, onHover)}
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

        {hoverDay !== null && (
          <line
            x1={xFor(hoverDay)}
            x2={xFor(hoverDay)}
            y1={PAD_TOP}
            y2={PAD_TOP + plotH}
            className="climate-chart-guide"
          />
        )}

        <path d={path} className="climate-chart-line" />
        {points.map((v, i) => (
          <circle
            key={i}
            cx={xFor(i)}
            cy={yFor(v)}
            r={hoverDay === i ? 5 : 2.5}
            className={`climate-chart-dot${hoverDay === i ? ' climate-chart-dot-active' : ''}`}
          />
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

      {hoverDay !== null && (
        <ChartTooltip x={xFor(hoverDay)} y={yFor(points[hoverDay])}>
          <strong>
            Day {hoverDay + 1} · {formatDay(dates[hoverDay])}
          </strong>
          <span>Cumulative: {points[hoverDay].toFixed(0)} °C-days</span>
          <span>That day: +{(dailyGdd[hoverDay] ?? 0).toFixed(1)}</span>
        </ChartTooltip>
      )}
    </div>
  )
}

function CrfBarChart({ points, dates, hoverDay, onHover }: ClimateChartProps) {
  const yMax = niceMax(Math.max(...points, 1))
  const plotW = CHART_WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = CHART_HEIGHT - PAD_TOP - PAD_BOTTOM
  const slot = plotW / points.length
  const barW = Math.max(slot - 6, 3)
  const yFor = (v: number) => PAD_TOP + plotH - (v / yMax) * plotH
  const ticks = [0, yMax / 2, yMax]

  const handlePointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const i = Math.floor((pointerX(e) - PAD_LEFT) / slot)
    onHover(Math.min(points.length - 1, Math.max(0, i)))
  }

  return (
    <div className="climate-chart-wrap">
      <svg
        className="climate-chart-svg climate-chart-interactive"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        tabIndex={0}
        aria-label="Daily rainfall over the 14-day forecast. Use the left and right arrow keys to inspect each day."
        onPointerMove={handlePointer}
        onPointerDown={handlePointer}
        onPointerLeave={() => onHover(null)}
        onBlur={() => onHover(null)}
        onKeyDown={(e) => onChartKey(e, points.length, hoverDay, onHover)}
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

        {hoverDay !== null && (
          <rect
            x={PAD_LEFT + hoverDay * slot}
            y={PAD_TOP}
            width={slot}
            height={plotH}
            rx={3}
            className="climate-chart-column-highlight"
          />
        )}

        {points.map((v, i) => {
          const x = PAD_LEFT + i * slot + (slot - barW) / 2
          const y = yFor(v)
          const state = hoverDay === null ? '' : hoverDay === i ? ' climate-chart-bar-active' : ' climate-chart-bar-dim'
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={barW}
              height={PAD_TOP + plotH - y}
              rx={2}
              className={`climate-chart-bar${state}`}
            />
          )
        })}

        <text x={PAD_LEFT} y={CHART_HEIGHT - 4} textAnchor="start" className="climate-chart-axis-label">
          Day 1
        </text>
        <text x={CHART_WIDTH - PAD_RIGHT} y={CHART_HEIGHT - 4} textAnchor="end" className="climate-chart-axis-label">
          Day {points.length}
        </text>
      </svg>

      {hoverDay !== null && (
        <ChartTooltip x={PAD_LEFT + hoverDay * slot + slot / 2} y={yFor(points[hoverDay])}>
          <strong>
            Day {hoverDay + 1} · {formatDay(dates[hoverDay])}
          </strong>
          <span>Rainfall: {points[hoverDay].toFixed(1)} mm</span>
        </ChartTooltip>
      )}
    </div>
  )
}

function ClimateIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="status-stat-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </span>
  )
}

function ClimateDriversPage({ user, weather, weatherError, climateMetrics }: ClimateDriversPageProps) {
  // Hovering a day in one chart highlights the same day in the other.
  const [hoverDay, setHoverDay] = useState<number | null>(null)
  const [shapPest, setShapPest] = useState<(typeof SHAP_PESTS)[number]>('BPH')
  const [shapFeatures, setShapFeatures] = useState<ExplanationFeature[]>([])
  const [shapError, setShapError] = useState('')
  const [shapStatus, setShapStatus] = useState<'ok' | 'model_not_loaded' | null>(null)

  useEffect(() => {
    let cancelled = false
    setShapFeatures([])
    setShapStatus(null)
    setShapError('')

    fetchPestForecastExplanation(user.municipality, shapPest, SHAP_GROWTH_STAGE)
      .then((res) => {
        if (cancelled) return
        setShapStatus(res.status)
        setShapFeatures(res.features)
      })
      .catch(() => {
        if (!cancelled) setShapError('Unable to load live SHAP explanation')
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality, shapPest])

  const maxShap = Math.max(1e-6, ...shapFeatures.map((f) => Math.abs(f.value)))

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
      <section className="status-stat-row climate-stat-row">
        <div className="status-stat-card climate-stat-card">
          <ClimateIcon>
            <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0Z" />
          </ClimateIcon>
          {weatherError ? (
            <p className="climate-stat-msg">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="status-stat-value">
                {climateMetrics.gdd}
                <span className="status-stat-unit">°C-days</span>
              </div>
              <div className="status-stat-label">Growing Degree Days (GDD)</div>
              <div className="status-stat-desc">Cumulative over the next 14 days</div>
            </>
          ) : (
            <p className="climate-stat-msg">Loading live weather data…</p>
          )}
        </div>

        <div className="status-stat-card climate-stat-card">
          <ClimateIcon>
            <path d="M16 13v8M8 13v8M12 15v8" />
            <path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25" />
          </ClimateIcon>
          {weatherError ? (
            <p className="climate-stat-msg">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="status-stat-value">
                {climateMetrics.sevenDayRainfall}
                <span className="status-stat-unit">mm</span>
              </div>
              <div className="status-stat-label">Cumulative Rainfall Factor (CRF)</div>
              <div className="status-stat-desc">
                7-day accumulated volume — tracks waterlogging / larval habitat risk
              </div>
            </>
          ) : (
            <p className="climate-stat-msg">Loading live weather data…</p>
          )}
        </div>

        <div className="status-stat-card climate-stat-card">
          <ClimateIcon>
            <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z" />
          </ClimateIcon>
          {weatherError ? (
            <p className="climate-stat-msg">{weatherError}</p>
          ) : climateMetrics ? (
            <>
              <div className="status-stat-value">
                {climateMetrics.humidityPersistence}
                <span className="status-stat-unit">%</span>
              </div>
              <div className="status-stat-label">Humidity Persistence (HP)</div>
              <div className="status-stat-desc">
                Sustained hours ≥80% RH — favorable to pest reproduction above 70%
              </div>
            </>
          ) : (
            <p className="climate-stat-msg">Loading live weather data…</p>
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
                <GddLineChart
                  points={cumulativeGdd}
                  dailyGdd={dailyGdd}
                  dates={weather.daily.time}
                  hoverDay={hoverDay}
                  onHover={setHoverDay}
                />
              </div>
              <div className="climate-chart-block">
                <div className="climate-chart-block-title">
                  <span className="climate-chart-swatch climate-chart-swatch-bar" />
                  Daily Rainfall / CRF (mm)
                </div>
                <CrfBarChart
                  points={dailyCrf}
                  dates={weather.daily.time}
                  hoverDay={hoverDay}
                  onHover={setHoverDay}
                />
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
                Which time-lagged climate variables drive the current {shapPest} outbreak prediction
              </div>
            </div>
            <div className="shap-legend">
              <span>
                <i className="shap-legend-up" /> Pushes risk up
              </span>
              <span>
                <i className="shap-legend-down" /> Pulls risk down
              </span>
            </div>
          </div>

          <div className="reports-filter-tabs shap-pest-tabs">
            {SHAP_PESTS.map((p) => (
              <button
                key={p}
                type="button"
                className={`reports-filter-tab${shapPest === p ? ' active' : ''}`}
                onClick={() => setShapPest(p)}
              >
                {p}
              </button>
            ))}
          </div>

          {shapError ? (
            <p className="stat-card-error">{shapError}</p>
          ) : shapStatus === 'model_not_loaded' ? (
            <p className="stat-card-error">BiLSTM model for {shapPest} not loaded yet.</p>
          ) : shapFeatures.length === 0 ? (
            <p className="stat-card-loading">Computing live SHAP explanation…</p>
          ) : (
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
          )}

          <p className="ipm-footnote">
            Live SHAP attributions from the trained BiLSTM for {shapPest} in {user.municipality} —
            positive values pushed the forecast up, negative values pulled it down.
          </p>
        </div>
      </section>
    </>
  )
}

export default ClimateDriversPage
