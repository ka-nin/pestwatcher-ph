// Client-side mirror of server-python/app/preprocessing/features.py, used only
// to narrate the Simulation page's "how the computation works" pipeline view.
// The server remains the source of truth for the actual prediction; these
// functions exist purely to show the same formulas running on the same
// numbers the user typed in, step by step.

import type { GrowthStage, PestKey, SimulationDailyObservation } from './api'

const GROWTH_STAGES: GrowthStage[] = ['Seedling', 'Tillering', 'Elongation', 'Panicle', 'Flowering', 'Ripening']
const REPRODUCTIVE_STAGES = new Set<GrowthStage>(['Panicle', 'Flowering', 'Ripening'])

const PEST_FEATURE_PARAMS: Record<PestKey, { gddBaseTempC: number; hpThresholdPct: number }> = {
  BPH: { gddBaseTempC: 10.0, hpThresholdPct: 80.0 },
  RSB: { gddBaseTempC: 15.0, hpThresholdPct: 80.0 },
}

const WSI_DAILY_WATER_REQUIREMENT_MM = 6.0

export function vpdForDay(tmax: number, tmin: number, rh: number): number {
  const tMean = (tmax + tmin) / 2
  const satVp = 0.6108 * Math.exp((17.27 * tMean) / (tMean + 237.3))
  const actualVp = satVp * (rh / 100)
  return satVp - actualVp
}

export function diurnalRangeForDay(tmax: number, tmin: number): number {
  return tmax - tmin
}

export function stageOneHot(stage: GrowthStage): number[] {
  return GROWTH_STAGES.map((s) => (s === stage ? 1 : 0))
}

function trend(series: number[]): number {
  const n = series.length
  if (n < 2) return 0
  const xMean = (n - 1) / 2
  const yMean = series.reduce((a, b) => a + b, 0) / n
  let num = 0
  let den = 0
  series.forEach((y, i) => {
    num += (i - xMean) * (y - yMean)
    den += (i - xMean) ** 2
  })
  return den ? num / den : 0
}

export interface DayFeatureRow {
  date: string
  tmax: number
  tmin: number
  relative_humidity: number
  rainfall: number
  vpd: number
  diurnalRange: number
  growth_stage: GrowthStage
}

export interface StaticFeatureRow {
  label: string
  key: string
  value: number
  unit: string
  formulaHint: string
}

export interface PipelineFeatures {
  sequenceRows: DayFeatureRow[]
  staticRows: StaticFeatureRow[]
  sequenceFeatureCount: number
  staticFeatureCount: number
}

export function buildPipelineFeatures(pest: PestKey, days: SimulationDailyObservation[]): PipelineFeatures {
  const { gddBaseTempC, hpThresholdPct } = PEST_FEATURE_PARAMS[pest]

  const sequenceRows: DayFeatureRow[] = days.map((d) => ({
    date: d.date,
    tmax: d.tmax,
    tmin: d.tmin,
    relative_humidity: d.relative_humidity,
    rainfall: d.rainfall,
    vpd: vpdForDay(d.tmax, d.tmin, d.relative_humidity),
    diurnalRange: diurnalRangeForDay(d.tmax, d.tmin),
    growth_stage: d.growth_stage,
  }))

  const tMax = days.map((d) => d.tmax)
  const tMin = days.map((d) => d.tmin)
  const rh = days.map((d) => d.relative_humidity)
  const rainfall = days.map((d) => d.rainfall)
  const tempMean = tMax.map((hi, i) => (hi + tMin[i]) / 2)

  const gddAccum = tempMean.reduce((sum, t) => sum + Math.max(t - gddBaseTempC, 0), 0)
  const crf = rainfall.reduce((a, b) => a + b, 0)
  const hp = (rh.filter((v) => v >= hpThresholdPct).length / rh.length) * 100
  const requirement = WSI_DAILY_WATER_REQUIREMENT_MM * rainfall.length
  const wsi = requirement > 0 ? Math.min(Math.max(requirement - crf, 0) / requirement, 1) : 0
  const rainfallTrend = trend(rainfall)
  const tempTrend = trend(tempMean)

  const lastStage = days[days.length - 1].growth_stage
  const isReproductive = REPRODUCTIVE_STAGES.has(lastStage) ? 1 : 0
  const reproductiveXRainfall = isReproductive * crf
  const reproductiveXTemp = isReproductive * (tempMean.reduce((a, b) => a + b, 0) / tempMean.length)

  const staticRows: StaticFeatureRow[] = [
    { label: 'GDD (accumulated)', key: 'gdd', value: gddAccum, unit: '°C·day', formulaHint: `Σ max(mean(Tmax,Tmin) − ${gddBaseTempC}, 0)` },
    { label: 'CRF (cumulative rainfall)', key: 'crf', value: crf, unit: 'mm', formulaHint: 'Σ rainfall over 14 days' },
    { label: 'HP (humidity persistence)', key: 'hp', value: hp, unit: '%', formulaHint: `% of days with RH ≥ ${hpThresholdPct}%` },
    { label: 'WSI (water stress index)', key: 'wsi', value: wsi, unit: '0–1', formulaHint: 'deficit vs. 6mm/day demand, clipped [0,1]' },
    { label: 'Rainfall trend', key: 'rainfall_trend', value: rainfallTrend, unit: 'mm/day', formulaHint: 'least-squares slope over the window' },
    { label: 'Temperature trend', key: 'temp_trend', value: tempTrend, unit: '°C/day', formulaHint: 'least-squares slope over the window' },
    { label: 'Reproductive stage flag', key: 'is_reproductive', value: isReproductive, unit: '0/1', formulaHint: `1 if growth stage is Panicle/Flowering/Ripening` },
    { label: 'Reproductive × rainfall', key: 'repro_x_rainfall', value: reproductiveXRainfall, unit: 'mm', formulaHint: 'interaction term: flag × CRF' },
    { label: 'Reproductive × temperature', key: 'repro_x_temp', value: reproductiveXTemp, unit: '°C', formulaHint: 'interaction term: flag × mean temp' },
  ]

  return {
    sequenceRows,
    staticRows,
    sequenceFeatureCount: 12, // tmax, tmin, rh, rainfall, vpd, diurnal range, + 6 one-hot stage columns
    staticFeatureCount: staticRows.length,
  }
}

export const RISK_THRESHOLD_HINT: Record<PestKey, string> = {
  BPH: 'Vegetative: Low <10, Medium 10–20, High >20 hoppers/hill · Reproductive: Low <5, Medium 5–10, High >10',
  RSB: 'Vegetative: Low <2%, Medium 2–5%, High >5% dead hearts · Reproductive: Low <5%, Medium 5–10%, High >10% white ears',
}
