import { useEffect, useState } from 'react'
import { assessFieldPhoto, type FieldAssessment, type PestKey } from '../../lib/api'
import './FieldAssessmentPage.css'

// A cell at or above this share is drawn at full strength; the scale is capped
// because the model's cell values are small percentages.
const CELL_FULL_PCT = 3

function cellColour(value: number, hasDamage: boolean) {
  if (!hasDamage) return 'rgba(0, 0, 0, 0)'
  const strength = Math.min(1, 0.25 + value / CELL_FULL_PCT)
  return `rgba(214, 69, 65, ${strength * 0.55})`
}

function FieldAssessmentPage() {
  const [pest, setPest] = useState<PestKey>('RSB')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [fieldSize, setFieldSize] = useState('')
  const [result, setResult] = useState<FieldAssessment | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  const sizeNumber = fieldSize.trim() === '' ? null : Number(fieldSize)
  const sizeInvalid = sizeNumber != null && (!Number.isFinite(sizeNumber) || sizeNumber <= 0)

  async function run() {
    if (!file || sizeInvalid) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      setResult(await assessFieldPhoto(file, pest, sizeNumber))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Field assessment failed.')
    } finally {
      setBusy(false)
    }
  }

  const ok = result?.status === 'ok'
  return (
    <>
      <section className="panel forecast-summary-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Field Assessment</div>
            <div className="panel-subtitle">
              Upload a whole-field photo to estimate how severe the damage is and how widely it is spread
            </div>
          </div>
          <span className="badge badge-yellow">Estimate · not verified</span>
        </div>
      </section>

      <div className="fa-grid">
        <section className="panel fa-panel">
          <div className="fa-field">
            <label htmlFor="fa-pest">Pest</label>
            <select id="fa-pest" value={pest} onChange={(e) => setPest(e.target.value as PestKey)}>
              <option value="RSB">Rice Stem Borer (whiteheads)</option>
              <option value="BPH">Brown Planthopper (hopperburn)</option>
            </select>
          </div>
          <div className="fa-field">
            <label htmlFor="fa-photo">Field photo</label>
            <input
              id="fa-photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setResult(null)
                setError('')
              }}
            />
          </div>
          <div className="fa-field">
            <label htmlFor="fa-size">Field size in hectares (optional)</label>
            <input
              id="fa-size"
              type="number"
              min="0"
              step="0.1"
              placeholder="e.g. 1.5"
              value={fieldSize}
              onChange={(e) => setFieldSize(e.target.value)}
            />
            {sizeInvalid && <span className="fa-error">Enter a size above 0.</span>}
          </div>
          <button className="fa-run" disabled={!file || busy || sizeInvalid} onClick={run}>
            {busy ? 'Assessing…' : 'Assess photo'}
          </button>
          {error && <p className="fa-error">{error}</p>}
        </section>

        <section className="panel fa-panel">
          {!previewUrl && <p className="stat-card-loading">Choose a photo to begin.</p>}
          {previewUrl && (
            <div className="fa-photo-wrap">
              <img src={previewUrl} alt="Field photo" className="fa-photo" />
              {ok && (
                <div
                  className="fa-overlay"
                  style={{ gridTemplateColumns: `repeat(${result!.cols}, 1fr)`, gridTemplateRows: `repeat(${result!.rows}, 1fr)` }}
                >
                  {result!.cell_values.flat().map((v, i) => (
                    <div key={i} className="fa-cell" style={{ background: cellColour(v, result!.cell_has_damage.flat()[i]) }} title={`${v.toFixed(2)}% of this cell`}>
                      <span>{v.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {result && !ok && (
        <section className="panel fa-panel">
          <p className="fa-error">{result.message}</p>
        </section>
      )}

      {ok && (
        <section className="panel fa-panel">
          <div className="fa-metrics">
            <div className="fa-metric">
              <div className="fa-metric-label">Severity</div>
              <div className="fa-metric-value">{result!.pct_affected?.toFixed(2)}%</div>
              <div className="fa-metric-note">of the photo covered by damage</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Spread</div>
              <div className="fa-metric-value">{result!.cells_affected_pct?.toFixed(0)}%</div>
              <div className="fa-metric-note">of the field area shows damage</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Affected area</div>
              <div className="fa-metric-value">{result!.affected_hectares != null ? `${result!.affected_hectares} ha` : 'n/a'}</div>
              <div className="fa-metric-note">{result!.affected_hectares != null ? `of ${result!.field_size_ha} ha` : 'enter the field size'}</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Where present</div>
              <div className="fa-metric-value">{result!.severity_where_present_pct?.toFixed(2)}%</div>
              <div className="fa-metric-note">average over affected cells</div>
            </div>
          </div>
          <p className="fa-caveat">
            {result!.message} Severity is the share of the photo covered by whiteheads, a stand-in for the percentage of
            white ears. Highlighted cells are the ones the model judges to contain damage.
          </p>
        </section>
      )}
    </>
  )
}

export default FieldAssessmentPage
