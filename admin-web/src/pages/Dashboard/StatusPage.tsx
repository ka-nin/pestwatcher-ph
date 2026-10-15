import { useEffect, useState } from 'react'
import {
  API_BASE_URL,
  fetchMunicipalitiesRisk,
  fetchPestForecastTrajectory,
  fetchProvinceReports,
  type GrowthStage,
  type LguUser,
  type MunicipalityOverview,
  type ReportRecord,
  type RiskLevel,
  type TrajectoryPoint,
  type WeatherForecast,
} from '../../lib/api'
import { ASSUMED_GROWTH_STAGE, etlBandFor, RISK_TONE } from '../../lib/etl'
import DayDetailModal from '../../components/DayDetailModal'
import ProvinceMap from './ProvinceMap'

interface ClimateMetrics {
  gdd: number
  sevenDayRainfall: number
  humidityPersistence: number
}

interface StatusPageProps {
  user: LguUser
  weather: WeatherForecast | null
  weatherError: string
  climateMetrics: ClimateMetrics | null
  onNavigateToReports: () => void
}

const TRAJECTORY_DAYS = 14
const ACTIVE_GROWTH_STAGE: GrowthStage = ASSUMED_GROWTH_STAGE

const peakCardMeta = [
  {
    key: 'bph' as const,
    pest: 'BPH' as const,
    title: 'Peak Pest Day - BPH',
    unit: 'hoppers/hill',
    etlSuffix: ' hoppers/hill',
    format: (v: number) => Math.round(v).toString(),
  },
  {
    key: 'rsb' as const,
    pest: 'RSB' as const,
    title: 'Peak Pest Day - RSB',
    unit: '% Dead Hearts',
    etlSuffix: '%',
    format: (v: number) => `${v.toFixed(1)}%`,
  },
]

const heatmapMeta = [
  {
    key: 'bph' as const,
    pest: 'BPH' as const,
    title: 'Brown Planthopper',
    unitLabel: 'hoppers/hill',
    formatValue: (v: number) => Math.round(v).toString(),
  },
  {
    key: 'rsb' as const,
    pest: 'RSB' as const,
    title: 'Rice Stem Borer',
    unitLabel: '% Dead Hearts',
    formatValue: (v: number) => `${v.toFixed(1)}%`,
  },
]

function formatDateLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function findPeak(points: TrajectoryPoint[]): TrajectoryPoint | null {
  if (points.length === 0) return null
  return points.reduce((max, p) => (p.predicted_value > max.predicted_value ? p : max), points[0])
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const HEATMAP_TONE: Record<RiskLevel, 'low' | 'mid' | 'high'> = {
  Low: 'low',
  Medium: 'mid',
  High: 'high',
}

function buildWeeklyRows(points: TrajectoryPoint[]): { range: string; cells: (TrajectoryPoint | null)[] }[] {
  if (points.length === 0) return []

  const cells: (TrajectoryPoint | null)[] = []
  const leadingBlanks = new Date(points[0].date).getDay() // 0=Sun..6=Sat
  for (let i = 0; i < leadingBlanks; i++) cells.push(null)
  cells.push(...points)
  while (cells.length % 7 !== 0) cells.push(null)

  const rows = []
  for (let i = 0; i < cells.length; i += 7) {
    const week = cells.slice(i, i + 7)
    const known = week.filter((c): c is TrajectoryPoint => c !== null)
    const range = known.length
      ? `${formatDateLabel(known[0].date)} - ${formatDateLabel(known[known.length - 1].date)}`
      : ''
    rows.push({ range, cells: week })
  }
  return rows
}

function formatSyncedAt(iso: string) {
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function LiveBadge() {
  return (
    <span className="badge badge-green status-live-badge">
      <span className="status-live-dot" />
      LIVE
    </span>
  )
}

function StatusIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="status-stat-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </span>
  )
}

function RiskBadge({ level }: { level: keyof typeof RISK_TONE | null | undefined }) {
  if (!level) return <span className="badge badge-neutral">N/A</span>
  return <span className={`badge badge-${RISK_TONE[level]}`}>{level.toUpperCase()}</span>
}

