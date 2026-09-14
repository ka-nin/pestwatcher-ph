import { useEffect, useState } from 'react'
import { fetchAdminOverview, type MunicipalityOverview } from '../../lib/api'
import { RISK_TONE } from '../../lib/etl'

interface OverviewPageProps {
  accessToken: string
  onSessionExpired: () => void
}

function OverviewPage({ accessToken, onSessionExpired }: OverviewPageProps) {
  const [rows, setRows] = useState<MunicipalityOverview[] | null>(null)
  const [growthStageUsed, setGrowthStageUsed] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchAdminOverview(accessToken)
      .then((res) => {
        if (cancelled) return
        setRows(res.municipalities)
        setGrowthStageUsed(res.growthStageUsed)
      })
      .catch((err: Error) => {
        if (cancelled) return
        if (err.message.startsWith('Session expired')) {
          onSessionExpired()
        } else {
          setError(err.message)
        }
      })

    return () => {
      cancelled = true
    }
  }, [accessToken, onSessionExpired])

  const highRiskCount = rows
    ? rows.filter((r) => r.bph.risk_level === 'High' || r.rsb.risk_level === 'High').length
    : 0
  const mediumRiskCount = rows
    ? rows.filter(
        (r) =>
          r.bph.risk_level !== 'High' &&
          r.rsb.risk_level !== 'High' &&
          (r.bph.risk_level === 'Medium' || r.rsb.risk_level === 'Medium'),
      ).length
    : 0

  return (
    <>
      <section className="panel admin-panel">
        <div className="admin-stat-row">
          <div className="admin-stat-card">
            <div className="admin-stat-value">{rows?.length ?? '—'}</div>
            <div className="admin-stat-label">Municipalities Monitored</div>
          </div>
          <div className="admin-stat-card">
            <div className="admin-stat-value" style={{ color: rows && highRiskCount > 0 ? '#c23b3b' : undefined }}>
              {rows ? highRiskCount : '—'}
            </div>
            <div className="admin-stat-label">High-Risk Municipalities</div>
          </div>
          <div className="admin-stat-card">
            <div className="admin-stat-value" style={{ color: rows && mediumRiskCount > 0 ? '#a5761f' : undefined }}>
              {rows ? mediumRiskCount : '—'}
            </div>
            <div className="admin-stat-label">Medium-Risk Municipalities</div>
          </div>
        </div>
      </section>

      <section className="panel admin-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Municipalities Overview</div>
          <div className="panel-subtitle">
            Live BPH / RSB forecast for every LGU-registered municipality
            {growthStageUsed && ` · growth stage assumed: ${growthStageUsed}`}
          </div>
        </div>
      </div>

      {error ? (
        <p className="stat-card-error">{error}</p>
      ) : rows === null ? (
        <p className="stat-card-loading">Loading municipalities…</p>
      ) : rows.length === 0 ? (
        <p className="stat-card-loading">No municipalities on file yet.</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
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
              {rows.map((row) => (
                <tr key={row.municipality}>
                  <td>{row.municipality}</td>
                  <td>{row.province}</td>
                  <td>{row.bph.predicted_value != null ? Math.round(row.bph.predicted_value) : '—'}</td>
                  <td>
                    {row.bph.risk_level ? (
                      <span className={`badge badge-${RISK_TONE[row.bph.risk_level]}`}>
                        {row.bph.risk_level.toUpperCase()}
                      </span>
                    ) : (
                      <span className="badge badge-neutral">N/A</span>
                    )}
                  </td>
                  <td>{row.rsb.predicted_value != null ? row.rsb.predicted_value.toFixed(1) : '—'}</td>
                  <td>
                    {row.rsb.risk_level ? (
                      <span className={`badge badge-${RISK_TONE[row.rsb.risk_level]}`}>
                        {row.rsb.risk_level.toUpperCase()}
                      </span>
                    ) : (
                      <span className="badge badge-neutral">N/A</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </section>
    </>
  )
}

export default OverviewPage
