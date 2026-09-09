import { createContext, useContext } from "react";

export type ToastVariant = "success" | "error" | "info";

export interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** ms before auto-dismiss; 0 disables auto-dismiss */
  duration?: number;
}

export interface ToastContextValue {
  show: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
  success: (title: string, description?: string) => string;
  error: (title: string, description?: string) => string;
  info: (title: string, description?: string) => string;
}

export const ToastContext = createContext<ToastContextValue>({
  show: () => "",
  dismiss: () => {},
  success: () => "",
  error: () => "",
  info: () => "",
});

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}
