import { useEffect } from 'react'
import type { ReportRecord } from '../lib/api'

interface ConfirmDeleteModalProps {
  report: ReportRecord
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDeleteModal({ report, busy, onConfirm, onCancel }: ConfirmDeleteModalProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [busy, onCancel])

  return (
    <div className="modal-backdrop modal-backdrop-blur" onClick={busy ? undefined : onCancel}>
      <div
        className="modal-panel confirm-modal"
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-delete-title"
      >
        <div className="confirm-modal-icon" aria-hidden="true">
          !
        </div>

        <div className="panel-title confirm-modal-title" id="confirm-delete-title">
          Delete this report?
        </div>
        <div className="panel-subtitle">
          {report.pest_type} · {report.municipality} · {report.severity.toUpperCase()}
        </div>

        <p className="confirm-modal-text">
          The report will stop affecting the pest forecast and the farmers&rsquo; alerts. It is kept in the Deleted
          tab as an audit trail, showing who deleted it and when.
        </p>

        <div className="confirm-modal-actions">
          <button type="button" className="report-action-btn report-action-reject confirm-modal-cancel" onClick={onCancel} disabled={busy} autoFocus>
            Cancel
          </button>
          <button type="button" className="report-action-btn report-action-danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Deleting…' : 'Delete report'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmDeleteModal
