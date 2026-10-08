import { useEffect, useState } from 'react'
import { fetchAdminOverview, type MunicipalityOverview } from '../../lib/api'
import { RISK_TONE } from '../../lib/etl'

interface OverviewPageProps {
  accessToken: string
  onSessionExpired: () => void
}

function StatIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="admin-stat-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </span>
  )
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
          <div className="admin-stat-card admin-stat-card-green">
            <StatIcon>
              <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z" />
              <circle cx="12" cy="10" r="3" />
            </StatIcon>
            <div className="admin-stat-value">{rows?.length ?? '—'}</div>
            <div className="admin-stat-label">Municipalities Monitored</div>
          </div>
          <div className="admin-stat-card admin-stat-card-green">
            <StatIcon>
              <path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z" />
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
            </StatIcon>
            <div className="admin-stat-value">{rows ? highRiskCount : '—'}</div>
            <div className="admin-stat-label">High-Risk Municipalities</div>
          </div>
          <div className="admin-stat-card admin-stat-card-green">
            <StatIcon>
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </StatIcon>
            <div className="admin-stat-value">{rows ? mediumRiskCount : '—'}</div>
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
          <table className="admin-table admin-table-overview">
            <thead>
              <tr>
                <th>Municipality</th>
                <th>Province</th>
                <th className="admin-col-center">BPH (hoppers/hill)</th>
                <th className="admin-col-center">BPH Risk</th>
                <th className="admin-col-center">RSB (% Dead Hearts)</th>
                <th className="admin-col-center">RSB Risk</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.municipality}>
                  <td>{row.municipality}</td>
                  <td>{row.province}</td>
                  <td className="admin-col-center">{row.bph.predicted_value != null ? Math.round(row.bph.predicted_value) : '—'}</td>
                  <td className="admin-col-center">
                    {row.bph.risk_level ? (
                      <span className={`badge badge-${RISK_TONE[row.bph.risk_level]}`}>
                        {row.bph.risk_level.toUpperCase()}
                      </span>
                    ) : (
                      <span className="badge badge-neutral">N/A</span>
                    )}
                  </td>
                  <td className="admin-col-center">{row.rsb.predicted_value != null ? row.rsb.predicted_value.toFixed(1) : '—'}</td>
                  <td className="admin-col-center">
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
