export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface LguUser {
  accountType: 'lgu'
  username: string
  roleLevel: string
  province: string
  municipality: string
  latitude: number
  longitude: number
}

export interface SuperAdminUser {
  accountType: 'superadmin'
  username: string
  fullName: string
}

export type AuthUser = LguUser | SuperAdminUser

export interface Session {
  user: AuthUser
  accessToken: string
}

interface LoginSuccess {
  user: AuthUser
  accessToken: string
}

interface LoginFailure {
  message: string
}

export async function login(username: string, password: string): Promise<Session> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data: LoginSuccess | LoginFailure = await res.json()

  if (!res.ok) {
    throw new Error((data as LoginFailure).message ?? 'Login failed')
  }

  const success = data as LoginSuccess
  if (success.user.accountType !== 'lgu' && success.user.accountType !== 'superadmin') {
    throw new Error('This account type cannot access the admin dashboard')
  }

  return { user: success.user, accessToken: success.accessToken }
}

async function authFetch(token: string, path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${token}`,
    },
  })

  if (res.status === 401 || res.status === 403) {
    throw new Error(res.status === 401 ? 'Session expired — please log in again' : 'Not authorized')
  }

  return res
}

export interface WeatherForecast {
  location: {
    latitude: number
    longitude: number
    elevation: number
    timezone: string
    timezoneAbbreviation: string
  }
  current: {
    time: string
    temperature_2m: number
    relative_humidity_2m: number
    precipitation: number
    rain: number
  }
  hourly: {
    time: string[]
    relative_humidity_2m: number[]
  }
  daily: {
    time: string[]
    temperature_2m_max: number[]
    temperature_2m_min: number[]
    precipitation_sum: number[]
  }
}

export async function fetchWeatherForecast(
  latitude: number,
  longitude: number,
): Promise<WeatherForecast> {
  const res = await fetch(
    `${API_BASE_URL}/api/weather/forecast?latitude=${latitude}&longitude=${longitude}`,
  )

  if (!res.ok) {
    throw new Error('Failed to fetch weather data')
  }

  return res.json()
}

export type PestKey = 'BPH' | 'RSB'
export type GrowthStage =
  | 'Seedling'
  | 'Tillering'
  | 'Elongation'
  | 'Panicle'
  | 'Flowering'
  | 'Ripening'
export type RiskLevel = 'Low' | 'Medium' | 'High'

export interface PestForecast {
  status: 'ok' | 'model_not_loaded'
  predicted_value: number | null
  unit: 'hoppers_per_hill' | 'pct_damage' | null
  risk_level: RiskLevel | null
  message: string
}

export async function fetchPestForecast(
  municipality: string,
  pest: PestKey,
  growthStage: GrowthStage,
): Promise<PestForecast> {
  const params = new URLSearchParams({ municipality, pest, growth_stage: growthStage })
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/live?${params}`)

  if (!res.ok) {
    throw new Error('Failed to fetch pest forecast')
  }

  return res.json()
}

export interface TrajectoryPoint {
  date: string
  predicted_value: number
  unit: 'hoppers_per_hill' | 'pct_damage'
  risk_level: RiskLevel
}

export interface TrajectoryResponse {
  status: 'ok' | 'model_not_loaded'
  points: TrajectoryPoint[]
  message: string
}

