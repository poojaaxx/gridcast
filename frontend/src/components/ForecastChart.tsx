import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface ForecastChartPoint {
  timestamp: string;
  actual?: number | null;
  predicted?: number | null;
  lower?: number | null;
  upper?: number | null;
  bandwidth?: number | null;
}

function formatTick(value: string) {
  const date = new Date(value);
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const byKey = Object.fromEntries(payload.map((p: any) => [p.dataKey, p]));
  return (
    <div className="rounded-lg border border-base-700 bg-base-850 px-3 py-2.5 shadow-xl text-xs min-w-[160px]">
      <p className="text-slate-400 mb-1.5 font-medium">{new Date(label).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
      {byKey.actual !== undefined && byKey.actual.value != null && (
        <div className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: byKey.actual.color }} /> Actual
          </span>
          <span className="font-semibold text-slate-100 tabular-nums">{Math.round(byKey.actual.value).toLocaleString()} MW</span>
        </div>
      )}
      {byKey.predicted !== undefined && byKey.predicted.value != null && (
        <div className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: byKey.predicted.color }} /> Forecast
          </span>
          <span className="font-semibold text-slate-100 tabular-nums">{Math.round(byKey.predicted.value).toLocaleString()} MW</span>
        </div>
      )}
      {byKey.lower?.payload?.upper != null && byKey.lower?.payload?.lower != null && (
        <div className="flex items-center justify-between gap-4 py-0.5 border-t border-base-700/60 mt-1 pt-1">
          <span className="text-slate-500">95% interval</span>
          <span className="text-slate-400 tabular-nums">
            {Math.round(byKey.lower.payload.lower).toLocaleString()}–{Math.round(byKey.lower.payload.upper).toLocaleString()}
          </span>
        </div>
      )}
    </div>
  );
}

type SeriesKey = "actual" | "predicted" | "interval";

export default function ForecastChart({ data, height = 340 }: { data: ForecastChartPoint[]; height?: number }) {
  const [hidden, setHidden] = useState<Set<SeriesKey>>(new Set());
  const toggle = (key: SeriesKey) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const prepared = data.map((d) => ({
    ...d,
    bandwidth: d.upper != null && d.lower != null ? d.upper - d.lower : null,
  }));

  const legendItems: { key: SeriesKey; label: string; color: string }[] = [
    { key: "actual", label: "Actual", color: "#e2e8f0" },
    { key: "predicted", label: "Forecast", color: "#2dd4bf" },
    { key: "interval", label: "Prediction Interval", color: "#2dd4bf" },
  ];

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={prepared} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="intervalFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.16} />
              <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTick}
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#1a2332" }}
            minTickGap={40}
          />
          <YAxis
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v) => `${Math.round(v / 100) / 10}k`}
          />
          <Tooltip content={<CustomTooltip />} />

          {!hidden.has("interval") && (
            <>
              <Area dataKey="lower" stackId="interval" stroke="none" fill="transparent" isAnimationActive={false} legendType="none" name="lower" />
              <Area dataKey="bandwidth" stackId="interval" stroke="none" fill="url(#intervalFill)" isAnimationActive={false} name="Prediction Interval" legendType="none" />
            </>
          )}

          <Line
            type="monotone"
            dataKey="actual"
            stroke="#e2e8f0"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            name="Actual"
            connectNulls
            hide={hidden.has("actual")}
            legendType="none"
          />
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#2dd4bf"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            isAnimationActive={false}
            name="Forecast"
            connectNulls
            hide={hidden.has("predicted")}
            legendType="none"
          />
          <Legend content={() => null} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex flex-wrap items-center gap-4 px-2 pt-1">
        {legendItems.map((item) => {
          const isHidden = hidden.has(item.key);
          return (
            <button
              key={item.key}
              onClick={() => toggle(item.key)}
              className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${isHidden ? "text-slate-600" : "text-slate-400 hover:text-slate-200"}`}
              aria-pressed={!isHidden}
            >
              {item.key === "interval" ? (
                <span className="h-2.5 w-2.5 rounded-sm opacity-40" style={{ backgroundColor: item.color }} />
              ) : (
                <span
                  className="h-0.5 w-3.5 rounded-full"
                  style={{ backgroundColor: item.color, borderTop: item.key === "predicted" ? "1px dashed" : undefined }}
                />
              )}
              <span className={isHidden ? "line-through" : ""}>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
