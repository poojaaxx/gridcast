import type { ReactNode } from "react";
import SectionHeader from "./SectionHeader";
import { SkeletonChart } from "./Skeleton";
import ErrorState from "./ErrorState";
import EmptyState from "./EmptyState";

interface Props {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  height?: number;
  children: ReactNode;
  className?: string;
}

/** Standard panel shell used by every chart on every page: consistent header,
 * plus one code path for loading / error / empty so pages don't hand-roll it. */
export default function ChartContainer({
  title,
  subtitle,
  actions,
  loading,
  error,
  onRetry,
  isEmpty,
  emptyTitle = "No data yet",
  emptyDescription = "There's nothing to show for the current selection.",
  emptyAction,
  height = 300,
  children,
  className,
}: Props) {
  return (
    <div className={`panel ${className ?? ""}`}>
      <SectionHeader title={title} subtitle={subtitle} actions={actions} />
      <div className="p-4">
        {loading ? (
          <SkeletonChart height={height} />
        ) : error ? (
          <ErrorState message={error} onRetry={onRetry} />
        ) : isEmpty ? (
          <EmptyState title={emptyTitle} description={emptyDescription} secondary={emptyAction} />
        ) : (
          <div className="animate-in">{children}</div>
        )}
      </div>
    </div>
  );
}
