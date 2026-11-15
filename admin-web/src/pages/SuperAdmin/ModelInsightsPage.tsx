import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  fetchModelInsights,
  type FeatureComparisonResponse,
  type ModelInsightsResponse,
  type PredictionPointDto,
  type ResnetRegressionMetrics,
  type ResnetTestMetrics,
  type ShapFeatureDto,
} from '../../lib/api'
import { PHOTO_FLOW, WEATHER_FLOW, type FlowStep, type PestCode } from './modelInsightsData'
import './ModelInsightsPage.css'

type TabKey = 'flow' | 'system' | 'resnet' | 'bilstm'
type LaneKey = 'photo' | 'weather'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'flow', label: 'How it works' },
  { key: 'system', label: 'System Performance' },
  { key: 'resnet', label: 'ResNet-50 performance' },
  { key: 'bilstm', label: 'BiLSTM regression' },
]

const GREEN = '#2f6b32'
const GREEN_SOFT = '#dcebd6'
const YELLOW = '#e0b23c'
const ORANGE = '#dd6b3a'
const GREY = '#c9c5b8'
const INK = '#3a382f'

const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`

/* ------------------------------------------------------------------ */
/* Small illustrations, one per flow step                              */
/* ------------------------------------------------------------------ */

function Grid({ cols, rows, cell, x0, y0, hit = [], stray = [] }: {
  cols: number
  rows: number
  cell: number
  x0: number
  y0: number
  hit?: [number, number][]
  stray?: [number, number][]
}) {
  const isHit = (c: number, r: number) => hit.some(([hc, hr]) => hc === c && hr === r)
  const isStray = (c: number, r: number) => stray.some(([sc, sr]) => sc === c && sr === r)
  const cells: ReactNode[] = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      cells.push(
        <rect
          key={`${c}-${r}`}
          x={x0 + c * cell}
          y={y0 + r * cell}
          width={cell}
          height={cell}
          fill={isHit(c, r) ? GREEN : isStray(c, r) ? ORANGE : '#f7f5ee'}
          fillOpacity={isHit(c, r) ? 0.4 : isStray(c, r) ? 0.35 : 1}
          stroke={GREY}
          strokeWidth={0.7}
          className={isHit(c, r) ? 'mi-pulse' : undefined}
        />,
      )
    }
  }
  return <>{cells}</>
}

function StepArt({ id }: { id: string }) {
  const label = { fontSize: 9, fill: INK, fontWeight: 700 } as const
  switch (id) {
    case 'photo':
      return (
        <svg viewBox="0 0 220 130">
          <rect x="24" y="14" width="172" height="102" rx="8" fill={GREEN_SOFT} stroke={GREEN} strokeWidth="1.5" />
          {[50, 80, 110, 140, 170].map((x) => (
            <path key={x} d={`M${x} 116 C ${x - 6} 84, ${x + 8} 60, ${x} 34`} stroke={GREEN} strokeWidth="2" fill="none" opacity="0.55" />
          ))}
          <circle cx="98" cy="70" r="3.4" fill="#7a4b22" className="mi-pulse" />
          <circle cx="132" cy="52" r="3" fill="#7a4b22" className="mi-pulse" />
          <circle cx="152" cy="88" r="3.2" fill="#7a4b22" className="mi-pulse" />
        </svg>
      )
    case 'route':
      return (
        <svg viewBox="0 0 220 130">
          <rect x="18" y="38" width="52" height="52" rx="5" fill="#f7f5ee" stroke={GREEN} strokeWidth="1.5" />
          <text x="44" y="68" textAnchor="middle" {...label}>whole</text>
          <text x="44" y="104" textAnchor="middle" fontSize="8.5" fill="#777">≤ 480 px</text>
          <path d="M78 64 H108" stroke={GREY} strokeWidth="2" markerEnd="url(#mi-arrow)" />
          <rect x="118" y="20" width="86" height="86" rx="5" fill="#f7f5ee" stroke={ORANGE} strokeWidth="1.5" />
          {[1, 2, 3].map((i) => (
            <g key={i}>
              <path d={`M${118 + i * 21.5} 20 V106`} stroke={GREY} strokeWidth="0.8" />
              <path d={`M118 ${20 + i * 21.5} H204`} stroke={GREY} strokeWidth="0.8" />
            </g>
          ))}
          <text x="161" y="123" textAnchor="middle" fontSize="8.5" fill="#777">&gt; 480 px → grid (BPH)</text>
          <defs>
            <marker id="mi-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
              <path d="M0 0 L8 4 L0 8 Z" fill={GREY} />
            </marker>
          </defs>
        </svg>
      )
    case 'tiles':
      return (
        <svg viewBox="0 0 220 130">
          <Grid cols={8} rows={5} cell={24} x0={14} y0={5} hit={[[3, 2], [4, 2], [3, 3], [4, 3]]} />
          <circle cx="98" cy="72" r="4" fill="#7a4b22" />
          <text x="110" y="126" textAnchor="middle" fontSize="8.5" fill="#777">one insect lights up several overlapping tiles</text>
        </svg>
      )
    case 'resnet':
      return (
        <svg viewBox="0 0 220 130">
          {[0, 1, 2, 3].map((i) => (
            <rect
              key={i}
              x={16 + i * 34}
              y={65 - (46 - i * 9) / 2}
              width="26"
              height={46 - i * 9}
              rx="3"
              fill={GREEN}
              fillOpacity={0.25 + i * 0.18}
              stroke={GREEN}
              strokeWidth="1"
            />
          ))}
          <path d="M148 65 H162" stroke={GREY} strokeWidth="2" />
          <circle cx="186" cy="65" r="21" fill="#fff" stroke={ORANGE} strokeWidth="2" className="mi-pulse" />
          <text x="186" y="63" textAnchor="middle" fontSize="11" fontWeight="800" fill={ORANGE}>0.97</text>
          <text x="186" y="76" textAnchor="middle" fontSize="7.5" fill="#777">BPH</text>
          <text x="66" y="118" textAnchor="middle" fontSize="8.5" fill="#777">224 × 224 → 2048 features → yes / no</text>
        </svg>
      )
    case 'group':
      return (
        <svg viewBox="0 0 220 130">
          <Grid cols={8} rows={5} cell={24} x0={14} y0={5} hit={[[3, 2], [4, 2], [3, 3], [4, 3]]} stray={[[6, 0]]} />
          <rect x="86" y="53" width="48" height="48" fill="none" stroke={GREEN} strokeWidth="2.5" rx="3" />
          <text x="110" y="124" textAnchor="middle" fontSize="8.5" fill="#777">1 group kept · 1 lone tile dropped as noise</text>
          <path d="M152 12 l16 16 M168 12 l-16 16" stroke={ORANGE} strokeWidth="2" />
        </svg>
      )
    case 'result':
      return (
        <svg viewBox="0 0 220 130">
          <rect x="22" y="22" width="84" height="34" rx="17" fill={GREEN} fillOpacity="0.9" />
          <text x="64" y="44" textAnchor="middle" fontSize="12" fontWeight="800" fill="#fff">BPH 0.97</text>
          <rect x="114" y="22" width="84" height="34" rx="17" fill="#eee9dc" />
          <text x="156" y="44" textAnchor="middle" fontSize="12" fontWeight="800" fill="#8a8574">RSB 0.12</text>
          <rect x="22" y="72" width="176" height="36" rx="8" fill="#f7f5ee" stroke={GREY} />
          <text x="110" y="94" textAnchor="middle" fontSize="11" fontWeight="700" fill={INK}>≈ 3 BPH groups (estimate)</text>
        </svg>
      )
    case 'weather':
      return (
        <svg viewBox="0 0 220 130">
          {Array.from({ length: 14 }, (_, i) => {
            const rain = [2, 0, 0, 8, 22, 30, 12, 4, 0, 0, 6, 18, 9, 3][i]
            return <rect key={i} x={16 + i * 14} y={104 - rain * 1.6} width="9" height={rain * 1.6 + 1} rx="2" fill="#5b9bd5" opacity="0.75" />
          })}
          <path
            d={`M20 ${50} ${[46, 44, 40, 42, 47, 45, 41, 39, 43, 48, 46, 42, 40].map((y, i) => `L${34 + i * 14} ${y}`).join(' ')}`}
            stroke={ORANGE}
            strokeWidth="2.2"
            fill="none"
          />
          <text x="110" y="122" textAnchor="middle" fontSize="8.5" fill="#777">14 days · temperature line · rainfall bars</text>
        </svg>
      )
    case 'features':
      return (
        <svg viewBox="0 0 220 130">
          {[
            ['Tmax', 22, 22],
            ['Tmin', 84, 22],
            ['Humidity', 146, 22],
            ['Rain', 22, 62],
            ['Stage', 84, 62],
          ].map(([text, x, y]) => (
            <g key={text as string}>
              <rect x={x as number} y={y as number} width="52" height="28" rx="14" fill={GREEN_SOFT} stroke={GREEN} strokeWidth="1.2" className="mi-pulse" />
              <text x={(x as number) + 26} y={(y as number) + 18} textAnchor="middle" fontSize="10.5" fontWeight="800" fill={GREEN}>{text}</text>
            </g>
          ))}
          <text x="110" y="118" textAnchor="middle" fontSize="8.5" fill="#777">raw readings in, learned features inside, no formulas</text>
        </svg>
      )
    case 'bilstm':
      return (
        <svg viewBox="0 0 220 130">
          {[0, 1, 2, 3, 4].map((i) => (
            <g key={i}>
              <rect x={14 + i * 34} y="30" width="26" height="22" rx="4" fill={GREEN} fillOpacity="0.3" stroke={GREEN} />
              <rect x={14 + i * 34} y="70" width="26" height="22" rx="4" fill={ORANGE} fillOpacity="0.3" stroke={ORANGE} />
            </g>
          ))}
          <path d="M14 22 H172" stroke={GREEN} strokeWidth="1.6" markerEnd="url(#mi-arrow2)" />
          <path d="M172 100 H14" stroke={ORANGE} strokeWidth="1.6" markerEnd="url(#mi-arrow3)" />
          <circle cx="198" cy="61" r="16" fill="#fff" stroke={GREEN} strokeWidth="2" className="mi-pulse" />
          <text x="198" y="65" textAnchor="middle" fontSize="10" fontWeight="800" fill={GREEN}>ŷ</text>
          <text x="90" y="122" textAnchor="middle" fontSize="8.5" fill="#777">forward + backward over 14 days</text>
          <defs>
            <marker id="mi-arrow2" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill={GREEN} /></marker>
            <marker id="mi-arrow3" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill={ORANGE} /></marker>
          </defs>
        </svg>
      )
    case 'value':
      return (
        <svg viewBox="0 0 220 130">
          <path d="M16 96 L40 92 L64 88 L88 78 L112 70 L136 58 L160 52 L184 46 L204 40 V110 H16 Z" fill={GREEN} fillOpacity="0.14" />
          <path d="M16 96 L40 92 L64 88 L88 78 L112 70 L136 58 L160 52 L184 46 L204 40" stroke={GREEN} strokeWidth="2.4" fill="none" />
          {[16, 64, 112, 160, 204].map((x, i) => (
            <circle key={x} cx={x} cy={[96, 88, 70, 52, 40][i]} r="3.4" fill="#fff" stroke={GREEN} strokeWidth="1.8" />
          ))}
          <text x="110" y="124" textAnchor="middle" fontSize="8.5" fill="#777">one continuous value per day</text>
        </svg>
      )
    case 'anchor':
      return (
        <svg viewBox="0 0 220 130">
          <rect x="14" y="22" width="92" height="30" rx="6" fill="#fdf1e3" stroke={ORANGE} strokeWidth="1.4" />
          <text x="60" y="41" textAnchor="middle" fontSize="9" fill={ORANGE} fontWeight="700">verified report</text>
          <rect x="14" y="78" width="92" height="30" rx="6" fill="#eef4ea" stroke={GREEN} strokeWidth="1.4" />
          <text x="60" y="97" textAnchor="middle" fontSize="9" fill={GREEN} fontWeight="700">weather + stage</text>
          <path className="mi-draw" d="M106 37 C140 37 140 65 160 65" stroke={ORANGE} strokeWidth="2" fill="none" />
          <path className="mi-draw" d="M106 93 C140 93 140 65 160 65" stroke={GREEN} strokeWidth="2" fill="none" />
          <rect x="160" y="50" width="48" height="30" rx="6" fill="#e8f0fa" stroke="#2b5d9a" strokeWidth="1.4" />
          <text x="184" y="69" textAnchor="middle" fontSize="9" fill="#2b5d9a" fontWeight="700">BiLSTM</text>
          <text x="110" y="124" textAnchor="middle" fontSize="8.5" fill="#777">an input to the model, not a shift afterwards</text>
        </svg>
      )
    case 'etl':
      return (
        <svg viewBox="0 0 220 130">
          <rect x="18" y="52" width="60" height="26" rx="4" fill="#7fb356" />
          <rect x="80" y="52" width="60" height="26" rx="4" fill={YELLOW} />
          <rect x="142" y="52" width="60" height="26" rx="4" fill={ORANGE} />
          {[['Low', 48], ['Medium', 110], ['High', 172]].map(([t, x]) => (
            <text key={t as string} x={x as number} y="69" textAnchor="middle" fontSize="10" fontWeight="800" fill="#fff">{t}</text>
          ))}
          <path d="M120 42 l-7 -12 h14 z" fill={INK} className="mi-pulse" />
          <text x="110" y="104" textAnchor="middle" fontSize="8.5" fill="#777">fixed thresholds, outside the model</text>
        </svg>
      )
    case 'dash':
    default:
      return (
        <svg viewBox="0 0 220 130">
          <rect x="70" y="8" width="80" height="116" rx="12" fill="#f7f5ee" stroke={GREEN} strokeWidth="1.6" />
          <rect x="80" y="22" width="60" height="26" rx="6" fill={GREEN_SOFT} />
          <rect x="86" y="30" width="24" height="10" rx="5" fill={YELLOW} />
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <rect key={i} x={82 + i * 10} y={104 - [12, 14, 16, 22, 30, 34][i]} width="7" height={[12, 14, 16, 22, 30, 34][i]} rx="2" fill={i < 4 ? '#7fb356' : YELLOW} />
          ))}
          <rect x="80" y="58" width="60" height="6" rx="3" fill={GREY} />
          <rect x="80" y="70" width="42" height="6" rx="3" fill={GREY} />
        </svg>
      )
  }
}

/* ------------------------------------------------------------------ */
/* Tab 1: animated flow                                                */
/* ------------------------------------------------------------------ */

function FlowTab() {
  const [lane, setLane] = useState<LaneKey>('photo')
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(true)

  const steps: FlowStep[] = lane === 'photo' ? PHOTO_FLOW : WEATHER_FLOW
  const step = steps[index]

  useEffect(() => {
    if (!playing) return undefined
    const id = window.setInterval(() => setIndex((i) => (i + 1) % steps.length), 2800)
    return () => window.clearInterval(id)
  }, [playing, steps.length])

  const chooseLane = (next: LaneKey) => {
    setLane(next)
    setIndex(0)
    setPlaying(true)
  }

  return (
    <>
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">How the system reads a photo and the weather</div>
            <div className="panel-subtitle">
              Two inputs, two models, one shared risk pipeline. Click a step, or press play.
            </div>
          </div>
          <div className="mi-controls">
            <button
              type="button"
              className="mi-btn"
              onClick={() => {
                setIndex((i) => (i - 1 + steps.length) % steps.length)
                setPlaying(false)
              }}
              aria-label="Previous step"
            >
              ‹ Prev
            </button>
            <button type="button" className="mi-btn mi-btn-solid" onClick={() => setPlaying((p) => !p)}>
              {playing ? '❚❚ Pause' : '▶ Play'}
            </button>
            <button
              type="button"
              className="mi-btn"
              onClick={() => {
                setIndex((i) => (i + 1) % steps.length)
                setPlaying(false)
              }}
              aria-label="Next step"
            >
              Next ›
            </button>
            <button
              type="button"
              className="mi-btn"
              onClick={() => {
                setIndex(0)
                setPlaying(true)
              }}
            >
              ↺ Replay
            </button>
          </div>
        </div>

        <div className="mi-lane-tabs">
          <button
            type="button"
            className={`mi-lane-tab${lane === 'photo' ? ' active' : ''}`}
            onClick={() => chooseLane('photo')}
          >
            <span className="mi-lane-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 4h-5L8 6H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-3z" />
                <circle cx="12" cy="13" r="3.5" />
              </svg>
            </span>
            <span className="mi-lane-text">
              <strong>Images</strong>
              <small>ResNet-50 · which pest is in the photo</small>
            </span>
          </button>
          <button
            type="button"
            className={`mi-lane-tab${lane === 'weather' ? ' active' : ''}`}
            onClick={() => chooseLane('weather')}
          >
            <span className="mi-lane-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 0 1 0 9Z" />
              </svg>
            </span>
            <span className="mi-lane-text">
              <strong>Weather</strong>
              <small>BiLSTM · how bad it will get in 14 days</small>
            </span>
          </button>
        </div>

        <div className="mi-track-wrap">
          <ol
            className="mi-track"
            style={
              {
                '--n': steps.length,
                '--p': steps.length > 1 ? index / (steps.length - 1) : 0,
              } as React.CSSProperties
            }
          >
            <li className="mi-track-fill" aria-hidden="true" />
            {steps.map((s, i) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`mi-node${i === index ? ' active' : ''}${i < index ? ' done' : ''}`}
                  onClick={() => {
                    setIndex(i)
                    setPlaying(false)
                  }}
                >
                  <span className="mi-node-num">{i < index ? '✓' : i + 1}</span>
                  <span className="mi-node-label">{s.short}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>

        <div className="mi-detail" key={`${lane}-${step.id}`}>
          <div className="mi-art">
            <StepArt id={step.id} />
          </div>
          <div className="mi-detail-text">
            <span className="mi-step-count">
              Step {index + 1} of {steps.length}
            </span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            <div className="mi-chips">
              {step.outputs.map((o) => (
                <span key={o} className="mi-chip">
                  {o}
                </span>
              ))}
            </div>
            <div className="mi-code">
              <span>Code</span> {step.code}
            </div>
          </div>
        </div>
      </section>

      <section className="panel mi-panel">
        <div className="panel-title">Where the two paths meet</div>
        <p className="mi-note">
          The photo tells the system <strong>which pest</strong> is present. The weather tells it{' '}
          <strong>how the pest population is expected to change over 14 days</strong>. They are different kinds of
          data (a picture and a timeline), so each has its own model, and the ETL thresholds turn the forecast into
          the Low, Medium or High level everyone sees. LGU-verified field reports keep the forecast anchored to what
          is actually happening.
        </p>
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Shared bits                                                         */
/* ------------------------------------------------------------------ */

function PestToggle({ value, onChange }: { value: PestCode; onChange: (p: PestCode) => void }) {
  return (
    <div className="mi-toggle" role="tablist">
      {(['BPH', 'RSB'] as PestCode[]).map((p) => (
        <button
          key={p}
          type="button"
          role="tab"
          aria-selected={value === p}
          className={value === p ? 'active' : ''}
          onClick={() => onChange(p)}
        >
          {p === 'BPH' ? 'Brown Planthopper (BPH)' : 'Rice Stem Borer (RSB)'}
        </button>
      ))}
    </div>
  )
}

function MetricCard({ label, value, hint, tone }: { label: string; value: string; hint: string; tone?: 'good' | 'warn' }) {
  return (
    <div className={`mi-metric${tone ? ` ${tone}` : ''}`}>
      <div className="mi-metric-label">{label}</div>
      <div className="mi-metric-value">{value}</div>
      <div className="mi-metric-hint">{hint}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Tab 2: ResNet-50                                                    */
/* ------------------------------------------------------------------ */

function ConfusionMatrix({
  matrix,
  negLabel = 'not this pest',
  posLabel = 'this pest',
}: {
  matrix: [[number, number], [number, number]]
  negLabel?: string
  posLabel?: string
}) {
  const rows = [
    { name: `Actual: ${negLabel}`, cells: matrix[0] },
    { name: `Actual: ${posLabel}`, cells: matrix[1] },
  ]
  return (
    <div className="mi-cm">
      <div className="mi-cm-corner" />
      <div className="mi-cm-col">Predicted: {negLabel}</div>
      <div className="mi-cm-col">Predicted: {posLabel}</div>
      {rows.map((row, r) => {
        const total = row.cells[0] + row.cells[1]
        return (
          <div className="mi-cm-row" key={row.name}>
            <div className="mi-cm-rowlabel">{row.name}</div>
            {row.cells.map((count, c) => {
              const correct = r === c
              const share = total === 0 ? 0 : count / total
              const bg = correct
                ? `rgba(47,107,50,${0.12 + share * 0.6})`
                : `rgba(194,59,59,${Math.min(0.75, share * 9 + (count > 0 ? 0.08 : 0))})`
              return (
                <div className="mi-cm-cell" key={c} style={{ background: bg, color: correct && share > 0.55 ? '#fff' : INK }}>
                  <strong>{count.toLocaleString()}</strong>
                  <span>{pct(share)} of row</span>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

// Which combinations of the grid test to show (the current setting is always added).
const GRID_SHOWN: [number, number][] = [
  [0.5, 1],
  [0.9, 1],
  [0.95, 1],
  [0.99, 1],
  [0.99, 2],
  [0.99, 4],
]

/** Held-out performance of the separate bug-vs-no-bug detector. It runs only
 * when neither tracked pest fires, so it is what lets the app say "an insect
 * we don't recognise" instead of "no pest" — the metrics were previously only
 * in the artifact file, never on screen. */
function UnknownInsectPanel({ metrics }: { metrics: ResnetTestMetrics | null }) {
  if (!metrics) {
    return (
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Unknown-insect detector</div>
            <div className="panel-subtitle">Held-out test metrics not found on the server</div>
          </div>
        </div>
        <p className="mi-note">
          No test metrics file was found for the unknown-insect detector. The detector itself still runs if its
          weights are present; only this report is missing.
        </p>
      </section>
    )
  }

  const testSize = metrics.confusion_matrix.flat().reduce((a, b) => a + b, 0)

  return (
    <section className="panel mi-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Unknown-insect detector</div>
          <div className="panel-subtitle">
            Is there an insect at all? · {testSize.toLocaleString()} held-out test crops
          </div>
        </div>
      </div>

      <p className="mi-note">
        This is a third classifier, separate from the two pest models. It is consulted only when neither the BPH nor
        the RSB classifier fires, and it is what lets the app answer “there is an insect here, just not one we track”
        instead of wrongly reporting no pest.
      </p>

      <div className="mi-metrics">
        <MetricCard label="Accuracy" value={pct(metrics.accuracy)} hint="Share of all crops judged correctly" tone="good" />
        <MetricCard label="Precision" value={pct(metrics.positive_precision)} hint="When it says “an insect”, how often it is right" tone="good" />
        <MetricCard label="Recall" value={pct(metrics.positive_recall)} hint="Share of real insects it finds" tone="good" />
        <MetricCard label="F1 score" value={pct(metrics.positive_f1)} hint="Balance of precision and recall" tone="good" />
      </div>

      <div className="mi-two-col">
        <div>
          <h4 className="mi-h4">Confusion matrix</h4>
          <ConfusionMatrix matrix={metrics.confusion_matrix} negLabel="no insect" posLabel="an insect" />
          <p className="mi-note">Rows are the truth, columns are the model’s answer. Green cells are correct; red cells are mistakes.</p>
        </div>
        <div>
          <h4 className="mi-h4">Why this matters</h4>
          <p className="mi-note">
            Without this detector, any insect outside the two trained pests would be reported to the farmer as “no pest
            detected”, which is the more damaging error of the two: it tells someone their field is clear when
            something is eating it. With it, the farmer is told an unrecognised insect was found and advised to have it
            checked.
          </p>
          <p className="mi-note">
            The {metrics.confusion_matrix[1][0].toLocaleString()} missed insects and{' '}
            {metrics.confusion_matrix[0][1].toLocaleString()} false alarms are on cropped images, not whole field
            photos.
          </p>
        </div>
      </div>
    </section>
  )
}

/** Held-out results of the photo regressors that turn a detected pest into a
 * number (hoppers per hill, % coverage, % damage). The test-set badge matters:
 * only the count target is scored on real photos; coverage and damage are
 * scored on synthetic composites, so their R² shows the model recovers what
 * the generator drew, not accuracy on a real field. */
function RegressionPanel({ metrics }: { metrics?: Record<string, ResnetRegressionMetrics | null> }) {
  const rows = Object.entries(metrics ?? {}).filter((entry): entry is [string, ResnetRegressionMetrics] => entry[1] != null)
  if (rows.length === 0) return null
  return (
    <section className="panel mi-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Quantitative estimates from a photo</div>
          <div className="panel-subtitle">ResNet-50 regressors · how many, how much is covered, how much is damaged</div>
        </div>
      </div>
      <div className="admin-table-wrap">
        <table className="admin-table mi-regression-table">
          <thead>
            <tr>
              <th>Estimate</th>
              <th className="admin-col-center">R²</th>
              <th className="admin-col-center">RMSE</th>
              <th className="admin-col-center">MAE</th>
              <th className="admin-col-center">Average actual</th>
              <th className="admin-col-center">Test images</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, m]) => (
              <tr key={label}>
                <td>{label}</td>
                <td className="admin-col-center">{m.r2.toFixed(2)}</td>
                <td className="admin-col-center">{m.rmse.toFixed(1)}</td>
                <td className="admin-col-center">{m.mae.toFixed(1)}</td>
                <td className="admin-col-center">{m.mean_actual_label.toFixed(1)}</td>
                <td className="admin-col-center">
                  {m.n_test_images}{' '}
                  <span className={`badge ${m.test_set_is_synthetic ? 'badge-neutral' : 'badge-green'}`}>
                    {m.test_set_is_synthetic ? 'synthetic' : 'real photos'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mi-note">
        Only estimates tested on real photos say how the model does in the field. A synthetic test set shows the
        model can recover the value an image generator drew, which is a consistency check, not field accuracy. Every
        estimate is shown to the technologist as a suggestion and counts only after they confirm it.
      </p>
    </section>
  )
}

function ResnetTab({ data }: { data: ModelInsightsResponse }) {
  const [pest, setPest] = useState<PestCode>('BPH')
  const m = data.resnet[pest]
  const comparison = data.resnetBphComparison
  const evalBlock = data.grid.evaluation?.mosaic_832px
  const current = data.grid.current

  const gridRows = useMemo(() => {
    if (!evalBlock) return []
    const wanted = [...GRID_SHOWN]
    if (!wanted.some(([t, n]) => t === current.threshold && n === current.minTiles)) {
      wanted.push([current.threshold, current.minTiles])
    }
    return wanted
      .map(([threshold, minTiles]) => {
        const row = evalBlock.grid[`thr${threshold}_min${minTiles}`]
        return row ? { threshold, minTiles, row, isCurrent: threshold === current.threshold && minTiles === current.minTiles } : null
      })
      .filter((r): r is NonNullable<typeof r> => r !== null)
  }, [evalBlock, current])

  if (!m) {
    return (
      <section className="panel mi-panel">
        <p className="mi-note">No ResNet-50 test metrics file was found on the server for this model.</p>
      </section>
    )
  }

  const testSize = m.confusion_matrix.flat().reduce((a, b) => a + b, 0)
  // Don't claim a perfect score the matrix doesn't support — RSB sits at
  // 99.5%, not 100%, and a panelist reading the matrix would catch it.
  const mistakes = m.confusion_matrix[0][1] + m.confusion_matrix[1][0]

  return (
    <>
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">ResNet-50 image classifier</div>
            <div className="panel-subtitle">
              One yes/no classifier per pest · {testSize.toLocaleString()} held-out test crops
            </div>
          </div>
          <PestToggle value={pest} onChange={setPest} />
        </div>

        <div className="mi-metrics">
          <MetricCard label="Accuracy" value={pct(m.accuracy)} hint="Share of all crops classified correctly" tone="good" />
          <MetricCard label="Precision" value={pct(m.positive_precision)} hint="When it says “this pest”, how often it is right" tone="good" />
          <MetricCard label="Recall" value={pct(m.positive_recall)} hint="Share of real pests it finds" tone="good" />
          <MetricCard label="F1 score" value={pct(m.positive_f1)} hint="Balance of precision and recall" tone="good" />
        </div>

        <div className="mi-two-col">
          <div>
            <h4 className="mi-h4">Confusion matrix</h4>
            <ConfusionMatrix matrix={m.confusion_matrix} />
            <p className="mi-note">Rows are the truth, columns are the model’s answer. Green cells are correct; red cells are mistakes.</p>
          </div>

          {pest === 'BPH' ? (
            <div>
              <h4 className="mi-h4">What background training fixed (BPH)</h4>
              {comparison ? (
                <>
                  <div className="mi-compare">
                    {comparison.rows.map((row) => (
                      <div key={row.label} className="mi-compare-row">
                        <div className="mi-compare-label">
                          {row.label}
                          <small>
                            {row.kind === 'falseAlarm' ? 'wrongly called BPH (lower is better)' : 'caught (higher is better)'} · {row.n.toLocaleString()} test crops
                          </small>
                        </div>
                        <div className="mi-compare-bars">
                          <div className="mi-bar-line">
                            <span className="mi-bar-tag">Before</span>
                            <div className="mi-bar-track"><div className="mi-bar-fill old" style={{ width: `${row.old}%` }} /></div>
                            <span className="mi-bar-num">{row.old}%</span>
                          </div>
                          <div className="mi-bar-line">
                            <span className="mi-bar-tag">After</span>
                            <div className="mi-bar-track"><div className="mi-bar-fill new" style={{ width: `${row.new}%` }} /></div>
                            <span className="mi-bar-num">{row.new}%</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="mi-note">
                    Adding {comparison.background_patches_added.toLocaleString()} empty-background patches as negatives cut
                    false alarms on background from {comparison.rows[0]?.old}% to {comparison.rows[0]?.new}%.
                  </p>
                </>
              ) : (
                <p className="mi-note">The before/after comparison file was not found on the server.</p>
              )}
            </div>
          ) : (
            <div>
              <h4 className="mi-h4">Reading a very high score</h4>
              <p className="mi-note">
                {mistakes === 0
                  ? `Every one of the ${testSize.toLocaleString()} test crops was classified correctly.`
                  : `${mistakes} of ${testSize.toLocaleString()} test crops were misclassified.`}{' '}
                A score this high is expected here: RSB photos are large close-ups of one insect, which look very
                different from the other classes, so the task is easy. Be ready to explain this if a panelist asks, and
                note that these scores are on cropped insects, not whole field photos.
              </p>
            </div>
          )}
        </div>
      </section>

      <UnknownInsectPanel metrics={data.resnetUnknown} />

      <RegressionPanel metrics={data.resnetRegression} />

      {pest === 'BPH' && (
        <section className="panel mi-panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">BPH grid test on bigger photos</div>
              <div className="panel-subtitle">
                {evalBlock
                  ? `832 px scenes stitched from held-out photos · ${evalBlock.n_bph} with BPH, ${evalBlock.n_bph_free} without`
                  : 'Grid test results not found on the server'}
              </div>
            </div>
            <span className="badge badge-yellow">Experimental</span>
          </div>
          {gridRows.length > 0 && (
            <div className="mi-table-wrap">
              <table className="mi-table">
                <thead>
                  <tr>
                    <th>Grid setting</th>
                    <th>BPH scenes found</th>
                    <th>False alarms</th>
                    <th>Count error (MAE)</th>
                    <th>Count vs truth (r)</th>
                  </tr>
                </thead>
                <tbody>
                  {gridRows.map(({ threshold, minTiles, row, isCurrent }) => (
                    <tr key={`${threshold}-${minTiles}`} className={isCurrent ? 'current' : undefined}>
                      <td>
                        cutoff {threshold} · min {minTiles} tile{minTiles > 1 ? 's' : ''}{' '}
                        {isCurrent && <span className="badge badge-green">in use</span>}
                      </td>
                      <td>{row.recall != null ? pct(row.recall) : '—'}</td>
                      <td className={row.false_alarm != null && row.false_alarm > 0.5 ? 'bad' : undefined}>
                        {row.false_alarm != null ? pct(row.false_alarm) : '—'}
                      </td>
                      <td>{row.count_mae_on_bph?.toFixed(2) ?? '—'}</td>
                      <td>{row.correlation?.toFixed(2) ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mi-note">
            The grid count is an approximate density hint, not an exact insect count, and it still gives false alarms on
            BPH-free scenes. The safest setting is used today; hard-negative retraining is the planned next step.
          </p>
        </section>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Tab 3: BiLSTM                                                       */
/* ------------------------------------------------------------------ */

const BILSTM_UNITS: Record<PestCode, { unit: string; label: string }> = {
  BPH: { unit: 'hoppers/hill', label: 'hoppers per hill' },
  RSB: { unit: '% damage', label: '% dead hearts / white ears' },
}

function evenlySampled<T>(items: T[], max: number): T[] {
  if (items.length <= max) return items
  const step = items.length / max
  return Array.from({ length: max }, (_, i) => items[Math.floor(i * step)])
}

// Several municipalities share each date; the time chart averages them per day.
function dailyAverage(points: PredictionPointDto[]): { date: string; actual: number; predicted: number }[] {
  const byDate = new Map<string, { actual: number; predicted: number; n: number }>()
  for (const p of points) {
    const entry = byDate.get(p.date) ?? { actual: 0, predicted: 0, n: 0 }
    entry.actual += p.actual
    entry.predicted += p.predicted
    entry.n += 1
    byDate.set(p.date, entry)
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, e]) => ({ date, actual: e.actual / e.n, predicted: e.predicted / e.n }))
}

interface XY {
  actual: number
  predicted: number
}

function niceMax(values: number[]): number {
  const raw = Math.max(...values, 1)
  const step = raw > 20 ? 10 : raw > 8 ? 5 : raw > 3 ? 2 : 1
  return Math.ceil(raw / step) * step
}

function ScatterPlot({ points, unit }: { points: XY[]; unit: string }) {
  const W = 560
  const H = 300
  const pad = { l: 44, r: 12, t: 12, b: 38 }
  const max = niceMax(points.flatMap((p) => [p.actual, p.predicted]))
  const x = (v: number) => pad.l + (v / max) * (W - pad.l - pad.r)
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b)
  const ticks = [0, max / 2, max]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mi-svg" role="img" aria-label="Predicted versus actual values">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#ece8dc" />
          <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize="9.5" fill="#888">{t}</text>
          <text x={x(t)} y={H - pad.b + 14} textAnchor="middle" fontSize="9.5" fill="#888">{t}</text>
        </g>
      ))}
      <line x1={x(0)} y1={y(0)} x2={x(max)} y2={y(max)} stroke={GREY} strokeDasharray="5 4" strokeWidth="1.5" />
      <text x={x(max) - 4} y={y(max) + 14} textAnchor="end" fontSize="9" fill="#999">perfect prediction</text>
      {points.map((p, i) => (
        <circle key={i} cx={x(p.actual)} cy={y(p.predicted)} r="2.8" fill={GREEN} fillOpacity="0.4" />
      ))}
      <text x={(pad.l + W - pad.r) / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="#666">Actual ({unit})</text>
      <text transform={`translate(11 ${(pad.t + H - pad.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize="10" fill="#666">Predicted ({unit})</text>
    </svg>
  )
}

function SeriesPlot({ series, unit }: { series: { date: string; actual: number; predicted: number }[]; unit: string }) {
  const W = 560
  const H = 300
  const pad = { l: 44, r: 12, t: 22, b: 38 }
  const max = niceMax(series.flatMap((p) => [p.actual, p.predicted]))
  const x = (i: number) => pad.l + (i / Math.max(series.length - 1, 1)) * (W - pad.l - pad.r)
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b)
  const line = (key: 'actual' | 'predicted') => series.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mi-svg" role="img" aria-label="Actual and predicted values over the test period">
      {[0, max / 2, max].map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#ece8dc" />
          <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize="9.5" fill="#888">{t}</text>
        </g>
      ))}
      <path d={line('actual')} stroke={INK} strokeWidth="1.6" fill="none" />
      <path d={line('predicted')} stroke={GREEN} strokeWidth="1.8" fill="none" strokeDasharray="5 3" />
      <g transform={`translate(${pad.l + 6} ${pad.t - 8})`} fontSize="10">
        <line x1="0" x2="18" y1="0" y2="0" stroke={INK} strokeWidth="2" />
        <text x="24" y="3" fill="#555">Actual</text>
        <line x1="70" x2="88" y1="0" y2="0" stroke={GREEN} strokeWidth="2.2" strokeDasharray="6 3" />
        <text x="94" y="3" fill="#555">Predicted</text>
      </g>
      <text x={pad.l} y={H - 22} fontSize="9.5" fill="#888">{series[0]?.date}</text>
      <text x={W - pad.r} y={H - 22} textAnchor="end" fontSize="9.5" fill="#888">{series[series.length - 1]?.date}</text>
      <text x={(pad.l + W - pad.r) / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="#666">Test period · daily average of municipalities ({unit})</text>
    </svg>
  )
}

