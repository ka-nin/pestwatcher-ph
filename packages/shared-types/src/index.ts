/**
 * Types shared between the frontends and server-python.
 *
 * STATUS: nothing imports this package yet. `admin-web` declares it as a
 * workspace dependency and the root README describes it as the place to keep
 * TypeScript in step with the Pydantic schemas, but in practice `admin-web`
 * declares its own response types inline in `src/lib/api.ts` and `user-mobile`
 * is plain JS. Treat what follows as the contract to migrate toward, not as
 * something currently enforced anywhere.
 *
 * It previously exported a `PestRecord` interface that matched no actual API
 * response and used a `riskLevel` of 'Low' | 'Moderate' | 'High' — 'Moderate'
 * is not a value the system produces. The two real vocabularies are below, and
 * they are deliberately distinct.
 */

/**
 * The IPM decision bands. Derived from the BiLSTM's continuous forecast by the
 * fixed ETL table, never learned.
 *
 * Source of truth: server-python/app/decision/etl_thresholds.py (RiskLevel).
 */
export type EtlRiskLevel = 'Low' | 'Medium' | 'High'

/**
 * How confident the ResNet-50 classifier is that a photo contains a pest.
 *
 * Source of truth: server-python/app/models/resnet_model.py (RiskLevel).
 *
 * This is NOT an agronomic risk level and must never be rendered as one — it
 * describes certainty about an image, not pest pressure in a field. The names
 * overlap with EtlRiskLevel by accident of wording, which is exactly why both
 * are spelled out here.
 */
export type DetectionConfidenceLevel = 'Low' | 'Moderate' | 'High' | 'Critical'

/** The two pests with a trained forecasting model (ml/config.py PEST_PARAMS). */
export type PestCode = 'BPH' | 'RSB'

/** Units the forecast and the ETL table share, per pest. */
export type ForecastUnit = 'hoppers_per_hill' | 'pct_damage'

/** Rice growth stages (ml/config.py GROWTH_STAGE_BUCKETS). */
export type GrowthStage =
  | 'Seedling'
  | 'Tillering'
  | 'Elongation'
  | 'Panicle'
  | 'Flowering'
  | 'Ripening'

/** The bucket a growth stage collapses into for ETL threshold lookup. */
export type GrowthStageBucket = 'Vegetative' | 'Reproductive'

/** Lifecycle of a farmer-submitted sighting (app/schemas/reports.py). */
export type ReportStatus = 'pending' | 'verified' | 'rejected'
