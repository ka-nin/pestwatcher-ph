import type { RiskLevel, TrajectoryPoint } from '../../lib/api'

interface TrajectoryChartProps {
  points: TrajectoryPoint[]
  lowMax: number
  highMin: number
  unitLabel: string
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

function TrajectoryChart({ points, lowMax, highMin, unitLabel }: TrajectoryChartProps) {
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

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="trajectory-chart" role="img">
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

      {/* data points */}
      {points.map((p, i) => (
        <circle key={p.date} cx={xPixel(i)} cy={yPixel(p.predicted_value)} r={3.5} fill={riskFill[p.risk_level]} />
      ))}
    </svg>
  )
}

export default TrajectoryChart
