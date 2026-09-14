import { useEffect, useState } from 'react'
import {
  fetchPestForecastExplanation,
  type ExplanationFeature,
  type GrowthStage,
  type PestKey,
  type TrajectoryPoint,
} from '../lib/api'
import { ETL_BANDS, RISK_TONE } from '../lib/etl'

interface DayDetailModalProps {
  municipality: string
  pestKey: 'bph' | 'rsb'
  pestCode: PestKey
  pestLabel: string
  growthStage: GrowthStage
  unitLabel: string
  point: TrajectoryPoint
  formatValue: (value: number) => string
  onClose: () => void
}

function formatFullDate(iso: string) {
  return new Date(iso).toLocaleDateString([], {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

function isToday(iso: string) {
  const target = new Date(iso)
  const today = new Date()
  target.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)
  return target.getTime() === today.getTime()
}

function DayDetailModal({
  municipality,
  pestKey,
  pestCode,
  pestLabel,
  growthStage,
  unitLabel,
  point,
  formatValue,
  onClose,
}: DayDetailModalProps) {
  const [features, setFeatures] = useState<ExplanationFeature[] | null>(null)
  const [explainError, setExplainError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchPestForecastExplanation(municipality, pestCode, growthStage)
      .then((res) => {
        if (cancelled) return
        if (res.status === 'ok') {
          setFeatures(res.features)
        } else {
          setExplainError(res.message || 'Model not loaded for this pest yet')
        }
      })
      .catch(() => {
        if (!cancelled) setExplainError('Unable to load risk factor breakdown')
      })

    return () => {
      cancelled = true
    }
  }, [municipality, pestCode, growthStage])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const tone = RISK_TONE[point.risk_level]
  const etl = ETL_BANDS[pestKey]
  const maxFeature = features?.length
    ? Math.max(...features.map((f) => Math.abs(f.value)))
    : 1

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-head">
          <div>
            <div className="panel-title">{pestLabel} · {formatFullDate(point.date)}</div>
            <div className="panel-subtitle">{municipality} · {growthStage} stage</div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="stat-card-big">
          <span className="stat-card-big-value">{formatValue(point.predicted_value)}</span>
          <span className="stat-card-big-unit">{unitLabel}</span>
        </div>

        <div className="stat-card-etl">
          ETL: <strong>{etl.highMin}{pestKey === 'rsb' ? '% Dead Hearts' : ' hoppers/hill'}</strong>
        </div>

        <div className="stat-card-risk-row">
          <span className="stat-card-risk-label">Risk Level</span>
          <span className={`badge badge-${tone}`}>{point.risk_level.toUpperCase()}</span>
        </div>

        <div className="modal-section-title">
          Risk Factor Attribution
          {!isToday(point.date) && (
            <span className="modal-section-hint"> · based on today's live conditions</span>
          )}
        </div>

        {explainError ? (
          <p className="stat-card-error">{explainError}</p>
        ) : features === null ? (
          <p className="stat-card-loading">Loading risk factor breakdown…</p>
        ) : features.length === 0 ? (
          <p className="stat-card-loading">No attribution data available.</p>
        ) : (
          <>
            <div className="feature-bars">
              {features.map((f) => (
                <div className="feature-bar-row" key={f.label}>
                  <div className="feature-bar-label">{f.label}</div>
                  <div className="feature-bar-track">
                    <div
                      className={`feature-bar-fill ${f.value >= 0 ? 'feature-bar-up' : 'feature-bar-down'}`}
                      style={{ width: `${(Math.abs(f.value) / maxFeature) * 100}%` }}
                    />
                  </div>
                  <div className={`feature-bar-value ${f.value >= 0 ? 'feature-bar-up-text' : 'feature-bar-down-text'}`}>
                    {f.value >= 0 ? '+' : ''}
                    {f.value.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
            <p className="modal-footnote">
              Values are each feature's contribution to the predicted {unitLabel}, not a percentage —
              positive pushed the forecast up, negative pulled it down.
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export default DayDetailModal
