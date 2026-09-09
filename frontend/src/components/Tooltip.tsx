import clsx from "clsx";
import type { ReactNode } from "react";

interface Props {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
  /** Use "flex w-full" when wrapping a full-width control (e.g. a sidebar button). */
  className?: string;
}

/** Lightweight hover tooltip for icon-only controls. The wrapped control still
 * needs its own aria-label - this is a visual aid, not the accessible name. */
export default function Tooltip({ label, children, side = "bottom", className }: Props) {
  return (
    <span className={clsx("relative group", className ?? "inline-flex")}>
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-base-700 bg-base-850 px-2 py-1 text-2xs font-medium text-slate-300 opacity-0 shadow-elevated transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 z-50 ${
          side === "bottom" ? "top-full mt-1.5" : "bottom-full mb-1.5"
        }`}
      >
        {label}
      </span>
    </span>
  );
}
