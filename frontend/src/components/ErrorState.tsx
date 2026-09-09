import { RefreshCw, WifiOff } from "lucide-react";

interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
}

export default function ErrorState({ title = "Unable to load data", message, onRetry, retrying }: Props) {
  return (
    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center gap-3 py-16 text-center animate-in">
      <div className="rounded-full bg-danger-500/10 p-3">
        <WifiOff className="h-5 w-5 text-danger-400" aria-hidden="true" />
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-200">{title}</p>
        <p className="max-w-sm text-xs text-slate-500 mt-1">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} disabled={retrying} className="btn-secondary mt-1 px-3 py-1.5">
          <RefreshCw className={`h-3.5 w-3.5 ${retrying ? "animate-spin" : ""}`} />
          {retrying ? "Retrying…" : "Retry"}
        </button>
      )}
    </div>
  );
}
