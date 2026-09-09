import { useMemo, useState } from "react";
import { Calendar, Layers, Sigma, TrendingUp } from "lucide-react";
import Topbar from "../components/Topbar";
import ForecastChart, { type ForecastChartPoint } from "../components/ForecastChart";
import ChartContainer from "../components/ChartContainer";
import LoadingState from "../components/LoadingState";
import DateRangeSelector from "../components/DateRangeSelector";
import ModelSelector from "../components/ModelSelector";
import SegmentedControl from "../components/SegmentedControl";
import MetricCard from "../components/MetricCard";
import { useAsync } from "../hooks/useAsync";
import { useRegion } from "../hooks/useRegion";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { api } from "../services/api";
import { MODEL_LABELS } from "../types";

export default function ForecastExplorer() {
  const { region } = useRegion();
  const [rangeDays, setRangeDays] = useState(7);
  const [horizon, setHorizon] = useState<24 | 48>(24);
  const [modelType, setModelType] = useState<string>("lightgbm");

  const modelsQuery = useAsync(async () => api.models.list(), []);
  const models = modelsQuery.data ?? [];
  const modelTypes = useMemo(() => Array.from(new Set(models.map((m) => m.model_type))), [models]);
  const activeModelType = modelTypes.includes(modelType) ? modelType : modelTypes[0];
  const latestVersionForType = models.find((m) => m.model_type === activeModelType);

  const dataQuery = useAsync(async () => {
    if (!region || !latestVersionForType) return { actual: [], forecast: [] };

    const now = new Date();
    const start = new Date(now.getTime() - rangeDays * 24 * 3600 * 1000);
    const end = new Date(now.getTime() + horizon * 3600 * 1000);

    const [actual, history] = await Promise.all([
      api.data.load(region.name, start.toISOString(), now.toISOString(), 5000),
      api.forecasts.history(region.name, {
        model_version: latestVersionForType.version,
        start: start.toISOString(),
        end: end.toISOString(),
        limit: 10000,
      }),
    ]);

    // Multiple forecasts can target the same timestamp (re-issued as time
    // advances). Keep the one with the smallest horizon - i.e. the most
    // recently issued, most information-rich prediction - for a clean line.
    const bestByTarget = new Map<string, (typeof history)[number]>();
    for (const f of history) {
      if (f.horizon_hours !== horizon) continue;
      const existing = bestByTarget.get(f.target_timestamp);
      if (!existing || f.generated_at > existing.generated_at) bestByTarget.set(f.target_timestamp, f);
    }

    return { actual, forecast: Array.from(bestByTarget.values()) };
  }, [region?.id, latestVersionForType?.id, rangeDays, horizon]);

  const { refresh, refreshing } = usePageRefresh([modelsQuery.refetch, dataQuery.refetch]);

  if (!region) return <LoadingState label="Loading region…" />;

  const forecastRows = dataQuery.data?.forecast ?? [];
  const chartMap = new Map<string, ForecastChartPoint>();
  for (const obs of dataQuery.data?.actual ?? []) {
    chartMap.set(obs.timestamp, { timestamp: obs.timestamp, actual: obs.load_mw });
  }
  for (const f of forecastRows) {
    const existing = chartMap.get(f.target_timestamp) ?? { timestamp: f.target_timestamp };
    chartMap.set(f.target_timestamp, { ...existing, predicted: f.predicted_load_mw, lower: f.lower_bound, upper: f.upper_bound });
  }
  const chartData = Array.from(chartMap.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  const avgPredicted = forecastRows.length
    ? forecastRows.reduce((sum, f) => sum + f.predicted_load_mw, 0) / forecastRows.length
    : null;
  const peakPredicted = forecastRows.length ? Math.max(...forecastRows.map((f) => f.predicted_load_mw)) : null;
  const avgIntervalWidth =
    forecastRows.length && forecastRows.every((f) => f.lower_bound != null && f.upper_bound != null)
      ? forecastRows.reduce((sum, f) => sum + ((f.upper_bound ?? 0) - (f.lower_bound ?? 0)), 0) / forecastRows.length
      : null;
  const mostRecentGeneratedAt = forecastRows.length
    ? forecastRows.reduce((latest, f) => (f.generated_at > latest ? f.generated_at : latest), forecastRows[0].generated_at)
    : null;

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Forecast Explorer"
        subtitle="Actual load vs. model predictions with uncertainty bands"
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={dataQuery.updatedAt}
      />

      <div className="p-4 md:p-6 space-y-6">
        <div className="panel p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="stat-label hidden sm:inline">Model</span>
            <ModelSelector value={activeModelType} onChange={setModelType} options={modelTypes} disabled={modelsQuery.loading} />
          </div>

          <div className="flex items-center gap-2">
            <span className="stat-label hidden sm:inline">Horizon</span>
            <SegmentedControl
              aria-label="Forecast horizon"
              value={horizon}
              onChange={setHorizon}
              options={[
                { label: "24H", value: 24 },
                { label: "48H", value: 48 },
              ]}
            />
          </div>

          <div className="flex items-center gap-2 sm:ml-auto">
            <span className="stat-label hidden sm:inline">Range</span>
            <DateRangeSelector value={rangeDays} onChange={setRangeDays} />
          </div>
        </div>

        {latestVersionForType && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Avg Predicted Load" value={avgPredicted ? Math.round(avgPredicted).toLocaleString() : "—"} unit="MW" icon={TrendingUp} accent="teal" />
            <MetricCard label="Peak Predicted Load" value={peakPredicted ? Math.round(peakPredicted).toLocaleString() : "—"} unit="MW" icon={Sigma} accent="slate" />
            <MetricCard label="Avg Interval Width" value={avgIntervalWidth ? `±${Math.round(avgIntervalWidth / 2).toLocaleString()}` : "—"} unit="MW" icon={Layers} accent="amber" />
            <MetricCard
              label="Generated"
              value={mostRecentGeneratedAt ? new Date(mostRecentGeneratedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—"}
              unit={mostRecentGeneratedAt ? new Date(mostRecentGeneratedAt).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : undefined}
              icon={Calendar}
              accent="slate"
            />
          </div>
        )}

        <ChartContainer
          title={activeModelType ? MODEL_LABELS[activeModelType] ?? activeModelType : "Forecast"}
          subtitle={
            latestVersionForType
              ? `Version ${latestVersionForType.version} · ${latestVersionForType.feature_columns.length} features · shaded band = 95% prediction interval`
              : "Shaded band = 95% prediction interval"
          }
          loading={dataQuery.loading || modelsQuery.loading}
          error={dataQuery.error}
          onRetry={refresh}
          isEmpty={!latestVersionForType ? true : chartData.length === 0}
          emptyTitle={!latestVersionForType ? "No trained models" : "No data in range"}
          emptyDescription={
            !latestVersionForType
              ? "Train a model first from the API (`POST /models/train`) or run `make train`."
              : "Try a wider date range or generate more demo data."
          }
          height={440}
        >
          <ForecastChart data={chartData} height={440} />
        </ChartContainer>
      </div>
    </div>
  );
}
