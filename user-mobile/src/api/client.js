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

export async function fetchMunicipalities() {
  const res = await fetch(`${API_BASE_URL}/api/locations/municipalities`);
  return parseJsonOrThrow(res, 'Failed to fetch municipality list');
}

export async function fetchMunicipalitiesRisk() {
  const res = await fetch(`${API_BASE_URL}/api/locations/municipalities/risk`);
  return parseJsonOrThrow(res, 'Failed to fetch municipality risk overview');
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

// municipality/growthStage are optional: without them the backend still
// classifies the photo, it just skips the 14-day BiLSTM forecast that
// normally rides along in the same response (see
// app/routers/inference.py's /image endpoint).
export async function submitImageInference(imageBlob, municipality, growthStage) {
  const formData = new FormData();
  formData.append('file', imageBlob, 'scan.jpg');
  if (municipality) formData.append('municipality', municipality);
  if (growthStage) formData.append('growth_stage', growthStage);
  const res = await fetch(`${API_BASE_URL}/api/inference/image`, {
    method: 'POST',
    body: formData,
  });
  return parseJsonOrThrow(res, 'Failed to submit image for inference');
}

export async function fetchReports(province) {
  const params = province ? `?${new URLSearchParams({ province })}` : '';
  const res = await fetch(`${API_BASE_URL}/api/reports${params}`);
  return parseJsonOrThrow(res, 'Failed to fetch reports');
}

// multipart/form-data, not JSON — a report can optionally carry a photo
// (`photoFile`, a File/Blob from a camera/gallery input), so the whole
// submission goes through the same shape /api/inference/image already
// uses for images. `fields` values are coerced to strings by FormData;
// the backend parses them back with the right types (see
// app/routers/reports.py:submit_report).
export async function submitReport(fields, photoFile) {
  const formData = new FormData();
  Object.entries(fields).forEach(([key, value]) => {
    if (value != null && value !== '') formData.append(key, value);
  });
  if (photoFile) formData.append('file', photoFile, photoFile.name || 'sighting.jpg');

  const res = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    body: formData,
  });
  return parseJsonOrThrow(res, 'Failed to submit report');
}
