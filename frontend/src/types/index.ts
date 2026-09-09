export interface Region {
  id: number;
  name: string;
  country: string;
  timezone: string;
  latitude: number;
  longitude: number;
  created_at: string;
}

export interface LoadObservation {
  id: number;
  region_id: number;
  timestamp: string;
  load_mw: number;
  source: string;
}

export interface WeatherObservation {
  id: number;
  region_id: number;
  timestamp: string;
  temperature_c: number;
  humidity_percent: number;
  precipitation: number;
  weather_code: number;
}

export interface ModelVersion {
  id: number;
  model_name: string;
  version: string;
  model_type: string;
  training_start: string;
  training_end: string;
  metrics_json: {
    mean_metrics?: Record<string, number>;
    std_metrics?: Record<string, number>;
    residual_std?: number;
    training_rows?: number;
    walk_forward?: {
      folds: Array<{
        fold: number;
        train_start: string;
        train_end: string;
        val_start: string;
        val_end: string;
        metrics: Record<string, number>;
      }>;
    };
  };
  artifact_path: string | null;
  feature_columns: string[];
  created_at: string;
}

export interface Forecast {
  id: number;
  region_id: number;
  model_version_id: number;
  generated_at: string;
  target_timestamp: string;
  horizon_hours: number;
  predicted_load_mw: number;
  lower_bound: number | null;
  upper_bound: number | null;
}

export interface ForecastWithModel extends Forecast {
  model_type: string;
  model_version: string;
}

export interface ModelPerformance {
  model_type: string;
  forecast_count: number;
  mae: number;
  rmse: number;
  mape: number;
  smape: number;
}

export interface ModelComparison {
  models: ModelPerformance[];
  best_model: string | null;
}

export interface PerformancePoint {
  period: string;
  model_type: string;
  forecast_count: number;
  mae: number;
  rmse: number;
  mape: number;
  smape: number;
}

export type DriftHealth = "healthy" | "degraded" | "insufficient_data";

export interface DriftStatus {
  status: DriftHealth;
  recent_mape: number | null;
  baseline_mape: number | null;
  change_percent: number | null;
  recent_count: number;
  baseline_count: number;
  threshold_pct: number;
}

export type UserRole = "admin" | "analyst";

export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  username: string;
  action: string;
  status: "success" | "failure";
  detail: Record<string, unknown> | null;
  created_at: string;
}

export type DataMode = "live" | "demo";

export interface SystemStatus {
  backend_status: string;
  database_status: string;
  environment: string;
  data_mode: DataMode;
  electricity_provider: string;
  current_admin: string;
  last_ingestion_at: string | null;
  last_forecast_generated_at: string | null;
  last_evaluation_scored_at: string | null;
}

export const MODEL_LABELS: Record<string, string> = {
  seasonal_naive: "Seasonal Naive",
  linear_regression: "Linear Regression",
  lightgbm: "LightGBM",
};

export const MODEL_COLORS: Record<string, string> = {
  seasonal_naive: "#94a3b8",
  linear_regression: "#60a5fa",
  lightgbm: "#2dd4bf",
};
