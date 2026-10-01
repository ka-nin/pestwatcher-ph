import { useEffect, useState } from 'react'
import { fetchReportGapAnalysis, type GapAnalysisResponse, type ReportRecord } from '../lib/api'
import { ETL_BANDS, RISK_TONE } from '../lib/etl'
import GapAnalysisChart from './GapAnalysisChart'

function formatDayLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function formatValue(value: number | null, unitLabel: string) {
  if (value === null) return '—'
  return unitLabel === '%' ? `${value.toFixed(1)}%` : Math.round(value).toString()
}

function formatGap(historical: number | null, reportBased: number | null, unitLabel: string) {
  if (historical === null || reportBased === null) return null
  const diff = reportBased - historical
  const sign = diff > 0 ? '+' : diff < 0 ? '−' : '±'
  const magnitude = unitLabel === '%' ? Math.abs(diff).toFixed(1) : Math.round(Math.abs(diff)).toString()
  return { diff, label: `${sign}${magnitude}${unitLabel === '%' ? '%' : ''}` }
}

interface GapAnalysisModalProps {
  report: ReportRecord
  onClose: () => void
}

function GapAnalysisModal({ report, onClose }: GapAnalysisModalProps) {
  const [result, setResult] = useState<GapAnalysisResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  useEffect(() => {
    let cancelled = false

    fetchReportGapAnalysis(report.id)
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [report.id])

  const bandKey = result?.pest === 'RSB' ? 'rsb' : 'bph'
  const band = ETL_BANDS[bandKey]
  const unitLabel = result?.unit === 'pct_damage' ? '%' : '/hill'

  return (
    <div className="modal-backdrop modal-backdrop-blur" onClick={onClose}>
      <div
        className="modal-panel gap-modal-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gap-analysis-title"
      >
        <div className="modal-head">
          <div>
            <div className="panel-title" id="gap-analysis-title">
              Gap Analysis
            </div>
            <div className="panel-subtitle">
              {report.pest_type} · {report.municipality}, {report.province} · Reported {report.date_spotted}
            </div>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {error && <p className="stat-card-error">{error}</p>}

        {!error && !result && <p className="stat-card-loading">Analyzing…</p>}

        {result?.status === 'report_not_verified' && (
          <p className="stat-card-error">{result.implication}</p>
        )}

        {result?.status === 'model_not_loaded' && (
          <p className="stat-card-error">{result.message}</p>
        )}

        {result?.status === 'ok' && (
          <>
            <div className="gap-modal-legend">
              <span className="gap-modal-legend-item">
                <span className="gap-modal-legend-swatch gap-modal-legend-swatch-historical" />
                14-day prediction (historical / weather-only)
              </span>
              <span className="gap-modal-legend-item">
                <span className="gap-modal-legend-swatch gap-modal-legend-swatch-report" />
                14-day prediction (based on this report)
              </span>
            </div>

            <GapAnalysisChart days={result.days} lowMax={band.lowMax} highMin={band.highMin} unitLabel={unitLabel} />

            <div className="gap-modal-table-wrap">
              <table className="gap-modal-table">
                <colgroup>
                  <col className="gap-modal-col-date" />
                  <col />
                  <col />
                  <col className="gap-modal-col-gap" />
                  <col className="gap-modal-col-weight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Historical</th>
                    <th>Report-Based</th>
                    <th>Gap</th>
                    <th>Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {result.days.map((day) => {
                    const gap = formatGap(day.historical_value, day.report_based_value, unitLabel)
                    const gapTone = gap === null || gap.diff === 0 ? 'neutral' : gap.diff > 0 ? 'red' : 'green'
                    return (
                      <tr key={day.date}>
                        <td>{formatDayLabel(day.date)}</td>
                        <td>
                          <span className="gap-modal-table-value">{formatValue(day.historical_value, unitLabel)}</span>
                          {day.historical_risk_level && (
                            <span className={`badge badge-${RISK_TONE[day.historical_risk_level]} gap-modal-table-badge`}>
                              {day.historical_risk_level}
                            </span>
                          )}
                        </td>
                        <td>
                          <span className="gap-modal-table-value">{formatValue(day.report_based_value, unitLabel)}</span>
                          {day.report_based_risk_level && (
                            <span className={`badge badge-${RISK_TONE[day.report_based_risk_level]} gap-modal-table-badge`}>
                              {day.report_based_risk_level}
                            </span>
                          )}
                        </td>
                        <td className={`gap-modal-table-gap gap-modal-table-gap-${gapTone}`}>
                          {gap ? gap.label : '—'}
                        </td>
                        <td className="gap-modal-table-weight">{Math.round(day.report_weight * 100)}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="gap-modal-implication">
              <div className="gap-modal-implication-label">What this means</div>
              <p>{result.implication}</p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default GapAnalysisModal
