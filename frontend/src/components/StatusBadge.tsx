import clsx from "clsx";
import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import type { ComponentType } from "react";

export type Status = "healthy" | "warning" | "degraded" | "critical" | "insufficient_data" | "info";

interface StatusConfig {
  label: string;
  icon: ComponentType<{ className?: string }>;
  dot: string;
  text: string;
  bg: string;
  border: string;
}

export const STATUS_CONFIG: Record<Status, StatusConfig> = {
  healthy: { label: "Healthy", icon: CheckCircle2, dot: "bg-success-500", text: "text-success-400", bg: "bg-success-500/10", border: "border-success-500/20" },
  warning: { label: "Warning", icon: AlertTriangle, dot: "bg-warn-500", text: "text-warn-400", bg: "bg-warn-500/10", border: "border-warn-500/20" },
  degraded: { label: "Degraded", icon: XCircle, dot: "bg-danger-500", text: "text-danger-400", bg: "bg-danger-500/10", border: "border-danger-500/20" },
  critical: { label: "Critical", icon: XCircle, dot: "bg-danger-500", text: "text-danger-400", bg: "bg-danger-500/10", border: "border-danger-500/20" },
  insufficient_data: { label: "Collecting Data", icon: HelpCircle, dot: "bg-slate-500", text: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/20" },
  info: { label: "Info", icon: HelpCircle, dot: "bg-info-500", text: "text-info-400", bg: "bg-info-500/10", border: "border-info-500/20" },
};

interface Props {
  status: Status;
  label?: string;
  size?: "sm" | "md";
  withIcon?: boolean;
  pulse?: boolean;
}

export default function StatusBadge({ status, label, size = "sm", withIcon = false, pulse = false }: Props) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.info;
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        "badge border",
        config.bg,
        config.text,
        config.border,
        size === "md" && "px-3 py-1.5 text-xs"
      )}
    >
      {withIcon ? (
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <span className={clsx("h-1.5 w-1.5 rounded-full", config.dot, pulse && "animate-pulseDot")} aria-hidden="true" />
      )}
      {label ?? config.label}
    </span>
  );
}
