/**
 * Constants for the dashboard's weather readouts.
 *
 * The dashboard shows plain weather (temperature, rainfall, humidity) for the
 * coming days. It computes no agronomic indices: the forecasting model reads
 * the raw daily weather and the growth stage itself and learns what matters,
 * so there is no formula here to keep in step with the model.
 */

/** How many forecast days the rainfall and humidity readouts cover. */
export const OUTLOOK_DAYS = 7
