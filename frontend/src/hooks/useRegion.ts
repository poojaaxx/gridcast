import { createContext, useContext } from "react";
import type { Region } from "../types";

interface RegionContextValue {
  region: Region | null;
  regions: Region[];
  setRegionName: (name: string) => void;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export const RegionContext = createContext<RegionContextValue>({
  region: null,
  regions: [],
  setRegionName: () => {},
  loading: true,
  error: null,
  refetch: () => {},
});

export function useRegion(): RegionContextValue {
  return useContext(RegionContext);
}
