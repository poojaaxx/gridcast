import SegmentedControl from "./SegmentedControl";

export interface RangeOption {
  label: string;
  days: number;
}

export const DEFAULT_RANGES: RangeOption[] = [
  { label: "7D", days: 7 },
  { label: "14D", days: 14 },
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
];

interface Props {
  value: number;
  onChange: (days: number) => void;
  options?: RangeOption[];
}

export default function DateRangeSelector({ value, onChange, options = DEFAULT_RANGES }: Props) {
  return (
    <SegmentedControl
      aria-label="Date range"
      value={value}
      onChange={onChange}
      options={options.map((o) => ({ label: o.label, value: o.days }))}
    />
  );
}
