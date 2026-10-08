import { useEffect, useMemo, useState } from 'react'
import {
  fetchSmsGatewayStatus,
  fetchSmsOutbox,
  fetchSmsRecipients,
  sendSms,
  type SmsGatewayStatus,
  type SmsMessageRecord,
  type SmsRecipient,
} from '../../lib/api'
import type { LguUser } from '../../lib/api'
import './SmsPage.css'

const MAX_BODY = 640

interface SmsPageProps {
  user: LguUser
  accessToken: string
  /** Prefills the advisory from whatever the dashboard is currently showing,
   *  so the technologist edits a draft instead of typing from a blank box. */
  draft?: string
}

function formatStamp(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function SmsPage({ user, accessToken, draft }: SmsPageProps) {
  const [recipients, setRecipients] = useState<SmsRecipient[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [extraNumberFields, setExtraNumberFields] = useState<string[]>([''])
  const [body, setBody] = useState(draft ?? '')
  const [gateway, setGateway] = useState<SmsGatewayStatus | null>(null)
  const [outbox, setOutbox] = useState<SmsMessageRecord[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<string>('')

  async function refresh() {
    try {
      const [r, g, o] = await Promise.all([
        fetchSmsRecipients(accessToken),
        fetchSmsGatewayStatus(accessToken),
        fetchSmsOutbox(accessToken),
      ])
      setRecipients(r)
      setGateway(g)
      setOutbox(o)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load SMS data')
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  const typedNumbers = useMemo(
    () => extraNumberFields.map((s) => s.trim()).filter(Boolean),
    [extraNumberFields],
  )
  const totalTargets = selected.size + typedNumbers.length

  function updateExtraNumber(index: number, value: string) {
    setExtraNumberFields((prev) => prev.map((n, i) => (i === index ? value : n)))
  }

  function addExtraNumberField() {
    setExtraNumberFields((prev) => [...prev, ''])
  }

  function removeExtraNumberField(index: number) {
    setExtraNumberFields((prev) => (prev.length === 1 ? [''] : prev.filter((_, i) => i !== index)))
  }

  function toggle(username: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(username)) next.delete(username)
      else next.add(username)
      return next
    })
  }

  async function handleSend() {
    setError('')
    setResult('')
    if (!body.trim()) {
      setError('Write the advisory first.')
      return
    }
    if (totalTargets === 0) {
      setError('Pick at least one farmer, or type a mobile number.')
      return
    }
    setSending(true)
    try {
      const res = await sendSms(accessToken, {
        body: body.trim(),
        usernames: [...selected],
        phone_numbers: typedNumbers,
      })
      const bits = [`${res.sent} sent`]
      if (res.failed) bits.push(`${res.failed} failed`)
      if (res.skipped.length) bits.push(`${res.skipped.length} skipped`)
      const mode = res.provider === 'console' ? ' (simulation — nothing left the server)' : ''
      setResult(`${bits.join(', ')}${mode}.${res.skipped.length ? ' Skipped: ' + res.skipped.join('; ') : ''}`)
      setSelected(new Set())
      setExtraNumberFields([''])
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send')
    } finally {
      setSending(false)
    }
  }

  const simulated = gateway?.provider === 'console'
  const bannerTone = simulated ? 'simulated' : gateway?.reachable ? 'live' : 'broken'
  const parts = Math.max(1, Math.ceil(body.length / 160))
  const allSelected = recipients.length > 0 && selected.size === recipients.length

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(recipients.map((r) => r.username)))
  }

  return (
    <div className="sms-page">
      <div className={`sms-banner ${bannerTone}`}>
        <span className="sms-banner-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4" />
            <path d="M12 8h.01" />
          </svg>
        </span>
        <div className="sms-banner-text">
          <strong>
            {simulated ? 'Simulation mode' : gateway?.reachable ? 'Live gateway connected' : 'Gateway unreachable'}
          </strong>
          <span>{gateway?.detail ?? 'Checking the gateway…'}</span>
        </div>
      </div>

      <div className="sms-grid">
        <section className="sms-card">
          <div className="sms-card-head">
            <span className="sms-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-4 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
              </svg>
            </span>
            <div>
              <h2>Compose advisory</h2>
              <p className="sms-hint">
                Sent from {user.municipality}. Messages go out only when you send them — the system never
                texts farmers on its own.
              </p>
            </div>
          </div>

          <div className="sms-section">
            <label className="sms-label" htmlFor="sms-body">
              <span className="sms-step">1</span> Message
            </label>
            <textarea
              id="sms-body"
              className="sms-textarea"
              rows={6}
              maxLength={MAX_BODY}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="e.g. PestWatcher PH advisory: Brown Planthopper risk is HIGH in your area over the next 14 days. Inspect your field and consult your technician before spraying."
            />
            <div className="sms-counter-row">
              <div className="sms-meter" aria-hidden="true">
                <span style={{ width: `${Math.min(100, (body.length / MAX_BODY) * 100)}%` }} />
              </div>
              <span className="sms-counter">
                {body.length} / {MAX_BODY}
              </span>
              <span className="sms-parts">
                {parts} SMS part{parts === 1 ? '' : 's'}
              </span>
            </div>
          </div>

          <div className="sms-section">
            <div className="sms-label-row">
              <span className="sms-label">
                <span className="sms-step">2</span> Registered farmers in {user.municipality}
              </span>
              {recipients.length > 0 && (
                <button type="button" className="sms-link-btn" onClick={toggleAll}>
                  {allSelected ? 'Clear all' : 'Select all'}
                </button>
              )}
            </div>
            {recipients.length === 0 ? (
              <p className="sms-empty-box">
                No farmer in this municipality has a mobile number on file yet. You can still type a number below.
              </p>
            ) : (
              <ul className="sms-recipients">
                {recipients.map((r) => (
                  <li key={r.username}>
                    <label className={selected.has(r.username) ? 'is-selected' : undefined}>
                      <input
                        type="checkbox"
                        checked={selected.has(r.username)}
                        onChange={() => toggle(r.username)}
                      />
                      <span className="sms-recipient-name">{r.full_name}</span>
                      <span className="sms-recipient-phone">{r.phone}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="sms-section">
            <label className="sms-label">
              <span className="sms-step">3</span> Or type mobile numbers
            </label>
            <div className="sms-extra-list">
              {extraNumberFields.map((number, index) => (
                <div className="sms-extra-row" key={index}>
                  <input
                    className="sms-input"
                    value={number}
                    onChange={(e) => updateExtraNumber(index, e.target.value)}
                    placeholder="0917 123 4567"
                  />
                  {extraNumberFields.length > 1 && (
                    <button
                      type="button"
                      className="sms-extra-remove"
                      onClick={() => removeExtraNumberField(index)}
                      aria-label="Remove this number"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button type="button" className="sms-link-btn sms-add-number" onClick={addExtraNumberField}>
              + Add another number
            </button>
            <div className="sms-counter">09xxxxxxxxx or +639xxxxxxxxx both work.</div>
          </div>

          {error && <div className="sms-error">{error}</div>}
          {result && <div className="sms-result">{result}</div>}

          <button className="sms-send" onClick={handleSend} disabled={sending || totalTargets === 0}>
            {sending ? 'Sending…' : `Send to ${totalTargets || 'no'} recipient${totalTargets === 1 ? '' : 's'}`}
          </button>
        </section>

        <section className="sms-card">
          <div className="sms-card-head">
            <span className="sms-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-6l-2 3h-4l-2-3H2" />
                <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z" />
              </svg>
            </span>
            <div>
              <h2>Outbox</h2>
              <p className="sms-hint">Every advisory sent from {user.municipality}, newest first.</p>
            </div>
          </div>

          {outbox.length === 0 ? (
            <div className="sms-empty-state">
              <span aria-hidden="true">✉</span>
              <strong>Nothing sent yet</strong>
              <p>Advisories you send will show up here.</p>
            </div>
          ) : (
            <ul className="sms-outbox">
              {outbox.map((m) => {
                const name = m.recipient_name ?? m.recipient_phone
                return (
                  <li key={m.id} className={`sms-outbox-row ${m.status}`}>
                    <span className="sms-avatar" aria-hidden="true">
                      {(name ?? '?').trim().charAt(0).toUpperCase()}
                    </span>
                    <div className="sms-outbox-main">
                      <div className="sms-outbox-head">
                        <span className="sms-outbox-to">{name}</span>
                        <span className={`sms-badge ${m.status}`}>{m.status}</span>
                      </div>
                      <div className="sms-outbox-meta">
                        {formatStamp(m.created_at)} · {m.sent_by}
                        {m.provider === 'console' ? ' · simulated' : ''}
                      </div>
                      <div className="sms-outbox-body">{m.body}</div>
                      {m.error && <div className="sms-outbox-error">{m.error}</div>}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
