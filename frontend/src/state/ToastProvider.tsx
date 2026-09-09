import { useCallback, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { ToastContext, type ToastInput, type ToastVariant } from "../hooks/useToast";

interface Toast extends Required<Pick<ToastInput, "title" | "variant" | "duration">> {
  id: string;
  description?: string;
}

const VARIANT_CONFIG: Record<ToastVariant, { icon: typeof CheckCircle2; classes: string }> = {
  success: { icon: CheckCircle2, classes: "border-success-500/30 text-success-400" },
  error: { icon: AlertTriangle, classes: "border-danger-500/30 text-danger-400" },
  info: { icon: Info, classes: "border-info-500/30 text-info-400" },
};

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (input: ToastInput) => {
      const id = `toast-${++counter.current}-${Date.now()}`;
      const toast: Toast = {
        id,
        title: input.title,
        description: input.description,
        variant: input.variant ?? "info",
        duration: input.duration ?? 4500,
      };
      setToasts((prev) => [...prev, toast]);
      if (toast.duration > 0) {
        setTimeout(() => dismiss(id), toast.duration);
      }
      return id;
    },
    [dismiss]
  );

  const success = useCallback((title: string, description?: string) => show({ title, description, variant: "success" }), [show]);
  const error = useCallback((title: string, description?: string) => show({ title, description, variant: "error", duration: 6000 }), [show]);
  const info = useCallback((title: string, description?: string) => show({ title, description, variant: "info" }), [show]);

  return (
    <ToastContext.Provider value={{ show, dismiss, success, error, info }}>
      {children}
      <div
        className="fixed bottom-5 right-5 z-[100] flex w-full max-w-sm flex-col gap-2.5"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((toast) => {
          const config = VARIANT_CONFIG[toast.variant];
          const Icon = config.icon;
          return (
            <div
              key={toast.id}
              role="status"
              className={`animate-slideInRight pointer-events-auto flex items-start gap-3 rounded-xl border bg-base-850/95 backdrop-blur px-4 py-3 shadow-elevated ${config.classes}`}
            >
              <Icon className="h-4.5 w-4.5 flex-shrink-0 mt-0.5" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-100">{toast.title}</p>
                {toast.description && <p className="mt-0.5 text-xs text-slate-400 leading-relaxed">{toast.description}</p>}
              </div>
              <button
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss notification"
                className="flex-shrink-0 text-slate-500 hover:text-slate-200 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
