import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  fetchModelInsights,
  type FeatureComparisonResponse,
  type ModelInsightsResponse,
  type PredictionPointDto,
} from '../../lib/api'
import { PHOTO_FLOW, WEATHER_FLOW, type FlowStep, type PestCode } from './modelInsightsData'
import './ModelInsightsPage.css'

type TabKey = 'flow' | 'resnet' | 'bilstm'
type LaneKey = 'photo' | 'weather'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'flow', label: 'How it works' },
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
            ['GDD', 22, 22],
            ['CRF', 84, 22],
            ['HP', 146, 22],
            ['VPD', 22, 62],
            ['WSI', 84, 62],
            ['Trends', 146, 62],
          ].map(([text, x, y]) => (
            <g key={text as string}>
              <rect x={x as number} y={y as number} width="52" height="28" rx="14" fill={GREEN_SOFT} stroke={GREEN} strokeWidth="1.2" className="mi-pulse" />
              <text x={(x as number) + 26} y={(y as number) + 18} textAnchor="middle" fontSize="10.5" fontWeight="800" fill={GREEN}>{text}</text>
            </g>
          ))}
          <text x="110" y="118" textAnchor="middle" fontSize="8.5" fill="#777">computed from biology, not guessed by the network</text>
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
          <path d="M16 92 L60 88 L104 80 L148 72 L204 62" stroke={GREY} strokeWidth="2" strokeDasharray="5 4" fill="none" />
          <path className="mi-draw" d="M16 46 L60 56 L104 66 L148 70 L204 62" stroke={GREEN} strokeWidth="2.6" fill="none" />
          <path d="M16 20 V108" stroke={ORANGE} strokeWidth="1.5" strokeDasharray="3 3" />
          <circle cx="16" cy="46" r="4" fill={ORANGE} className="mi-pulse" />
          <text x="24" y="20" fontSize="8.5" fill={ORANGE} fontWeight="700">verified report</text>
          <text x="110" y="122" textAnchor="middle" fontSize="8.5" fill="#777">shift fades to zero over 13 days</text>
          <text x="204" y="54" textAnchor="end" fontSize="8" fill="#777">weather only</text>
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
            <button type="button" className="mi-btn" onClick={() => setPlaying((p) => !p)}>
              {playing ? '❚❚ Pause' : '▶ Play'}
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
            <strong>Images</strong> · ResNet-50 · which pest is in the photo
          </button>
          <button
            type="button"
            className={`mi-lane-tab${lane === 'weather' ? ' active' : ''}`}
            onClick={() => chooseLane('weather')}
          >
            <strong>Weather</strong> · BiLSTM · how bad it will get in 14 days
          </button>
        </div>

        <ol className="mi-track">
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
                <span className="mi-node-num">{i + 1}</span>
                <span className="mi-node-label">{s.short}</span>
              </button>
            </li>
          ))}
        </ol>

        <div className="mi-progress">
          <span style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
        </div>

        <div className="mi-detail" key={`${lane}-${step.id}`}>
          <div className="mi-art">
            <StepArt id={step.id} />
          </div>
          <div className="mi-detail-text">
            <div className="mi-step-count">
              Step {index + 1} of {steps.length}
            </div>
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

function ConfusionMatrix({ matrix }: { matrix: [[number, number], [number, number]] }) {
  const rows = [
    { name: 'Actual: not this pest', cells: matrix[0] },
    { name: 'Actual: this pest', cells: matrix[1] },
  ]
  return (
    <div className="mi-cm">
      <div className="mi-cm-corner" />
      <div className="mi-cm-col">Predicted: not this pest</div>
      <div className="mi-cm-col">Predicted: this pest</div>
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
              <h4 className="mi-h4">Reading a perfect score</h4>
              <p className="mi-note">
                Every one of the {testSize.toLocaleString()} test crops was classified correctly. That is expected here:
                RSB photos are large close-ups of one insect, which look very different from the other classes, so the
                task is easy. Be ready to explain this if a panelist asks, and note that these scores are on cropped
                insects, not whole field photos.
              </p>
            </div>
          )}
        </div>
      </section>

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
            <div className="panel-title">Baseline: engineered vs. raw climate features</div>
            <div className="panel-subtitle">The thesis's RQ2 / RQ3 comparison</div>
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
          <div className="panel-title">Baseline: engineered vs. raw climate features</div>
          <div className="panel-subtitle">
            Same BiLSTM architecture, same {data.n_folds}-fold expanding-window CV splits · engineered =
            GDD/CRF/HP/VPD/WSI/trends · raw = Tmax/Tmin/RH/rainfall only
          </div>
        </div>
      </div>

      <div className="mi-table-wrap">
        <table className="mi-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Engineered</th>
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
                      {result.better_configuration}
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
        Engineered and raw configurations were trained and evaluated on the exact same {data.n_folds} chronological
        test folds, so each metric's 5 paired differences were checked for normality (Shapiro-Wilk) before choosing a
        paired t-test or a Wilcoxon signed-rank test — matching the thesis's stated statistical treatment for RQ2/RQ3.
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
          {data && <span className="badge badge-green">Live data</span>}
        </div>

        {error && <p className="stat-card-error">{error}</p>}
        {!data && !error && <p className="stat-card-loading">Loading model results…</p>}

        {data && (
          <div className="mi-status">
            {data.models.map((s) => (
              <div key={s.name} className="mi-status-item">
                <span className={`mi-dot${s.loaded ? ' on' : ''}`} />
                <div>
                  <strong>{s.name}</strong>
                  <small>
                    {s.loaded ? 'Loaded' : 'Not loaded'} · {s.detail}
                    {s.updated ? ` · updated ${s.updated}` : ''}
                  </small>
                </div>
              </div>
            ))}
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
      {tab === 'resnet' && data && <ResnetTab data={data} />}
      {tab === 'bilstm' && data && <BilstmTab data={data} />}
    </>
  )
}

export default ModelInsightsPage
