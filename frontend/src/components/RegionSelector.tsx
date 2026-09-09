import { MapPin } from "lucide-react";
import { useRegion } from "../hooks/useRegion";

/** Global region switcher - changing it updates every page via RegionProvider. */
export default function RegionSelector() {
  const { region, regions, setRegionName, loading } = useRegion();

  if (loading && regions.length === 0) {
    return <div className="skeleton h-8 w-36 rounded-lg" />;
  }
  if (regions.length === 0) return null;

  return (
    <div className="relative">
      <MapPin className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
      <select
        value={region?.name ?? ""}
        onChange={(e) => setRegionName(e.target.value)}
        aria-label="Select region"
        className="input-select appearance-none pl-8 pr-7 cursor-pointer"
      >
        {regions.map((r) => (
          <option key={r.id} value={r.name}>
            {r.name}
          </option>
        ))}
      </select>
    </div>
  );
}
