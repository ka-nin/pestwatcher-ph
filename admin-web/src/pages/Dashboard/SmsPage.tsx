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
import type { AdminUser } from '../../lib/api'
import './SmsPage.css'

const MAX_BODY = 640

interface SmsPageProps {
  user: AdminUser
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
  const [extraNumbers, setExtraNumbers] = useState('')
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
    () => extraNumbers.split(/[,\n;]/).map((s) => s.trim()).filter(Boolean),
    [extraNumbers],
  )
  const totalTargets = selected.size + typedNumbers.length

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
      setExtraNumbers('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send')
    } finally {
      setSending(false)
    }
  }

  const simulated = gateway?.provider === 'console'

  return (
    <div className="sms-page">
      <div className={`sms-banner${simulated ? ' simulated' : gateway?.reachable ? ' live' : ' broken'}`}>
        <strong>
          {simulated ? 'Simulation mode' : gateway?.reachable ? 'Live gateway connected' : 'Gateway unreachable'}
        </strong>
        <span>{gateway?.detail ?? 'Checking the gateway…'}</span>
      </div>

      <div className="sms-grid">
        <section className="sms-card">
          <h2>Compose advisory</h2>
          <p className="sms-hint">
            Sent from {user.municipality}. Messages go out only when you send them — the system never
            texts farmers on its own.
          </p>

          <label className="sms-label" htmlFor="sms-body">Message</label>
          <textarea
            id="sms-body"
            className="sms-textarea"
            rows={6}
            maxLength={MAX_BODY}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="e.g. PestWatcher PH advisory: Brown Planthopper risk is HIGH in your area over the next 14 days. Inspect your field and consult your technician before spraying."
          />
          <div className="sms-counter">
            {body.length} / {MAX_BODY} characters · about {Math.max(1, Math.ceil(body.length / 160))} SMS part(s)
          </div>

          <label className="sms-label">Registered farmers in {user.municipality}</label>
          {recipients.length === 0 ? (
            <p className="sms-empty">
              No farmer in this municipality has a mobile number on file yet. You can still type a
              number below.
            </p>
          ) : (
            <ul className="sms-recipients">
              {recipients.map((r) => (
                <li key={r.username}>
                  <label>
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

          <label className="sms-label" htmlFor="sms-extra">Or type mobile numbers</label>
          <input
            id="sms-extra"
            className="sms-input"
            value={extraNumbers}
            onChange={(e) => setExtraNumbers(e.target.value)}
            placeholder="0917 123 4567, 0918 222 3333"
          />
          <div className="sms-counter">Separate several with commas. 09xxxxxxxxx or +639xxxxxxxxx both work.</div>

          {error && <div className="sms-error">{error}</div>}
          {result && <div className="sms-result">{result}</div>}

          <button className="sms-send" onClick={handleSend} disabled={sending || totalTargets === 0}>
            {sending ? 'Sending…' : `Send to ${totalTargets || 'no'} recipient${totalTargets === 1 ? '' : 's'}`}
          </button>
        </section>

        <section className="sms-card">
          <h2>Outbox</h2>
          <p className="sms-hint">Every advisory sent from {user.municipality}, newest first.</p>
          {outbox.length === 0 ? (
            <p className="sms-empty">Nothing sent yet.</p>
          ) : (
            <ul className="sms-outbox">
              {outbox.map((m) => (
                <li key={m.id} className={`sms-outbox-row ${m.status}`}>
                  <div className="sms-outbox-head">
                    <span className="sms-outbox-to">{m.recipient_name ?? m.recipient_phone}</span>
                    <span className={`sms-badge ${m.status}`}>{m.status}</span>
                  </div>
                  <div className="sms-outbox-meta">
                    {formatStamp(m.created_at)} · {m.sent_by}
                    {m.provider === 'console' ? ' · simulated' : ''}
                  </div>
                  <div className="sms-outbox-body">{m.body}</div>
                  {m.error && <div className="sms-outbox-error">{m.error}</div>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
