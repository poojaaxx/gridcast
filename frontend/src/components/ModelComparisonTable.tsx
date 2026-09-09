import clsx from "clsx";
import { Trophy } from "lucide-react";
import type { ModelPerformance } from "../types";
import { MODEL_COLORS, MODEL_LABELS } from "../types";

interface Props {
  models: ModelPerformance[];
  bestModel: string | null;
}

const COLUMNS: { key: keyof ModelPerformance; label: string; suffix?: string }[] = [
  { key: "mae", label: "MAE", suffix: "MW" },
  { key: "rmse", label: "RMSE", suffix: "MW" },
  { key: "mape", label: "MAPE", suffix: "%" },
  { key: "smape", label: "sMAPE", suffix: "%" },
  { key: "forecast_count", label: "Forecasts" },
];

export default function ModelComparisonTable({ models, bestModel }: Props) {
  const sorted = [...models].sort((a, b) => a.mape - b.mape);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-base-700/60 text-left">
            <th className="px-4 py-3 font-medium text-slate-500 text-2xs uppercase tracking-wider w-10">Rank</th>
            <th className="px-4 py-3 font-medium text-slate-500 text-2xs uppercase tracking-wider">Model</th>
            {COLUMNS.map((col) => (
              <th key={col.key} className="px-4 py-3 font-medium text-slate-500 text-2xs uppercase tracking-wider text-right">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((model, index) => {
            const isBest = model.model_type === bestModel;
            return (
              <tr
                key={model.model_type}
                className={clsx(
                  "border-b border-base-700/30 last:border-0 transition-colors",
                  isBest ? "bg-accent-500/5" : "hover:bg-base-800/50"
                )}
              >
                <td className="px-4 py-3 text-slate-500 tabular-nums">{index + 1}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: MODEL_COLORS[model.model_type] ?? "#94a3b8" }}
                    />
                    <span className="font-medium text-slate-200">{MODEL_LABELS[model.model_type] ?? model.model_type}</span>
                    {isBest && (
                      <span className="badge bg-accent-500/10 text-accent-400 ml-1">
                        <Trophy className="h-3 w-3" /> Best
                      </span>
                    )}
                  </div>
                </td>
                {COLUMNS.map((col) => (
                  <td key={col.key} className="px-4 py-3 text-right tabular-nums text-slate-300">
                    {typeof model[col.key] === "number"
                      ? (model[col.key] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                      : model[col.key]}
                    {col.suffix && <span className="text-slate-500 ml-1">{col.suffix}</span>}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
