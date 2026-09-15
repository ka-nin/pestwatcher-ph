import { useEffect, useState } from 'react'
import { fetchEtlThresholds, type EtlThresholdsResponse } from '../../lib/api'

interface SettingsPageProps {
  accessToken: string
  onSessionExpired: () => void
}

const UNIT_LABEL: Record<string, string> = {
  BPH: 'hoppers/hill',
  RSB: '% damage',
}

function SettingsPage({ accessToken, onSessionExpired }: SettingsPageProps) {
  const [data, setData] = useState<EtlThresholdsResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchEtlThresholds(accessToken)
      .then((res) => {
        if (!cancelled) setData(res)
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

  return (
    <section className="panel admin-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Economic Threshold Level (ETL) Reference</div>
          <div className="panel-subtitle">
            Fixed agronomic decision thresholds, per pest and growth stage — read-only by design
          </div>
        </div>
      </div>

      <p className="admin-note">
        These values are transcribed from the thesis's ETL table and intentionally kept out of the
        model — the BiLSTM forecasts a continuous value, and this fixed standard buckets it into
        Low/Medium/High. Changing them here isn't supported, since drifting from the cited agronomic
        standard is exactly what the fixed-threshold design is meant to prevent; the source of truth is
        <code> server-python/app/decision/etl_thresholds.py</code>.
      </p>

      {error ? (
        <p className="stat-card-error">{error}</p>
      ) : data === null ? (
        <p className="stat-card-loading">Loading thresholds…</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Pest</th>
                <th>Growth Stage</th>
                <th>Low</th>
                <th>Medium</th>
                <th>High</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.thresholds).map(([pest, stages]) =>
                Object.entries(stages).map(([stage, band]) => {
                  const unit = UNIT_LABEL[pest] ?? ''
                  return (
                    <tr key={`${pest}-${stage}`}>
                      <td>{pest}</td>
                      <td>{stage}</td>
                      <td>{`< ${band.lowMax} ${unit}`}</td>
                      <td>{`${band.lowMax}–${band.highMin} ${unit}`}</td>
                      <td>{`≥ ${band.highMin} ${unit}`}</td>
                    </tr>
                  )
                }),
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default SettingsPage
