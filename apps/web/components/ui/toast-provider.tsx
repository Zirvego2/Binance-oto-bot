"use client";

import * as React from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  push: (toast: Omit<ToastItem, "id">) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

let idCounter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const push = React.useCallback((toast: Omit<ToastItem, "id">) => {
    const id = ++idCounter;
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed z-[100] flex w-full flex-col gap-2 px-3 pb-[calc(4.5rem+env(safe-area-inset-bottom))] pt-3 sm:bottom-4 sm:right-4 sm:max-w-sm sm:p-0 sm:pb-0 md:pb-0 bottom-0 left-0 right-0 sm:left-auto">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-lg border p-3 shadow-lg backdrop-blur sm:max-w-sm",
              toast.variant === "success" && "border-success/40 bg-success/10",
              toast.variant === "error" && "border-destructive/40 bg-destructive/10",
              toast.variant === "info" && "border-border bg-card"
            )}
          >
            {toast.variant === "success" && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
            {toast.variant === "error" && <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />}
            {toast.variant === "info" && <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
            <div className="flex-1 text-sm">
              <p className="font-medium">{toast.title}</p>
              {toast.description && <p className="mt-0.5 text-xs text-muted-foreground">{toast.description}</p>}
            </div>
            <button onClick={() => dismiss(toast.id)} className="text-muted-foreground hover:text-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast, ToastProvider icinde kullanilmalidir");
  return ctx;
}
