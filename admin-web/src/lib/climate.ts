/**
 * Constants for the dashboard's Climate Drivers card.
 *
 * IMPORTANT — these are NOT the model's input features, and the card must not
 * be read as showing them. The distinction matters because the names overlap:
 *
 *   dashboard (here)                 model (server-python/app/preprocessing/features.py)
 *   ----------------------------     ------------------------------------------------
 *   next 7 days, from the forecast   the 14 days BEFORE the prediction date
 *   GDD base 10 C for both pests     per-pest base: BPH 10 C, RSB 15 C
 *   rainfall summed over 7 days      CRF summed over 14 days
 *   humidity from HOURLY readings    humidity persistence from DAILY readings
 *
 * So the card answers "what weather is coming this week", while the model
 * answers "what weather led up to this forecast". Both are legitimate; they
 * are simply different quantities and should never be presented as the same
 * number. If the dashboard ever needs the model's real features, they should
 * come from the backend rather than be recomputed here — that is the only way
 * the two can be guaranteed to agree.
 *
 * Previously GDD_BASE_TEMP_C was declared separately in Dashboard.tsx and
 * ClimateDriversPage.tsx, which is exactly how two copies of a constant drift.
 */

/** Base temperature for the dashboard's GDD readout, in degrees Celsius. */
export const GDD_BASE_TEMP_C = 10

/** RH% at or above which an hour counts toward the humidity-persistence readout. */
export const HUMIDITY_PERSISTENCE_THRESHOLD = 80

/** How many forecast days the rainfall and humidity readouts cover. */
export const OUTLOOK_DAYS = 7