function StatusPage({ user, weather, weatherError, climateMetrics, onNavigateToReports }: StatusPageProps) {
  const [trajectories, setTrajectories] = useState<Partial<Record<'bph' | 'rsb', TrajectoryPoint[]>>>({})
  const [forecastError, setForecastError] = useState('')
  const [selectedCell, setSelectedCell] = useState<{
    key: 'bph' | 'rsb'
    point: TrajectoryPoint
  } | null>(null)
  const [reports, setReports] = useState<ReportRecord[]>([])
  const [municipalityRisk, setMunicipalityRisk] = useState<MunicipalityOverview[] | null>(null)
  const [municipalityRiskError, setMunicipalityRiskError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchMunicipalitiesRisk()
      .then((res) => {
        if (!cancelled) setMunicipalityRisk(res.municipalities)
      })
      .catch(() => {
        if (!cancelled) setMunicipalityRiskError('Unable to load municipality risk status')
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    fetchProvinceReports(user.province)
      .then((data) => {
        if (!cancelled) setReports(data)
      })
      .catch(() => {
        // Non-critical for this panel — the map just shows no report pins.
      })

    return () => {
      cancelled = true
    }
  }, [user.province])

  useEffect(() => {
    let cancelled = false

    Promise.all(
      peakCardMeta.map((meta) =>
        fetchPestForecastTrajectory(user.municipality, meta.pest, ACTIVE_GROWTH_STAGE, TRAJECTORY_DAYS).then(
          (res) => [meta.key, res.status === 'ok' ? res.points : []] as const,
        ),
      ),
    )
      .then((results) => {
        if (cancelled) return
        setTrajectories(Object.fromEntries(results))
      })
      .catch(() => {
        if (!cancelled) setForecastError('Unable to load live pest forecast')
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality])

  const peaks: Partial<Record<'bph' | 'rsb', TrajectoryPoint>> = {
    bph: findPeak(trajectories.bph ?? []) ?? undefined,
    rsb: findPeak(trajectories.rsb ?? []) ?? undefined,
  }

  // Real recent AI reads from farmer-submitted photos — reports.ai_pest_detected/
  // ai_confidence are set server-side by the ResNet-50 classifier at submission
  // time (see server-python/app/routers/reports.py). `reports` is already
  // sorted most-recent-first by the API.
  const recentSurveillance = reports.filter((r) => r.photo_url && r.ai_confidence != null).slice(0, 4)
  const lastSyncedAt = reports.find((r) => r.photo_url)?.submitted_at

  return (
    <>
      <section className="panel status-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Live Weather · {user.municipality}</div>
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
          <LiveBadge />
        </div>

        {weatherError ? (
          <p className="stat-card-error">{weatherError}</p>
        ) : weather ? (
          <div className="status-stat-row">
            <div className="status-stat-card">
              <StatusIcon>
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </StatusIcon>
              <div className="status-stat-value">{Math.round(weather.current.temperature_2m)}°C</div>
              <div className="status-stat-label">Temperature</div>
            </div>
            <div className="status-stat-card">
              <StatusIcon>
                <path d="M8 13a4 4 0 0 1 8 0c0 3-4 7-4 7s-4-4-4-7Z" />
                <path d="M12 6V2" />
              </StatusIcon>
              <div className="status-stat-value">{weather.current.rain.toFixed(1)}mm</div>
              <div className="status-stat-label">Rainfall</div>
            </div>
            <div className="status-stat-card">
              <StatusIcon>
                <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z" />
              </StatusIcon>
              <div className="status-stat-value">{Math.round(weather.current.relative_humidity_2m)}%</div>
              <div className="status-stat-label">Relative Humidity</div>
            </div>
          </div>
        ) : (
          <p className="stat-card-loading">Loading live weather data…</p>
        )}
      </section>

      <section className="panel municipality-risk-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Municipality Risk Status</div>
            <div className="panel-subtitle">Live BPH / RSB risk across every municipality on file</div>
          </div>
          <LiveBadge />
        </div>

        {municipalityRiskError ? (
          <p className="stat-card-error">{municipalityRiskError}</p>
        ) : municipalityRisk === null ? (
          <p className="stat-card-loading">Loading municipality risk status…</p>
        ) : (
          <div className="status-table-wrap">
            <table className="status-table">
              <thead>
                <tr>
                  <th>Municipality</th>
                  <th>Province</th>
                  <th>BPH (hoppers/hill)</th>
                  <th>BPH Risk</th>
                  <th>RSB (% Dead Hearts)</th>
                  <th>RSB Risk</th>
                </tr>
              </thead>
              <tbody>
                {municipalityRisk.map((row) => {
                  const isOwn = row.municipality === user.municipality
                  return (
                    <tr key={row.municipality} className={isOwn ? 'is-own' : undefined}>
                      <td>
                        <span className="status-table-name">
                          {row.municipality}
                          {isOwn && <span className="municipality-risk-you">Your area</span>}
                        </span>
                      </td>
                      <td>{row.province}</td>
                      <td>{row.bph.predicted_value != null ? Math.round(row.bph.predicted_value) : '—'}</td>
                      <td>
                        <RiskBadge level={row.bph.risk_level} />
                      </td>
                      <td>{row.rsb.predicted_value != null ? row.rsb.predicted_value.toFixed(1) : '—'}</td>
                      <td>
                        <RiskBadge level={row.rsb.risk_level} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="stat-row">
        <div className="stat-card">
          <div className="stat-card-head">
            <div className="stat-card-headleft">
              <span className="stat-icon stat-icon-green" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22V12" />
                  <path d="M12 12c0-4 3-7 8-7 0 5-3 8-8 8Z" />
                  <path d="M12 15c0-3-2.5-5.5-7-5.5 0 4.5 2.5 6.5 7 6.5Z" />
                </svg>
              </span>
              <div>
                <div className="stat-card-title">Crop Context & Climate Drivers</div>
                <div className="stat-card-subtitle">Current conditions and growth stage</div>
              </div>
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

        {forecastError && <p className="stat-card-error">{forecastError}</p>}
        {peakCardMeta.map((meta) => {
          const peak = peaks[meta.key]
          const tone = peak ? RISK_TONE[peak.risk_level] : 'blue'

          const highMin = etlBandFor(meta.key, ACTIVE_GROWTH_STAGE).highMin
          const pct = peak ? Math.min(100, Math.round((peak.predicted_value / highMin) * 100)) : 0

          return (
            <div className="stat-card" key={meta.key}>
              <div className="stat-card-head">
                <div className="stat-card-headleft">
                  <span className={`stat-icon stat-icon-${tone}`} aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m3 17 6-6 4 4 8-8" />
                      <path d="M15 7h6v6" />
                    </svg>
                  </span>
                  <div>
                    <div className="stat-card-title">{meta.title}</div>
                    <div className="stat-card-subtitle">Projected peak intensity</div>
                  </div>
                </div>
                <span className="badge badge-blue">{peak ? formatDateLabel(peak.date) : '…'}</span>
              </div>

              <div className="stat-card-big">
                <span className="stat-card-big-value">{peak ? meta.format(peak.predicted_value) : '—'}</span>
                <span className="stat-card-big-unit">{meta.unit}</span>
              </div>

              <div className="etl-meter">
                <div className="etl-meter-bar">
                  <span className={`etl-meter-fill etl-${tone}`} style={{ width: `${pct}%` }} />
                </div>
                <div className="etl-meter-labels">
                  <span>{peak ? `${pct}% of ETL` : '…'}</span>
                  <span>
                    ETL {highMin}
                    {meta.etlSuffix}
                  </span>
                </div>
              </div>

              <div className="stat-card-risk-row">
                <span className="stat-card-risk-label">Risk</span>
                <span className={`badge badge-${tone}`}>{peak ? peak.risk_level.toUpperCase() : 'LOADING…'}</span>
              </div>
              <div className="stat-card-footer">
                {peak ? `${formatDateLabel(peak.date)} · Projected ${meta.pest}` : 'Loading forecast…'}
              </div>
            </div>
          )
        })}
      </section>

      <section className="map-row">
        <div className="panel map-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">{user.province} Province Map</div>
              <div className="panel-subtitle">Farmer-reported sightings across the province, pinned by risk — click a pin to zoom in</div>
            </div>
            <LiveBadge />
          </div>

          <ProvinceMap
            latitude={user.latitude}
            longitude={user.longitude}
            label={`${user.municipality}, ${user.province}`}
            province={user.province}
            reports={reports}
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
            <span className="legend-item">
              <span className="legend-dot legend-dot-verified" /> Verified
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-dot-pending" /> Pending review
            </span>
            <span className="legend-item">
              <span className="legend-line-boundary" /> {user.province} boundary
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
                {user.municipality} forecast · Source: DOST-PAGASA CLSU + BPI-CPMD
              </div>
            </div>
            <LiveBadge />
          </div>

          <div className="heatmap-legend">
            <span><i className="heatmap-low" /> Low</span>
            <span><i className="heatmap-mid" /> Medium</span>
            <span><i className="heatmap-high" /> High</span>
            <span className="heatmap-legend-hint">Click a day for details</span>
          </div>

          {heatmapMeta.map((meta) => {
            const rows = buildWeeklyRows(trajectories[meta.key] ?? [])
            return (
              <div className="heatmap-block" key={meta.key}>
                <div className="heatmap-block-head">
                  <span className="heatmap-block-title">{meta.title}</span>
                  <span className="heatmap-block-note">
                    ETL: {etlBandFor(meta.key, ACTIVE_GROWTH_STAGE).highMin}
                    {meta.pest === 'RSB' ? '% Dead Hearts' : ' hoppers/hill'}
                  </span>
                </div>
                {rows.length === 0 ? (
                  <p className="stat-card-loading">Loading forecast…</p>
                ) : (
                  <table className="heatmap-table">
                    <thead>
                      <tr>
                        <th />
                        {WEEKDAY_LABELS.map((d) => (
                          <th key={d}>{d}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          <td className="heatmap-range">{row.range}</td>
                          {row.cells.map((cell, i) => (
                            <td
                              key={i}
                              className={`heatmap-cell heatmap-${cell ? HEATMAP_TONE[cell.risk_level] : 'empty'}${
                                cell ? ' heatmap-cell-clickable' : ''
                              }`}
                              role={cell ? 'button' : undefined}
                              tabIndex={cell ? 0 : undefined}
                              onClick={cell ? () => setSelectedCell({ key: meta.key, point: cell }) : undefined}
                              onKeyDown={
                                cell
                                  ? (e) => {
                                      if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault()
                                        setSelectedCell({ key: meta.key, point: cell })
                                      }
                                    }
                                  : undefined
                              }
                            >
                              {cell ? meta.formatValue(cell.predicted_value) : '-'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="row-3">
        <div className="panel surveillance-panel surveillance-panel-full">
          <div className="panel-head">
            <div className="panel-title">Optical Field Surveillance (ResNet-50)</div>
            <span className="panel-hint">Farmer uploads</span>
          </div>

          {recentSurveillance.length === 0 ? (
            <p className="stat-card-loading">
              No AI-classified farmer photos yet for {user.municipality} — a photo submitted through a report is
              classified automatically and will appear here.
            </p>
          ) : (
            <div className="surveillance-grid">
              {recentSurveillance.map((report) => (
                <div className="surveillance-item" key={report.id}>
                  <div className="surveillance-thumb">
                    {report.photo_url && (
                      <img src={`${API_BASE_URL}${report.photo_url}`} alt="Farmer-submitted pest sighting" />
                    )}
                  </div>
                  <div className="surveillance-caption">
                    {report.ai_pest_detected ?? 'No pest detected'} ·{' '}
                    {Math.round((report.ai_confidence ?? 0) * 100)}% conf
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="surveillance-footer">
            <span>{lastSyncedAt ? `Last synced: ${formatSyncedAt(lastSyncedAt)}` : 'No photos synced yet'}</span>
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault()
                onNavigateToReports()
              }}
            >
              View All Reports
            </a>
          </div>
        </div>
      </section>

      {selectedCell &&
        (() => {
          const meta = heatmapMeta.find((m) => m.key === selectedCell.key)!
          return (
            <DayDetailModal
              key={`${selectedCell.key}-${selectedCell.point.date}`}
              municipality={user.municipality}
              pestKey={meta.key}
              pestCode={meta.pest}
              pestLabel={meta.title}
              growthStage={ACTIVE_GROWTH_STAGE}
              unitLabel={meta.unitLabel}
              point={selectedCell.point}
              formatValue={meta.formatValue}
              onClose={() => setSelectedCell(null)}
            />
          )
        })()}
    </>
  )
}

export default StatusPage
