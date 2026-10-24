import type { RiskLevel, TrajectoryPoint } from '../../lib/api'

interface TrajectoryChartProps {
  points: TrajectoryPoint[]
  lowMax: number
  highMin: number
  unitLabel: string
  /** Text for a value in the hover tooltip, e.g. "12 hoppers/hill". */
  valueText: (value: number) => string
  /** Index of the day being inspected (shared with the daily breakdown). */
  hoverIndex: number | null
  onHover: (index: number | null) => void
}

const riskFill: Record<RiskLevel, string> = {
  Low: '#4b9e5f',
  Medium: '#e0b23b',
  High: '#d3564f',
}

const WIDTH = 360
const HEIGHT = 200
const MARGIN = { top: 10, right: 10, bottom: 28, left: 32 }
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom

export function niceMax(highMin: number, dataMax: number) {
  const raw = Math.max(highMin * 1.5, dataMax * 1.15)
  const step = raw > 20 ? 10 : 5
  return Math.ceil(raw / step) * step
}

function formatDateLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// Monotone cubic (Fritsch–Carlson) interpolation — the same family of curve
// recharts' `type="monotone"` draws for the mobile trend chart. A plain
// Catmull-Rom spline can overshoot past the real data values on sharp rises
// (e.g. a line dipping below 0 between two low points); this variant clamps
// each segment's tangent so the curve never overshoots its neighboring
// points, matching mobile's look without inventing dips/bumps that aren't
// in the data.
function monotonePath(pts: { x: number; y: number }[]): string {
  const n = pts.length
  if (n === 0) return ''
  if (n === 1) return `M ${pts[0].x} ${pts[0].y}`

  const dx: number[] = []
  const secant: number[] = []
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1].x - pts[i].x)
    secant.push((pts[i + 1].y - pts[i].y) / (dx[i] || 1))
  }

  const tangent: number[] = new Array(n)
  tangent[0] = secant[0]
  tangent[n - 1] = secant[n - 2]
  for (let i = 1; i < n - 1; i++) {
    tangent[i] = secant[i - 1] === 0 || secant[i] === 0 || secant[i - 1] < 0 !== secant[i] < 0
      ? 0
      : (secant[i - 1] + secant[i]) / 2
  }

  for (let i = 0; i < n - 1; i++) {
    if (secant[i] === 0) {
      tangent[i] = 0
      tangent[i + 1] = 0
      continue
    }
    const alpha = tangent[i] / secant[i]
    const beta = tangent[i + 1] / secant[i]
    if (alpha < 0) tangent[i] = 0
    if (beta < 0) tangent[i + 1] = 0
    const magnitude = alpha * alpha + beta * beta
    if (magnitude > 9) {
      const tau = 3 / Math.sqrt(magnitude)
      tangent[i] = tau * alpha * secant[i]
      tangent[i + 1] = tau * beta * secant[i]
    }
  }

  let path = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 0; i < n - 1; i++) {
    const cp1x = pts[i].x + dx[i] / 3
    const cp1y = pts[i].y + (tangent[i] * dx[i]) / 3
    const cp2x = pts[i + 1].x - dx[i] / 3
    const cp2y = pts[i + 1].y - (tangent[i + 1] * dx[i]) / 3
    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${pts[i + 1].x} ${pts[i + 1].y}`
  }
  return path
}

function TrajectoryChart({
  points,
  lowMax,
  highMin,
  unitLabel,
  valueText,
  hoverIndex,
  onHover,
}: TrajectoryChartProps) {
  if (points.length === 0) {
    return <p className="stat-card-loading">Loading trajectory…</p>
  }

  const dataMax = Math.max(...points.map((p) => p.predicted_value))
  const yMax = niceMax(highMin, dataMax)

  const yPixel = (value: number) => MARGIN.top + PLOT_H * (1 - value / yMax)
  const xPixel = (i: number) =>
    MARGIN.left + (points.length === 1 ? 0 : (i / (points.length - 1)) * PLOT_W)

  const yTicks = Array.from(new Set([0, lowMax, highMin, yMax])).sort((a, b) => a - b)
  const labelEvery = Math.max(1, Math.ceil(points.length / 7))

  const linePath = monotonePath(points.map((p, i) => ({ x: xPixel(i), y: yPixel(p.predicted_value) })))

  // 80% confidence band: the upper edge left to right, then the lower edge back.
  const hasBand = points.length > 1 && points.every((p) => p.predicted_low != null && p.predicted_high != null)
  const bandPath = hasBand
    ? `${monotonePath(points.map((p, i) => ({ x: xPixel(i), y: yPixel(p.predicted_high as number) })))} L ${xPixel(points.length - 1)} ${yPixel(points[points.length - 1].predicted_low as number)} ${monotonePath(
        points.map((p, i) => ({ x: xPixel(points.length - 1 - i), y: yPixel(points[points.length - 1 - i].predicted_low as number) })),
      ).replace(/^M [\d.\-]+ [\d.\-]+/, '')} Z`
    : null

  const handlePointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * WIDTH
    const i = Math.round(((x - MARGIN.left) / PLOT_W) * (points.length - 1))
    onHover(Math.min(points.length - 1, Math.max(0, i)))
  }

  const handleKey = (e: React.KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      onHover(hoverIndex === null ? 0 : Math.min(points.length - 1, hoverIndex + 1))
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onHover(hoverIndex === null ? points.length - 1 : Math.max(0, hoverIndex - 1))
    } else if (e.key === 'Escape') {
      onHover(null)
    }
  }

  const active = hoverIndex !== null ? points[hoverIndex] : null
  const activeLeft = hoverIndex !== null ? Math.min(88, Math.max(12, (xPixel(hoverIndex) / WIDTH) * 100)) : 0
  const etlPercent = active ? Math.round((active.predicted_value / highMin) * 100) : 0

  return (
    <div className="trajectory-wrap">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="trajectory-chart trajectory-chart-interactive"
        role="img"
        tabIndex={0}
        aria-label="Forecast trajectory. Use the left and right arrow keys to inspect each day."
        onPointerMove={handlePointer}
        onPointerDown={handlePointer}
        onPointerLeave={() => onHover(null)}
        onBlur={() => onHover(null)}
        onKeyDown={handleKey}
      >
        {/* risk bands */}
        <rect
          x={MARGIN.left}
          y={yPixel(lowMax)}
          width={PLOT_W}
          height={yPixel(0) - yPixel(lowMax)}
          fill="#4b9e5f"
          opacity={0.12}
        />
        <rect
          x={MARGIN.left}
          y={yPixel(highMin)}
          width={PLOT_W}
          height={yPixel(lowMax) - yPixel(highMin)}
          fill="#e0b23b"
          opacity={0.15}
        />
        <rect
          x={MARGIN.left}
          y={yPixel(yMax)}
          width={PLOT_W}
          height={yPixel(highMin) - yPixel(yMax)}
          fill="#d3564f"
          opacity={0.12}
        />

        {/* ETL line */}
        <line
          x1={MARGIN.left}
          x2={WIDTH - MARGIN.right}
          y1={yPixel(highMin)}
          y2={yPixel(highMin)}
          stroke="#b08a2e"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        <text x={WIDTH - MARGIN.right} y={yPixel(highMin) - 4} textAnchor="end" className="trajectory-etl-label">
          ETL: {highMin}
          {unitLabel}
        </text>

        {/* y axis ticks */}
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={yPixel(t)}
              y2={yPixel(t)}
              stroke="#e5e0d3"
              strokeWidth={0.5}
            />
            <text x={MARGIN.left - 6} y={yPixel(t) + 3} textAnchor="end" className="trajectory-axis-label">
              {t}
            </text>
          </g>
        ))}

        {/* x axis labels */}
        {points.map((p, i) => {
          if (i % labelEvery !== 0 && i !== points.length - 1) return null
          const anchor = i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'
          return (
            <text key={p.date} x={xPixel(i)} y={HEIGHT - 8} textAnchor={anchor} className="trajectory-axis-label">
              {formatDateLabel(p.date)}
            </text>
          )
        })}

        {/* guide line for the inspected day */}
        {hoverIndex !== null && (
          <line
            x1={xPixel(hoverIndex)}
            x2={xPixel(hoverIndex)}
            y1={MARGIN.top}
            y2={MARGIN.top + PLOT_H}
            className="trajectory-guide"
          />
        )}

        {/* confidence band, clipped to the plot area */}
        {bandPath && (
          <>
            <clipPath id="trajectory-plot-clip">
              <rect x={MARGIN.left} y={MARGIN.top} width={PLOT_W} height={PLOT_H} />
            </clipPath>
            <path d={bandPath} className="trajectory-band" clipPath="url(#trajectory-plot-clip)" />
          </>
        )}

        {/* faint connecting line */}
        <path d={linePath} className="trajectory-line" />

        {/* data points */}
        {points.map((p, i) => (
          <circle
            key={p.date}
            cx={xPixel(i)}
            cy={yPixel(p.predicted_value)}
            r={hoverIndex === i ? 6 : 3.5}
            fill={riskFill[p.risk_level]}
            className={hoverIndex === i ? 'trajectory-dot trajectory-dot-active' : 'trajectory-dot'}
          />
        ))}
      </svg>

      {active && hoverIndex !== null && (
        <div
          className="trajectory-tooltip"
          style={{ left: `${activeLeft}%`, top: `${(yPixel(active.predicted_value) / HEIGHT) * 100}%` }}
        >
          <strong>{formatDateLabel(active.date)}</strong>
          <span>{valueText(active.predicted_value)}</span>
          {active.predicted_low != null && active.predicted_high != null && (
            <span className="trajectory-tooltip-range">
              Likely range {valueText(active.predicted_low)} to {valueText(active.predicted_high)}
            </span>
          )}
          <span className="trajectory-tooltip-risk">
            <i style={{ background: riskFill[active.risk_level] }} />
            {active.risk_level} risk · {etlPercent}% of ETL
          </span>
        </div>
      )}
    </div>
  )
}

export default TrajectoryChart
