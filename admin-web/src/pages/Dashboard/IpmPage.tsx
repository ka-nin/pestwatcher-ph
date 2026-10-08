import { useEffect, useState } from 'react'
import {
  fetchPestForecast,
  fetchPestForecastTrajectory,
  type LguUser,
  type PestForecast,
  type RiskLevel,
  type TrajectoryPoint,
} from '../../lib/api'
import { ASSUMED_GROWTH_STAGE, etlBandFor, RISK_TONE } from '../../lib/etl'
import './IpmPage.css'

interface IpmPageProps {
  user: LguUser
}

const ETL_HIGH_LIMIT: Record<'bph' | 'rsb', number> = {
  bph: etlBandFor('bph').highMin,
  rsb: etlBandFor('rsb').highMin,
}

const riskTone = RISK_TONE

const pestCardMeta = [
  {
    key: 'bph' as const,
    pest: 'BPH' as const,
    title: 'Brown Planthopper',
    stage: ASSUMED_GROWTH_STAGE,
    unit: 'hoppers/hill',
    actionsTitle: 'Recommended Actions',
    actions: [
      'Scout 10 hills per plot weekly',
      'Apply neem-based botanical spray',
      'Maintain alternate wetting and drying (AWD) irrigation',
      'Preserve natural enemies, avoid blanket insecticide use',
    ],
  },
  {
    key: 'rsb' as const,
    pest: 'RSB' as const,
    title: 'Rice Stem Borer',
    stage: ASSUMED_GROWTH_STAGE,
    unit: '% Dead Hearts',
    actionsTitle: 'Routine Monitoring',
    actions: [
      'Light trap surveillance',
      'Check first instar weekly',
      'Record adult moth catches',
      'Inspect tillers for egg masses on leaf tips',
      'Maintain synchronous planting with neighboring farms',
    ],
  },
]

const TIMELINE_DAYS = 14

const BPH_ACTION_BY_RISK: Record<RiskLevel, string> = {
  Low: 'Routine scouting',
  Medium: 'Apply botanical spray',
  High: 'Escalate to LGU advisory',
}

const RSB_ACTION_BY_RISK: Record<RiskLevel, string> = {
  Low: 'Light trap check',
  Medium: 'Inspect tillers, record moth catches',
  High: 'Escalate to LGU advisory',
}

const HEATMAP_TONE: Record<RiskLevel, 'low' | 'mid' | 'high'> = {
  Low: 'low',
  Medium: 'mid',
  High: 'high',
}

function riskChipLabel(tone: 'low' | 'mid' | 'high') {
  if (tone === 'low') return 'LOW'
  if (tone === 'mid') return 'MED'
  return 'HIGH'
}

