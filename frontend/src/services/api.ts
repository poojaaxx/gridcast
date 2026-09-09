import type {
  AuditLogEntry,
  DriftStatus,
  Forecast,
  ForecastWithModel,
  LoadObservation,
  ModelComparison,
  ModelPerformance,
  ModelVersion,
  PerformancePoint,
  Region,
  SystemStatus,
  User,
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

/** Dispatched whenever any request comes back 401, so AuthProvider can clear
 * stale client-side auth state without every caller needing to check for it
 * individually (e.g. a session that expired mid-page). */
const UNAUTHORIZED_EVENT = "gridcast:unauthorized";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    // Required for the httpOnly session cookie to be sent/received - the
    // frontend and backend run on different ports (different origins), so
    // this is not optional even though both are "localhost".
    credentials: "include",
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
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
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
  health: () =>
    request<{ status: string; database: string; data_mode: "live" | "demo"; electricity_provider: string; region: string }>(
      "/health"
    ),

  auth: {
    login: (username: string, password: string) =>
      request<User>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
    me: () => request<User>("/auth/me"),
  },

  admin: {
    status: () => request<SystemStatus>("/admin/status"),
    auditLog: (limit = 50) => request<AuditLogEntry[]>(`/admin/audit-log${qs({ limit })}`),
  },

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

export function onUnauthorized(handler: () => void): () => void {
  window.addEventListener(UNAUTHORIZED_EVENT, handler);
  return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
}
