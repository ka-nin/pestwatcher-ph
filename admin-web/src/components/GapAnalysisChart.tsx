import type { GapAnalysisDay } from '../lib/api'
import { niceMax } from '../pages/Dashboard/TrajectoryChart'

interface GapAnalysisChartProps {
  days: GapAnalysisDay[]
  lowMax: number
  highMin: number
  unitLabel: string
}

const WIDTH = 740
const HEIGHT = 260
const MARGIN = { top: 10, right: 16, bottom: 28, left: 40 }
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom

function formatDateLabel(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function polyline(days: GapAnalysisDay[], key: 'historical_value' | 'report_based_value', xPixel: (i: number) => number, yPixel: (v: number) => number) {
  const segments: string[] = []
  let current: string[] = []

  days.forEach((day, i) => {
    const value = day[key]
    if (value === null) {
      if (current.length > 1) segments.push(current.join(' '))
      current = []
      return
    }
    current.push(`${xPixel(i)},${yPixel(value)}`)
  })
  if (current.length > 1) segments.push(current.join(' '))

  return segments
}

function GapAnalysisChart({ days, lowMax, highMin, unitLabel }: GapAnalysisChartProps) {
  if (days.length === 0) {
    return <p className="stat-card-loading">Loading comparison…</p>
  }

  const allValues = days.flatMap((d) => [d.historical_value, d.report_based_value]).filter((v): v is number => v !== null)
  const dataMax = allValues.length ? Math.max(...allValues) : 0
  const yMax = niceMax(highMin, dataMax)

  const yPixel = (value: number) => MARGIN.top + PLOT_H * (1 - value / yMax)
  const xPixel = (i: number) => MARGIN.left + (days.length === 1 ? 0 : (i / (days.length - 1)) * PLOT_W)

  const yTicks = Array.from(new Set([0, lowMax, highMin, yMax])).sort((a, b) => a - b)
  const labelEvery = Math.max(1, Math.ceil(days.length / 7))

  const historicalSegments = polyline(days, 'historical_value', xPixel, yPixel)
  const reportSegments = polyline(days, 'report_based_value', xPixel, yPixel)

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="trajectory-chart" role="img">
      <rect x={MARGIN.left} y={yPixel(lowMax)} width={PLOT_W} height={yPixel(0) - yPixel(lowMax)} fill="#4b9e5f" opacity={0.1} />
      <rect x={MARGIN.left} y={yPixel(highMin)} width={PLOT_W} height={yPixel(lowMax) - yPixel(highMin)} fill="#e0b23b" opacity={0.13} />
      <rect x={MARGIN.left} y={yPixel(yMax)} width={PLOT_W} height={yPixel(highMin) - yPixel(yMax)} fill="#d3564f" opacity={0.1} />

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

      {yTicks.map((t) => (
        <g key={t}>
          <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={yPixel(t)} y2={yPixel(t)} stroke="#e5e0d3" strokeWidth={0.5} />
          <text x={MARGIN.left - 6} y={yPixel(t) + 3} textAnchor="end" className="trajectory-axis-label">
            {t}
          </text>
        </g>
      ))}

      {days.map((d, i) => {
        if (i % labelEvery !== 0 && i !== days.length - 1) return null
        const anchor = i === 0 ? 'start' : i === days.length - 1 ? 'end' : 'middle'
        return (
          <text key={d.date} x={xPixel(i)} y={HEIGHT - 8} textAnchor={anchor} className="trajectory-axis-label">
            {formatDateLabel(d.date)}
          </text>
        )
      })}

      {/* historical (weather-only) line — dashed, neutral */}
      {historicalSegments.map((points, i) => (
        <polyline key={`h-${i}`} points={points} fill="none" stroke="#777" strokeWidth={1.75} strokeDasharray="5 4" />
      ))}

      {/* report-based (anchored) line — solid, accent */}
      {reportSegments.map((points, i) => (
        <polyline key={`r-${i}`} points={points} fill="none" stroke="#2f6b32" strokeWidth={2} />
      ))}

      {days.map((d, i) =>
        d.historical_value !== null ? (
          <circle key={`hd-${d.date}`} cx={xPixel(i)} cy={yPixel(d.historical_value)} r={2.5} fill="#777" />
        ) : null,
      )}
      {days.map((d, i) =>
        d.report_based_value !== null ? (
          <circle key={`rd-${d.date}`} cx={xPixel(i)} cy={yPixel(d.report_based_value)} r={3} fill="#2f6b32" />
        ) : null,
      )}
    </svg>
  )
}

export default GapAnalysisChart