function formatTimelineDate(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function IpmPage({ user }: IpmPageProps) {
  const [forecasts, setForecasts] = useState<Partial<Record<'bph' | 'rsb', PestForecast>>>({})
  const [forecastError, setForecastError] = useState('')

  const [trajectories, setTrajectories] = useState<Partial<Record<'bph' | 'rsb', TrajectoryPoint[]>>>({})
  const [timelineError, setTimelineError] = useState('')

  useEffect(() => {
    let cancelled = false

    Promise.all(
      pestCardMeta.map((meta) =>
        fetchPestForecast(user.municipality, meta.pest, meta.stage).then(
          (forecast) => [meta.key, forecast] as const,
        ),
      ),
    )
      .then((results) => {
        if (cancelled) return
        setForecasts(Object.fromEntries(results))
      })
      .catch(() => {
        if (!cancelled) setForecastError('Unable to load live pest forecast')
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality])

  useEffect(() => {
    let cancelled = false

    Promise.all(
      pestCardMeta.map((meta) =>
        fetchPestForecastTrajectory(user.municipality, meta.pest, meta.stage, TIMELINE_DAYS).then(
          (res) => [meta.key, res.status === 'ok' ? res.points : []] as const,
        ),
      ),
    )
      .then((results) => {
        if (cancelled) return
        setTrajectories(Object.fromEntries(results))
      })
      .catch(() => {
        if (!cancelled) setTimelineError('Unable to load live 14-day forecast timeline')
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality])

  return (
    <>
      {forecastError && <p className="ipm-footnote">{forecastError}</p>}

      <section className="ipm-grid">
        {pestCardMeta.map((meta) => {
          const forecast = forecasts[meta.key]
          const loaded = forecast?.status === 'ok'
          const value = loaded ? forecast.predicted_value!.toFixed(meta.pest === 'RSB' ? 2 : 0) : '—'
          const displayUnit = loaded && forecast.unit === 'pct_damage' ? '%' : meta.unit
          const risk = loaded ? forecast.risk_level! : null
          const tone = risk ? riskTone[risk] : 'green'
          const percentOfEtl = loaded
            ? Math.min(100, (forecast.predicted_value! / ETL_HIGH_LIMIT[meta.key]) * 100)
            : 0

          return (
            <div className="panel ipm-card" key={meta.key}>
              <div className="panel-head">
                <div className="ipm-card-headleft">
                  <span className={`stat-icon stat-icon-${tone}`} aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                    </svg>
                  </span>
                  <div>
                    <div className="panel-title">{meta.title}</div>
                    <div className="panel-subtitle">Current Stage: {meta.stage}</div>
                  </div>
                </div>
                <span className="badge badge-green">{meta.stage}</span>
              </div>

              <div className="stat-card-big">
                <span className="stat-card-big-value">{value}</span>
                <span className="stat-card-big-unit">{displayUnit}</span>
              </div>

              <div className="ipm-progress-row">
                <span>{meta.pest === 'BPH' ? 'Density vs ETL' : 'Damage vs ETL'}</span>
                <span className="ipm-progress-limit">
                  High Risk ETL Limit: {ETL_HIGH_LIMIT[meta.key]}
                  {meta.pest === 'RSB' ? '%' : ''}
                </span>
              </div>
              <div className="ipm-progress-track">
                <div
                  className={`ipm-progress-fill ipm-progress-${tone}`}
                  style={{ width: `${percentOfEtl}%` }}
                />
              </div>

              <div className="stat-card-risk-row ipm-risk-row">
                <span className="stat-card-risk-label">Risk</span>
                <span className={`badge badge-${tone}`}>
                  {risk ? `${risk} Risk` : forecast ? 'Model not loaded' : 'Loading…'}
                </span>
              </div>

              <div className="ipm-actions">
                <div className="ipm-actions-title">{meta.actionsTitle}</div>
                <ul>
                  {meta.actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </section>

      <section className="row-2">
        <div className="panel timeline-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">14-Day Action Timeline</div>
              <div className="panel-subtitle">
                When to send each pest-specific advisory based on forecasted ETL breaches
              </div>
            </div>
          </div>

          {timelineError && <p className="stat-card-error">{timelineError}</p>}

          <div className="timeline-table-wrap">
            <table className="timeline-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>BPH Density</th>
                  <th>BPH Action</th>
                  <th>RSB Damage</th>
                  <th>RSB Action</th>
                </tr>
              </thead>
              <tbody>
                {(trajectories.bph ?? []).map((bphPoint, i) => {
                  const rsbPoint = trajectories.rsb?.[i]
                  const bphTone = HEATMAP_TONE[bphPoint.risk_level]
                  const rsbTone = rsbPoint ? HEATMAP_TONE[rsbPoint.risk_level] : null

                  return (
                    <tr key={bphPoint.date}>
                      <td>{formatTimelineDate(bphPoint.date)}</td>
                      <td>
                        <span className="timeline-value">{Math.round(bphPoint.predicted_value)}</span>
                        <span className={`badge badge-chip heatmap-${bphTone}`}>{riskChipLabel(bphTone)}</span>
                      </td>
                      <td>{BPH_ACTION_BY_RISK[bphPoint.risk_level]}</td>
                      <td>
                        {rsbPoint && (
                          <>
                            <span className="timeline-value">{rsbPoint.predicted_value.toFixed(1)}%</span>
                            <span className={`badge badge-chip heatmap-${rsbTone}`}>
                              {riskChipLabel(rsbTone!)}
                            </span>
                          </>
                        )}
                      </td>
                      <td>{rsbPoint ? RSB_ACTION_BY_RISK[rsbPoint.risk_level] : ''}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <p className="ipm-footnote">
        BPH/RSB forecasts and the 14-day timeline above are live from the trained BiLSTM model
        for {user.municipality}, {user.province}, with risk levels from the thesis's Table 2 ETL
        standards. The advisory message below remains placeholder data.
      </p>
    </>
  )
}

export default IpmPage
