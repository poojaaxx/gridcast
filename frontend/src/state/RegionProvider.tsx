import { useEffect, useMemo, useState, type ReactNode } from "react";
import { RegionContext } from "../hooks/useRegion";
import { api } from "../services/api";
import type { Region } from "../types";

const STORAGE_KEY = "gridcast:selected-region";

export default function RegionProvider({ children }: { children: ReactNode }) {
  const [regions, setRegions] = useState<Region[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api
      .regions.list()
      .then((data) => {
        if (!mounted) return;
        setRegions(data);
        setError(null);
        if (data.length > 0 && !data.some((r) => r.name === selectedName)) {
          setSelectedName(data[0].name);
        }
      })
      .catch((err) => mounted && setError(err.message ?? "Failed to load regions"))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  useEffect(() => {
    if (selectedName) localStorage.setItem(STORAGE_KEY, selectedName);
  }, [selectedName]);

  const region = useMemo(() => regions.find((r) => r.name === selectedName) ?? regions[0] ?? null, [regions, selectedName]);

  return (
    <RegionContext.Provider
      value={{
        region,
        regions,
        setRegionName: setSelectedName,
        loading,
        error,
        refetch: () => setVersion((v) => v + 1),
      }}
    >
      {children}
    </RegionContext.Provider>
  );
}
