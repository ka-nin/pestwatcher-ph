// What the forecasting model reads, shown on the Simulation page's "how the
// computation works" view. The model is given the raw daily weather and the
// growth stage and learns the rest itself, so there is no formula here: the
// rows below are the inputs exactly as the server builds them
// (server-python/app/models/bilstm_model.py). The server remains the source
// of truth for the actual prediction.

import type { GrowthStage, PestKey, SimulationDailyObservation } from './api'

const GROWTH_STAGES: GrowthStage[] = ['Seedling', 'Tillering', 'Elongation', 'Panicle', 'Flowering', 'Ripening']

export function stageOneHot(stage: GrowthStage): number[] {
  return GROWTH_STAGES.map((s) => (s === stage ? 1 : 0))
}

export interface DayFeatureRow {
  date: string
  tmax: number
  tmin: number
  relative_humidity: number
  rainfall: number
  growth_stage: GrowthStage
}

export interface StaticFeatureRow {
  label: string
  key: string
  value: number
  unit: string
  note: string
}

export interface PipelineFeatures {
  sequenceRows: DayFeatureRow[]
  staticRows: StaticFeatureRow[]
  sequenceFeatureCount: number
  staticFeatureCount: number
}

export function buildPipelineFeatures(_pest: PestKey, days: SimulationDailyObservation[]): PipelineFeatures {
  const sequenceRows: DayFeatureRow[] = days.map((d) => ({
    date: d.date,
    tmax: d.tmax,
    tmin: d.tmin,
    relative_humidity: d.relative_humidity,
    rainfall: d.rainfall,
    growth_stage: d.growth_stage,
  }))

  // The simulation has no technologist-verified report, so the model gets the
  // "no report on file" encoding it was trained with.
  const staticRows: StaticFeatureRow[] = [
    { label: 'Latest verified value', key: 'last_observed_value', value: 0, unit: '', note: 'none in this simulation' },
    { label: 'Days since that report', key: 'days_since_observation', value: 60, unit: 'days', note: 'the "no report" setting' },
    { label: 'Report on file', key: 'has_recent_observation', value: 0, unit: '0/1', note: '0 = no verified report' },
  ]

  return {
    sequenceRows,
    staticRows,
    sequenceFeatureCount: 10, // tmax, tmin, rh, rainfall + 6 one-hot growth-stage columns
    staticFeatureCount: staticRows.length,
  }
}

export const RISK_THRESHOLD_HINT: Record<PestKey, string> = {
  BPH: 'Vegetative: Low <10, Medium 10–20, High >20 hoppers/hill · Reproductive: Low <5, Medium 5–10, High >10',
  RSB: 'Vegetative: Low <2%, Medium 2–5%, High >5% dead hearts · Reproductive: Low <5%, Medium 5–10%, High >10% white ears',
}
