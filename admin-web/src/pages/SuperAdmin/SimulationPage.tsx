import { useEffect, useMemo, useRef, useState } from 'react'
import {
  runSimulationForecast,
  runSimulationImage,
  type FeatureComparisonMetricResult,
  type GrowthStage,
  type PestKey,
  type SimulationDailyObservation,
  type SimulationForecastResponse,
  type SimulationImageResult,
  type SimulationModelResult,
} from '../../lib/api'
import './ModelInsightsPage.css'
import './SimulationPage.css'

interface SimulationPageProps {
  accessToken: string
  onSessionExpired: () => void
}

const GROWTH_STAGES: GrowthStage[] = ['Seedling', 'Tillering', 'Elongation', 'Panicle', 'Flowering', 'Ripening']
const WINDOW_DAYS = 14

const PEST_FULL_NAME: Record<PestKey, string> = {
  BPH: 'Brown Planthopper (BPH)',
  RSB: 'Rice Stem Borer (RSB)',
}

const DEFAULT_DAY = { tmax: 33, tmin: 24, relative_humidity: 82, rainfall: 8 }

function todayMinus(daysAgo: number): string {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return d.toISOString().slice(0, 10)
}

function buildDefaultWindow(growthStage: GrowthStage): SimulationDailyObservation[] {
  return Array.from({ length: WINDOW_DAYS }, (_, i) => ({
    date: todayMinus(WINDOW_DAYS - 1 - i),
    ...DEFAULT_DAY,
    growth_stage: growthStage,
  }))
}