export async function fetchPestForecastTrajectory(
  municipality: string,
  pest: PestKey,
  growthStage: GrowthStage,
  days = 13,
): Promise<TrajectoryResponse> {
  const params = new URLSearchParams({
    municipality,
    pest,
    growth_stage: growthStage,
    days: String(days),
  })
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/trajectory?${params}`)

  if (!res.ok) {
    throw new Error('Failed to fetch pest forecast trajectory')
  }

  return res.json()
}

// ---- Gap Analysis: per-report "Analyze Gap" button on the Farmer Reports
// tab. For one verified report, shows the 14-day forecast starting on the
// report's own date two ways — plain weather-only (historical) and what the
// forecast would look like if this report were allowed to anchor it
// (report-based) — plus a plain-language implication. Read-only: neither
// trajectory here is what a farmer/technician sees as a live prediction —
// see server-python/app/routers/inference.py's _run_forecast docstring.

export interface GapAnalysisDay {
  date: string
  historical_value: number | null
  historical_risk_level: RiskLevel | null
  report_based_value: number | null
  report_based_risk_level: RiskLevel | null
  report_weight: number
}

export interface GapAnalysisResponse {
  status: 'ok' | 'model_not_loaded' | 'report_not_verified'
  report_id: string
  municipality: string
  pest: PestKey
  unit: 'hoppers_per_hill' | 'pct_damage' | null
  days: GapAnalysisDay[]
  implication: string
  message: string
}

export async function fetchReportGapAnalysis(reportId: string): Promise<GapAnalysisResponse> {
  const res = await fetch(`${API_BASE_URL}/api/reports/${encodeURIComponent(reportId)}/gap-analysis`)

  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.message ?? 'Failed to fetch gap analysis')
  }

  return res.json()
}

export interface ExplanationFeature {
  label: string
  value: number
}

export interface ExplanationResponse {
  status: 'ok' | 'model_not_loaded'
  features: ExplanationFeature[]
  message: string
}

export type ReportStatus = 'pending' | 'verified' | 'rejected'

export interface ReportRecord {
  id: string
  username: string
  pest_type: string
  pest_code: string | null
  severity: string
  province: string
  municipality: string
  crop_growth_stage: string
  area_affected: number | null
  date_spotted: string
  notes: string
  latitude: number | null
  longitude: number | null
  submitted_at: string
  status: ReportStatus
  verified_by: string | null
  verified_at: string | null
  photo_path: string | null
  photo_url: string | null
  ai_pest_detected: string | null
  ai_confidence: number | null
  estimated_value: number | null
  verified_value: number | null
  deleted_at: string | null
  deleted_by: string | null
}

// Scoped by municipality, not province — an LGU technician's account is
// tied to one municipality (see server-python/app/data/lgu_users.py) and
// should only ever see that municipality's own sightings, not the whole
// province's (that broader view is what the mobile app's "regional
// alerts" feed uses `province` for instead).
export async function fetchReports(municipality?: string): Promise<ReportRecord[]> {
  const params = municipality ? `?${new URLSearchParams({ municipality })}` : ''
  const res = await fetch(`${API_BASE_URL}/api/reports${params}`)

  if (!res.ok) {
    throw new Error('Failed to fetch reports')
  }

  return res.json()
}

// Province-wide sightings, for the dashboard map only (read-only pins). The
// Reports tab stays municipality-scoped via fetchReports above.
export async function fetchProvinceReports(province: string): Promise<ReportRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/reports?${new URLSearchParams({ province })}`)

  if (!res.ok) {
    throw new Error('Failed to fetch reports')
  }

  return res.json()
}

export async function updateReportStatus(
  token: string,
  id: string,
  status: Extract<ReportStatus, 'verified' | 'rejected'>,
  verifiedValue?: number | null,
): Promise<ReportRecord> {
  const res = await authFetch(token, `/api/reports/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status,
      ...(verifiedValue != null ? { verified_value: verifiedValue } : {}),
    }),
  })

  if (!res.ok) {
    throw new Error('Failed to update report')
  }

  return res.json()
}

// Soft delete: the report is kept as an audit trail and comes back with
// deleted_at / deleted_by set (see server-python/app/routers/reports.py).
export async function deleteReport(token: string, id: string): Promise<ReportRecord> {
  const res = await authFetch(token, `/api/reports/${encodeURIComponent(id)}`, { method: 'DELETE' })

  if (!res.ok) {
    throw new Error('Failed to delete report')
  }

  return res.json()
}

export async function fetchDeletedReports(token: string): Promise<ReportRecord[]> {
  const res = await authFetch(token, '/api/reports/deleted')

  if (!res.ok) {
    throw new Error('Failed to fetch deleted reports')
  }

  return res.json()
}

export async function fetchPestForecastExplanation(
  municipality: string,
  pest: PestKey,
  growthStage: GrowthStage,
  topN = 7,
): Promise<ExplanationResponse> {
  const params = new URLSearchParams({
    municipality,
    pest,
    growth_stage: growthStage,
    top_n: String(topN),
  })
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/explain?${params}`)

  if (!res.ok) {
    throw new Error('Failed to fetch pest forecast explanation')
  }

  return res.json()
}

// --- SuperAdmin: LGU account management + cross-municipality overview ---

export interface LguAccountAdmin {
  username: string
  roleLevel: string
  province: string
  municipality: string
  latitude: number
  longitude: number
  isActive: boolean
}

export interface CreateLguUserPayload {
  username: string
  password: string
  roleLevel?: string
  province: string
  municipality: string
  latitude: number
  longitude: number
}

export interface UpdateLguUserPayload {
  password?: string
  roleLevel?: string
  province?: string
  municipality?: string
  latitude?: number
  longitude?: number
  isActive?: boolean
}

