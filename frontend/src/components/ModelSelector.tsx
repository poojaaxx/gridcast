import { ChevronDown, Cpu } from "lucide-react";
import { MODEL_COLORS, MODEL_LABELS } from "../types";

interface Props {
  value: string | undefined;
  onChange: (value: string) => void;
  options: string[];
  disabled?: boolean;
}

/** Model-type dropdown, color-coded to match every chart's series color. */
export default function ModelSelector({ value, onChange, options, disabled }: Props) {
  return (
    <div className="relative">
      <Cpu className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
      {value && (
        <span
          className="pointer-events-none absolute left-7 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full"
          style={{ backgroundColor: MODEL_COLORS[value] ?? "#94a3b8" }}
        />
      )}
      <select
        value={value ?? ""}
        disabled={disabled || options.length === 0}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Select model"
        className="input-select appearance-none pl-9 pr-7 cursor-pointer disabled:cursor-not-allowed"
      >
        {options.length === 0 && <option value="">No trained models</option>}
        {options.map((mt) => (
          <option key={mt} value={mt}>
            {MODEL_LABELS[mt] ?? mt}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
    </div>
  );
}