const COMPARISON_METRIC_LABELS: Record<string, { label: string; lowerIsBetter: boolean; pct?: boolean }> = {
  rmse: { label: 'RMSE', lowerIsBetter: true },
  mae: { label: 'MAE', lowerIsBetter: true },
  r2: { label: 'R²', lowerIsBetter: false },
  accuracy: { label: 'Accuracy', lowerIsBetter: false, pct: true },
  precision_macro: { label: 'Precision (macro)', lowerIsBetter: false, pct: true },
  recall_macro: { label: 'Recall (macro)', lowerIsBetter: false, pct: true },
  f1_macro: { label: 'F1 (macro)', lowerIsBetter: false, pct: true },
}
const COMPARISON_METRIC_ORDER = Object.keys(COMPARISON_METRIC_LABELS)

function formatMetricValue(value: number, pct?: boolean): string {
  return pct ? `${(value * 100).toFixed(1)}%` : value.toFixed(3)
}

function FeatureComparisonSection({ data, unit }: { data: FeatureComparisonResponse | null; unit: string }) {
  if (!data) {
    return (
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Baseline: framework vs. raw climate inputs</div>
            <div className="panel-subtitle">The framework (raw weather + growth stage + verified report) vs. the raw-weather control</div>
          </div>
        </div>
        <p className="mi-note">
          Comparison results have not been generated yet. Run{' '}
          <code>python -m ml.bilstm.compare_features --pest {unit === 'hoppers/hill' ? 'BPH' : 'RSB'}</code>{' '}
          from server-python.
        </p>
      </section>
    )
  }

  return (
    <section className="panel mi-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Baseline: framework vs. raw climate inputs</div>
          <div className="panel-subtitle">
            Same BiLSTM architecture, same {data.n_folds}-fold expanding-window CV splits · framework =
            weather + growth stage + latest verified report · raw = Tmax/Tmin/RH/rainfall only
          </div>
        </div>
      </div>

      <div className="mi-table-wrap">
        <table className="mi-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Framework</th>
              <th>Raw (baseline)</th>
              <th>Winner</th>
              <th>Test</th>
              <th>p-value</th>
              <th>Significant (α={data.alpha})</th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON_METRIC_ORDER.filter((metric) => metric in data.significance).map((metric) => {
              const meta = COMPARISON_METRIC_LABELS[metric]
              const result = data.significance[metric]
              return (
                <tr key={metric}>
                  <td>{meta.label}</td>
                  <td>{formatMetricValue(result.mean_engineered, meta.pct)}</td>
                  <td>{formatMetricValue(result.mean_raw, meta.pct)}</td>
                  <td>
                    <span className={`badge ${result.better_configuration === 'engineered' ? 'badge-green' : 'badge-yellow'}`}>
                      {result.better_configuration === 'engineered' ? 'framework' : result.better_configuration}
                    </span>
                  </td>
                  <td>{result.test}</td>
                  <td>{result.p_value.toFixed(4)}</td>
                  <td className={result.significant ? 'bad' : undefined}>{result.significant ? 'Yes' : 'No'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mi-note">
        The framework and the raw baseline were trained and evaluated on the exact same {data.n_folds} chronological
        test folds, so each metric's 5 paired differences were checked for normality (Shapiro-Wilk) before choosing a
        paired t-test or a Wilcoxon signed-rank test, whichever the normality check called for.
      </p>
    </section>
  )
}

function BilstmTab({ data }: { data: ModelInsightsResponse }) {
  const [pest, setPest] = useState<PestCode>('BPH')
  const info = data.bilstm[pest]
  const u = BILSTM_UNITS[pest]
  const m = info.metrics
  const scatter = useMemo(() => evenlySampled(info.predictions?.points ?? [], 500), [info.predictions])
  const series = useMemo(() => dailyAverage(info.predictions?.points ?? []), [info.predictions])
  const features = info.shap?.features ?? []
  const topShare = Math.max(...features.map((f) => f.share), 0.0001)

  return (
    <>
      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">BiLSTM forecast accuracy</div>
            <div className="panel-subtitle">
              Continuous forecast, 14 days ahead · {u.label}
              {info.predictions ? ` · ${info.predictions.n.toLocaleString()} held-out test windows` : ''}
            </div>
          </div>
          <PestToggle value={pest} onChange={setPest} />
        </div>

        {m ? (
          <>
            <div className="mi-metrics three">
              <MetricCard
                label="RMSE"
                value={m.rmse.toFixed(2)}
                hint={`Typical error size in ${u.unit}; big misses count extra (lower is better)`}
              />
              <MetricCard label="MAE" value={m.mae.toFixed(2)} hint={`Average miss in ${u.unit} (lower is better)`} />
              <MetricCard
                label="R²"
                value={m.r2.toFixed(2)}
                hint={`Explains about ${Math.round(m.r2 * 100)}% of the ups and downs (1.0 is perfect)`}
                tone="warn"
              />
            </div>
            <p className="mi-note">
              The R² is modest. The training data is synthetic, and the same ceiling appeared with a much smaller, more
              regularized model, so it reflects the data rather than the model’s capacity.
            </p>
          </>
        ) : (
          <p className="mi-note">No BiLSTM test metrics file was found on the server for this model.</p>
        )}
      </section>

      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Predicted vs actual</div>
            <div className="panel-subtitle">Held-out test set (the most recent dates, never used for training)</div>
          </div>
        </div>
        {info.predictions ? (
          <div className="mi-two-col charts">
            <div>
              <h4 className="mi-h4">Each dot is one test window</h4>
              <ScatterPlot points={scatter} unit={u.unit} />
              <p className="mi-note">The closer the dots sit to the dashed line, the better the forecast.</p>
            </div>
            <div>
              <h4 className="mi-h4">Following the trend over time</h4>
              <SeriesPlot series={series} unit={u.unit} />
              <p className="mi-note">The model follows the general rise and fall but smooths out sharp peaks.</p>
            </div>
          </div>
        ) : (
          <p className="mi-note">
            The test predictions have not been exported yet. Run <code>python -m ml.bilstm.export_insights --pest {pest}</code>{' '}
            from server-python.
          </p>
        )}
      </section>

      <FeatureComparisonSection data={info.featureComparison} unit={u.unit} />

      <section className="panel mi-panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">What drives the forecast (SHAP)</div>
            <div className="panel-subtitle">
              Share of the model’s total reliance on each input
              {info.shap ? ` · averaged over ${info.shap.sample_size} test windows` : ''}
            </div>
          </div>
        </div>
        {features.length > 0 ? (
          <>
            <div className="mi-shap">
              {features.map((f) => (
                <div className="mi-shap-row" key={f.label}>
                  <div className="mi-shap-label">
                    {f.label}
                    <small>{f.group === 'static' ? '14-day summary feature' : 'Daily sequence feature (summed over 14 days)'}</small>
                  </div>
                  <div className="mi-bar-track">
                    <div
                      className="mi-bar-fill shap"
                      style={{ width: `${(f.share / topShare) * 100}%`, background: f.group === 'static' ? GREEN : YELLOW }}
                    />
                  </div>
                  <div className="mi-bar-num">{(f.share * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
            <div className="mi-legend">
              <span><i style={{ background: GREEN }} /> 14-day summary features</span>
              <span><i style={{ background: YELLOW }} /> Daily sequence features</span>
            </div>
            <p className="mi-note">
              Growth stage ranks high because pest levels differ strongly between stages of the rice crop, and the model
              picks that up directly. This is the model’s overall reliance, not a cause-and-effect claim.
            </p>
          </>
        ) : (
          <p className="mi-note">
            The SHAP summary has not been exported yet. Run <code>python -m ml.bilstm.export_insights --pest {pest}</code>{' '}
            from server-python.
          </p>
        )}
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* System-wide performance tab — both pests and both models combined into */
/* one picture, pooled where the units actually allow it                 */
/* ------------------------------------------------------------------ */

/** Generic NxN confusion matrix — ConfusionMatrix above is hard-typed to
 * 2x2 for ResNet's binary task; the ETL table is Low/Medium/High (3x3).
 * Reuses the same .mi-cm* CSS classes, just with a computed column count. */
function NConfusionMatrix({ matrix, labels }: { matrix: number[][]; labels: string[] }) {
  return (
    <div className="mi-cm" style={{ gridTemplateColumns: `110px repeat(${labels.length}, 1fr)` }}>
      <div className="mi-cm-corner" />
      {labels.map((l) => (
        <div className="mi-cm-col" key={l}>
          Predicted: {l}
        </div>
      ))}
      {matrix.map((row, r) => {
        const total = row.reduce((a, b) => a + b, 0)
        return (
          <div className="mi-cm-row" key={labels[r]}>
            <div className="mi-cm-rowlabel">Actual: {labels[r]}</div>
            {row.map((count, c) => {
              const correct = r === c
              const share = total === 0 ? 0 : count / total
              const bg = correct
                ? `rgba(47,107,50,${0.12 + share * 0.6})`
                : `rgba(194,59,59,${Math.min(0.75, share * 9 + (count > 0 ? 0.08 : 0))})`
              return (
                <div className="mi-cm-cell" key={c} style={{ background: bg, color: correct && share > 0.55 ? '#fff' : INK }}>
                  <strong>{count.toLocaleString()}</strong>
                  <span>{pct(share)} of row</span>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

/** Sums two equal-shaped confusion matrices cell-by-cell. This is "micro"
 * pooling — combine the raw counts first, then derive accuracy/precision/
 * recall/F1 from the pooled counts — rather than averaging each pest's own
 * pre-computed percentages, which would weight a pest with fewer windows
 * exactly as heavily as one with thousands more. Valid here specifically
 * because both pests' confusion matrices share the same label set and the
 * same meaning per cell (Low/Medium/High, or pest-present/absent) — unlike
 * RMSE/MAE, which are never pooled across pests because the two targets
 * (hoppers/hill vs. % damage) aren't the same unit to begin with. */
function sumMatrices(a: number[][], b: number[][]): number[][] {
  return a.map((row, r) => row.map((v, c) => v + b[r][c]))
}

/** Macro accuracy/precision/recall/F1 from a pooled confusion matrix —
 * the same macro definition (unweighted mean across classes) each pest's
 * own etl_classification/resnet metrics already use, just computed once
 * on the combined counts. A class with zero predicted instances (BPH and
 * RSB both never predict "High" — see Technical Documentation §15.2) gets
 * precision 0 by convention, not NaN, matching how each pest's own figure
 * was already computed. */
function macroMetricsFromMatrix(matrix: number[][], labels: string[]) {
  const n = matrix.length
  const total = matrix.flat().reduce((a, b) => a + b, 0)
  const diag = matrix.reduce((sum, row, i) => sum + row[i], 0)
  const accuracy = total === 0 ? 0 : diag / total

  // Per-class breakdown, not just the macro average of it — this is what
  // actually explains an accuracy or precision number instead of just
  // restating it. Kept alongside the macro figures so a card can expand
  // into "here's which class is dragging this down" with real numbers.
  const perClass = labels.map((label, i) => {
    const tp = matrix[i][i]
    const rowTotal = matrix[i].reduce((a, b) => a + b, 0) // actual = i
    const colTotal = matrix.reduce((a, row) => a + row[i], 0) // predicted = i
    const precision = colTotal === 0 ? 0 : tp / colTotal
    const recall = rowTotal === 0 ? 0 : tp / rowTotal
    const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall)
    return { label, precision, recall, f1, support: rowTotal, predicted: colTotal }
  })

  return {
    accuracy,
    precisionMacro: perClass.reduce((s, c) => s + c.precision, 0) / n,
    recallMacro: perClass.reduce((s, c) => s + c.recall, 0) / n,
    f1Macro: perClass.reduce((s, c) => s + c.f1, 0) / n,
    perClass,
  }
}

/** Both pests' SHAP summaries merged by feature label, ranked by the
 * average of the two normalized shares. Each pest's own `share` column
 * already sums to 1.0 across all of its features, so the average of two such
 * columns also sums to 1.0 — no renormalization needed. This is a system-
 * wide explanation (which features matter across the whole deployed
 * system) rather than the per-forecast SHAP on the Climate Drivers page,
 * which explains one live prediction. */
function mergeShap(bph: ShapFeatureDto[] | undefined, rsb: ShapFeatureDto[] | undefined) {
  if (!bph || !rsb) return []
  const rsbByLabel = new Map(rsb.map((f) => [f.label, f]))
  return bph
    .map((bphFeat) => {
      const rsbFeat = rsbByLabel.get(bphFeat.label)
      const rsbShare = rsbFeat?.share ?? 0
      return {
        label: bphFeat.label,
        group: bphFeat.group,
        bphShare: bphFeat.share,
        rsbShare,
        avgShare: (bphFeat.share + rsbShare) / 2,
      }
    })
    .sort((a, b) => b.avgShare - a.avgShare)
}

/** A MetricCard that opens into a detail panel on click instead of just
 * sitting there as a number. The card itself stays visually identical to
 * MetricCard at rest — only a chevron hints it's interactive — so the
 * at-a-glance headline numbers aren't cluttered until someone actually
 * wants the explanation behind one. */
/** A MetricCard that opens a detail overlay on click, rather than pushing
 * the rest of the page down to make room for an inline panel — with eight
 * of these on one tab, an inline expansion meant the cards below it kept
 * jumping position depending on what was already open. A modal keeps every
 * card exactly where it is; only the detail content appears, on top. */
function ClickableMetricCard({
  label,
  value,
  hint,
  tone,
  onClick,
}: {
  label: string
  value: string
  hint: string
  tone?: 'good' | 'warn'
  onClick: () => void
}) {
  return (
    <button type="button" className={`mi-metric mi-clickable${tone ? ` ${tone}` : ''}`} onClick={onClick}>
      <div className="mi-metric-label">{label}</div>
      <div className="mi-metric-value">{value}</div>
      <div className="mi-metric-hint">{hint}</div>
      <span className="mi-clickable-hint-icon" aria-hidden="true">
        ⓘ
      </span>
    </button>
  )
}

/** The shared overlay every card opens into — one instance per section,
 * swapping its content, rather than one modal per card. */
function DetailModal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="mi-modal-backdrop" onClick={onClose}>
      <div className="mi-modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="mi-modal-head">
          <div className="mi-modal-title">{title}</div>
          <button type="button" className="mi-modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="mi-modal-body">{children}</div>
      </div>
    </div>
  )
}

/** Per-class precision/recall/F1 as a small readable table — shared by any
 * card that expands into "which class is driving this number", rather than
 * writing the same table three times for accuracy/precision/recall. */
function PerClassTable({
  rows,
  rowHeader = 'Band',
  countLabel = 'Windows',
  col1Label = 'Precision',
  col2Label = 'Recall',
  col3Label = 'F1',
}: {
  rows: { label: string; precision: number; recall: number; f1: number; support: number }[]
  rowHeader?: string
  countLabel?: string
  col1Label?: string
  col2Label?: string
  col3Label?: string
}) {
  return (
    <table className="mi-perclass-table">
      <thead>
        <tr>
          <th>{rowHeader}</th>
          <th>{col1Label}</th>
          <th>{col2Label}</th>
          <th>{col3Label}</th>
          <th>{countLabel}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}>
            <td>{r.label}</td>
            <td>{pct(r.precision)}</td>
            <td>{pct(r.recall)}</td>
            <td>{pct(r.f1)}</td>
            <td>{r.support.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function SystemPerformanceSection({ data }: { data: ModelInsightsResponse }) {
  const bphEtl = data.bilstm.BPH.metrics?.etl_classification
  const rsbEtl = data.bilstm.RSB.metrics?.etl_classification
  const bphResnet = data.resnet.BPH
  const rsbResnet = data.resnet.RSB
  const bphShap = data.bilstm.BPH.shap?.features
  const rsbShap = data.bilstm.RSB.shap?.features

  const pooledEtl = useMemo(() => {
    if (!bphEtl || !rsbEtl) return null
    const matrix = sumMatrices(bphEtl.confusion_matrix, rsbEtl.confusion_matrix)
    const labels = bphEtl.confusion_matrix_labels
    return { matrix, labels, ...macroMetricsFromMatrix(matrix, labels) }
  }, [bphEtl, rsbEtl])

  const pooledResnet = useMemo(() => {
    if (!bphResnet || !rsbResnet) return null
    const matrix = sumMatrices(bphResnet.confusion_matrix, rsbResnet.confusion_matrix)
    const labels = ['not this pest', 'this pest']
    return { matrix, labels, ...macroMetricsFromMatrix(matrix, labels) }
  }, [bphResnet, rsbResnet])

  const bphMetrics = data.bilstm.BPH.metrics
  const rsbMetrics = data.bilstm.RSB.metrics
  const bphPoints = data.bilstm.BPH.predictions?.points
  const rsbPoints = data.bilstm.RSB.predictions?.points

  /** RMSE and MAE can't be pooled in their raw units (hoppers/hill vs. %
   * damage — see the Forecast accuracy card's own disclosure). Dividing
   * each by its own test set's observed range turns both into the same
   * thing: "error as a share of how much this pest's target actually
   * varies." That IS unitless, so averaging the two normalized values is
   * legitimate in a way averaging 6.71 and 1.38 directly never was. R² is
   * already unitless by definition (it's a ratio of variances), so it was
   * always safe to average — it just hadn't been, for consistency with the
   * two it was sitting next to.
   * This is a derived metric, not one the manuscript currently defines —
   * flagged in the card itself, not quietly introduced. */
  const normalizedForecast = useMemo(() => {
    if (!bphMetrics || !rsbMetrics || !bphPoints?.length || !rsbPoints?.length) return null
    const rangeOf = (points: { actual: number }[]) => {
      const actuals = points.map((p) => p.actual)
      return Math.max(...actuals) - Math.min(...actuals)
    }
    const bphRange = rangeOf(bphPoints)
    const rsbRange = rangeOf(rsbPoints)
    if (bphRange <= 0 || rsbRange <= 0) return null
    const bphNrmse = bphMetrics.rmse / bphRange
    const rsbNrmse = rsbMetrics.rmse / rsbRange
    const bphNmae = bphMetrics.mae / bphRange
    const rsbNmae = rsbMetrics.mae / rsbRange
    return {
      bphRange,
      rsbRange,
      bphNrmse,
      rsbNrmse,
      bphNmae,
      rsbNmae,
      avgNrmse: (bphNrmse + rsbNrmse) / 2,
      avgNmae: (bphNmae + rsbNmae) / 2,
      avgR2: (bphMetrics.r2 + rsbMetrics.r2) / 2,
    }
  }, [bphMetrics, rsbMetrics, bphPoints, rsbPoints])

  const shapRows = useMemo(() => mergeShap(bphShap, rsbShap), [bphShap, rsbShap])
  // Scaled against the largest single pest share in the list (not the
  // averaged value each row is ranked by) — so a bar's length is directly
  // comparable to every other bar, BPH or RSB, row or row.
  const topShapShare = Math.max(0.0001, ...shapRows.flatMap((r) => [r.bphShare, r.rsbShare]))

  const [modal, setModal] = useState<{ title: string; node: ReactNode } | null>(null)
  const openModal = (title: string, node: ReactNode) => setModal({ title, node })
  const closeModal = () => setModal(null)

  const shapList = (compact?: boolean) => (
    <div className={`mi-syswide-shap-list${compact ? ' mi-syswide-shap-list-compact' : ''}`}>
      {shapRows.slice(0, compact ? 5 : 10).map((row) => (
        <div className="mi-syswide-shap-row" key={row.label}>
          <div className="mi-syswide-shap-row-label">
            {row.label}
            <span className={`mi-syswide-shap-group-tag ${row.group}`}>{row.group}</span>
          </div>
          {/* One bar per pest, not one shared bar for two numbers — the old
              version put a single bar (scaled to the average) next to two
              percentages, so it was never clear which number the bar was
              actually showing. */}
          <div className="mi-syswide-shap-pest-bars">
            <div className="mi-syswide-shap-pest-bar">
              <span className="mi-syswide-shap-pest-tag bph">BPH</span>
              <div className="mi-syswide-shap-bar-track">
                <div className="mi-syswide-shap-bar bph" style={{ width: `${(row.bphShare / topShapShare) * 100}%` }} />
              </div>
              <span className="mi-syswide-shap-pest-value">{pct(row.bphShare, 0)}</span>
            </div>
            <div className="mi-syswide-shap-pest-bar">
              <span className="mi-syswide-shap-pest-tag rsb">RSB</span>
              <div className="mi-syswide-shap-bar-track">
                <div className="mi-syswide-shap-bar rsb" style={{ width: `${(row.rsbShare / topShapShare) * 100}%` }} />
              </div>
              <span className="mi-syswide-shap-pest-value">{pct(row.rsbShare, 0)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )

  if (!bphEtl && !rsbEtl && !bphResnet && !rsbResnet) return null

  return (
    <section className="panel mi-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">System Performance</div>
          <div className="panel-subtitle">
            Both pests and both models combined into one picture, rather than four separate results spread
            across tabs.
          </div>
        </div>
      </div>

      {/* The one-glance answer, before any of the detail — each one opens
          what's actually behind the number in an overlay, on click. */}
      <div className="mi-syswide-headline">
        {pooledEtl && bphEtl && rsbEtl && (
          <button
            type="button"
            className="mi-syswide-headline-item"
            onClick={() =>
              openModal(
                'Risk-level calls correct',
                <>
                  <p className="mi-note">
                    <strong>Not even across pests.</strong> BPH lands at {pct(bphEtl.accuracy)}, RSB at{' '}
                    {pct(rsbEtl.accuracy)} — RSB's higher number is mostly its Low band being easier to call
                    correctly (90%+ of its windows are Low to begin with), not the model doing better work.
                  </p>
                  {shapRows.length > 0 && (
                    <>
                      <p className="mi-note" style={{ marginBottom: 8 }}>
                        <strong>What the forecast behind this decision is actually reading</strong> — live SHAP
                        attribution, not a written description of it:
                      </p>
                      {shapList(true)}
                    </>
                  )}
                </>,
              )
            }
          >
            <span className="mi-syswide-headline-value">{pct(pooledEtl.accuracy)}</span>
            <span className="mi-syswide-headline-label">Risk-level calls correct</span>
            <span className="mi-syswide-headline-sub">Forecast → Low / Medium / High, both pests</span>
            <span className="mi-clickable-hint-icon" aria-hidden="true">
              ⓘ
            </span>
          </button>
        )}
        {pooledResnet && bphResnet && rsbResnet && (
          <button
            type="button"
            className="mi-syswide-headline-item"
            onClick={() =>
              openModal(
                'Photo calls correct',
                <>
                  <p className="mi-note">
                    <strong>Per pest:</strong> BPH identification is {pct(bphResnet.accuracy)} accurate, RSB{' '}
                    {pct(rsbResnet.accuracy)} — both classifiers are close, unlike the forecast side above.
                  </p>
                  <p className="mi-note mi-syswide-callout">
                    <strong>No SHAP here, honestly.</strong> SHAP in this system explains the BiLSTM's weather
                    and growth-stage inputs — it was never applied to ResNet's convolutional layers, which would need a
                    different method (e.g. Grad-CAM) to show which pixels drove a call. That explainability layer
                    doesn't exist yet; this card can't manufacture one.
                  </p>
                </>,
              )
            }
          >
            <span className="mi-syswide-headline-value">{pct(pooledResnet.accuracy)}</span>
            <span className="mi-syswide-headline-label">Photo calls correct</span>
            <span className="mi-syswide-headline-sub">Pest present / absent, both classifiers</span>
            <span className="mi-clickable-hint-icon" aria-hidden="true">
              ⓘ
            </span>
          </button>
        )}
        {normalizedForecast && (
          <button
            type="button"
            className="mi-syswide-headline-item"
            onClick={() =>
              openModal(
                'Forecast error, normalized',
                <>
                  <p className="mi-note">
                    <strong>This is a derived figure, computed here rather than reported directly by the models.</strong> RMSE and MAE can't
                    be averaged in their raw units — BPH is hoppers/hill, RSB is % damage, and 6.71 plus 1.38
                    isn't a real quantity in either unit. Dividing each pest's RMSE and MAE by its own test set's
                    observed range turns both into "error as a share of how much this pest's target actually
                    varies," which has no unit — so averaging the two normalized values is legitimate in a way
                    averaging the raw numbers never was. R² is already unitless by definition, so it's a plain
                    average of the two.
                  </p>
                  <PerClassTable
                    rows={[
                      { label: 'BPH', precision: normalizedForecast.bphNrmse, recall: normalizedForecast.bphNmae, f1: bphMetrics?.r2 ?? 0, support: Math.round(normalizedForecast.bphRange * 100) / 100 },
                      { label: 'RSB', precision: normalizedForecast.rsbNrmse, recall: normalizedForecast.rsbNmae, f1: rsbMetrics?.r2 ?? 0, support: Math.round(normalizedForecast.rsbRange * 100) / 100 },
                    ]}
                    rowHeader="Pest"
                    countLabel="Observed range"
                    col1Label="NRMSE"
                    col2Label="NMAE"
                    col3Label="R²"
                  />
                  <p className="mi-note mi-syswide-callout">
                    Raw, real-unit RMSE/MAE/R² per pest still live on the <strong>BiLSTM regression</strong> tab —
                    this card doesn't replace those, it's the one number this tab can show that they can't.
                  </p>
                </>,
              )
            }
          >
            <span className="mi-syswide-headline-value">{pct(normalizedForecast.avgNrmse)}</span>
            <span className="mi-syswide-headline-label">Forecast error, normalized</span>
            <span className="mi-syswide-headline-sub">RMSE ÷ observed range, averaged across both pests</span>
            <span className="mi-clickable-hint-icon" aria-hidden="true">
              ⓘ
            </span>
          </button>
        )}
      </div>

      {pooledEtl && (
        <div className="mi-syswide-block">
          <h4 className="mi-h4">Decision agreement — forecast to risk level</h4>
          <p className="mi-note">
            Both pests' Low/Medium/High matrices summed cell-by-cell, then metrics recomputed from the combined
            counts — not an average of two percentages, which would ignore how differently the bands are balanced
            between pests.
          </p>
          <div className="mi-metrics three" style={{ marginBottom: 14 }}>
            <ClickableMetricCard
              label="Accuracy"
              value={pct(pooledEtl.accuracy)}
              hint="All bands, both pests"
              tone="good"
              onClick={() =>
                openModal(
                  'Decision agreement — Accuracy',
                  <>
                    <p className="mi-note">
                      Accuracy this high mostly reflects how common Low is (
                      {pooledEtl.perClass[0]?.support.toLocaleString()} of the pooled windows) — a model that only
                      ever said "Low" would already score well on this metric alone. The per-band split below is
                      the honest read.
                    </p>
                    <PerClassTable rows={pooledEtl.perClass} />
                  </>,
                )
              }
            />
            <ClickableMetricCard
              label="Precision (macro)"
              value={pct(pooledEtl.precisionMacro)}
              hint="Unweighted mean across the three bands"
              tone="good"
              onClick={() =>
                openModal(
                  'Decision agreement — Precision',
                  <>
                    <p className="mi-note">
                      Low's precision carries this average; High sits at 0% because the matrix above shows zero
                      High predictions to be precise <em>about</em> — there's nothing to divide by, so it counts as
                      0 rather than undefined.
                    </p>
                    <PerClassTable rows={pooledEtl.perClass} />
                  </>,
                )
              }
            />
            <ClickableMetricCard
              label="Recall (macro)"
              value={pct(pooledEtl.recallMacro)}
              hint="Unweighted mean across the three bands"
              tone="good"
              onClick={() =>
                openModal(
                  'Decision agreement — Recall',
                  <>
                    <p className="mi-note">
                      Medium's recall ({pct(pooledEtl.perClass[1]?.recall ?? 0)}) is the most informative number in
                      this row — it's the system's rate of actually catching a real Medium-risk window, not just
                      how often "Medium" happens to be right when guessed.
                    </p>
                    <PerClassTable rows={pooledEtl.perClass} />
                  </>,
                )
              }
            />
          </div>
          <NConfusionMatrix matrix={pooledEtl.matrix} labels={pooledEtl.labels} />
          <p className="mi-note mi-syswide-callout">
            <strong>The High column is entirely zero.</strong> System-wide, the deployed models never predict the
            High band — the same finding each pest shows on its own.
          </p>
        </div>
      )}

      {pooledResnet && (
        <div className="mi-syswide-block">
          <h4 className="mi-h4">Visual identification — pest present or absent</h4>
          <p className="mi-note">
            Counted as <strong>decisions, not images</strong>: every photo is scored by both classifiers, and each
            pest's negatives are built from the other pest's crops — so one RSB crop is a positive in RSB's test
            set and a negative in BPH's. The totals below are roughly twice the number of distinct crops behind
            them.
          </p>
          <div className="mi-metrics three" style={{ marginBottom: 14 }}>
            <ClickableMetricCard
              label="Accuracy"
              value={pct(pooledResnet.accuracy)}
              hint="Across every yes/no call both classifiers make"
              tone="good"
              onClick={() =>
                openModal(
                  'Visual identification — Accuracy',
                  <>
                    <p className="mi-note">
                      Pooling hides which classifier earned this: BPH alone is {pct(bphResnet?.accuracy ?? 0)}, RSB
                      alone {pct(rsbResnet?.accuracy ?? 0)} — see the per-class table for where the combined count
                      actually came from.
                    </p>
                    <PerClassTable
                      rows={pooledResnet.perClass.map((c) => ({ ...c, label: c.label === 'not this pest' ? 'Absent' : 'Present' }))}
                      rowHeader="Photo"
                      countLabel="Crops"
                    />
                  </>,
                )
              }
            />
            <ClickableMetricCard
              label="Precision (macro)"
              value={pct(pooledResnet.precisionMacro)}
              hint="Unweighted mean, present/absent"
              tone="good"
              onClick={() =>
                openModal(
                  'Visual identification — Precision',
                  <>
                    <p className="mi-note">
                      "Present" precision ({pct(pooledResnet.perClass[1]?.precision ?? 0)}) is the one that matters
                      most operationally — when either classifier says a pest is in the photo, this is how often
                      that's true.
                    </p>
                    <PerClassTable
                      rows={pooledResnet.perClass.map((c) => ({ ...c, label: c.label === 'not this pest' ? 'Absent' : 'Present' }))}
                      rowHeader="Photo"
                      countLabel="Crops"
                    />
                  </>,
                )
              }
            />
            <ClickableMetricCard
              label="Recall (macro)"
              value={pct(pooledResnet.recallMacro)}
              hint="Unweighted mean, present/absent"
              tone="good"
              onClick={() =>
                openModal(
                  'Visual identification — Recall',
                  <>
                    <p className="mi-note">
                      "Present" recall ({pct(pooledResnet.perClass[1]?.recall ?? 0)}) is the share of real
                      sightings the system actually catches — the number that matters if a missed detection is the
                      costly direction of error.
                    </p>
                    <PerClassTable
                      rows={pooledResnet.perClass.map((c) => ({ ...c, label: c.label === 'not this pest' ? 'Absent' : 'Present' }))}
                      rowHeader="Photo"
                      countLabel="Crops"
                    />
                  </>,
                )
              }
            />
          </div>
          <NConfusionMatrix matrix={pooledResnet.matrix} labels={pooledResnet.labels} />
        </div>
      )}

      {shapRows.length > 0 && (
        <div className="mi-syswide-block">
          <h4 className="mi-h4">What drives the predictions</h4>
          <p className="mi-note">
            Each pest's attribution shares averaged and re-ranked — what moves the system overall, not one
            forecast. Climate Drivers runs this same mechanism on a single live prediction.
          </p>
          {shapList(false)}
        </div>
      )}

      {/* This tab only does what the per-model tabs can't: pool across both
          pests. Raw-unit forecast error (RMSE/MAE in hoppers/hill vs. %
          damage) still isn't repeated here — those genuinely can't be
          averaged — but the normalized headline card above is the single
          number this tab can show that the per-pest tabs can't. */}
      <p className="mi-note mi-syswide-footer">
        Raw, real-unit detail lives on the other tabs: forecast error in <strong>BiLSTM regression</strong> (kept
        there because hoppers/hill and % damage can't be averaged directly), and per-classifier scores in{' '}
        <strong>ResNet-50 performance</strong>.
      </p>

      {modal && (
        <DetailModal title={modal.title} onClose={closeModal}>
          {modal.node}
        </DetailModal>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

interface ModelInsightsPageProps {
  accessToken: string
  onSessionExpired: () => void
}

function ModelInsightsPage({ accessToken, onSessionExpired }: ModelInsightsPageProps) {
  const [tab, setTab] = useState<TabKey>('flow')
  const [data, setData] = useState<ModelInsightsResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchModelInsights(accessToken)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err: Error) => {
        if (cancelled) return
        if (err.message.startsWith('Session expired')) {
          onSessionExpired()
        } else {
          setError(err.message)
        }
      })

    return () => {
      cancelled = true
    }
  }, [accessToken, onSessionExpired])

  return (
    <>
      <section className="panel mi-panel mi-hero">
        <div className="panel-head">
          <div>
            <div className="panel-title">Model Insights</div>
            <div className="panel-subtitle">
              How the images and weather are processed, and how well each model performs.
            </div>
          </div>
          {data && (
            <span className="badge badge-green mi-live-badge">
              <span className="mi-live-dot" />
              Live data
            </span>
          )}
        </div>

        {error && <p className="stat-card-error">{error}</p>}
        {!data && !error && <p className="stat-card-loading">Loading model results…</p>}

        {data && (
          <div className="mi-status">
            {data.models.map((s) => {
              const [model, pest] = s.name.split(' · ')
              return (
                <div key={s.name} className={`mi-status-item${s.loaded ? ' loaded' : ''}`}>
                  <div className="mi-status-top">
                    <div className="mi-status-title">
                      <strong>{model}</strong>
                      {pest && <span className="mi-status-pest">{pest}</span>}
                    </div>
                    <span className={`mi-status-state${s.loaded ? ' on' : ''}`}>
                      <span className={`mi-dot${s.loaded ? ' on' : ''}`} />
                      {s.loaded ? 'Loaded' : 'Not loaded'}
                    </span>
                  </div>
                  <div className="mi-status-detail">{s.detail}</div>
                  <div className="mi-status-updated">{s.updated ? `Updated ${s.updated}` : ' '}</div>
                </div>
              )
            })}
          </div>
        )}

        <div className="mi-tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              className={tab === t.key ? 'active' : ''}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </section>

      {tab === 'flow' && <FlowTab />}
      {tab === 'system' && data && <SystemPerformanceSection data={data} />}
      {tab === 'resnet' && data && <ResnetTab data={data} />}
      {tab === 'bilstm' && data && <BilstmTab data={data} />}
    </>
  )
}

export default ModelInsightsPage
