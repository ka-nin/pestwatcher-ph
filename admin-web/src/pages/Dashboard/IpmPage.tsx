import { useState } from 'react'
import type { LguUser } from '../../lib/api'
import './IpmPage.css'

interface IpmPageProps {
  user: LguUser
}

const pestCards = [
  {
    key: 'bph',
    title: 'Brown Planthopper',
    stage: 'Vegetative',
    big: { value: '12', unit: 'hoppers/hill' },
    metricLabel: 'Density vs ETL',
    etlLabel: 'High Risk ETL Limit: 20',
    percentOfEtl: 60,
    risk: { label: 'Medium Risk', tone: 'yellow' as const },
    actionsTitle: 'Recommended Actions',
    actions: [
      'Scout 10 hills per plot weekly',
      'Apply neem-based botanical spray',
      'Maintain alternate wetting and drying (AWD) irrigation',
      'Preserve natural enemies, avoid blanket insecticide use',
    ],
  },
  {
    key: 'rsb',
    title: 'Rice Stem Borer',
    stage: 'Vegetative',
    big: { value: '1.5%', unit: '% Dead Hearts' },
    metricLabel: 'Damage vs ETL',
    etlLabel: 'High Risk ETL Limit: 5%',
    percentOfEtl: 30,
    risk: { label: 'Low Risk', tone: 'green' as const },
    actionsTitle: 'Routine Monitoring',
    actions: [
      'Light trap surveillance',
      'Check first instar weekly',
      'Record adult moth catches',
      'Inspect tillers for egg masses on leaf tips',
      'Maintain synchronous planting with neighboring farms',
    ],
  },
]

const defaultAdvisoryMessage = `PESTWATCHER ALERT - Nueva Ecija
Petsa: May 17, 2026
Kasalukuyang panganib: MABABA
Brown Planthopper: mababa ang panganib. Ipagpatuloy ang regular na pagmamanman ng palayan.
Yellow Stem Borer: mababa ang panganib. Mag-check pa rin ng sintomas tulad ng deadheart o whitehead.
Payo: Mag-monitor ng palayan lingu-linggo. Hindi kailangan ang agarang pag-spray ng pestisidyo. Kumonsulta sa agricultural technician kung may nakitang pagdami ng peste.`

const timeline = [
  { date: 'May 17', bphDensity: '12', bphTone: 'low', bphAction: 'Routine scouting', rsbDamage: '1.5%', rsbTone: 'low', rsbAction: 'Light trap check' },
  { date: 'May 19', bphDensity: '15', bphTone: 'low', bphAction: 'Routine scouting', rsbDamage: '1.8%', rsbTone: 'low', rsbAction: 'Light trap check' },
  { date: 'May 21', bphDensity: '19', bphTone: 'mid', bphAction: 'Apply botanical spray', rsbDamage: '2.2%', rsbTone: 'low', rsbAction: 'Inspect tillers' },
  { date: 'May 23', bphDensity: '24', bphTone: 'mid', bphAction: 'Apply botanical spray', rsbDamage: '2.6%', rsbTone: 'low', rsbAction: 'Inspect tillers' },
  { date: 'May 25', bphDensity: '31', bphTone: 'high', bphAction: 'Escalate to LGU advisory', rsbDamage: '3.1%', rsbTone: 'mid', rsbAction: 'Record moth catches' },
  { date: 'May 27', bphDensity: '38', bphTone: 'high', bphAction: 'Escalate to LGU advisory', rsbDamage: '3.5%', rsbTone: 'mid', rsbAction: 'Record moth catches' },
]

function riskChipLabel(tone: string) {
  if (tone === 'low') return 'LOW'
  if (tone === 'mid') return 'MED'
  return 'HIGH'
}

type SendStatus = 'idle' | 'sending' | 'sent' | 'failed'

const SMS_SEGMENT_LENGTH = 160

