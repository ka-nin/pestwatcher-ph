export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface LguUser {
  username: string
  roleLevel: string
  province: string
  municipality: string
  latitude: number
  longitude: number
}

interface LoginSuccess {
  user: LguUser
}

interface LoginFailure {
  message: string
}

export async function login(username: string, password: string): Promise<LguUser> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data: LoginSuccess | LoginFailure = await res.json()

  if (!res.ok) {
    throw new Error((data as LoginFailure).message ?? 'Login failed')
  }

  return (data as LoginSuccess).user
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

export async function updateReportStatus(
  id: string,
  status: Extract<ReportStatus, 'verified' | 'rejected'>,
  verifiedBy: string,
): Promise<ReportRecord> {
  const res = await fetch(`${API_BASE_URL}/api/reports/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, verified_by: verifiedBy }),
  })

  if (!res.ok) {
    throw new Error('Failed to update report')
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
