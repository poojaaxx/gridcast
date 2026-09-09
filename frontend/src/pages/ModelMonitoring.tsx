import { ClipboardCheck } from "lucide-react";
import Topbar from "../components/Topbar";
import DriftStatusPanel from "../components/DriftStatus";
import StatusBadge, { type Status } from "../components/StatusBadge";
import AccuracyChart from "../components/AccuracyChart";
import ChartContainer from "../components/ChartContainer";
import SectionHeader from "../components/SectionHeader";
import MetricCard from "../components/MetricCard";
import LoadingState from "../components/LoadingState";
import EmptyState from "../components/EmptyState";
import { useAsync } from "../hooks/useAsync";
import { useRegion } from "../hooks/useRegion";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { api } from "../services/api";
import { MODEL_LABELS } from "../types";

const MODEL_TYPES = ["seasonal_naive", "linear_regression", "lightgbm"];

export default function ModelMonitoring() {
  const { region } = useRegion();

  const overallDriftQuery = useAsync(async () => (region ? api.evaluation.drift(region.name) : null), [region?.id]);
  const perModelDriftQuery = useAsync(async () => {
    if (!region) return [];
    const results = await Promise.all(MODEL_TYPES.map((mt) => api.evaluation.drift(region.name, mt)));
    return MODEL_TYPES.map((mt, i) => ({ modelType: mt, drift: results[i] }));
  }, [region?.id]);
  const trendQuery = useAsync(async () => (region ? api.evaluation.timeseries(region.name, "day") : []), [region?.id]);
  const summaryQuery = useAsync(async () => (region ? api.evaluation.summary(region.name) : []), [region?.id]);

  const { refresh, refreshing } = usePageRefresh([
    overallDriftQuery.refetch,
    perModelDriftQuery.refetch,
    trendQuery.refetch,
    summaryQuery.refetch,
  ]);

  if (!region) return <LoadingState label="Loading region…" />;

  const overallDrift = overallDriftQuery.data;
  const perModelDrift = perModelDriftQuery.data ?? [];
  const trend = trendQuery.data ?? [];
  const summary = summaryQuery.data ?? [];
  const totalScored = summary.reduce((sum, s) => sum + s.forecast_count, 0);

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Model Monitoring"
        subtitle="Continuous accuracy tracking & drift detection"
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={overallDriftQuery.updatedAt}
      />

      <div className="p-4 md:p-6 space-y-6">
        {overallDriftQuery.loading ? (
          <LoadingState />
        ) : overallDrift ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            <div className="lg:col-span-2">
              <DriftStatusPanel drift={overallDrift} />
            </div>
            <MetricCard
              label="Total Forecasts Scored"
              value={totalScored.toLocaleString()}
              unit="lifetime"
              icon={ClipboardCheck}
              accent="teal"
              loading={summaryQuery.loading}
            />
          </div>
        ) : (
          <EmptyState title="No monitoring data" description="Score some forecasts first so drift can be evaluated." />
        )}

        <div className="panel">
          <SectionHeader title="Per-Model Health" subtitle="Recent (7d) vs. baseline (30d) MAPE, evaluated independently per model" />
          {perModelDriftQuery.loading ? (
            <LoadingState />
          ) : perModelDrift.length === 0 ? (
            <div className="p-8">
              <EmptyState title="No per-model data yet" description="Train models and score forecasts to see individual health here." />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-base-700/60">
              {perModelDrift.map(({ modelType, drift }) => (
                <div key={modelType} className="p-5 flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-200">{MODEL_LABELS[modelType] ?? modelType}</span>
                    <StatusBadge status={drift.status as Status} withIcon />
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Recent MAPE</span>
                    <span className="text-slate-300 tabular-nums">{drift.recent_mape !== null ? `${drift.recent_mape.toFixed(2)}%` : "—"}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Baseline MAPE</span>
                    <span className="text-slate-300 tabular-nums">{drift.baseline_mape !== null ? `${drift.baseline_mape.toFixed(2)}%` : "—"}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Change</span>
                    <span className={`tabular-nums font-medium ${drift.change_percent !== null && drift.change_percent > 0 ? "text-danger-400" : "text-success-400"}`}>
                      {drift.change_percent !== null ? `${drift.change_percent > 0 ? "+" : ""}${drift.change_percent.toFixed(1)}%` : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between text-2xs text-slate-600 pt-1 border-t border-base-700/40">
                    <span>Scored (7d / 30d prior)</span>
                    <span className="tabular-nums">
                      {drift.recent_count} / {drift.baseline_count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <ChartContainer
          title="Historical Performance Trend"
          subtitle="Daily MAPE, all time — click a legend item to isolate a model"
          loading={trendQuery.loading}
          error={trendQuery.error}
          onRetry={refresh}
          isEmpty={trend.length === 0}
          emptyTitle="No scored forecasts yet"
          emptyDescription="Once forecasts are scored, the full accuracy history will chart here."
          height={320}
        >
          <AccuracyChart points={trend} height={320} />
        </ChartContainer>
      </div>
    </div>
  );
}
