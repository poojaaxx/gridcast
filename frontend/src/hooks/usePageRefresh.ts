import { useCallback, useRef, useState } from "react";
import { useToast } from "./useToast";

/** Combines several useAsync `refetch()` calls into one "Refresh" button
 * action: shows a spinner, blocks duplicate rapid clicks, and toasts the
 * outcome. Pass the refetch functions of every query the page depends on. */
export function usePageRefresh(refetchers: Array<() => Promise<void>>) {
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const busyRef = useRef(false);

  const refresh = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setRefreshing(true);
    try {
      await Promise.all(refetchers.map((fn) => fn()));
      toast.success("Data refreshed");
    } catch {
      toast.error("Refresh failed", "One or more requests could not be completed.");
    } finally {
      setRefreshing(false);
      busyRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, refetchers);

  return { refresh, refreshing };
}
