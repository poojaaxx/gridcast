import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { EvaluationHistoryRunStatus } from "../types";

const POLL_INTERVAL_MS = 4000;

/** Drives the admin-only "Build Evaluation History" operation. The backend
 * runs this in a background thread and returns immediately (see
 * app/services/evaluation_history_runner.py for why - Render's Free plan
 * has no Shell/Jobs/Cron to run a multi-minute one-off task any other way),
 * so this hook polls /admin/evaluation-history/status rather than waiting
 * on a single long HTTP request. Polling also starts on mount so refreshing
 * the Admin page mid-run reattaches to it instead of losing the state.
 */
export function useEvaluationHistoryRun() {
  const toast = useToast();
  const [state, setState] = useState<EvaluationHistoryRunStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previousStatusRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const result = await api.admin.evaluationHistory.status();
      setState(result);

      if (previousStatusRef.current === "running" && result.status === "completed") {
        toast.success("Evaluation history built", `${result.report?.newly_scored ?? 0} forecast(s) newly scored.`);
      } else if (previousStatusRef.current === "running" && result.status === "failed") {
        toast.error("Evaluation history backfill failed", result.error ?? "Unknown error.");
      }
      previousStatusRef.current = result.status;

      if (result.status !== "running") {
        stopPolling();
      }
    } catch {
      // Transient poll failures aren't surfaced as toasts - the next poll
      // (or the user re-opening the page) will pick the real state back up.
    } finally {
      setLoading(false);
    }
  }, [stopPolling, toast]);

  useEffect(() => {
    poll();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (state?.status === "running" && !pollRef.current) {
      pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    }
    return () => stopPolling();
  }, [state?.status, poll, stopPolling]);

  const start = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      const result = await api.admin.evaluationHistory.run();
      previousStatusRef.current = result.status;
      setState(result);
      if (result.status === "running" && !pollRef.current) {
        pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not start the evaluation history backfill.";
      setStartError(message);
      toast.error("Could not start", message);
    } finally {
      setStarting(false);
    }
  }, [poll, toast]);

  return { state, loading, starting, startError, start };
}
