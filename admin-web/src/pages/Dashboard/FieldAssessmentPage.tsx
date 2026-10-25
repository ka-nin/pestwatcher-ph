import { useEffect, useMemo, useState } from 'react'
import { scanFieldPhoto, type FieldAssessment, type FieldAssessmentDay, type GrowthStage, type LguUser, type PhotoScan } from '../../lib/api'
import { ASSUMED_GROWTH_STAGE, RISK_TONE } from '../../lib/etl'
import './FieldAssessmentPage.css'

const GROWTH_STAGES: GrowthStage[] = ['Seedling', 'Tillering', 'Elongation', 'Panicle', 'Flowering', 'Ripening']

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

function areaValue(ha: number | null, unit: SizeUnit) {
  return ha != null ? formatArea(ha, unit) : 'n/a'
}

function areaNote(r: FieldAssessment, selectedDay: FieldAssessmentDay | null, unit: SizeUnit) {
  if (selectedDay?.affected_hectares != null && r.field_size_ha != null) {
    return `of ${formatArea(r.field_size_ha, unit)}${r.field_size_source === 'photo_metadata' ? ' (from drone data)' : ''}`
  }
  return 'Enter the field size to get the affected area'
}

function dayLabel(dateStr: string, isMeasured: boolean) {
  const d = new Date(dateStr + 'T00:00:00')
  const label = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return isMeasured ? `${label} (today)` : label
}

function dateRangeLabel(days: FieldAssessmentDay[]) {
  const first = new Date(days[0].date + 'T00:00:00')
  const last = new Date(days[days.length - 1].date + 'T00:00:00')
  const sameYear = first.getFullYear() === last.getFullYear()
  const firstLabel = first.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: sameYear ? undefined : 'numeric' })
  const lastLabel = last.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  return `${firstLabel} – ${lastLabel}`
}

interface FieldAssessmentPageProps {
  user: LguUser
}

function FieldAssessmentPage({ user }: FieldAssessmentPageProps) {
  const [file, setFile] = useState<File | null>(null)
  const [fieldSize, setFieldSize] = useState('')
  const [unit, setUnit] = useState<SizeUnit>('ha')
  const [growthStage, setGrowthStage] = useState<GrowthStage>(ASSUMED_GROWTH_STAGE)
  const [scan, setScan] = useState<PhotoScan | null>(null)
  const [selectedDayIndex, setSelectedDayIndex] = useState(0)
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
    setSelectedDayIndex(0)
    try {
      setScan(await scanFieldPhoto(file, sizeNumber, user.municipality, growthStage))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Photo scan failed.')
    } finally {
      setBusy(false)
    }
  }

  const result: FieldAssessment | null = scan?.field_assessment ?? null
  const ok = result?.status === 'ok'
  const pestName = scan?.pest_detected === 'BPH' ? 'Brown Planthopper (BPH)' : scan?.pest_detected === 'RSB' ? 'Rice Stem Borer (RSB)' : null
  const daily = result?.daily ?? null
  const selectedDay: FieldAssessmentDay | null = daily?.[selectedDayIndex] ?? null
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
          <div className="fa-field">
            <label htmlFor="fa-growth-stage">Growth stage</label>
            <select id="fa-growth-stage" value={growthStage} onChange={(e) => setGrowthStage(e.target.value as GrowthStage)}>
              {GROWTH_STAGES.map((stage) => (
                <option key={stage} value={stage}>{stage}</option>
              ))}
            </select>
            <span className="fa-hint">Used with {user.municipality}'s weather for the 14-day outlook below.</span>
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
          {scan.estimated_count != null && (
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

      {ok && daily && (
        <section className="panel fa-panel">
          <div className="fa-day-head">
            <div>
              <div className="panel-title">14-day outlook</div>
              <div className="fa-day-range">{dateRangeLabel(daily)}</div>
            </div>
            {!selectedDay?.is_measured && <span className="badge badge-yellow">Projected from today's photo</span>}
          </div>
          <div className="fa-day-strip">
            {daily.map((d, i) => (
              <button
                key={d.date}
                type="button"
                className={`fa-day-btn${i === selectedDayIndex ? ' is-selected' : ''}`}
                onClick={() => setSelectedDayIndex(i)}
              >
                <span className="fa-day-label">{dayLabel(d.date, d.is_measured)}</span>
                <span className={`fa-day-risk fa-day-risk-${RISK_TONE[d.risk_level]}`}>{d.risk_level}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {ok && (
        <section className="panel fa-panel">
          <div className="fa-metrics">
            <div className="fa-metric">
              <div className="fa-metric-label">Severity</div>
              <div className="fa-metric-value">{(selectedDay?.severity_pct ?? result!.pct_affected)?.toFixed(2)}%</div>
              <div className="fa-metric-note">{result?.pest === 'BPH' ? 'of the plants in view are dried' : 'of the photo covered by damage'}</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Spread</div>
              <div className="fa-metric-value">{(selectedDay?.spread_pct ?? result!.cells_affected_pct)?.toFixed(0)}%</div>
              <div className="fa-metric-note">of the field's grid cells show damage</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Affected area</div>
              <div className="fa-metric-value">{areaValue(selectedDay?.affected_hectares ?? result!.affected_hectares, unit)}</div>
              <div className="fa-metric-note">{areaNote(result!, selectedDay, unit)}</div>
            </div>
            <div className="fa-metric">
              <div className="fa-metric-label">Pest count</div>
              <div className="fa-metric-value">{selectedDay ? selectedDay.pest_level.toFixed(2) : result!.severity_where_present_pct?.toFixed(2)}</div>
              <div className="fa-metric-note">
                {selectedDay
                  ? result!.pest === 'RSB' ? '% damage (BiLSTM forecast)' : 'hoppers/hill (BiLSTM forecast)'
                  : 'severity where present, average over affected cells'}
              </div>
            </div>
            {selectedDay && (
              <div className="fa-metric">
                <div className="fa-metric-label">Risk</div>
                <div className={`fa-metric-value fa-risk-${RISK_TONE[selectedDay.risk_level]}`}>{selectedDay.risk_level}</div>
                <div className="fa-metric-note">{selectedDay.is_measured ? "today's forecast" : 'forecast for this day'}</div>
              </div>
            )}
          </div>
          <p className="fa-caveat">
            {selectedDay?.is_measured
              ? 'Severity and spread are measured from this photo. '
              : "Severity, spread and affected area for this day are PROJECTED by scaling today's photo reading with the BiLSTM forecast — not a new measurement. "}
            {result?.pest === 'BPH'
              ? 'Hopperburn is read from the photo by colour and shape (a large solid dried patch with green plants around it), not by a trained model: a technologist must confirm it. Severity is the dried share of the plants in view.'
              : 'Estimate from a model trained on synthetic images; a technologist must confirm it. Severity is the share of the photo covered by whiteheads, a stand-in for the percentage of white ears.'}
          </p>
        </section>
      )}
    </>
  )
}

export default FieldAssessmentPage
