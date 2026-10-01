// Static content for the Model Insights page: the step-by-step explanations of
// the two pipelines. Everything numeric (metrics, predictions, SHAP) comes from
// the backend - see fetchModelInsights in lib/api.ts.

export type PestCode = 'BPH' | 'RSB'

export interface FlowStep {
  id: string
  title: string
  short: string
  body: string
  code: string
  outputs: string[]
}

export const PHOTO_FLOW: FlowStep[] = [
  {
    id: 'photo',
    title: 'Farmer photo',
    short: 'Photo in',
    body: 'The farmer takes or uploads a photo in the mobile app. It reaches the backend as a JPEG, PNG or WebP through POST /api/inference/image.',
    code: 'app/routers/inference.py',
    outputs: ['image file', 'municipality', 'growth stage'],
  },
  {
    id: 'route',
    title: 'Whole photo or grid?',
    short: 'Whole or grid?',
    body: 'Photos up to about 480 px go to the model whole. Bigger photos are shrunk to 832 px and cut into tiles. Only BPH uses the grid; RSB always sees the whole photo because its photos are close-ups of one large insect.',
    code: 'app/preprocessing/tiling.py',
    outputs: ['≤ 480 px → whole', '> 480 px → grid (BPH)'],
  },
  {
    id: 'tiles',
    title: 'Cut into tiles',
    short: 'Tiles',
    body: 'The photo is cut into overlapping 64 px squares, moved 32 px at a time, so any insect sits fully inside at least one tile. An 832 px photo becomes about 625 tiles.',
    code: 'app/preprocessing/tiling.py · make_tiles()',
    outputs: ['64 px tiles', '32 px stride'],
  },
  {
    id: 'resnet',
    title: 'ResNet-50 scores',
    short: 'ResNet-50',
    body: 'Two independent ResNet-50 models, one per pest, each answer one question: is this pest here, yes or no? Every tile (or the whole photo) is resized to 224×224 and scored between 0 and 1.',
    code: 'app/models/resnet_model.py',
    outputs: ['BPH score 0–1', 'RSB score 0–1'],
  },
  {
    id: 'group',
    title: 'Filter and group hits',
    short: 'Group hits',
    body: 'A tile is a hit at a score of 0.99 or more. Neighbouring hits merge into one group, and groups smaller than 4 tiles are dropped as noise. The number of groups is the grid count: an approximate density hint, not an exact insect count.',
    code: 'app/preprocessing/tiling.py · group_hits()',
    outputs: ['hit groups', 'grid count'],
  },
  {
    id: 'result',
    title: 'Pests detected',
    short: 'Result',
    body: 'Both pests can be reported for the same photo. The strongest one becomes the label that starts the forecast; the grid count is shown to the farmer as an estimate.',
    code: 'app/routers/inference.py',
    outputs: ['pests_detected', 'pest_scores', 'bph_grid_count'],
  },
]

export const WEATHER_FLOW: FlowStep[] = [
  {
    id: 'weather',
    title: '14 days of weather',
    short: 'Weather',
    body: 'For the farmer’s municipality the backend fetches the last 14 days from Open-Meteo: maximum and minimum temperature, humidity and rainfall. The growth stage comes from the farmer’s profile.',
    code: 'app/routers/weather.py',
    outputs: ['tmax / tmin', 'humidity', 'rainfall', 'growth stage'],
  },
  {
    id: 'features',
    title: 'Biologically-informed features',
    short: 'Features',
    body: 'Instead of feeding raw numbers to the network, the framework first computes growing degree days (GDD), cumulative rainfall (CRF), humidity persistence (HP), vapor pressure deficit (VPD), a water stress index (WSI) and trends. This is the thesis’s answer to learning from limited data.',
    code: 'app/preprocessing/features.py',
    outputs: ['12 daily features × 14 days', '9 window summaries'],
  },
  {
    id: 'bilstm',
    title: 'BiLSTM forecast',
    short: 'BiLSTM',
    body: 'The BiLSTM reads the 14-day sequence forwards and backwards, combines it with the summary features, and predicts one continuous value 14 days ahead. A separate model exists per pest.',
    code: 'app/models/bilstm_model.py',
    outputs: ['hoppers / hill (BPH)', '% damage (RSB)'],
  },
  {
    id: 'value',
    title: 'Daily forecast values',
    short: 'Daily values',
    body: 'Each date in the 14-day chart is predicted from its own preceding 14 days of weather, so the curve rises and falls with the weather. This is the regression output that RMSE, MAE and R² evaluate.',
    code: 'app/routers/inference.py · _build_trajectory()',
    outputs: ['14 daily values'],
  },
  {
    id: 'anchor',
    title: 'Verified-report anchor',
    short: 'Report anchor',
    body: 'If an LGU technician verified a report in the last 13 days, the forecast is shifted by the gap between the reported value and what the model predicted for that day. The shift fades in a straight line to zero over 13 days. With no report, nothing changes.',
    code: 'app/decision/report_anchor.py',
    outputs: ['shift × fade weight', 'newest report wins'],
  },
  {
    id: 'etl',
    title: 'ETL risk level',
    short: 'Risk level',
    body: 'Fixed PhilRice / DA-RCPC thresholds turn each number into Low, Medium or High. The model never learns its own definition of risk; the thresholds live outside it.',
    code: 'app/decision/etl_thresholds.py',
    outputs: ['Low', 'Medium', 'High'],
  },
  {
    id: 'dash',
    title: 'Farmer and LGU dashboards',
    short: 'Dashboards',
    body: 'The risk card, the 14-day trend chart, the scan result and the municipality overview all read this same pipeline, so every screen agrees.',
    code: 'user-mobile · admin-web',
    outputs: ['risk card', '14-day chart', 'overview'],
  },
]