function Dropdown({
  value,
  options,
  onChange,
}: {
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return undefined
    const onClickAway = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClickAway)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClickAway)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="sim-dropdown" ref={rootRef}>
      <button
        type="button"
        className={`sim-dropdown-trigger${open ? ' open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {value}
        <svg className="sim-dropdown-chevron" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 7.5L10 12.5L15 7.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <ul className="sim-dropdown-list" role="listbox">
          {options.map((option) => (
            <li key={option}>
              <button
                type="button"
                role="option"
                aria-selected={option === value}
                className={`sim-dropdown-option${option === value ? ' selected' : ''}`}
                onClick={() => {
                  onChange(option)
                  setOpen(false)
                }}
              >
                {option}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const RISK_COLOR: Record<string, string> = { Low: '#2f6b32', Medium: '#e0b23c', High: '#c23b3b' }

function RiskPill({ level }: { level: string | null }) {
  if (!level) return <span className="sim-pill sim-pill-muted">—</span>
  return (
    <span className="sim-pill" style={{ background: `${RISK_COLOR[level]}22`, color: RISK_COLOR[level] }}>
      {level}
    </span>
  )
}

function ModelResultCard({
  title,
  subtitle,
  result,
  tone,
}: {
  title: string
  subtitle: string
  result: SimulationModelResult | null
  tone: 'green' | 'yellow'
}) {
  return (
    <div className={`sim-result-card sim-result-${tone}`}>
      <div className="sim-result-head">
        <strong>{title}</strong>
        <small>{subtitle}</small>
      </div>
      {!result ? (
        <p className="mi-note">Not run yet.</p>
      ) : result.status === 'model_not_loaded' ? (
        <p className="mi-note">Model not loaded on the server.</p>
      ) : (
        <>
          <div className="sim-result-value">
            {result.predicted_value?.toFixed(2)}
            <span className="sim-result-unit">
              {result.unit === 'hoppers_per_hill' ? 'hoppers/hill' : '% damage'}
            </span>
          </div>
          <RiskPill level={result.risk_level} />
        </>
      )}
    </div>
  )
}

const COMPARISON_METRIC_LABELS: Record<string, { label: string; pct?: boolean }> = {
  rmse: { label: 'RMSE' },
  mae: { label: 'MAE' },
  r2: { label: 'R²' },
  accuracy: { label: 'Accuracy', pct: true },
  precision_macro: { label: 'Precision (macro)', pct: true },
  recall_macro: { label: 'Recall (macro)', pct: true },
  f1_macro: { label: 'F1 (macro)', pct: true },
}
const COMPARISON_METRIC_ORDER = Object.keys(COMPARISON_METRIC_LABELS)

function formatMetric(value: number, pct?: boolean): string {
  return pct ? `${(value * 100).toFixed(1)}%` : value.toFixed(3)
}

function HeldOutMetricsTable({ heldOut }: { heldOut: SimulationForecastResponse['heldOutMetrics'] }) {
  if (!heldOut) {
    return (
      <p className="mi-note">
        No held-out comparison on file yet for this pest. Run{' '}
        <code>python -m ml.bilstm.compare_features --pest BPH</code> (or RSB) from server-python.
      </p>
    )
  }
  return (
    <div className="mi-table-wrap">
      <table className="mi-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Engineered</th>
            <th>Raw (baseline)</th>
            <th>Winner</th>
            <th>p-value</th>
            <th>Significant</th>
          </tr>
        </thead>
        <tbody>
          {COMPARISON_METRIC_ORDER.filter((m) => m in heldOut.significance).map((metric) => {
            const meta = COMPARISON_METRIC_LABELS[metric]
            const r: FeatureComparisonMetricResult = heldOut.significance[metric]
            return (
              <tr key={metric}>
                <td>{meta.label}</td>
                <td>{formatMetric(r.mean_engineered, meta.pct)}</td>
                <td>{formatMetric(r.mean_raw, meta.pct)}</td>
                <td>
                  <span className={`badge ${r.better_configuration === 'engineered' ? 'badge-green' : 'badge-yellow'}`}>
                    {r.better_configuration}
                  </span>
                </td>
                <td>{r.p_value.toFixed(4)}</td>
                <td className={r.significant ? 'bad' : undefined}>{r.significant ? 'Yes' : 'No'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SimulationPage({ accessToken, onSessionExpired }: SimulationPageProps) {
  const [pest, setPest] = useState<PestKey>('BPH')
  const [growthStage, setGrowthStage] = useState<GrowthStage>('Tillering')
  const [days, setDays] = useState<SimulationDailyObservation[]>(() => buildDefaultWindow('Tillering'))
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SimulationForecastResponse | null>(null)

  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [imageRunning, setImageRunning] = useState(false)
  const [imageError, setImageError] = useState('')
  const [imageResult, setImageResult] = useState<SimulationImageResult | null>(null)

  const changeGrowthStage = (stage: GrowthStage) => {
    setGrowthStage(stage)
    setDays((prev) => prev.map((d) => ({ ...d, growth_stage: stage })))
  }

  const applyToAllDays = (field: keyof typeof DEFAULT_DAY, value: number) => {
    setDays((prev) => prev.map((d) => ({ ...d, [field]: value })))
  }

  const updateDay = (index: number, field: keyof typeof DEFAULT_DAY, value: number) => {
    setDays((prev) => prev.map((d, i) => (i === index ? { ...d, [field]: value } : d)))
  }

  const resetWindow = () => setDays(buildDefaultWindow(growthStage))

  const runForecast = async () => {
    setRunning(true)
    setError('')
    try {
      const res = await runSimulationForecast(accessToken, pest, days)
      setResult(res)
    } catch (err) {
      const e = err as Error
      if (e.message.startsWith('Session expired')) onSessionExpired()
      else setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const onPhotoSelected = (file: File | null) => {
    setPhoto(file)
    setImageResult(null)
    setImageError('')
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(file ? URL.createObjectURL(file) : null)
  }

  const runImage = async () => {
    if (!photo) return
    setImageRunning(true)
    setImageError('')
    try {
      const res = await runSimulationImage(accessToken, photo)
      setImageResult(res)
    } catch (err) {
      const e = err as Error
      if (e.message.startsWith('Session expired')) onSessionExpired()
      else setImageError(e.message)
    } finally {
      setImageRunning(false)
    }
  }

  const windowSummary = useMemo(() => {
    const avg = (field: keyof typeof DEFAULT_DAY) => days.reduce((sum, d) => sum + d[field], 0) / days.length
    return {
      tmax: avg('tmax').toFixed(1),
      tmin: avg('tmin').toFixed(1),
      rh: avg('relative_humidity').toFixed(1),
      rainfall: days.reduce((sum, d) => sum + d.rainfall, 0).toFixed(1),
    }
  }, [days])

  return (
    <>
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Simulation</div>
            <div className="panel-subtitle">
              Manually enter a 14-day weather window (and/or a pest photo), then compare the deployed engineered
              model against the raw-feature baseline, side by side.
            </div>
          </div>
        </div>

        <div className="sim-controls-row">
          <div className="mi-toggle" role="tablist">
            {(['BPH', 'RSB'] as PestKey[]).map((p) => (
              <button key={p} type="button" className={pest === p ? 'active' : ''} onClick={() => setPest(p)}>
                {PEST_FULL_NAME[p]}
              </button>
            ))}
          </div>

          <div className="sim-field">
            <span>Growth stage (applies to all 14 days)</span>
            <Dropdown
              value={growthStage}
              options={GROWTH_STAGES}
              onChange={(stage) => changeGrowthStage(stage as GrowthStage)}
            />
          </div>
        </div>

        <div className="sim-quickfill">
          <span>Quick-fill all 14 days:</span>
          <label>
            Tmax
            <input
              type="number"
              step="0.1"
              defaultValue={DEFAULT_DAY.tmax}
              onBlur={(e) => applyToAllDays('tmax', Number(e.target.value))}
            />
          </label>
          <label>
            Tmin
            <input
              type="number"
              step="0.1"
              defaultValue={DEFAULT_DAY.tmin}
              onBlur={(e) => applyToAllDays('tmin', Number(e.target.value))}
            />
          </label>
          <label>
            RH %
            <input
              type="number"
              step="0.1"
              defaultValue={DEFAULT_DAY.relative_humidity}
              onBlur={(e) => applyToAllDays('relative_humidity', Number(e.target.value))}
            />
          </label>
          <label>
            Rainfall mm
            <input
              type="number"
              step="0.1"
              defaultValue={DEFAULT_DAY.rainfall}
              onBlur={(e) => applyToAllDays('rainfall', Number(e.target.value))}
            />
          </label>
          <button type="button" className="mi-btn" onClick={resetWindow}>
            ↺ Reset to defaults
          </button>
        </div>

        <div className="mi-table-wrap sim-day-table">
          <table className="mi-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Date</th>
                <th>Tmax (°C)</th>
                <th>Tmin (°C)</th>
                <th>RH (%)</th>
                <th>Rainfall (mm)</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d, i) => (
                <tr key={d.date} className={i === days.length - 1 ? 'current' : undefined}>
                  <td>{i + 1 === days.length ? `${i + 1} (most recent)` : i + 1}</td>
                  <td>{d.date}</td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={d.tmax}
                      onChange={(e) => updateDay(i, 'tmax', Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={d.tmin}
                      onChange={(e) => updateDay(i, 'tmin', Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={d.relative_humidity}
                      onChange={(e) => updateDay(i, 'relative_humidity', Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={d.rainfall}
                      onChange={(e) => updateDay(i, 'rainfall', Number(e.target.value))}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mi-note">
          Window summary: mean Tmax {windowSummary.tmax}°C · mean Tmin {windowSummary.tmin}°C · mean RH{' '}
          {windowSummary.rh}% · total rainfall {windowSummary.rainfall}mm over {WINDOW_DAYS} days. The forecast is
          for 14 days after the most recent day above.
        </p>

        <div className="sim-run-row">
          <button type="button" className="mi-btn mi-btn-primary" onClick={runForecast} disabled={running}>
            {running ? 'Running…' : '▶ Run forecast'}
          </button>
          {error && <p className="stat-card-error">{error}</p>}
        </div>
      </section>

      {result && (
        <section className="panel mi-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">Live prediction: engineered vs. raw baseline</div>
              <div className="panel-subtitle">Same manually-entered window, same BiLSTM architecture, two feature sets</div>
            </div>
          </div>
          <div className="sim-results-row">
            <ModelResultCard
              title="Engineered (deployed)"
              subtitle="GDD · CRF · HP · VPD · WSI · trends · growth-stage one-hot"
              result={result.engineered}
              tone="green"
            />
            <ModelResultCard
              title="Raw (baseline)"
              subtitle="Tmax / Tmin / RH / Rainfall only — the thesis's RQ2 control"
              result={result.raw}
              tone="yellow"
            />
          </div>

          <h4 className="mi-h4">Held-out test performance (historical, both configurations)</h4>
          <HeldOutMetricsTable heldOut={result.heldOutMetrics} />
        </section>
      )}

      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Pest photo (ResNet-50)</div>
            <div className="panel-subtitle">Upload a field photo to run it through the real deployed classifier</div>
          </div>
        </div>

        <div className="sim-photo-row">
          <div className="sim-photo-upload">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => onPhotoSelected(e.target.files?.[0] ?? null)}
            />
            {photoPreview && <img src={photoPreview} alt="Selected pest photo preview" className="sim-photo-preview" />}
            <button type="button" className="mi-btn mi-btn-primary" onClick={runImage} disabled={!photo || imageRunning}>
              {imageRunning ? 'Classifying…' : '▶ Classify photo'}
            </button>
            {imageError && <p className="stat-card-error">{imageError}</p>}
          </div>

          {imageResult && (
            <div className="sim-photo-result">
              {imageResult.status === 'model_not_loaded' && <p className="mi-note">ResNet-50 model not loaded on the server.</p>}
              {imageResult.status === 'no_pest_detected' && (
                <p className="mi-note">No tracked pest (BPH/RSB) detected with sufficient confidence.</p>
              )}

              {imageResult.heldOutMetrics && (
                <>
                  <h4 className="mi-h4">Held-out test performance for the detected pest(s)</h4>
                  <div className="sim-image-metrics">
                    {Object.entries(imageResult.heldOutMetrics).map(([p, m]) =>
                      m ? (
                        <div key={p} className="sim-image-metric">
                          <div className="sim-image-metric-label">{PEST_FULL_NAME[p as PestKey] ?? p}</div>
                          <div className="sim-image-metric-value">{(m.accuracy * 100).toFixed(1)}%</div>
                          <div className="sim-image-metric-hint">
                            Accuracy · P {(m.positive_precision * 100).toFixed(0)}% · R{' '}
                            {(m.positive_recall * 100).toFixed(0)}% · F1 {(m.positive_f1 * 100).toFixed(0)}%
                          </div>
                        </div>
                      ) : null,
                    )}
                  </div>
                </>
              )}

              {imageResult.status === 'ok' && (
                <>
                  <div className="sim-result-value">
                    {PEST_FULL_NAME[imageResult.pest_detected as PestKey] ?? imageResult.pest_detected}
                    <span className="sim-result-unit">
                      {imageResult.confidence != null ? `${(imageResult.confidence * 100).toFixed(1)}% confidence` : ''}
                    </span>
                  </div>
                  {imageResult.pests_detected.length > 1 && (
                    <div className="sim-pest-scores">
                      {imageResult.pests_detected.map((p) => (
                        <span key={p} className="sim-pill sim-pill-muted">
                          {p}: {((imageResult.pest_scores[p] ?? 0) * 100).toFixed(1)}%
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </section>
    </>
  )
}

export default SimulationPage