function IpmPage({ user }: IpmPageProps) {
  const [message, setMessage] = useState(defaultAdvisoryMessage)
  const [showPreview, setShowPreview] = useState(false)
  const [sendStatus, setSendStatus] = useState<SendStatus>('idle')
  const [sentAt, setSentAt] = useState<string | null>(null)

  const segments = Math.max(1, Math.ceil(message.length / SMS_SEGMENT_LENGTH))

  const handleMessageChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value)
    // Editing after a send means the indicator no longer reflects what's on screen.
    if (sendStatus !== 'sending') {
      setSendStatus('idle')
    }
  }

  const handleSend = () => {
    if (!message.trim()) return
    setSendStatus('sending')
    // TODO: wire up to a real SMS gateway endpoint once one exists.
    setTimeout(() => {
      setSendStatus('sent')
      setSentAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    }, 900)
  }

  return (
    <>
      <section className="ipm-grid">
        {pestCards.map((pest) => (
          <div className="panel ipm-card" key={pest.key}>
            <div className="panel-head">
              <div>
                <div className="panel-title">{pest.title}</div>
                <div className="panel-subtitle">Current Stage: {pest.stage}</div>
              </div>
              <span className="badge badge-green">{pest.stage}</span>
            </div>

            <div className="stat-card-big">
              <span className="stat-card-big-value">{pest.big.value}</span>
              <span className="stat-card-big-unit">{pest.big.unit}</span>
            </div>

            <div className="ipm-progress-row">
              <span>{pest.metricLabel}</span>
              <span className="ipm-progress-limit">{pest.etlLabel}</span>
            </div>
            <div className="ipm-progress-track">
              <div
                className={`ipm-progress-fill ipm-progress-${pest.risk.tone}`}
                style={{ width: `${pest.percentOfEtl}%` }}
              />
            </div>

            <div className="stat-card-risk-row ipm-risk-row">
              <span className="stat-card-risk-label">Risk</span>
              <span className={`badge badge-${pest.risk.tone}`}>{pest.risk.label}</span>
            </div>

            <div className="ipm-actions">
              <div className="ipm-actions-title">{pest.actionsTitle}</div>
              <ul>
                {pest.actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </section>

      <section className="row-2">
        <div className="panel advisory-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">Provincial Advisory</div>
              <div className="panel-subtitle">SMS / public advisory message</div>
            </div>
            <svg className="advisory-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path
                d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-4 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <textarea
            className="advisory-message-input"
            value={message}
            onChange={handleMessageChange}
            rows={7}
            spellCheck={false}
          />
          <div className="advisory-meta">
            {message.length} characters · {segments} SMS segment{segments === 1 ? '' : 's'}
          </div>

          {showPreview && (
            <div className="advisory-preview">
              <div className="advisory-preview-label">Preview</div>
              <div className="advisory-preview-bubble">{message}</div>
            </div>
          )}

          <div className="advisory-actions">
            <div className="advisory-status" aria-live="polite">
              {sendStatus === 'sending' && (
                <span className="advisory-status-sending">
                  <span className="advisory-spinner" /> Sending…
                </span>
              )}
              {sendStatus === 'sent' && (
                <span className="advisory-status-sent">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Sent{sentAt ? ` at ${sentAt}` : ''}
                </span>
              )}
              {sendStatus === 'failed' && (
                <span className="advisory-status-failed">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Failed to send
                </span>
              )}
            </div>

            <button
              type="button"
              className="btn-outline"
              onClick={() => setShowPreview((v) => !v)}
            >
              {showPreview ? 'Hide Preview' : 'Preview SMS'}
            </button>
            <button
              type="button"
              className="btn-dark"
              onClick={handleSend}
              disabled={sendStatus === 'sending' || !message.trim()}
            >
              {sendStatus === 'sending' ? 'Sending…' : 'Send SMS'}
            </button>
          </div>
        </div>
      </section>

      <section className="row-2">
        <div className="panel timeline-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">14-Day Action Timeline</div>
              <div className="panel-subtitle">
                When to send each pest-specific advisory based on forecasted ETL breaches
              </div>
            </div>
          </div>

          <div className="timeline-table-wrap">
            <table className="timeline-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>BPH Density</th>
                  <th>BPH Action</th>
                  <th>RSB Damage</th>
                  <th>RSB Action</th>
                </tr>
              </thead>
              <tbody>
                {timeline.map((row) => (
                  <tr key={row.date}>
                    <td>{row.date}</td>
                    <td>
                      <span className="timeline-value">{row.bphDensity}</span>
                      <span className={`badge badge-chip heatmap-${row.bphTone}`}>
                        {riskChipLabel(row.bphTone)}
                      </span>
                    </td>
                    <td>{row.bphAction}</td>
                    <td>
                      <span className="timeline-value">{row.rsbDamage}</span>
                      <span className={`badge badge-chip heatmap-${row.rsbTone}`}>
                        {riskChipLabel(row.rsbTone)}
                      </span>
                    </td>
                    <td>{row.rsbAction}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <p className="ipm-footnote">
        Advisories are generated for {user.municipality}, {user.province} based on the active
        forecast model. Placeholder data — not yet wired to the ML pipeline.
      </p>
    </>
  )
}

export default IpmPage
