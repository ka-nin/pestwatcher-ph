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
  id: string,
  status: Extract<ReportStatus, 'verified' | 'rejected'>,
  verifiedBy: string,
  verifiedValue?: number | null,
): Promise<ReportRecord> {
  const res = await fetch(`${API_BASE_URL}/api/reports/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status,
      verified_by: verifiedBy,
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
