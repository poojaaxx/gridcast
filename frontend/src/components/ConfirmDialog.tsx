import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Blocking confirmation for expensive/irreversible admin actions (training,
 * large ingestion, demo generation) - prevents an accidental click from
 * kicking off a real operation. */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) confirmRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !busy && onCancel()} aria-hidden="true" />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="relative w-full max-w-sm panel p-5 shadow-elevated animate-in"
      >
        <div className="flex items-start gap-3">
          {danger && (
            <div className="rounded-lg bg-danger-500/10 p-2 flex-shrink-0">
              <AlertTriangle className="h-4.5 w-4.5 text-danger-400" />
            </div>
          )}
          <div className="min-w-0">
            <h2 id="confirm-dialog-title" className="text-sm font-semibold text-slate-100">
              {title}
            </h2>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-5">
          <button onClick={onCancel} disabled={busy} className="btn-secondary px-3 py-1.5">
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={busy}
            className={danger ? "btn px-3 py-1.5 bg-danger-500 text-white hover:bg-danger-600" : "btn-primary px-3 py-1.5"}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
