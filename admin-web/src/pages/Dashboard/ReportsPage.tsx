import { useEffect, useState } from 'react'
import {
  API_BASE_URL,
  fetchReports,
  updateReportStatus,
  type LguUser,
  type ReportRecord,
  type ReportStatus,
} from '../../lib/api'
import './ReportsPage.css'

interface ReportsPageProps {
  user: LguUser
}

const SEVERITY_TONE: Record<string, 'green' | 'yellow' | 'red' | 'neutral'> = {
  low: 'green',
  medium: 'yellow',
  high: 'red',
}

const STATUS_TONE: Record<ReportStatus, 'green' | 'red' | 'neutral'> = {
  verified: 'green',
  rejected: 'red',
  pending: 'neutral',
}

const FILTERS: { key: ReportStatus | 'all'; label: string }[] = [
  { key: 'pending', label: 'Pending Review' },
  { key: 'verified', label: 'Verified' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'all', label: 'All' },
]

function formatDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatTimestamp(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function ReportsPage({ user }: ReportsPageProps) {
  const [reports, setReports] = useState<ReportRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<ReportStatus | 'all'>('pending')
  const [actioningId, setActioningId] = useState<string | null>(null)

  // Tenant-scoped: an LGU tech only ever sees their own municipality's
  // sightings, not the whole province's — see fetchReports' doc comment.
  useEffect(() => {
    let cancelled = false

    fetchReports(user.municipality)
      .then((data) => {
        // Defensive: a backend still running pre-verification code won't
        // send `status` at all (undefined, not "pending"), which would
        // silently fail every filter below and make the page look empty
        // even though the fetch succeeded. Normalize it here once.
        if (!cancelled) setReports(data.map((r) => ({ ...r, status: r.status ?? 'pending' })))
      })
      .catch(() => {
        if (!cancelled) setError('Unable to load farmer reports')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user.municipality])

  const handleReview = async (id: string, status: Extract<ReportStatus, 'verified' | 'rejected'>) => {
    setActioningId(id)
    try {
      const updated = await updateReportStatus(id, status, user.username)
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)))
    } catch {
      setError('Unable to update this report — try again')
    } finally {
      setActioningId(null)
    }
  }

  const visible = filter === 'all' ? reports : reports.filter((r) => r.status === filter)
  const pendingCount = reports.filter((r) => r.status === 'pending').length

  return (
    <>
      <section className="panel reports-summary-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Farmer-Submitted Sightings</div>
            <div className="panel-subtitle">
              {user.municipality}, {user.province} · Verified reports feed into the live pest forecast
            </div>
          </div>
          <span className="badge badge-yellow">{pendingCount} awaiting review</span>
        </div>

        <div className="reports-filter-tabs">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`reports-filter-tab${filter === f.key ? ' active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="stat-card-error">{error}</p>}
      </section>

      <section className="reports-list">
        {loading && <p className="stat-card-loading">Loading reports…</p>}

        {!loading && visible.length === 0 && !error && (
          <div className="panel reports-empty">
            <p className="stat-card-loading">
              {reports.length === 0
                ? `No pending reports for ${user.municipality} right now.`
                : 'No reports in this view.'}
            </p>
          </div>
        )}

        {visible.map((report) => {
          const severityTone = SEVERITY_TONE[report.severity] ?? 'neutral'
          const statusTone = STATUS_TONE[report.status]
          const isActioning = actioningId === report.id

          return (
            <article className="panel report-card" key={report.id}>
              <div className="report-card-media">
                {report.photo_url ? (
                  <img src={`${API_BASE_URL}${report.photo_url}`} alt="Farmer-submitted pest sighting" />
                ) : (
                  <div className="report-card-media-placeholder">
                    <span>Manual Entry</span>
                    <span>No Visual Proof</span>
                  </div>
                )}
                {report.ai_confidence != null && (
                  <span className="report-ai-badge">
                    AI: {report.ai_pest_detected} · {Math.round(report.ai_confidence * 100)}%
                  </span>
                )}
              </div>

              <div className="report-card-body">
                <div className="report-card-top">
                  <div className="report-card-badges">
                    <span className={`badge badge-${severityTone}`}>{report.severity.toUpperCase()}</span>
                    <span className={`badge badge-${statusTone}`}>{report.status.toUpperCase()}</span>
                  </div>
                  <span className="report-card-date">{formatDate(report.date_spotted)}</span>
                </div>

                <h3 className="report-card-title">{report.pest_type}</h3>
                <p className="report-card-location">
                  {report.municipality}, {report.province}
                  {report.latitude != null && report.longitude != null && (
                    <span className="report-card-coords">
                      {' '}
                      · {report.latitude.toFixed(4)}, {report.longitude.toFixed(4)}
                    </span>
                  )}
                </p>

                <div className="report-card-agronomic">
                  <span>
                    <strong>Growth Stage:</strong> {report.crop_growth_stage}
                  </span>
                  {report.area_affected != null && (
                    <span>
                      <strong>Area Affected:</strong> {report.area_affected} ha
                    </span>
                  )}
                </div>

                {report.notes && <p className="report-card-notes">{report.notes}</p>}

                <div className="report-card-footer">
                  <span>Reported by {report.username}</span>
                  {report.status !== 'pending' && report.verified_by && (
                    <span>
                      {report.status === 'verified' ? 'Verified' : 'Rejected'} by {report.verified_by}
                      {report.verified_at && ` · ${formatTimestamp(report.verified_at)}`}
                    </span>
                  )}
                </div>

                {report.status === 'pending' && (
                  <div className="report-card-actions">
                    <button
                      type="button"
                      className="report-action-btn report-action-verify"
                      disabled={isActioning}
                      onClick={() => handleReview(report.id, 'verified')}
                    >
                      {isActioning ? 'Saving…' : 'Verify'}
                    </button>
                    <button
                      type="button"
                      className="report-action-btn report-action-reject"
                      disabled={isActioning}
                      onClick={() => handleReview(report.id, 'rejected')}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </article>
          )
        })}
      </section>
    </>
  )
}

export default ReportsPage
