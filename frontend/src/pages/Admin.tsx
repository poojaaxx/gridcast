import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Database,
  LineChart,
  RadioTower,
  Server,
  Sparkles,
  Target,
  User as UserIcon,
} from "lucide-react";
import Topbar from "../components/Topbar";
import SectionHeader from "../components/SectionHeader";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import ConfirmDialog from "../components/ConfirmDialog";
import ModelSelector from "../components/ModelSelector";
import SegmentedControl from "../components/SegmentedControl";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import { SkeletonTable } from "../components/Skeleton";
import { useAsync } from "../hooks/useAsync";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { useToast } from "../hooks/useToast";
import { useDemoBootstrap } from "../state/useDemoBootstrap";
import { useEvaluationHistoryRun } from "../state/useEvaluationHistoryRun";
import { api } from "../services/api";
import { MODEL_LABELS } from "../types";

const TRAINABLE_MODEL_TYPES = ["seasonal_naive", "linear_regression", "lightgbm"];

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Admin() {
  const toast = useToast();
  const [regionName, setRegionName] = useState("");
  const [trainModelType, setTrainModelType] = useState("lightgbm");
  const [forecastHorizon, setForecastHorizon] = useState<24 | 48>(24);
  const [confirmOpen, setConfirmOpen] = useState<"ingest" | "train" | "demo" | "eval-history" | null>(null);

  const statusQuery = useAsync(() => api.admin.status(), []);
  const auditQuery = useAsync(() => api.admin.auditLog(50), []);
  const modelsQuery = useAsync(() => api.models.list(), []);
  const bootstrap = useDemoBootstrap();
  const evalHistory = useEvaluationHistoryRun();
  const isLive = statusQuery.data?.data_mode === "live";

  // Default the target region to whichever region matches the server's
  // actual configured mode, once known - never guess ahead of it.
  useEffect(() => {
    if (regionName || !statusQuery.data) return;
    setRegionName(statusQuery.data.data_mode === "live" ? statusQuery.data.live_region : statusQuery.data.demo_region);
  }, [statusQuery.data, regionName]);

  const { refresh, refreshing } = usePageRefresh([statusQuery.refetch, auditQuery.refetch, modelsQuery.refetch]);

  const refreshAll = () => {
    statusQuery.refetch();
    auditQuery.refetch();
    modelsQuery.refetch();
  };

  const ingestAction = useAsyncAction(async () => {
    const result = await api.data.ingest(regionName, 200);
    toast.success("Ingestion complete", `${result.load_inserted} load + ${result.weather_inserted} weather records inserted.`);
    refreshAll();
    return result;
  });

  const trainAction = useAsyncAction(async () => {
    const result = await api.models.train(regionName, trainModelType);
    toast.success("Training complete", `${MODEL_LABELS[trainModelType] ?? trainModelType} → ${result.version}`);
    refreshAll();
    return result;
  });

  const forecastAction = useAsyncAction(async (horizon: 24 | 48) => {
    const result = await api.forecasts.generate(regionName, "latest", horizon);
    toast.success("Forecast generated", `${result.length} forecast points for the next ${horizon}h.`);
    refreshAll();
    return result;
  });

  const scoreAction = useAsyncAction(async () => {
    const result = await api.evaluation.score(regionName);
    toast.success("Scoring complete", `${result.scored} new forecast(s) scored against actuals.`);
    refreshAll();
    return result;
  });

  const status = statusQuery.data;
  const models = (modelsQuery.data ?? []).slice(0, 6);
  const auditLogs = auditQuery.data ?? [];

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Admin Console"
        subtitle="Operational control — ingestion, training, forecasting, evaluation"
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={statusQuery.updatedAt}
      />

      <div className="p-4 md:p-6 space-y-6">
        {/* --- Data mode banner: never let demo data pass as live --- */}
        {status && (
          <div
            className={`panel p-4 flex items-center gap-3 border-l-4 ${
              status.data_mode === "demo" ? "border-l-warn-500" : "border-l-success-500"
            }`}
          >
            <Sparkles className={`h-4 w-4 flex-shrink-0 ${status.data_mode === "demo" ? "text-warn-400" : "text-success-400"}`} />
            <p className="text-xs text-slate-300">
              <span className={`font-bold uppercase tracking-wide ${status.data_mode === "demo" ? "text-warn-400" : "text-success-400"}`}>
                {status.data_mode === "demo" ? "Demo Data" : "Live Data"}
              </span>{" "}
              — {status.data_mode === "demo"
                ? "this deployment is running on the deterministic synthetic generator, not real electricity data."
                : `sourced from the configured "${status.electricity_provider}" provider.`}
            </p>
          </div>
        )}

        {/* --- System Status --- */}
        <div>
          <SectionHeader title="System Status" subtitle="Live backend/database health and MLOps loop timestamps" />
          <div className="pt-4">
            {statusQuery.loading ? (
              <LoadingState />
            ) : statusQuery.error || !status ? (
              <ErrorState message={statusQuery.error ?? "Unable to load system status."} onRetry={refresh} />
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <MetricCard label="Backend" value={status.backend_status === "ok" ? "Online" : "Error"} icon={Server} accent={status.backend_status === "ok" ? "success" : "red"} />
                  <MetricCard label="Database" value={status.database_status === "ok" ? "Online" : "Error"} icon={Database} accent={status.database_status === "ok" ? "success" : "red"} />
                  <MetricCard label="Environment" value={status.environment} icon={Activity} accent="slate" />
                  <MetricCard label="Signed In As" value={status.current_admin} icon={UserIcon} accent="teal" />
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <MetricCard label="Data Mode" value={status.data_mode === "live" ? "Live" : "Demo"} icon={RadioTower} accent={status.data_mode === "live" ? "success" : "amber"} />
                  <MetricCard label="Provider" value={status.electricity_provider} icon={Sparkles} accent="slate" />
                  <MetricCard label="Live Region" value={status.live_region} icon={Target} accent="slate" />
                  <MetricCard label="Demo Region" value={status.demo_region} icon={Target} accent="slate" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <MetricCard label="Last Ingestion" value={formatTimestamp(status.last_ingestion_at)} icon={Database} accent="slate" />
                  <MetricCard label="Last Forecast Generated" value={formatTimestamp(status.last_forecast_generated_at)} icon={LineChart} accent="slate" />
                  <MetricCard label="Last Evaluation Scored" value={formatTimestamp(status.last_evaluation_scored_at)} icon={CheckCircle2} accent="slate" />
                </div>
                <div className="panel p-4 flex flex-wrap items-center gap-3">
                  <span className="stat-label flex-shrink-0">Continuous Pipeline (Worker)</span>
                  {status.last_pipeline_cycle_at ? (
                    <>
                      <StatusBadge
                        status={status.last_pipeline_cycle_status === "success" ? "healthy" : "degraded"}
                        label={status.last_pipeline_cycle_status === "success" ? "Last cycle OK" : "Last cycle failed"}
                      />
                      <span className="text-xs text-slate-500">{formatTimestamp(status.last_pipeline_cycle_at)}</span>
                    </>
                  ) : (
                    <span className="text-xs text-slate-500">
                      No cycles yet — the worker only runs automatically in LIVE mode (idle in demo mode by design).
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* --- Target region (shared by every action below) --- */}
        <div className="panel p-4 flex flex-wrap items-center gap-3">
          <Target className="h-4 w-4 text-slate-500 flex-shrink-0" />
          <label htmlFor="admin-region" className="stat-label flex-shrink-0">
            Target Region
          </label>
          <input
            id="admin-region"
            value={regionName}
            onChange={(e) => setRegionName(e.target.value)}
            className="input-select flex-1 min-w-[160px] max-w-xs"
            placeholder="demo-region"
          />
          <p className="text-2xs text-slate-600">Every action below operates on this region — created automatically on first ingestion if it doesn't exist.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* --- Data Operations --- */}
          <div className="panel">
            <SectionHeader title="Data Operations" subtitle="Ingest load + weather history" />
            <div className="p-5 flex flex-col gap-4">
              <p className="text-xs text-slate-500">
                {isLive
                  ? "LIVE mode: fetches real hourly demand from the configured EIA provider. If the provider fails, this action fails too — it never substitutes synthetic data."
                  : "DEMO mode: populates the target region with the deterministic synthetic generator."}
              </p>
              <button onClick={() => setConfirmOpen("ingest")} disabled={ingestAction.running} className="btn-primary py-2.5">
                {ingestAction.running ? "Ingesting…" : isLive ? "Run Live Ingestion (200 days)" : "Run Demo Ingestion (200 days)"}
              </button>
              <ActionResult action={ingestAction} successLabel={(r: any) => `Inserted ${r.load_inserted} load / ${r.weather_inserted} weather records (source: ${r.load_source})${r.degraded ? " — weather degraded this run." : "."}`} />
            </div>
          </div>

          {/* --- Model Operations --- */}
          <div className="panel">
            <SectionHeader title="Model Operations" subtitle="Train a forecasting model with walk-forward validation" />
            <div className="p-5 flex flex-col gap-4">
              <ModelSelector value={trainModelType} onChange={setTrainModelType} options={TRAINABLE_MODEL_TYPES} />
              <button onClick={() => setConfirmOpen("train")} disabled={trainAction.running} className="btn-primary py-2.5">
                {trainAction.running ? "Training…" : `Train ${MODEL_LABELS[trainModelType] ?? trainModelType}`}
              </button>
              <ActionResult action={trainAction} successLabel={(r: any) => `${r.version} — MAPE ${r.metrics_json?.mean_metrics?.mape?.toFixed(2) ?? "—"}%`} />
            </div>
          </div>

          {/* --- Forecast Operations --- */}
          <div className="panel">
            <SectionHeader title="Forecast Operations" subtitle="Generate forecasts from the latest trained model" />
            <div className="p-5 flex flex-col gap-4">
              <SegmentedControl
                aria-label="Forecast horizon"
                value={forecastHorizon}
                onChange={setForecastHorizon}
                options={[{ label: "24H", value: 24 }, { label: "48H", value: 48 }]}
              />
              <button onClick={() => forecastAction.run(forecastHorizon)} disabled={forecastAction.running} className="btn-primary py-2.5">
                {forecastAction.running ? "Generating…" : `Generate ${forecastHorizon}h Forecast`}
              </button>
              <ActionResult action={forecastAction} successLabel={(r: any) => `${r.length} forecast points generated.`} />
            </div>
          </div>

          {/* --- Evaluation Operations --- */}
          <div className="panel">
            <SectionHeader title="Evaluation Operations" subtitle="Score forecasts whose actuals have arrived" />
            <div className="p-5 flex flex-col gap-4">
              <p className="text-xs text-slate-500">
                Matches persisted forecasts to real actual observations and computes error metrics. Safe to run anytime — already-scored forecasts are never re-scored.
              </p>
              <button onClick={() => scoreAction.run()} disabled={scoreAction.running} className="btn-primary py-2.5">
                {scoreAction.running ? "Scoring…" : "Score Pending Forecasts"}
              </button>
              <ActionResult action={scoreAction} successLabel={(r: any) => `${r.scored} forecast(s) scored.`} />
            </div>
          </div>
        </div>

        {/* --- Evaluation History Backfill (LIVE only) --- */}
        <div className="panel border border-teal-500/20">
          <SectionHeader
            title="Evaluation History Backfill"
            subtitle="LIVE ONLY — one-time walk-forward backtest that populates real, out-of-sample forecast/evaluation history from already-ingested EIA/Open-Meteo data"
            actions={<StatusBadge status="healthy" label="Real Data Only" />}
          />
          <div className="p-5 flex flex-col gap-4">
            {!isLive ? (
              <p className="text-xs text-danger-400">
                Disabled — this operation only makes sense in LIVE mode, where real historical observations exist to backtest against.
              </p>
            ) : (
              <p className="text-xs text-slate-500">
                Trains a fresh model per historical day-block on real data strictly before that day (never the deployed
                artifact, which would leak future data), predicts recursively, and scores against real actuals. Safe to
                re-run — already-generated forecasts are never duplicated. Runs in the background on the server (this can
                take a couple of minutes for a full window) — this page polls for progress automatically, including
                after a refresh.
              </p>
            )}
            <button
              onClick={() => setConfirmOpen("eval-history")}
              disabled={!isLive || evalHistory.starting || evalHistory.state?.status === "running"}
              className="btn-primary py-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {evalHistory.state?.status === "running" ? "Building…" : "Build Evaluation History"}
            </button>

            {evalHistory.state?.status === "running" && (
              <p className="text-xs text-slate-500">
                Started {evalHistory.state.started_at ? new Date(evalHistory.state.started_at).toLocaleTimeString() : ""}
                {evalHistory.state.started_by ? ` by ${evalHistory.state.started_by}` : ""} — checking progress every few seconds…
              </p>
            )}
            {evalHistory.startError && <p className="text-xs text-danger-400">{evalHistory.startError}</p>}
            {evalHistory.state?.status === "failed" && (
              <p className="text-xs text-danger-400">Last run failed: {evalHistory.state.error}</p>
            )}
            {evalHistory.state?.status === "completed" && evalHistory.state.report && (
              <div className="rounded-lg border border-base-700/60 bg-base-800/40 p-4 space-y-2">
                <p className="text-xs text-slate-300">
                  Backtest window <span className="font-mono">{evalHistory.state.report.backtest_start}</span> →{" "}
                  <span className="font-mono">{evalHistory.state.report.backtest_end}</span> ({evalHistory.state.report.backtest_days} days) ·{" "}
                  {evalHistory.state.report.newly_scored} newly scored this run
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {evalHistory.state.report.performance.map((p) => (
                    <div key={p.model_type} className="text-xs text-slate-400">
                      <span className="text-slate-200 font-medium">{MODEL_LABELS[p.model_type] ?? p.model_type}</span>
                      {" — "}MAPE {p.mape.toFixed(2)}% · MAE {p.mae.toFixed(0)} · RMSE {p.rmse.toFixed(0)} · n={p.forecast_count}
                    </div>
                  ))}
                </div>
                <p className="text-2xs text-slate-500">
                  Best model: {evalHistory.state.report.best_model ? (MODEL_LABELS[evalHistory.state.report.best_model] ?? evalHistory.state.report.best_model) : "—"}
                  {" · "}Drift: {evalHistory.state.report.drift.status}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* --- Demo Controls --- */}
        <div className="panel border border-warn-500/20">
          <SectionHeader
            title="Demo Controls"
            subtitle="DEMO ONLY — populates this region with ~200 days of synthetic history, trains all 3 models, and scores initial forecasts"
            actions={<StatusBadge status="warning" label="Synthetic Data" />}
          />
          <div className="p-5 flex flex-col gap-4">
            {isLive && (
              <p className="text-xs text-danger-400">
                Disabled — this deployment is configured for LIVE mode. Demo data generation is blocked here to prevent
                synthetic records from accidentally being written into a live deployment.
              </p>
            )}
            <button
              onClick={() => setConfirmOpen("demo")}
              disabled={bootstrap.running || isLive}
              title={isLive ? "Disabled while running in LIVE mode" : undefined}
              className="btn-secondary py-2.5 border-warn-500/30 hover:border-warn-500/50 hover:text-warn-400 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {bootstrap.running ? bootstrap.step ?? "Working…" : "Generate Demo Data"}
            </button>
            {bootstrap.running && (
              <div>
                <div className="h-1.5 w-full rounded-full bg-base-700 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-warn-600 to-warn-400 transition-all duration-300" style={{ width: `${bootstrap.progress}%` }} />
                </div>
                <p className="text-2xs text-slate-500 mt-1.5">{bootstrap.step}</p>
              </div>
            )}
            {bootstrap.error && <p className="text-xs text-danger-400">{bootstrap.error}</p>}
          </div>
        </div>

        {/* --- Audit Activity --- */}
        <div className="panel">
          <SectionHeader title="Audit Activity" subtitle="Recent administrative actions — who, what, when, and whether it succeeded" actions={<ClipboardList className="h-4 w-4 text-slate-500" />} />
          {auditQuery.loading ? (
            <SkeletonTable />
          ) : auditQuery.error ? (
            <ErrorState message={auditQuery.error} onRetry={refresh} />
          ) : auditLogs.length === 0 ? (
            <p className="text-sm text-slate-500 py-10 text-center">No administrative actions recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-base-700/60 text-left">
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Time</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">User</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Action</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="border-b border-base-700/30 last:border-0 hover:bg-base-800/50">
                      <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-slate-300">{log.username}</td>
                      <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">{log.action}</td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={log.status === "success" ? "healthy" : "degraded"} label={log.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* --- Trained model versions (supporting detail for Model Operations) --- */}
        <div className="panel">
          <SectionHeader title="Model Versions" subtitle="Most recently trained models across all types" actions={<Cpu className="h-4 w-4 text-slate-500" />} />
          {modelsQuery.loading ? (
            <SkeletonTable />
          ) : models.length === 0 ? (
            <p className="text-sm text-slate-500 py-10 text-center">No models trained yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-base-700/60 text-left">
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Model</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Version</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider text-right">MAPE</th>
                    <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Trained</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={m.id} className="border-b border-base-700/30 last:border-0 hover:bg-base-800/50">
                      <td className="px-4 py-2.5 text-slate-200 font-medium">{MODEL_LABELS[m.model_type] ?? m.model_type}</td>
                      <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">{m.version}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-300">
                        {m.metrics_json?.mean_metrics?.mape != null ? `${m.metrics_json.mean_metrics.mape.toFixed(2)}%` : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{new Date(m.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen === "ingest"}
        title={isLive ? "Run live ingestion?" : "Run demo ingestion?"}
        description={
          isLive
            ? `This fetches ~200 days of real hourly demand from EIA for "${regionName}" and writes it to the database. Safe to re-run — existing timestamps are never duplicated. If the provider is unreachable, this fails rather than substituting synthetic data.`
            : `This generates ~200 days of synthetic load and weather history for "${regionName}" and writes it to the database. Safe to re-run — existing timestamps are never duplicated.`
        }
        confirmLabel="Run Ingestion"
        busy={ingestAction.running}
        onConfirm={async () => {
          try {
            await ingestAction.run();
          } finally {
            setConfirmOpen(null);
          }
        }}
        onCancel={() => setConfirmOpen(null)}
      />
      <ConfirmDialog
        open={confirmOpen === "train"}
        title={`Train ${MODEL_LABELS[trainModelType] ?? trainModelType}?`}
        description={`Runs walk-forward validation and fits a new model version on all available history for "${regionName}". This can take a little while for LightGBM.`}
        confirmLabel="Train Model"
        busy={trainAction.running}
        onConfirm={async () => {
          try {
            await trainAction.run();
          } finally {
            setConfirmOpen(null);
          }
        }}
        onCancel={() => setConfirmOpen(null)}
      />
      <ConfirmDialog
        open={confirmOpen === "eval-history"}
        title="Build evaluation history?"
        description="Runs a one-time walk-forward backtest against real, already-ingested EIA/Open-Meteo history for the live region. This can take a couple of minutes and runs in the background — safe to leave this page and come back. Re-running later is safe too; nothing is duplicated."
        confirmLabel="Build Evaluation History"
        busy={evalHistory.starting}
        onConfirm={async () => {
          setConfirmOpen(null);
          await evalHistory.start();
        }}
        onCancel={() => setConfirmOpen(null)}
      />
      <ConfirmDialog
        open={confirmOpen === "demo"}
        title="Generate demo data?"
        description={`DEMO ONLY: ingests ~200 days of synthetic history into "${regionName}", trains all 3 models, generates forecasts, and scores them. This will take a minute or two and issues real database writes.`}
        confirmLabel="Generate Demo Data"
        danger
        busy={bootstrap.running}
        onConfirm={async () => {
          setConfirmOpen(null);
          try {
            await bootstrap.run(regionName);
          } catch {
            // toast already surfaced by useDemoBootstrap
          } finally {
            refreshAll();
          }
        }}
        onCancel={() => setConfirmOpen(null)}
      />
    </div>
  );
}

function ActionResult({ action, successLabel }: { action: ReturnType<typeof useAsyncAction<any[], any>>; successLabel: (result: any) => string }) {
  if (action.error) return <p className="text-xs text-danger-400">{action.error}</p>;
  if (action.result && action.completedAt) {
    return (
      <p className="text-xs text-success-400">
        {successLabel(action.result)} <span className="text-slate-600">· {new Date(action.completedAt).toLocaleTimeString()}</span>
      </p>
    );
  }
  return null;
}
