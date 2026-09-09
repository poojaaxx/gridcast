import { Loader2 } from "lucide-react";

export default function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center gap-3 py-16 text-slate-500">
      <Loader2 className="h-6 w-6 animate-spin text-accent-500" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
