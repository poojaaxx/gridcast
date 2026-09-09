import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionLabel?: string;
  onAction?: () => void;
  actionPending?: boolean;
  actionPendingLabel?: string;
  /** 0-100. When provided alongside actionPending, renders a progress bar. */
  progress?: number;
  secondary?: ReactNode;
}

export default function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  actionLabel,
  onAction,
  actionPending,
  actionPendingLabel = "Working…",
  progress,
  secondary,
}: Props) {
  return (
    <div className="flex h-full min-h-[240px] w-full flex-col items-center justify-center gap-3 py-16 text-center animate-in">
      <div className="rounded-full bg-accent-500/10 p-3">
        <Icon className="h-5 w-5 text-accent-400" aria-hidden="true" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        <p className="max-w-sm text-xs text-slate-500 mt-1 leading-relaxed">{description}</p>
      </div>
      {actionLabel && onAction && (
        <button onClick={onAction} disabled={actionPending} className="btn-primary mt-2 px-4 py-2">
          {actionPending ? actionPendingLabel : actionLabel}
        </button>
      )}
      {actionPending && typeof progress === "number" && (
        <div className="w-full max-w-[220px] mt-1">
          <div className="h-1.5 w-full rounded-full bg-base-700 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-accent-600 to-accent-400 transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-2xs text-slate-600 mt-1.5 tabular-nums">{progress}%</p>
        </div>
      )}
      {secondary}
    </div>
  );
}
