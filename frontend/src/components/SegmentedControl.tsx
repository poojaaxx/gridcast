import clsx from "clsx";

export interface SegmentOption<T extends string | number> {
  label: string;
  value: T;
}

interface Props<T extends string | number> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
  "aria-label"?: string;
}

/** Generic pill toggle group - used for horizon (24h/48h), metric tabs, granularity, etc. */
export default function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  size = "sm",
  ...aria
}: Props<T>) {
  return (
    <div
      role="tablist"
      aria-label={aria["aria-label"]}
      className="inline-flex items-center rounded-lg border border-base-700 bg-base-850 p-0.5"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={clsx(
              "rounded-md font-medium transition-colors duration-150",
              size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
              active ? "bg-accent-500 text-base-950" : "text-slate-400 hover:text-slate-200"
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
