import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PerformancePoint } from "../types";
import { MODEL_COLORS, MODEL_LABELS } from "../types";

function formatTick(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const METRIC_UNIT: Record<string, string> = { mape: "%", smape: "%", mae: " MW", rmse: " MW" };

function CustomTooltip({ active, payload, label, metric }: any) {
  if (!active || !payload?.length) return null;
  const unit = METRIC_UNIT[metric] ?? "";
  return (
    <div className="rounded-lg border border-base-700 bg-base-850 px-3 py-2 shadow-xl text-xs">
      <p className="text-slate-400 mb-1.5">{formatTick(label)}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 py-0.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-slate-400">{MODEL_LABELS[p.dataKey] ?? p.dataKey}:</span>
          <span className="font-medium text-slate-200 tabular-nums">
            {p.value?.toFixed(2)}
            {unit}
          </span>
        </div>
      ))}
    </div>
  );
}

interface Props {
  points: PerformancePoint[];
  metric?: "mape" | "mae" | "smape" | "rmse";
  height?: number;
}

/** Multi-model accuracy trend with a clickable legend - click a model name to
 * isolate/hide its line, exactly like a real analytics product. */
export default function AccuracyChart({ points, metric = "mape", height = 300 }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const { rows, modelTypes } = useMemo(() => {
    const periods = Array.from(new Set(points.map((p) => p.period))).sort();
    const modelTypes = Array.from(new Set(points.map((p) => p.model_type)));
    const rows = periods.map((period) => {
      const row: Record<string, number | string> = { period };
      for (const modelType of modelTypes) {
        const match = points.find((p) => p.period === period && p.model_type === modelType);
        if (match) row[modelType] = match[metric as keyof PerformancePoint] as number;
      }
      return row;
    });
    return { rows, modelTypes };
  }, [points, metric]);

  const toggle = (dataKey: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(dataKey)) next.delete(dataKey);
      else next.add(dataKey);
      return next;
    });
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="period"
          tickFormatter={formatTick}
          stroke="#475569"
          tick={{ fill: "#64748b", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "#1a2332" }}
          minTickGap={30}
        />
        <YAxis
          stroke="#475569"
          tick={{ fill: "#64748b", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(v) => `${v}${METRIC_UNIT[metric] ?? ""}`}
        />
        <Tooltip content={<CustomTooltip metric={metric} />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "#94a3b8", cursor: "pointer" }}
          iconType="line"
          onClick={(e: any) => toggle(e.dataKey as string)}
          formatter={(value: string) => (
            <span className={hidden.has(value) ? "text-slate-600 line-through" : ""}>{MODEL_LABELS[value] ?? value}</span>
          )}
        />
        {modelTypes.map((modelType) => (
          <Line
            key={modelType}
            type="monotone"
            dataKey={modelType}
            stroke={MODEL_COLORS[modelType] ?? "#94a3b8"}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
            hide={hidden.has(modelType)}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
