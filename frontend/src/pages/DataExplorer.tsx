import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ChevronLeft, ChevronRight, Database, Gauge, Thermometer, Zap } from "lucide-react";
import Topbar from "../components/Topbar";
import DateRangeSelector from "../components/DateRangeSelector";
import SegmentedControl from "../components/SegmentedControl";
import ChartContainer from "../components/ChartContainer";
import MetricCard from "../components/MetricCard";
import LoadingState from "../components/LoadingState";
import EmptyState from "../components/EmptyState";
import { useAsync } from "../hooks/useAsync";
import { useAuth } from "../hooks/useAuth";
import { useRegion } from "../hooks/useRegion";
import { usePageRefresh } from "../hooks/usePageRefresh";
import { api } from "../services/api";
import { useDemoBootstrap } from "../state/useDemoBootstrap";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PAGE_SIZE = 20;

function tooltipStyle() {
  return {
    contentStyle: { background: "#0d1219", border: "1px solid #1a2332", borderRadius: 8, fontSize: 12 },
    labelStyle: { color: "#94a3b8" },
  };
}

type SeriesToggle = "load" | "temperature" | "humidity";

export default function DataExplorer() {
  const { region } = useRegion();
  const { isAdmin } = useAuth();
  const [rangeDays, setRangeDays] = useState(30);
  const [view, setView] = useState<"chart" | "table">("chart");
  const [visibleSeries, setVisibleSeries] = useState<Set<SeriesToggle>>(new Set(["load", "temperature"]));
  const [page, setPage] = useState(0);
  const bootstrap = useDemoBootstrap();

  // A new range/region has a different number of pages entirely - always
  // land back on the most recent page rather than an arbitrary stale index.
  useEffect(() => setPage(0), [region?.id, rangeDays]);

  const query = useAsync(async () => {
    if (!region) return { load: [], weather: [] };
    const end = new Date();
    const start = new Date(end.getTime() - rangeDays * 24 * 3600 * 1000);
    const [load, weather] = await Promise.all([
      api.data.load(region.name, start.toISOString(), end.toISOString(), 10000),
      api.data.weather(region.name, start.toISOString(), end.toISOString(), 10000),
    ]);
    return { load, weather };
  }, [region?.id, rangeDays]);

  const { refresh, refreshing } = usePageRefresh([query.refetch]);

  const load = query.data?.load ?? [];
  const weather = query.data?.weather ?? [];

  const weatherByTs = useMemo(() => new Map(weather.map((w) => [w.timestamp, w])), [weather]);

  const joined = useMemo(
    () =>
      load.map((l) => {
        const w = weatherByTs.get(l.timestamp);
        return {
          timestamp: l.timestamp,
          load_mw: l.load_mw,
          source: l.source,
          temperature_c: w?.temperature_c ?? null,
          humidity_percent: w?.humidity_percent ?? null,
        };
      }),
    [load, weatherByTs]
  );

  const timeSeries = useMemo(
    () =>
      joined.map((row) => ({
        timestamp: row.timestamp,
        load: visibleSeries.has("load") ? row.load_mw : undefined,
        temperature: visibleSeries.has("temperature") ? row.temperature_c ?? undefined : undefined,
        humidity: visibleSeries.has("humidity") ? row.humidity_percent ?? undefined : undefined,
      })),
    [joined, visibleSeries]
  );

  const tempVsLoad = useMemo(() => {
    return load
      .filter((l) => weatherByTs.has(l.timestamp))
      .map((l) => ({ temperature: weatherByTs.get(l.timestamp)!.temperature_c, load: l.load_mw }));
  }, [load, weatherByTs]);

  const hourlyProfile = useMemo(() => {
    const buckets = Array.from({ length: 24 }, (_, hour) => ({ hour, total: 0, count: 0 }));
    for (const l of load) {
      const hour = new Date(l.timestamp).getUTCHours();
      buckets[hour].total += l.load_mw;
      buckets[hour].count += 1;
    }
    return buckets.map((b) => ({ hour: `${b.hour}:00`, avgLoad: b.count ? Math.round(b.total / b.count) : 0 }));
  }, [load]);

  const weeklyProfile = useMemo(() => {
    const buckets = Array.from({ length: 7 }, (_, day) => ({ day, total: 0, count: 0 }));
    for (const l of load) {
      const jsDay = new Date(l.timestamp).getUTCDay();
      const day = (jsDay + 6) % 7;
      buckets[day].total += l.load_mw;
      buckets[day].count += 1;
    }
    return buckets.map((b) => ({ day: DAY_LABELS[b.day], avgLoad: b.count ? Math.round(b.total / b.count) : 0 }));
  }, [load]);

  const stats = useMemo(() => {
    if (load.length === 0) return null;
    const loads = load.map((l) => l.load_mw);
    const temps = weather.map((w) => w.temperature_c);
    return {
      avgLoad: loads.reduce((a, b) => a + b, 0) / loads.length,
      peakLoad: Math.max(...loads),
      avgTemp: temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null,
      count: load.length,
      coveragePct: load.length ? Math.round((joined.filter((r) => r.temperature_c !== null).length / load.length) * 100) : 0,
    };
  }, [load, weather, joined]);

  if (!region) return <LoadingState label="Loading region…" />;

  const pageCount = Math.max(1, Math.ceil(joined.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const tableRows = [...joined].reverse().slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  function toggleSeries(key: SeriesToggle) {
    setVisibleSeries((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title="Data Explorer"
        subtitle="Raw load & weather observations"
        onRefresh={refresh}
        refreshing={refreshing}
        lastUpdated={query.updatedAt}
      />

      <div className="p-4 md:p-6 space-y-6">
        {query.loading ? (
          <LoadingState />
        ) : query.error ? (
          <div className="panel p-8">
            <EmptyState title="Unable to load data" description={query.error} actionLabel="Retry" onAction={refresh} />
          </div>
        ) : load.length === 0 ? (
          <EmptyState
            title="No observations in range"
            description="An administrator can populate load and weather history for this region from the Admin Console."
            icon={Database}
            actionLabel={isAdmin ? "Generate Demo Data" : undefined}
            actionPendingLabel={bootstrap.step ?? "Working…"}
            onAction={isAdmin ? () => bootstrap.run(region.name) : undefined}
            actionPending={bootstrap.running}
            progress={bootstrap.progress}
            secondary={
              !isAdmin ? (
                <p className="text-xs text-slate-500">
                  <Link to="/login" className="text-accent-400 hover:underline">
                    Sign in as an administrator
                  </Link>{" "}
                  to generate data.
                </p>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard label="Avg Load" value={stats ? Math.round(stats.avgLoad).toLocaleString() : "—"} unit="MW" icon={Zap} accent="teal" />
              <MetricCard label="Peak Load" value={stats ? Math.round(stats.peakLoad).toLocaleString() : "—"} unit="MW" icon={Gauge} accent="amber" />
              <MetricCard label="Avg Temperature" value={stats?.avgTemp != null ? stats.avgTemp.toFixed(1) : "—"} unit="°C" icon={Thermometer} accent="slate" />
              <MetricCard label="Data Points" value={stats ? stats.count.toLocaleString() : "—"} unit={stats ? `${stats.coveragePct}% w/ weather` : undefined} icon={Database} accent="success" />
            </div>

            <div className="panel p-4 flex flex-wrap items-center gap-4">
              <DateRangeSelector value={rangeDays} onChange={setRangeDays} />
              <div className="flex items-center gap-1.5">
                {(["load", "temperature", "humidity"] as SeriesToggle[]).map((key) => {
                  const active = visibleSeries.has(key);
                  const colors: Record<SeriesToggle, string> = { load: "#2dd4bf", temperature: "#fbbf24", humidity: "#38bdf8" };
                  return (
                    <button
                      key={key}
                      onClick={() => toggleSeries(key)}
                      aria-pressed={active}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-2xs font-medium capitalize transition-colors ${
                        active ? "border-base-600 text-slate-300 bg-base-800" : "border-base-700/50 text-slate-600"
                      }`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: active ? colors[key] : "#475569" }} />
                      {key}
                    </button>
                  );
                })}
              </div>
              <div className="sm:ml-auto">
                <SegmentedControl
                  aria-label="View"
                  value={view}
                  onChange={setView}
                  options={[
                    { label: "Chart", value: "chart" },
                    { label: "Table", value: "table" },
                  ]}
                />
              </div>
            </div>

            {view === "chart" ? (
              <ChartContainer title="Load & Weather Over Time" subtitle="Toggle series above to focus the chart" height={320}>
                <ResponsiveContainer width="100%" height={320}>
                  <ComposedChart data={timeSeries} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      stroke="#475569"
                      tick={{ fill: "#64748b", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#1a2332" }}
                      minTickGap={50}
                    />
                    <YAxis yAxisId="load" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={52} />
                    <YAxis yAxisId="secondary" orientation="right" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip
                      {...tooltipStyle()}
                      labelFormatter={(v) => new Date(v).toLocaleString()}
                      formatter={(value: number, name: string) => [
                        typeof value === "number" ? value.toFixed(1) : value,
                        name === "load" ? "Load (MW)" : name === "temperature" ? "Temp (°C)" : "Humidity (%)",
                      ]}
                    />
                    {visibleSeries.has("load") && <Line yAxisId="load" type="monotone" dataKey="load" stroke="#2dd4bf" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />}
                    {visibleSeries.has("temperature") && <Line yAxisId="secondary" type="monotone" dataKey="temperature" stroke="#fbbf24" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />}
                    {visibleSeries.has("humidity") && <Line yAxisId="secondary" type="monotone" dataKey="humidity" stroke="#38bdf8" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />}
                  </ComposedChart>
                </ResponsiveContainer>
              </ChartContainer>
            ) : (
              <div className="panel">
                <div className="panel-header">
                  <h2 className="font-medium text-slate-200 text-sm">Observations</h2>
                  <span className="text-xs text-slate-500">
                    {joined.length.toLocaleString()} rows · page {currentPage + 1} of {pageCount}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-base-700/60 text-left">
                        <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Timestamp</th>
                        <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider text-right">Load (MW)</th>
                        <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider text-right">Temp (°C)</th>
                        <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider text-right">Humidity (%)</th>
                        <th className="px-4 py-2.5 font-medium text-slate-500 text-2xs uppercase tracking-wider">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tableRows.map((row) => (
                        <tr key={row.timestamp} className="border-b border-base-700/30 last:border-0 hover:bg-base-800/50">
                          <td className="px-4 py-2.5 text-slate-300 whitespace-nowrap">{new Date(row.timestamp).toLocaleString()}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-200">{Math.round(row.load_mw).toLocaleString()}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-400">{row.temperature_c != null ? row.temperature_c.toFixed(1) : "—"}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-400">{row.humidity_percent != null ? Math.round(row.humidity_percent) : "—"}</td>
                          <td className="px-4 py-2.5">
                            <span className="badge bg-base-700/50 text-slate-400">{row.source}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between px-4 py-3 border-t border-base-700/60">
                  <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={currentPage === 0} className="btn-ghost px-2 py-1.5">
                    <ChevronLeft className="h-4 w-4" /> Prev
                  </button>
                  <span className="text-xs text-slate-500">
                    Page {currentPage + 1} / {pageCount}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={currentPage >= pageCount - 1}
                    className="btn-ghost px-2 py-1.5"
                  >
                    Next <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ChartContainer title="Temperature vs. Load" subtitle="Cooling/heating sensitivity" height={280}>
                <ResponsiveContainer width="100%" height={280}>
                  <ScatterChart margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" />
                    <XAxis dataKey="temperature" name="Temperature" unit="°C" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} />
                    <YAxis dataKey="load" name="Load" unit="MW" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} width={56} />
                    <ZAxis range={[12, 12]} />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} {...tooltipStyle()} />
                    <Scatter data={tempVsLoad} fill="#2dd4bf" fillOpacity={0.35} />
                  </ScatterChart>
                </ResponsiveContainer>
              </ChartContainer>

              <ChartContainer title="Hourly Load Profile" subtitle="Average by hour of day (UTC)" height={280}>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={hourlyProfile}>
                    <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="hour" stroke="#475569" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#1a2332" }} interval={2} />
                    <YAxis stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={48} />
                    <Tooltip {...tooltipStyle()} />
                    <Bar dataKey="avgLoad" name="Avg Load (MW)" fill="#60a5fa" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>

              <ChartContainer title="Weekly Seasonality" subtitle="Average load by day of week" className="lg:col-span-2" height={240}>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={weeklyProfile}>
                    <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="day" stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1a2332" }} />
                    <YAxis stroke="#475569" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={48} />
                    <Tooltip {...tooltipStyle()} />
                    <Bar dataKey="avgLoad" name="Avg Load (MW)" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
