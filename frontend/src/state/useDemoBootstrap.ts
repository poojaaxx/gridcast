import { useRef, useState } from "react";
import { api } from "../services/api";
import { useRegion } from "../hooks/useRegion";
import { useToast } from "../hooks/useToast";

const MODEL_TYPES = ["seasonal_naive", "linear_regression", "lightgbm"];
const DEFAULT_REGION = "demo-region";
// Ingest + 3x(train + 2x generate) + score = 1 + 3*3 + 1 = 11 discrete steps.
const TOTAL_STEPS = 1 + MODEL_TYPES.length * 3 + 1;

export function useDemoBootstrap() {
  const { refetch: refetchRegions, setRegionName } = useRegion();
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const runningRef = useRef(false);

  async function run(regionName: string = DEFAULT_REGION) {
    if (runningRef.current) return; // guard against duplicate concurrent runs
    runningRef.current = true;
    setRunning(true);
    setError(null);
    setProgress(0);
    let completed = 0;
    const advance = (label: string) => {
      completed += 1;
      setStep(label);
      setProgress(Math.round((completed / TOTAL_STEPS) * 100));
    };

    try {
      advance("Ingesting ~200 days of load & weather data…");
      await api.data.ingest(regionName, 200);
      refetchRegions();
      setRegionName(regionName);

      for (const modelType of MODEL_TYPES) {
        advance(`Training ${modelType.replace(/_/g, " ")} model…`);
        const version = await api.models.train(regionName, modelType);

        advance(`Generating 24h forecast (${modelType.replace(/_/g, " ")})…`);
        await api.forecasts.generate(regionName, version.version, 24);

        advance(`Generating 48h forecast (${modelType.replace(/_/g, " ")})…`);
        await api.forecasts.generate(regionName, version.version, 48);
      }

      advance("Scoring historical forecasts…");
      await api.evaluation.score(regionName);

      setStep("Done");
      setProgress(100);
      toast.success("Demo data generated", "History ingested, 3 models trained, forecasts scored.");
    } catch (err: any) {
      const message = err?.message ?? "Demo bootstrap failed. Check backend logs.";
      setError(message);
      toast.error("Demo generation failed", message);
      throw err;
    } finally {
      setRunning(false);
      runningRef.current = false;
    }
  }

  return { run, running, step, progress, error };
}