export async function fetchLguUsers(token: string): Promise<LguAccountAdmin[]> {
  const res = await authFetch(token, '/api/admin/lgu-users')
  if (!res.ok) throw new Error('Failed to fetch LGU accounts')
  return res.json()
}

export async function createLguUser(token: string, payload: CreateLguUserPayload): Promise<LguAccountAdmin> {
  const res = await authFetch(token, '/api/admin/lgu-users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.message ?? 'Failed to create LGU account')
  }
  return res.json()
}

export async function updateLguUser(
  token: string,
  username: string,
  payload: UpdateLguUserPayload,
): Promise<LguAccountAdmin> {
  const res = await authFetch(token, `/api/admin/lgu-users/${encodeURIComponent(username)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.message ?? 'Failed to update LGU account')
  }
  return res.json()
}

export async function deleteLguUser(token: string, username: string): Promise<void> {
  const res = await authFetch(token, `/api/admin/lgu-users/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Failed to delete LGU account')
}

export interface MunicipalityOverview {
  province: string
  municipality: string
  bph: PestForecast
  rsb: PestForecast
}

export interface OverviewResponse {
  growthStageUsed: string
  municipalities: MunicipalityOverview[]
}

export async function fetchAdminOverview(token: string): Promise<OverviewResponse> {
  const res = await authFetch(token, '/api/admin/overview')
  if (!res.ok) throw new Error('Failed to fetch municipality overview')
  return res.json()
}

export interface MunicipalityGapAnalysis {
  province: string
  municipality: string
  bph: GapAnalysisResponse
  rsb: GapAnalysisResponse
}

export interface GapAnalysisOverviewResponse {
  growthStageUsed: string
  municipalities: MunicipalityGapAnalysis[]
}

export async function fetchAdminGapAnalysis(token: string): Promise<GapAnalysisOverviewResponse> {
  const res = await authFetch(token, '/api/admin/gap-analysis')
  if (!res.ok) throw new Error('Failed to fetch municipality gap analysis')
  return res.json()
}

// Public equivalent of fetchAdminOverview — every municipality on file
// (not just ones with an LGU account) and no auth, so any logged-in LGU
// technician's Status page can show province-wide risk context alongside
// their own municipality's detail, without needing SuperAdmin scope.
export async function fetchMunicipalitiesRisk(): Promise<OverviewResponse> {
  const res = await fetch(`${API_BASE_URL}/api/locations/municipalities/risk`)
  if (!res.ok) throw new Error('Failed to fetch municipality risk overview')
  return res.json()
}

export interface EtlThresholdsResponse {
  thresholds: Record<string, Record<string, { lowMax: number; highMin: number }>>
}

export async function fetchEtlThresholds(token: string): Promise<EtlThresholdsResponse> {
  const res = await authFetch(token, '/api/admin/etl-thresholds')
  if (!res.ok) throw new Error('Failed to fetch ETL thresholds')
  return res.json()
}

// ---- Model Insights (SuperAdmin) — see server-python/app/data/model_insights.py

export interface ModelStatusItem {
  name: string
  detail: string
  loaded: boolean
  updated: string | null
}

export interface ResnetTestMetrics {
  accuracy: number
  positive_precision: number
  positive_recall: number
  positive_f1: number
  confusion_matrix: [[number, number], [number, number]]
}

export interface RegressionTestMetrics {
  rmse: number
  mae: number
  r2: number
}

export interface PredictionPointDto {
  date: string
  municipality: string
  actual: number
  predicted: number
}

export interface ShapFeatureDto {
  label: string
  value: number
  share: number
  group: 'sequence' | 'static'
}

export interface FeatureComparisonMetricResult {
  test: string
  shapiro_p?: number
  paired_differences_normal?: boolean
  statistic?: number
  p_value: number
  significant: boolean
  mean_engineered: number
  mean_raw: number
  mean_difference: number
  better_configuration: 'engineered' | 'raw'
  reason?: string
}

export interface FeatureComparisonResponse {
  pest: PestKey
  n_folds: number
  alpha: number
  cross_validation: string
  epochs: number
  mean_scores: {
    engineered: Record<string, number>
    raw: Record<string, number>
  }
  significance: Record<string, FeatureComparisonMetricResult>
}

export interface BilstmInsights {
  metrics: RegressionTestMetrics | null
  predictions: { n: number; points: PredictionPointDto[] } | null
  shap: { sample_size: number; features: ShapFeatureDto[] } | null
  featureComparison: FeatureComparisonResponse | null
}

export interface GridEvalRowDto {
  recall: number | null
  false_alarm: number | null
  count_mae_on_bph: number | null
  mean_groups_on_bph_free: number | null
  correlation: number | null
}

export interface GridEvalBlock {
  n_bph: number
  n_bph_free: number
  grid: Record<string, GridEvalRowDto>
}

export interface ModelInsightsResponse {
  models: ModelStatusItem[]
  resnet: Record<'BPH' | 'RSB', ResnetTestMetrics | null>
  bilstm: Record<'BPH' | 'RSB', BilstmInsights>
  resnetBphComparison: {
    note: string
    rows: { label: string; kind: 'falseAlarm' | 'recall'; n: number; old: number; new: number }[]
    background_patches_added: number
  } | null
  grid: {
    current: { threshold: number; minTiles: number }
    evaluation: { single_416px: GridEvalBlock; mosaic_832px: GridEvalBlock } | null
  }
}

export async function fetchModelInsights(token: string): Promise<ModelInsightsResponse> {
  const res = await authFetch(token, '/api/admin/model-insights')

  if (!res.ok) {
    throw new Error('Failed to load model insights')
  }

  return res.json()
}

// ---- Simulation (SuperAdmin) — see server-python/app/schemas/simulation.py

export interface SimulationModelResult {
  status: 'ok' | 'model_not_loaded'
  predicted_value: number | null
  unit: 'hoppers_per_hill' | 'pct_damage' | null
  risk_level: RiskLevel | null
}

export interface SimulationForecastResponse {
  pest: PestKey
  engineered: SimulationModelResult
  raw: SimulationModelResult
  heldOutMetrics: FeatureComparisonResponse | null
}

export interface SimulationDailyObservation {
  date: string
  tmax: number
  tmin: number
  relative_humidity: number
  rainfall: number
  growth_stage: GrowthStage
}

export async function runSimulationForecast(
  token: string,
  pest: PestKey,
  dailyObservations: SimulationDailyObservation[],
): Promise<SimulationForecastResponse> {
  const res = await authFetch(token, '/api/admin/simulation/forecast', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pest, daily_observations: dailyObservations }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail?.[0]?.msg ?? data?.detail ?? 'Failed to run simulation forecast')
  }
  return res.json()
}

