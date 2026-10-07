import { useEffect, useState } from 'react'
import { fetchPestForecastTrajectory, type GrowthStage, type LguUser, type TrajectoryPoint } from '../../lib/api'
import { ASSUMED_GROWTH_STAGE, etlBandFor, RISK_TONE } from '../../lib/etl'
import TrajectoryChart, { niceMax } from './TrajectoryChart'
import './PestForecastPage.css'

interface PestForecastPageProps {
  user: LguUser
}

const TRAJECTORY_DAYS = 13
const ACTIVE_GROWTH_STAGE: GrowthStage = ASSUMED_GROWTH_STAGE

const riskTone = RISK_TONE

const forecastMeta = [
  {
    key: 'bph' as const,
    pest: 'BPH' as const,
    title: 'Brown Planthopper (BPH) Trajectory',
    breakdownTitle: 'BPH Daily Breakdown',
    unitLabel: '/hill',
    format: (v: number) => Math.round(v).toString(),
    valueText: (v: number) => `${Math.round(v)} hoppers/hill`,
  },
  {
    key: 'rsb' as const,
    pest: 'RSB' as const,
    title: 'Rice Stem Borer (RSB) Trajectory',
    breakdownTitle: 'RSB Daily Breakdown',
    unitLabel: '%',
    format: (v: number) => `${v.toFixed(1)}%`,
    valueText: (v: number) => `${v.toFixed(1)}% dead hearts`,
  },
]

function formatDayLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function PestForecastPage({ user }: PestForecastPageProps) {
  const [trajectories, setTrajectories] = useState<Partial<Record<'bph' | 'rsb', TrajectoryPoint[]>>>({})
  const [forecastError, setForecastError] = useState('')
  // Day being inspected, per pest: hovering the chart highlights the matching
  // daily-breakdown row and the other way round.
  const [hoverIndex, setHoverIndex] = useState<Record<'bph' | 'rsb', number | null>>({ bph: null, rsb: null })
  const setHover = (key: 'bph' | 'rsb', index: number | null) =>
    setHoverIndex((prev) => (prev[key] === index ? prev : { ...prev, [key]: index }))

  useEffect(() => {
    let cancelled = false

    Promise.all(
      forecastMeta.map((meta) =>
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
        if (!cancelled) setForecastError('Unable to load live pest forecast trajectory')
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality])

  return (
    <>
      <section className="panel forecast-summary-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">14-Day Sequential Temporal Forecast (BiLSTM)</div>
            <div className="panel-subtitle">
              {user.province}-wide forecast · Source: DOST-PAGASA CLSU + BPI-CPMD
            </div>
          </div>
          <span className="badge badge-green">Active Crop Stage: {ACTIVE_GROWTH_STAGE}</span>
        </div>
        {forecastError && <p className="stat-card-error">{forecastError}</p>}
      </section>

      <section className="forecast-chart-grid">
        {forecastMeta.map((meta) => {
          const points = trajectories[meta.key] ?? []
          return (
            <div className="panel forecast-chart-panel" key={meta.key}>
              <div className="forecast-chart-head">
                <span className="forecast-chart-title">{meta.title}</span>
                <span className="forecast-chart-note">
                  {meta.pest === 'BPH' ? `Hoppers / hill (0-${etlBandFor('bph', ACTIVE_GROWTH_STAGE).highMin * 1.5})` : '% Dead Hearts'}
                </span>
              </div>
              <TrajectoryChart
                points={points}
                lowMax={etlBandFor(meta.key, ACTIVE_GROWTH_STAGE).lowMax}
                highMin={etlBandFor(meta.key, ACTIVE_GROWTH_STAGE).highMin}
                unitLabel={meta.unitLabel}
                valueText={meta.valueText}
                hoverIndex={hoverIndex[meta.key]}
                onHover={(index) => setHover(meta.key, index)}
              />
            </div>
          )
        })}
      </section>

      <section className="forecast-chart-grid">
        {forecastMeta.map((meta) => {
          const points = trajectories[meta.key] ?? []
          // Same y-scale as the trajectory chart above, so a bar's fill %
          // here means the same thing it means there — a value near the
          // ETL limit fills most of the bar, not just "highest of a flat week."
          const band = etlBandFor(meta.key, ACTIVE_GROWTH_STAGE)
          const dataMax = points.length ? Math.max(...points.map((p) => p.predicted_value)) : 0
          const referenceMax = niceMax(band.highMin, dataMax)

          return (
            <div className="panel forecast-breakdown-panel" key={meta.key}>
              <div className="forecast-breakdown-title">{meta.breakdownTitle}</div>
              <div className="forecast-breakdown-list">
                {points.length === 0 && <p className="stat-card-loading">Loading…</p>}
                {points.map((p, i) => (
                  <div
                    className={`forecast-breakdown-row${hoverIndex[meta.key] === i ? ' is-active' : ''}`}
                    key={p.date}
                    tabIndex={0}
                    onMouseEnter={() => setHover(meta.key, i)}
                    onMouseLeave={() => setHover(meta.key, null)}
                    onFocus={() => setHover(meta.key, i)}
                    onBlur={() => setHover(meta.key, null)}
                  >
                    <span className="forecast-breakdown-date">{formatDayLabel(p.date)}</span>
                    <div className="forecast-breakdown-track">
                      <div
                        className={`forecast-breakdown-fill forecast-breakdown-${riskTone[p.risk_level]}`}
                        style={{ width: `${(p.predicted_value / referenceMax) * 100}%` }}
                      />
                    </div>
                    <span className="forecast-breakdown-value">{meta.format(p.predicted_value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </section>
    </>
  )
}

export default PestForecastPage
