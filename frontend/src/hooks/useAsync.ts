import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../services/api";

interface AsyncState<T> {
  data: T | null;
  /** true only while there is no data yet (first load / empty region switch) */
  loading: boolean;
  /** true during ANY fetch, including a manual refresh of existing data */
  validating: boolean;
  error: string | null;
  updatedAt: number | null;
}

/** Fetches `fn()` whenever `deps` change; exposes an awaitable `refetch` for
 * manual re-runs (so pages can drive a combined "Refresh" button). */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: React.DependencyList
): AsyncState<T> & { refetch: () => Promise<void> } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, validating: true, error: null, updatedAt: null });
  const requestId = useRef(0);

  const run = useCallback(() => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, validating: true, loading: prev.data === null, error: null }));
    return fn()
      .then((data) => {
        if (id === requestId.current) setState({ data, loading: false, validating: false, error: null, updatedAt: Date.now() });
      })
      .catch((err) => {
        if (id === requestId.current) {
          const message = err instanceof ApiError ? err.message : "Something went wrong. Is the backend running?";
          setState((prev) => ({ ...prev, loading: false, validating: false, error: message }));
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, refetch: run };
}
