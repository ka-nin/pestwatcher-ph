import { useEffect, useMemo, useState } from 'react'
import { scanFieldPhoto, type FieldAssessment, type PhotoScan } from '../../lib/api'
import './FieldAssessmentPage.css'

// A cell at or above this share is drawn at full strength; the scale is capped
// because the model's cell values are small percentages.
const CELL_FULL_PCT = 3

function cellColour(value: number, hasDamage: boolean) {
  if (!hasDamage) return 'rgba(0, 0, 0, 0)'
  const strength = Math.min(1, 0.25 + value / CELL_FULL_PCT)
  return `rgba(214, 69, 65, ${strength * 0.55})`
}

type SizeUnit = 'ha' | 'm2'
const M2_PER_HA = 10_000

// Area is shown in the unit the field size was entered in. The photo alone has no scale
// (a close-up and a wide shot look alike), so there is no area without a field size.
function formatArea(ha: number, unit: SizeUnit) {
  if (unit === 'm2') {
    const m2 = ha * M2_PER_HA
    return `${(m2 < 10 ? Number(m2.toFixed(1)) : Math.round(m2)).toLocaleString()} m²`
  }
  return `${Number(ha.toFixed(4))} ha`
}

function areaValue(r: FieldAssessment, unit: SizeUnit) {
  return r.affected_hectares != null ? formatArea(r.affected_hectares, unit) : 'n/a'
}

function areaNote(r: FieldAssessment, unit: SizeUnit) {
  if (r.affected_hectares != null && r.field_size_ha != null) {
    return `of ${formatArea(r.field_size_ha, unit)}${r.field_size_source === 'photo_metadata' ? ' (from drone data)' : ''}`
  }
  return 'Enter the field size to get the affected area'
}

function FieldAssessmentPage() {
  const [file, setFile] = useState<File | null>(null)
  const [fieldSize, setFieldSize] = useState('')
  const [unit, setUnit] = useState<SizeUnit>('ha')
  const [scan, setScan] = useState<PhotoScan | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const typed = fieldSize.trim() === '' ? null : Number(fieldSize)
  const sizeInvalid = typed != null && (!Number.isFinite(typed) || typed <= 0)
  const sizeNumber = typed == null ? null : unit === 'm2' ? typed / M2_PER_HA : typed

  async function run() {
    if (!file || sizeInvalid) return
    setBusy(true)
    setError('')
    setScan(null)
    try {
      setScan(await scanFieldPhoto(file, sizeNumber))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Photo scan failed.')
    } finally {
      setBusy(false)
    }
  }

  const result: FieldAssessment | null = scan?.field_assessment ?? null
  const ok = result?.status === 'ok'
  const pestName = scan?.pest_detected === 'BPH' ? 'Brown Planthopper (BPH)' : scan?.pest_detected === 'RSB' ? 'Rice Stem Borer (RSB)' : null
  return (
    <>
      <section className="panel forecast-summary-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Field Assessment</div>
            <div className="panel-subtitle">
              Upload a photo: the pest is identified automatically, then counted (planthoppers) or assessed for damage (stem borer)
            </div>
          </div>
          <span className="badge badge-yellow">Estimate · not verified</span>
        </div>
      </section>

      <div className="fa-grid">
        <section className="panel fa-panel">
          <div className="fa-field">
            <label htmlFor="fa-photo">Field photo</label>
            <input
              id="fa-photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setScan(null)
                setError('')
              }}
            />
          </div>
          <div className="fa-field">
            <label htmlFor="fa-size">Field size (optional)</label>
            <div className="fa-size-row">
              <input
                id="fa-size"
                type="number"
                min="0"
                step="any"
                placeholder={unit === 'ha' ? 'e.g. 1.5' : 'e.g. 5000'}
                value={fieldSize}
                onChange={(e) => setFieldSize(e.target.value)}
              />
              <select aria-label="Field size unit" value={unit} onChange={(e) => setUnit(e.target.value as SizeUnit)}>
                <option value="ha">hectares</option>
                <option value="m2">m²</option>
              </select>
            </div>
            <span className="fa-hint">Needed for the affected area: a photo has no scale of its own, except drone photos that record their height.</span>
            {sizeInvalid && <span className="fa-error">Enter a size above 0.</span>}
          </div>
          <button className="fa-run" disabled={!file || busy || sizeInvalid} onClick={run}>
            {busy ? 'Scanning…' : 'Scan photo'}
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

      {scan && (
        <section className="panel fa-panel">
          <div className="fa-metric-label">Detected automatically</div>
          <div className="fa-metric-value">{pestName ?? 'No tracked pest'}</div>
          <p className="fa-caveat">{scan.message}</p>
          {scan.pest_detected === 'BPH' && (
            <div className="fa-metrics">
              <div className="fa-metric">
                <div className="fa-metric-label">Estimated count</div>
                <div className="fa-metric-value">{scan.estimated_count?.toFixed(1) ?? 'n/a'}</div>
                <div className="fa-metric-note">hoppers per hill (AI estimate)</div>
              </div>
              <div className="fa-metric">
                <div className="fa-metric-label">Coverage</div>
                <div className="fa-metric-value">{scan.estimated_coverage_pct?.toFixed(0) ?? 'n/a'}%</div>
                <div className="fa-metric-note">of the photo affected</div>
              </div>
              <div className="fa-metric">
                <div className="fa-metric-label">Risk</div>
                <div className="fa-metric-value">{scan.risk_level ?? 'n/a'}</div>
                <div className="fa-metric-note">from detection confidence</div>
              </div>
            </div>
          )}
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
              <div className="fa-metric-note">of the photo's grid cells show damage</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Affected area</div>
              <div className="fa-metric-value">{areaValue(result!, unit)}</div>
              <div className="fa-metric-note">{areaNote(result!, unit)}</div>
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
