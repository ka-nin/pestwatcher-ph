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

function areaValue(r: FieldAssessment) {
  if (r.affected_hectares != null) return `${r.affected_hectares} ha`
  if (r.affected_area_m2 != null) return `~${Math.round(r.affected_area_m2)} m²`
  return 'n/a'
}

function areaNote(r: FieldAssessment) {
  if (r.affected_hectares != null) {
    return `of ${r.field_size_ha} ha${r.field_size_source === 'photo_metadata' ? ' (from drone data)' : ''}`
  }
  if (r.affected_area_m2 != null) {
    return `Between ${Math.round(r.affected_area_m2_low ?? 0)} and ${Math.round(r.affected_area_m2_high ?? 0)} m² of the ~${Math.round(r.visible_area_m2 ?? 0)} m² seen in the photo`
  }
  return 'Enter the field size'
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
            <span className="fa-hint">Leave blank to estimate the area from the photo itself.</span>
            {sizeInvalid && <span className="fa-error">Enter a size above 0.</span>}
          </div>
          <button className="fa-run" disabled={!file || busy || sizeInvalid} onClick={run}>
            {busy ? 'Assessing…' : 'Assess photo'}
          </button>
          {error && <p className="fa-error">{error}</p>}
        </section>

        <section className="panel fa-panel">
          {!previewUrl && <div className="fa-empty">Choose a field photo to begin.</div>}
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
                      {result!.cell_has_damage.flat()[i] && <span>{v.toFixed(1)}%</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {previewUrl && ok && <p className="fa-legend"><i /> Cells the model judges to contain damage</p>}
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
              <div className="fa-metric-value">{areaValue(result!)}</div>
              <div className="fa-metric-note">{areaNote(result!)}</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Where present</div>
              <div className="fa-metric-value">{result!.severity_where_present_pct?.toFixed(2)}%</div>
              <div className="fa-metric-note">average over affected cells</div>
            </div>
          </div>
          <p className="fa-caveat">
            Estimate from a model trained on synthetic images; a technologist must confirm it. Severity is the share of
            the photo covered by whiteheads, a stand-in for the percentage of white ears.
          </p>
        </section>
      )}
    </>
  )
}

export default FieldAssessmentPage
