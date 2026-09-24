import { useEffect, useState } from 'react'
import {
  API_BASE_URL,
  deleteReport,
  fetchDeletedReports,
  fetchReports,
  updateReportStatus,
  type LguUser,
  type ReportRecord,
  type ReportStatus,
} from '../../lib/api'
import ConfirmDeleteModal from '../../components/ConfirmDeleteModal'
import './ReportsPage.css'

interface ReportsPageProps {
  user: LguUser
  accessToken: string
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

type ReportFilter = ReportStatus | 'all' | 'deleted'

const FILTERS: { key: ReportFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'verified', label: 'Verified' },
  { key: 'pending', label: 'Pending' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'deleted', label: 'Deleted' },
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

function ReportsPage({ user, accessToken }: ReportsPageProps) {
  const [reports, setReports] = useState<ReportRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<ReportFilter>('pending')
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [draftValues, setDraftValues] = useState<Record<string, string>>({})
  const [pendingDelete, setPendingDelete] = useState<ReportRecord | null>(null)
  const [deletedReports, setDeletedReports] = useState<ReportRecord[]>([])

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

  useEffect(() => {
    let cancelled = false

    fetchDeletedReports(accessToken)
      .then((data) => {
        if (!cancelled) setDeletedReports(data)
      })
      .catch(() => {
        // The audit tab just stays empty; the main list is unaffected.
      })

    return () => {
      cancelled = true
    }
  }, [accessToken])

  const handleReview = async (id: string, status: Extract<ReportStatus, 'verified' | 'rejected'>) => {
    setActioningId(id)
    try {
      const draft = draftValues[id]
      const verifiedValue = status === 'verified' && draft !== undefined && draft !== '' ? Number(draft) : undefined
      const updated = await updateReportStatus(id, status, user.username, verifiedValue)
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)))
    } catch {
      setError('Unable to update this report — try again')
    } finally {
      setActioningId(null)
    }
  }

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return
    const id = pendingDelete.id
    setActioningId(id)
    try {
      const deleted = await deleteReport(accessToken, id)
      setReports((prev) => prev.filter((r) => r.id !== id))
      setDeletedReports((prev) => [deleted, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete this report — try again')
    } finally {
      setActioningId(null)
      setPendingDelete(null)
    }
  }

  const visible =
    filter === 'deleted' ? deletedReports : filter === 'all' ? reports : reports.filter((r) => r.status === filter)
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
              {filter === 'deleted'
                ? 'No deleted reports — anything an LGU technician deletes is kept here as an audit trail.'
                : reports.length === 0
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
                    AI: {report.ai_pest_detected ?? 'No pest detected'} ·{Math.round(report.ai_confidence * 100)}%
                  </span>
                )}
              </div>

              <div className="report-card-body">
                <div className="report-card-top">
                  <div className="report-card-badges">
                    <span className={`badge badge-${severityTone}`}>{report.severity.toUpperCase()}</span>
                    <span className={`badge badge-${statusTone}`}>{report.status.toUpperCase()}</span>
                    {report.deleted_at && <span className="badge badge-red">DELETED</span>}
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
                  {report.estimated_value != null && (
                    <span>
                      <strong>Farmer Estimate:</strong> {report.estimated_value}
                    </span>
                  )}
                  {report.status === 'verified' && report.verified_value != null && (
                    <span>
                      <strong>Confirmed Value:</strong> {report.verified_value}
                    </span>
                  )}
                </div>

                {report.notes && <p className="report-card-notes">{report.notes}</p>}

                <div className="report-card-footer">
                  <span>Reported by {report.username}</span>
                  {report.deleted_at && (
                    <span className="report-deleted-note">
                      Deleted by {report.deleted_by ?? 'unknown'} · {formatTimestamp(report.deleted_at)}
                    </span>
                  )}
                  {report.status !== 'pending' && report.verified_by && (
                    <span>
                      {report.status === 'verified' ? 'Verified' : 'Rejected'} by {report.verified_by}
                      {report.verified_at && ` · ${formatTimestamp(report.verified_at)}`}
                    </span>
                  )}
                </div>

                {report.status === 'pending' && !report.deleted_at && (
                  <>
                    <label className="report-value-input">
                      Confirm count/damage value
                      <input
                        type="number"
                        placeholder={report.estimated_value != null ? String(report.estimated_value) : 'e.g. 12'}
                        value={draftValues[report.id] ?? (report.estimated_value != null ? String(report.estimated_value) : '')}
                        onChange={(e) => setDraftValues((prev) => ({ ...prev, [report.id]: e.target.value }))}
                      />
                    </label>
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
                  </>
                )}

                {!report.deleted_at && (
                <div className="report-card-actions">
                  <button
                    type="button"
                    className="report-action-btn report-action-delete"
                    disabled={isActioning}
                    onClick={() => setPendingDelete(report)}
                  >
                    Delete report
                  </button>
                </div>
                )}
              </div>
            </article>
          )
        })}
      </section>

      {pendingDelete && (
        <ConfirmDeleteModal
          report={pendingDelete}
          busy={actioningId === pendingDelete.id}
          onConfirm={handleConfirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </>
  )
}

export default ReportsPage
