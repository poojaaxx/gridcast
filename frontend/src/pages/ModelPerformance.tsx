import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Trophy } from "lucide-react";
import Topbar from "../components/Topbar";
import ModelComparisonTable from "../components/ModelComparisonTable";
import AccuracyChart from "../components/AccuracyChart";
import ChartContainer from "../components/ChartContainer";
import SegmentedControl from "../components/SegmentedControl";
import { SkeletonTable } from "../components/Skeleton";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import SectionHeader from "../components/SectionHeader";
import { useAsync } from "../hooks/useAsync";
import { useRegion } from "../hooks/useRegion";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { api } from "../services/api";
import { MODEL_COLORS, MODEL_LABELS } from "../types";

type Metric = "mape" | "mae" | "rmse" | "smape";
const METRIC_OPTIONS: { label: string; value: Metric }[] = [
  { label: "MAPE", value: "mape" },
  { label: "MAE", value: "mae" },
  { label: "RMSE", value: "rmse" },
  { label: "sMAPE", value: "smape" },
];
const METRIC_UNIT: Record<Metric, string> = { mape: "%", smape: "%", mae: " MW", rmse: " MW" };

export default function ModelPerformance() {
  const { region } = useRegion();
  const [metric, setMetric] = useState<Metric>("mape");
  const [granularity, setGranularity] = useState<"day" | "week">("week");
  const [excludedModels, setExcludedModels] = useState<Set<string>>(new Set());

  const summaryQuery = useAsync(async () => (region ? api.evaluation.summary(region.name) : []), [region?.id]);
  const comparisonQuery = useAsync(
    async () => (region ? api.evaluation.modelComparison(region.name) : { models: [], best_model: null }),
    [region?.id]
  );
  const trendQuery = useAsync(async () => (region ? api.evaluation.timeseries(region.name, granularity) : []), [region?.id, granularity]);
  const modelsQuery = useAsync(async () => api.models.list(), []);

  const { refresh, refreshing } = usePageRefresh([
    summaryQuery.refetch,
    comparisonQuery.refetch,
    trendQuery.refetch,
    modelsQuery.refetch,
  ]);

  if (!region) return <LoadingState label="Loading region…" />;

  const summary = (summaryQuery.data ?? []).filter((s) => !excludedModels.has(s.model_type));
  const comparison = comparisonQuery.data;
  const trend = (trendQuery.data ?? []).filter((p) => !excludedModels.has(p.model_type));
  const models = modelsQuery.data ?? [];
  const allModelTypes = Array.from(new Set((summaryQuery.data ?? []).map((s) => s.model_type)));

  const latestPerType = new Map<string, (typeof models)[number]>();
  for (const m of models) {
    if (!latestPerType.has(m.model_type) || m.created_at > latestPerType.get(m.model_type)!.created_at) {
      latestPerType.set(m.model_type, m);
    }
  }

  const foldRows: Record<string, number | string>[] = [];
  const visibleFoldModels = Array.from(latestPerType.entries()).filter(([mt]) => !excludedModels.has(mt));
  const maxFolds = Math.max(0, ...visibleFoldModels.map(([, m]) => m.metrics_json.walk_forward?.folds.length ?? 0));
  for (let i = 0; i < maxFolds; i++) {
    const row: Record<string, number | string> = { fold: `Fold ${i + 1}` };
    for (const [modelType, version] of visibleFoldModels) {
      const fold = version.metrics_json.walk_forward?.folds[i];
      if (fold) row[modelType] = fold.metrics[metric];
    }
    foldRows.push(row);
  }

  const bestSummary = comparison?.best_model ? (summaryQuery.data ?? []).find((s) => s.model_type === comparison.best_model) : null;
  const naiveSummary = (summaryQuery.data ?? []).find((s) => s.model_type === "seasonal_naive");
  const improvementPct =
    bestSummary && naiveSummary && naiveSummary.model_type !== bestSummary.model_type && naiveSummary.mape > 0
      ? ((naiveSummary.mape - bestSummary.mape) / naiveSummary.mape) * 100
      : null;

  function toggleModel(modelType: string) {
    setExcludedModels((prev) => {
      const next = new Set(prev);
      if (next.has(modelType)) next.delete(modelType);
      else next.add(modelType);
      return next;
    });
  }

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Model Performance"
        subtitle="ML evaluation dashboard — live accuracy across all trained models"
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={summaryQuery.updatedAt}
      />

      <div className="p-4 md:p-6 space-y-6">
        {bestSummary && (
          <div className="panel p-5 flex flex-wrap items-center gap-6 bg-gradient-to-br from-base-850 to-base-800/60">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-accent-500/10 p-2.5">
                <Trophy className="h-5 w-5 text-accent-400" />
              </div>
              <div>
                <p className="stat-label">Best Performer</p>
                <p className="text-lg font-bold text-slate-100">{MODEL_LABELS[bestSummary.model_type] ?? bestSummary.model_type}</p>
              </div>
            </div>
            <div className="h-10 w-px bg-base-700 hidden sm:block" />
            <div>
              <p className="stat-label">MAPE</p>
              <p className="text-lg font-bold text-accent-400 tabular-nums">{bestSummary.mape.toFixed(2)}%</p>
            </div>
            {improvementPct !== null && (
              <>
                <div className="h-10 w-px bg-base-700 hidden sm:block" />
                <div>
                  <p className="stat-label">Improvement vs Seasonal Naive</p>
                  <p className={`text-lg font-bold tabular-nums ${improvementPct > 0 ? "text-success-400" : "text-danger-400"}`}>
                    {improvementPct > 0 ? "↓" : "↑"} {Math.abs(improvementPct).toFixed(0)}%
                  </p>
                </div>
              </>
            )}
            <div className="ml-auto text-xs text-slate-500">
              Based on {bestSummary.forecast_count.toLocaleString()} scored forecasts
            </div>
          </div>
        )}

        <div className="panel p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="stat-label hidden sm:inline">Metric</span>
            <SegmentedControl aria-label="Metric" value={metric} onChange={setMetric} options={METRIC_OPTIONS} />
          </div>
          {allModelTypes.length > 1 && (
            <div className="flex items-center gap-1.5 sm:ml-auto flex-wrap">
              <span className="stat-label hidden sm:inline mr-1">Models</span>
              {allModelTypes.map((mt) => {
                const active = !excludedModels.has(mt);
                return (
                  <button
                    key={mt}
                    onClick={() => toggleModel(mt)}
                    aria-pressed={active}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-2xs font-medium transition-colors ${
                      active ? "border-base-600 text-slate-300 bg-base-800" : "border-base-700/50 text-slate-600"
                    }`}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: active ? MODEL_COLORS[mt] ?? "#94a3b8" : "#475569" }}
                    />
                    {MODEL_LABELS[mt] ?? mt}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="panel">
          <SectionHeader title="Model Comparison" subtitle="Computed from persisted forecast scores" />
          {summaryQuery.loading ? (
            <SkeletonTable />
          ) : summaryQuery.error ? (
            <ErrorState message={summaryQuery.error} onRetry={refresh} />
          ) : summary.length === 0 ? (
            <EmptyState title="No scored forecasts yet" description="Run `make score` (or POST /evaluation/score) after actuals arrive for existing forecasts." />
          ) : (
            <ModelComparisonTable models={summary} bestModel={comparison?.best_model ?? null} />
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartContainer
            title="Accuracy by Model"
            subtitle={`${METRIC_OPTIONS.find((m) => m.value === metric)?.label} across all trained models`}
            loading={summaryQuery.loading}
            error={summaryQuery.error}
            onRetry={refresh}
            isEmpty={summary.length === 0}
            height={280}
          >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={summary.map((s) => ({ ...s, label: MODEL_LABELS[s.model_type] ?? s.model_type }))}>
                <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1a2332" }} />
                <YAxis stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => `${v}${METRIC_UNIT[metric]}`} />
                <Tooltip
                  contentStyle={{ background: "#0d1219", border: "1px solid #1a2332", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#94a3b8" }}
                  formatter={(value: number) => [`${value.toFixed(2)}${METRIC_UNIT[metric]}`, METRIC_OPTIONS.find((m) => m.value === metric)?.label]}
                />
                <Bar dataKey={metric} radius={[4, 4, 0, 0]}>
                  {summary.map((s) => (
                    <Cell key={s.model_type} fill={MODEL_COLORS[s.model_type] ?? "#94a3b8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>

          <ChartContainer
            title="Trend Over Time"
            subtitle={`${METRIC_OPTIONS.find((m) => m.value === metric)?.label} by ${granularity}`}
            actions={
              <SegmentedControl
                aria-label="Trend granularity"
                value={granularity}
                onChange={setGranularity}
                options={[
                  { label: "Weekly", value: "week" },
                  { label: "Daily", value: "day" },
                ]}
              />
            }
            loading={trendQuery.loading}
            error={trendQuery.error}
            onRetry={refresh}
            isEmpty={trend.length === 0}
            emptyTitle="No trend data yet"
            emptyDescription="Scored forecasts will populate this trend as they accumulate."
            height={280}
          >
            <AccuracyChart points={trend} metric={metric} height={280} />
          </ChartContainer>
        </div>

        <ChartContainer
          title="Forecast Error Distribution"
          subtitle="Walk-forward validation error per fold (latest trained version) — never a random split"
          loading={modelsQuery.loading}
          error={modelsQuery.error}
          onRetry={refresh}
          isEmpty={foldRows.length === 0}
          emptyTitle="No trained models yet"
          height={280}
        >
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={foldRows}>
              <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="fold" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1a2332" }} />
              <YAxis stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => `${v}${METRIC_UNIT[metric]}`} />
              <Tooltip
                contentStyle={{ background: "#0d1219", border: "1px solid #1a2332", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#94a3b8" }}
                formatter={(value: number, name: string) => [`${value.toFixed(2)}${METRIC_UNIT[metric]}`, MODEL_LABELS[name] ?? name]}
              />
              {visibleFoldModels.map(([modelType]) => (
                <Bar key={modelType} dataKey={modelType} fill={MODEL_COLORS[modelType] ?? "#94a3b8"} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      </div>
    </div>
  );
}
