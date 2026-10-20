import { useEffect, useState } from 'react'
import {
  fetchPestForecastTrajectory,
  type GrowthOutlook,
  type GrowthStage,
  type LguUser,
  type SpreadSummary,
  type TrajectoryPoint,
} from '../../lib/api'
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

function outlookLine(outlook: GrowthOutlook, unitLabel: string, format: (v: number) => string) {
  const perDay = unitLabel === '%' ? `${Math.abs(outlook.change_per_day).toFixed(2)}%` : Math.abs(outlook.change_per_day).toFixed(1)
  const parts: string[] = []
  if (outlook.trend === 'stable') {
    parts.push('Stable over the next 2 weeks')
  } else {
    const verb = outlook.trend === 'rising' ? 'Rising' : 'Falling'
    const rel = outlook.pct_change_per_day != null ? ` (${outlook.pct_change_per_day > 0 ? '+' : ''}${outlook.pct_change_per_day.toFixed(1)}%/day)` : ''
    parts.push(`${verb} about ${perDay}${unitLabel === '%' ? '' : ' per hill'} per day${rel}`)
  }
  if (outlook.doubling_days != null) parts.push(`doubles in ~${Math.round(outlook.doubling_days)} days`)
  parts.push(
    outlook.days_to_high === 0
      ? 'already at High'
      : outlook.days_to_high != null
        ? `reaches High in ~${outlook.days_to_high} days`
        : 'stays below High',
  )
  parts.push(`peak ${format(outlook.peak_value)} on ${formatDayLabel(outlook.peak_date)}`)
  return parts.join(' · ')
}

function spreadLine(spread: SpreadSummary) {
  if (spread.recent_reports === 0 && spread.previous_reports === 0) {
    return `No verified reports in the last ${spread.window_days * 2} days`
  }
  const trend =
    spread.trend === 'spreading' ? 'spreading' : spread.trend === 'shrinking' ? 'shrinking' : 'about the same'
  const coverage = spread.mean_photo_coverage_pct != null ? ` · photos show ~${Math.round(spread.mean_photo_coverage_pct)}% of the visible area affected` : ''
  return `${spread.recent_hectares} ha reported affected in ${spread.recent_reports} verified report${spread.recent_reports === 1 ? '' : 's'} (last ${spread.window_days} days), vs ${spread.previous_hectares} ha before: ${trend}${coverage}`
}

function formatDayLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function PestForecastPage({ user }: PestForecastPageProps) {
  const [trajectories, setTrajectories] = useState<Partial<Record<'bph' | 'rsb', TrajectoryPoint[]>>>({})
  const [outlooks, setOutlooks] = useState<Partial<Record<'bph' | 'rsb', { outlook: GrowthOutlook | null; spread: SpreadSummary | null }>>>({})
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
          (res) => [meta.key, res] as const,
        ),
      ),
    )
      .then((results) => {
        if (cancelled) return
        setTrajectories(Object.fromEntries(results.map(([key, res]) => [key, res.status === 'ok' ? res.points : []])))
        setOutlooks(
          Object.fromEntries(results.map(([key, res]) => [key, { outlook: res.outlook ?? null, spread: res.spread ?? null }])),
        )
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
              {outlooks[meta.key] && (
                <div className="forecast-outlook">
                  {outlooks[meta.key]?.outlook && (
                    <p>
                      <span className="forecast-outlook-label">How fast</span>
                      {outlookLine(outlooks[meta.key]!.outlook!, meta.unitLabel, meta.format)}
                    </p>
                  )}
                  {outlooks[meta.key]?.spread && (
                    <p>
                      <span className="forecast-outlook-label">How far</span>
                      {spreadLine(outlooks[meta.key]!.spread!)}
                    </p>
                  )}
                </div>
              )}
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
