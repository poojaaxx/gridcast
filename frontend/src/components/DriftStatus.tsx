import clsx from "clsx";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import StatusBadge, { STATUS_CONFIG, type Status } from "./StatusBadge";
import type { DriftStatus as DriftStatusType } from "../types";

/**
 * The backend only ever returns "healthy" | "degraded" | "insufficient_data"
 * (see evaluation_service.get_drift_status). "insufficient_data" covers two
 * genuinely different situations that must not be presented identically:
 *
 *  - truly nothing scored yet (recent_mape is null)          -> insufficient_data
 *  - real recent performance is known, but there's no 30-day
 *    baseline yet to compare it against (baseline_mape null) -> building_baseline
 *
 * Collapsing these produced a real contradiction: a region with hundreds of
 * scored forecasts and a solid recent MAPE was shown as "Collecting Data"
 * with a progress bar that had already hit 100%. This derives one consistent
 * display status from the real backend fields - used everywhere drift status
 * is rendered so Overview and Monitoring can never disagree.
 */
export function getDisplayStatus(drift: DriftStatusType): Status {
  if (drift.status === "healthy" || drift.status === "degraded") return drift.status;
  if (drift.recent_mape !== null && drift.recent_count > 0) return "building_baseline";
  return "insufficient_data";
}

export function DriftBadge({ status, size }: { status: string; size?: "sm" | "md" }) {
  return <StatusBadge status={(status as Status) ?? "insufficient_data"} size={size} />;
}

function TrendIndicator({ changePercent }: { changePercent: number | null }) {
  if (changePercent === null) return <span className="text-slate-500">—</span>;
  if (Math.abs(changePercent) < 1) {
    return (
      <span className="inline-flex items-center gap-1 text-slate-400">
        <Minus className="h-3.5 w-3.5" /> Stable
      </span>
    );
  }
  const improving = changePercent < 0;
  return (
    <span className={clsx("inline-flex items-center gap-1 font-medium", improving ? "text-success-400" : "text-danger-400")}>
      {improving ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />}
      {improving ? "Improving" : "Worsening"}
    </span>
  );
}

/** Meaningful health card: distinct visual language per state, never an empty shell. */
export default function DriftStatusPanel({ drift, targetScored = 20 }: { drift: DriftStatusType; targetScored?: number }) {
  const displayStatus = getDisplayStatus(drift);
  const config = STATUS_CONFIG[displayStatus];

  if (displayStatus === "insufficient_data") {
    const scored = drift.recent_count + drift.baseline_count;
    const progress = Math.min(100, Math.round((scored / targetScored) * 100));
    return (
      <div className="panel p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="stat-label">Model Health</span>
          <StatusBadge status="insufficient_data" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-200">Collecting evaluation history</p>
          <p className="text-xs text-slate-500 mt-1">Score forecasts against real actuals to unlock model health tracking.</p>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
            <span>Forecasts scored</span>
            <span className="tabular-nums text-slate-300">
              {scored} / {targetScored}+
            </span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-base-700 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent-600 to-accent-400 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  if (displayStatus === "building_baseline") {
    return (
      <div className="panel p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="stat-label">Model Health</span>
          <StatusBadge status="building_baseline" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Recent MAPE (7d)</p>
            <p className={clsx("text-xl font-semibold tabular-nums", config.text)}>
              {drift.recent_mape !== null ? `${drift.recent_mape.toFixed(2)}%` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Baseline MAPE (30d)</p>
            <p className="text-xl font-semibold tabular-nums text-slate-600">Building…</p>
          </div>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed rounded-lg bg-base-800/60 border border-base-700/60 px-3 py-2.5">
          Based on <span className="text-slate-300 font-medium tabular-nums">{drift.recent_count}</span> forecasts scored in the
          last 7 days. Drift comparison needs forecasting activity going back 30+ days beyond that before a baseline can be
          established.
        </p>
      </div>
    );
  }

  return (
    <div className="panel p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="stat-label">Model Health</span>
        <StatusBadge status={displayStatus} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-slate-500 mb-1">Recent MAPE (7d)</p>
          <p className={clsx("text-xl font-semibold tabular-nums", config.text)}>
            {drift.recent_mape !== null ? `${drift.recent_mape.toFixed(2)}%` : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Baseline MAPE (30d)</p>
          <p className="text-xl font-semibold tabular-nums text-slate-300">
            {drift.baseline_mape !== null ? `${drift.baseline_mape.toFixed(2)}%` : "—"}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between rounded-lg bg-base-800/60 border border-base-700/60 px-3 py-2.5 text-xs">
        <span className="text-slate-500">7-Day Trend</span>
        <TrendIndicator changePercent={drift.change_percent} />
      </div>
      {drift.change_percent !== null && (
        <p className="text-xs text-slate-500 leading-relaxed">
          Recent error is{" "}
          <span className={clsx("font-semibold", drift.change_percent > 0 ? "text-danger-400" : "text-success-400")}>
            {drift.change_percent > 0 ? "+" : ""}
            {drift.change_percent.toFixed(1)}%
          </span>{" "}
          vs. the 30-day baseline (degradation threshold: {drift.threshold_pct}%).
        </p>
      )}
    </div>
  );
}
