import type { RiskLevel } from './api'

// TODO: placeholder ETL bands mirroring server-python/app/decision/etl_thresholds.py's
// current placeholders — keep these two in sync until the thesis's real
// Table 2 values are finalized and hardcoded here permanently.
export const ETL_BANDS: Record<'bph' | 'rsb', { lowMax: number; highMin: number }> = {
  bph: { lowMax: 10, highMin: 20 },
  rsb: { lowMax: 2, highMin: 5 },
}

export const RISK_TONE: Record<RiskLevel, 'green' | 'yellow' | 'red'> = {
  Low: 'green',
  Medium: 'yellow',
  High: 'red',
}
