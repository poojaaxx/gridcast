import { useCallback, useRef, useState } from "react";
import { ApiError } from "../services/api";

interface AsyncActionState<R> {
  running: boolean;
  error: string | null;
  result: R | null;
  completedAt: number | null;
}

/** Shared plumbing for every Admin Console action button: guards against
 * duplicate concurrent clicks, tracks a loading/error/result/timestamp
 * state so the UI can show exactly what happened and when. */
export function useAsyncAction<Args extends unknown[], R>(fn: (...args: Args) => Promise<R>) {
  const [state, setState] = useState<AsyncActionState<R>>({ running: false, error: null, result: null, completedAt: null });
  const busyRef = useRef(false);

  const run = useCallback(
    async (...args: Args): Promise<R | undefined> => {
      if (busyRef.current) return undefined;
      busyRef.current = true;
      setState((prev) => ({ ...prev, running: true, error: null }));
      try {
        const result = await fn(...args);
        setState({ running: false, error: null, result, completedAt: Date.now() });
        return result;
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Something went wrong. Is the backend running?";
        setState((prev) => ({ ...prev, running: false, error: message, completedAt: Date.now() }));
        throw err;
      } finally {
        busyRef.current = false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fn]
  );

  return { ...state, run };
}
