import { Award, Gauge, TrendingUp, Zap } from "lucide-react";
import Topbar from "../components/Topbar";
import MetricCard from "../components/MetricCard";
import ChartContainer from "../components/ChartContainer";
import ForecastChart, { type ForecastChartPoint } from "../components/ForecastChart";
import AccuracyChart from "../components/AccuracyChart";
import LoadingState from "../components/LoadingState";
import EmptyState from "../components/EmptyState";
import DriftStatusPanel from "../components/DriftStatus";
import { useAsync } from "../hooks/useAsync";
import { useRegion } from "../hooks/useRegion";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { api } from "../services/api";
import { useDemoBootstrap } from "../state/useDemoBootstrap";
import { MODEL_LABELS } from "../types";

export default function Overview() {
  const { region, loading: regionLoading, error: regionError } = useRegion();
  const bootstrap = useDemoBootstrap();

  const actualQuery = useAsync(async () => {
    if (!region) return [];
    const end = new Date();
    const start = new Date(end.getTime() - 5 * 24 * 3600 * 1000);
    return api.data.load(region.name, start.toISOString(), end.toISOString(), 2000);
  }, [region?.id]);

  const forecastQuery = useAsync(async () => {
    if (!region) return [];
    return api.forecasts.latest(region.name, "latest");
  }, [region?.id]);

  const summaryQuery = useAsync(async () => {
    if (!region) return [];
    return api.evaluation.summary(region.name);
  }, [region?.id]);

  const comparisonQuery = useAsync(async () => {
    if (!region) return { models: [], best_model: null };
    return api.evaluation.modelComparison(region.name);
  }, [region?.id]);

  const driftQuery = useAsync(async () => {
    if (!region) return null;
    return api.evaluation.drift(region.name);
  }, [region?.id]);

  const trendQuery = useAsync(async () => {
    if (!region) return [];
    return api.evaluation.timeseries(region.name, "day");
  }, [region?.id]);

  const { refresh, refreshing } = usePageRefresh([
    actualQuery.refetch,
    forecastQuery.refetch,
    summaryQuery.refetch,
    comparisonQuery.refetch,
    driftQuery.refetch,
    trendQuery.refetch,
  ]);

  const lastUpdated = [actualQuery.updatedAt, forecastQuery.updatedAt, driftQuery.updatedAt]
    .filter((t): t is number => t !== null)
    .reduce((max, t) => Math.max(max, t), 0) || null;

  if (regionLoading) return <LoadingState label="Loading region…" />;

  if (!region) {
    return (
      <div className="flex flex-col h-full">
        <Topbar title="Overview" subtitle="Grid demand at a glance" />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            title="No regions yet"
            description="GridCast has no data to show. Generate a demo region with ~200 days of synthetic load & weather history, train all three models, and produce initial forecasts — all in one click."
            icon={Zap}
            actionLabel="Generate Demo Data"
            actionPendingLabel={bootstrap.step ?? "Working…"}
            onAction={() => bootstrap.run()}
            actionPending={bootstrap.running}
            progress={bootstrap.progress}
          />
        </div>
      </div>
    );
  }
  if (regionError) return <div className="p-8"><EmptyState title="Failed to load regions" description={regionError} /></div>;

  const actual = actualQuery.data ?? [];
  const forecasts = forecastQuery.data ?? [];
  const summary = summaryQuery.data ?? [];
  const comparison = comparisonQuery.data;
  const drift = driftQuery.data;
  const trend = trendQuery.data ?? [];

  const hasAnyData = actual.length > 0 || forecasts.length > 0;

  const currentLoad = actual.length ? actual[actual.length - 1].load_mw : null;
  const nextHourForecast = forecasts.find((f) => f.horizon_hours === 1)?.predicted_load_mw ?? null;
  const bestModelSummary = comparison?.best_model ? summary.find((s) => s.model_type === comparison.best_model) : null;

  const chartMap = new Map<string, ForecastChartPoint>();
  for (const obs of actual) {
    chartMap.set(obs.timestamp, { timestamp: obs.timestamp, actual: obs.load_mw });
  }
  for (const f of forecasts) {
    const existing = chartMap.get(f.target_timestamp) ?? { timestamp: f.target_timestamp };
    chartMap.set(f.target_timestamp, {
      ...existing,
      predicted: f.predicted_load_mw,
      lower: f.lower_bound,
      upper: f.upper_bound,
    });
  }
  const chartData = Array.from(chartMap.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  const anyLoading = actualQuery.loading || forecastQuery.loading || summaryQuery.loading || comparisonQuery.loading || driftQuery.loading;

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Overview"
        subtitle={`${region.name} · ${region.timezone}`}
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={lastUpdated}
      />

      <div className="p-4 md:p-6 space-y-6">
        {!hasAnyData && !anyLoading ? (
          <EmptyState
            title="No forecasts yet"
            description="This region has no load history or forecasts. Populate it with synthetic demo data to bring the dashboard to life."
            icon={Zap}
            actionLabel="Generate Demo Data"
            actionPendingLabel={bootstrap.step ?? "Working…"}
            onAction={() => bootstrap.run(region.name)}
            actionPending={bootstrap.running}
            progress={bootstrap.progress}
          />
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                label="Current Load"
                value={currentLoad ? Math.round(currentLoad).toLocaleString() : "—"}
                unit="MW"
                accent="teal"
                icon={Zap}
                loading={actualQuery.loading}
              />
              <MetricCard
                label="Next Hour Forecast"
                value={nextHourForecast ? Math.round(nextHourForecast).toLocaleString() : "—"}
                unit="MW"
                accent="slate"
                icon={TrendingUp}
                loading={forecastQuery.loading}
              />
              <MetricCard
                label="Overall Forecast MAPE"
                value={bestModelSummary ? bestModelSummary.mape.toFixed(2) : "—"}
                unit="%"
                accent="amber"
                icon={Gauge}
                loading={summaryQuery.loading}
              />
              <MetricCard
                label="Best Model"
                value={comparison?.best_model ? MODEL_LABELS[comparison.best_model] ?? comparison.best_model : "—"}
                accent="success"
                icon={Award}
                loading={comparisonQuery.loading}
              />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
              <ChartContainer
                title="Forecast vs Actual"
                subtitle="Last 5 days of observed load + next 24h forecast"
                loading={actualQuery.loading || forecastQuery.loading}
                error={actualQuery.error || forecastQuery.error}
                onRetry={refresh}
                isEmpty={chartData.length === 0}
                emptyTitle="No forecast data"
                emptyDescription="Generate forecasts to see them plotted against actual load."
                height={340}
                className="xl:col-span-2"
              >
                <ForecastChart data={chartData} />
              </ChartContainer>

              {driftQuery.loading ? (
                <div className="panel p-5 space-y-3">
                  <div className="skeleton h-3 w-24 rounded" />
                  <div className="skeleton h-16 w-full rounded" />
                  <div className="skeleton h-3 w-full rounded" />
                </div>
              ) : drift ? (
                <DriftStatusPanel drift={drift} />
              ) : (
                <div className="panel p-5">
                  <EmptyState title="Model health unavailable" description="Score some forecasts to see health status here." />
                </div>
              )}
            </div>

            <ChartContainer
              title="Recent Accuracy Trend"
              subtitle="Daily MAPE across all trained models — click a legend item to isolate it"
              loading={trendQuery.loading}
              error={trendQuery.error}
              onRetry={refresh}
              isEmpty={trend.length === 0}
              emptyTitle="No scored forecasts yet"
              emptyDescription="Once forecasts are scored against real actuals, accuracy trends will appear here."
              height={300}
            >
              <AccuracyChart points={trend.slice(-90)} height={300} />
            </ChartContainer>
          </>
        )}
      </div>
    </div>
  );
}
