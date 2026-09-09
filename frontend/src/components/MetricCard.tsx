import clsx from "clsx";
import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string;
  unit?: string;
  trend?: { value: string; positive: boolean } | null;
  icon?: LucideIcon;
  accent?: "teal" | "amber" | "red" | "slate" | "success";
  loading?: boolean;
}

const ACCENTS: Record<string, string> = {
  teal: "text-accent-400",
  amber: "text-warn-400",
  red: "text-danger-400",
  slate: "text-slate-100",
  success: "text-success-400",
};

const ICON_BG: Record<string, string> = {
  teal: "bg-accent-500/10",
  amber: "bg-warn-500/10",
  red: "bg-danger-500/10",
  slate: "bg-base-700/50",
  success: "bg-success-500/10",
};

export default function MetricCard({ label, value, unit, trend, icon: Icon, accent = "teal", loading }: Props) {
  if (loading) {
    return (
      <div className="panel p-5 flex flex-col gap-3">
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton h-8 w-20 rounded" />
        <div className="skeleton h-3 w-16 rounded" />
      </div>
    );
  }

  return (
    <div className="panel-interactive p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        {Icon && (
          <span className={clsx("rounded-md p-1.5", ICON_BG[accent])}>
            <Icon className={clsx("h-3.5 w-3.5", ACCENTS[accent])} aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className={clsx("metric-value", ACCENTS[accent])}>{value}</span>
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
      {trend && (
        <div className={clsx("flex items-center gap-1 text-xs font-medium", trend.positive ? "text-success-400" : "text-danger-400")}>
          {trend.positive ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
          <span>{trend.value}</span>
        </div>
      )}
    </div>
  );
}
