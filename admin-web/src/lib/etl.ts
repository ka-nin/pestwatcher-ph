import type { GrowthStage, RiskLevel } from './api'

/**
 * Client-side mirror of server-python/app/decision/etl_thresholds.py.
 *
 * These are the thesis's Table 2 values, and unlike the previous version of
 * this file they are stage-specific, exactly as the backend is: BPH tightens
 * during Reproductive, and RSB switches damage indicator entirely (% dead
 * hearts while Vegetative, % white ears while Reproductive) which is why its
 * Reproductive band is numerically higher rather than lower.
 *
 * Nothing here decides a risk level for real. The backend derives every
 * Low/Medium/High the dashboard displays; these numbers exist so the UI can
 * draw reference lines and print "ETL: N" next to a forecast. If the two ever
 * disagree, the backend is right and this file is the bug.
 */
export const ETL_BANDS: Record<
  'bph' | 'rsb',
  Record<GrowthStageBucket, { lowMax: number; highMin: number; unit: string }>
> = {
  bph: {
    Vegetative: { lowMax: 10, highMin: 20, unit: 'hoppers/hill' },
    Reproductive: { lowMax: 5, highMin: 10, unit: 'hoppers/hill' },
  },
  rsb: {
    Vegetative: { lowMax: 2, highMin: 5, unit: '% dead hearts' },
    Reproductive: { lowMax: 5, highMin: 10, unit: '% white ears' },
  },
}

export type GrowthStageBucket = 'Vegetative' | 'Reproductive'

/** Mirrors GROWTH_STAGE_BUCKETS in server-python/ml/config.py. */
export const GROWTH_STAGE_BUCKETS: Record<GrowthStage, GrowthStageBucket> = {
  Seedling: 'Vegetative',
  Tillering: 'Vegetative',
  Elongation: 'Vegetative',
  Panicle: 'Reproductive',
  Flowering: 'Reproductive',
  Ripening: 'Reproductive',
}

/**
 * The growth stage the dashboard currently assumes for every municipality.
 *
 * It is one constant rather than the four separate hardcoded 'Tillering'
 * literals that used to live across StatusPage, PestForecastPage, IpmPage and
 * ClimateDriversPage, so the stage and the ETL bands derived from it can no
 * longer drift apart. Replacing this with a real per-municipality stage (from
 * a PhilRice crop calendar, or from the LGU's own records) is the one change
 * needed to make every threshold on the dashboard stage-correct.
 */
export const ASSUMED_GROWTH_STAGE: GrowthStage = 'Tillering'

/** The ETL band for a pest at a given growth stage. */
export function etlBandFor(pestKey: 'bph' | 'rsb', stage: GrowthStage = ASSUMED_GROWTH_STAGE) {
  return ETL_BANDS[pestKey][GROWTH_STAGE_BUCKETS[stage]]
}

export const RISK_TONE: Record<RiskLevel, 'green' | 'yellow' | 'red'> = {
  Low: 'green',
  Medium: 'yellow',
  High: 'red',
}
