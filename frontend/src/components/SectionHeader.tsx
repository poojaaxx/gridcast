import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

/** Consistent panel/section heading used across every chart & table block. */
export default function SectionHeader({ title, subtitle, actions }: Props) {
  return (
    <div className="panel-header">
      <div className="min-w-0">
        <h2 className="font-semibold text-slate-200 text-sm truncate">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}
