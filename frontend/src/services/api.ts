import type {
  DriftStatus,
  Forecast,
  ForecastWithModel,
  LoadObservation,
  ModelComparison,
  ModelPerformance,
  ModelVersion,
  PerformancePoint,
  Region,
  WeatherObservation,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // ignore body parse failure
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const str = search.toString();
  return str ? `?${str}` : "";
}

export const api = {
  health: () => request<{ status: string; database: string }>("/health"),

  regions: {
    list: () => request<Region[]>("/regions"),
    create: (payload: Omit<Region, "id" | "created_at">) =>
      request<Region>("/regions", { method: "POST", body: JSON.stringify(payload) }),
  },

  data: {
    load: (region: string, start?: string, end?: string, limit?: number) =>
      request<LoadObservation[]>(`/data/load${qs({ region, start, end, limit })}`),
    weather: (region: string, start?: string, end?: string, limit?: number) =>
      request<WeatherObservation[]>(`/data/weather${qs({ region, start, end, limit })}`),
    ingest: (region: string, days = 180) =>
      request<{
        region: string;
        region_id: number;
        weather_source: string;
        weather_inserted: number;
        weather_skipped: number;
        load_source: string;
        load_inserted: number;
        load_skipped: number;
      }>("/data/ingest", { method: "POST", body: JSON.stringify({ region, days }) }),
  },

  models: {
    list: () => request<ModelVersion[]>("/models"),
    get: (id: number) => request<ModelVersion>(`/models/${id}`),
    train: (region: string, model_type: string) =>
      request<ModelVersion>("/models/train", { method: "POST", body: JSON.stringify({ region, model_type }) }),
  },

  forecasts: {
    generate: (region: string, model_version: string, horizon_hours: number) =>
      request<Forecast[]>("/forecasts/generate", {
        method: "POST",
        body: JSON.stringify({ region, model_version, horizon_hours }),
      }),
    latest: (region: string, model_version = "latest") =>
      request<ForecastWithModel[]>(`/forecasts/latest${qs({ region, model_version })}`),
    history: (region: string, opts?: { model_version?: string; start?: string; end?: string; limit?: number }) =>
      request<ForecastWithModel[]>(`/forecasts/history${qs({ region, ...opts })}`),
  },

  evaluation: {
    score: (region?: string) =>
      request<{ scored: number }>("/evaluation/score", { method: "POST", body: JSON.stringify({ region }) }),
    summary: (region?: string) => request<ModelPerformance[]>(`/evaluation/summary${qs({ region })}`),
    timeseries: (region?: string, granularity: "day" | "week" = "day") =>
      request<PerformancePoint[]>(`/evaluation/timeseries${qs({ region, granularity })}`),
    modelComparison: (region?: string) => request<ModelComparison>(`/evaluation/model-comparison${qs({ region })}`),
    drift: (region?: string, model_type?: string) =>
      request<DriftStatus>(`/evaluation/drift${qs({ region, model_type })}`),
  },
};