export interface SimulationImageResult {
  status: 'ok' | 'model_not_loaded' | 'no_pest_detected'
  pest_detected: PestKey | null
  confidence: number | null
  pests_detected: PestKey[]
  pest_scores: Record<string, number>
  heldOutMetrics: Record<string, ResnetTestMetrics | null> | null
}

export async function runSimulationImage(token: string, file: File): Promise<SimulationImageResult> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await authFetch(token, '/api/admin/simulation/image', { method: 'POST', body: formData })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail ?? 'Failed to run simulation image classification')
  }
  return res.json()
}

// --- SMS advisories (server-python/app/routers/sms.py) --------------------

export interface SmsRecipient {
  username: string
  full_name: string
  municipality: string
  phone: string
}

export interface SmsMessageRecord {
  id: string
  batch_id: string
  recipient_phone: string
  recipient_username: string | null
  recipient_name: string | null
  body: string
  municipality: string
  sent_by: string
  status: 'queued' | 'sent' | 'failed'
  provider: string
  provider_message_id: string | null
  error: string | null
  created_at: string
  sent_at: string | null
}

export interface SmsSendResult {
  batch_id: string
  provider: string
  sent: number
  failed: number
  skipped: string[]
  messages: SmsMessageRecord[]
}

export interface SmsGatewayStatus {
  provider: string
  configured: boolean
  reachable: boolean | null
  detail: string
}

export async function fetchSmsRecipients(token: string): Promise<SmsRecipient[]> {
  const res = await authFetch(token, '/api/sms/recipients')
  if (!res.ok) throw new Error('Failed to load SMS recipients')
  return res.json()
}

export async function fetchSmsGatewayStatus(token: string): Promise<SmsGatewayStatus> {
  const res = await authFetch(token, '/api/sms/gateway-status')
  if (!res.ok) throw new Error('Failed to check the SMS gateway')
  return res.json()
}

export async function fetchSmsOutbox(token: string): Promise<SmsMessageRecord[]> {
  const res = await authFetch(token, '/api/sms')
  if (!res.ok) throw new Error('Failed to load the SMS outbox')
  return res.json()
}

export async function sendSms(
  token: string,
  payload: { body: string; usernames?: string[]; phone_numbers?: string[]; to_all_farmers?: boolean },
): Promise<SmsSendResult> {
  const res = await authFetch(token, '/api/sms/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail ?? 'Failed to send the advisory')
  }
  return res.json()
}
