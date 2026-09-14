// Talks to the FastAPI backend (server-python). Mirrors the pattern already
// working in admin-web/src/lib/api.ts so both apps stay consistent.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function parseJsonOrThrow(res, fallbackMessage) {
  let data;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    throw new Error(data?.message ?? fallbackMessage);
  }
  return data;
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await parseJsonOrThrow(res, 'Login failed');
  return data.user;
}

export async function fetchWeatherForecast(latitude, longitude) {
  const params = new URLSearchParams({ latitude, longitude });
  const res = await fetch(`${API_BASE_URL}/api/weather/forecast?${params}`);
  return parseJsonOrThrow(res, 'Failed to fetch weather data');
}

export async function fetchPestForecast(municipality, pest, growthStage) {
  const params = new URLSearchParams({ municipality, pest, growth_stage: growthStage });
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/live?${params}`);
  return parseJsonOrThrow(res, 'Failed to fetch pest forecast');
}

export async function fetchPestForecastTrajectory(municipality, pest, growthStage, days = 13) {
  const params = new URLSearchParams({
    municipality,
    pest,
    growth_stage: growthStage,
    days: String(days),
  });
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/trajectory?${params}`);
  return parseJsonOrThrow(res, 'Failed to fetch pest forecast trajectory');
}

export async function fetchPestForecastExplanation(municipality, pest, growthStage, topN = 7) {
  const params = new URLSearchParams({
    municipality,
    pest,
    growth_stage: growthStage,
    top_n: String(topN),
  });
  const res = await fetch(`${API_BASE_URL}/api/inference/forecast/explain?${params}`);
  return parseJsonOrThrow(res, 'Failed to fetch pest forecast explanation');
}

export async function submitImageInference(imageBlob) {
  const formData = new FormData();
  formData.append('file', imageBlob, 'scan.jpg');
  const res = await fetch(`${API_BASE_URL}/api/inference/image`, {
    method: 'POST',
    body: formData,
  });
  return parseJsonOrThrow(res, 'Failed to submit image for inference');
}

export async function submitReport(report) {
  const res = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  });
  return parseJsonOrThrow(res, 'Failed to submit report');
}
