"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";


/**
 * Sistema de toast leve, sem libs externas.
 *
 * Uso:
 *   const { toast } = useToast();
 *   toast.success("Usuário criado");
 *   toast.error("Falhou: ...", { duration: 8000 });
 *
 * Toasts ficam empilhados no canto inferior direito. Auto-fade após
 * `duration` (default 4s). Erros têm default maior (6s) e podem ser
 * dispensados manualmente.
 */

type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: string;
  variant: ToastVariant;
  message: string;
  duration: number;
}

interface ToastApi {
  success: (msg: string, opts?: { duration?: number }) => void;
  error: (msg: string, opts?: { duration?: number }) => void;
  info: (msg: string, opts?: { duration?: number }) => void;
}

const ToastContext = createContext<{ toast: ToastApi } | null>(null);


export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (variant: ToastVariant, message: string, duration: number) => {
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `t-${Date.now()}-${Math.random()}`;
      setItems((prev) => [...prev, { id, variant, message, duration }]);
    },
    []
  );

  const api: ToastApi = {
    success: (msg, opts) => push("success", msg, opts?.duration ?? 4000),
    error: (msg, opts) => push("error", msg, opts?.duration ?? 6000),
    info: (msg, opts) => push("info", msg, opts?.duration ?? 4000),
  };

  return (
    <ToastContext.Provider value={{ toast: api }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 w-full max-w-sm pointer-events-none"
        aria-live="polite"
        aria-atomic="false"
      >
        {items.map((item) => (
          <ToastView key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}


export function useToast(): { toast: ToastApi } {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast precisa estar dentro de <ToastProvider>");
  }
  return ctx;
}


function ToastView({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: () => void;
}) {
  // Auto-dismiss após duration. Pause on hover não implementado (simples).
  useEffect(() => {
    const id = window.setTimeout(onDismiss, item.duration);
    return () => window.clearTimeout(id);
  }, [item.duration, onDismiss]);

  const Icon =
    item.variant === "success"
      ? CheckCircle2
      : item.variant === "error"
        ? XCircle
        : Info;

  const tone =
    item.variant === "success"
      ? "border-green-500/30 bg-green-500/10 text-green-700"
      : item.variant === "error"
        ? "border-destructive/30 bg-destructive/10 text-destructive"
        : "border-primary/30 bg-primary/10 text-primary";

  return (
    <div
      role={item.variant === "error" ? "alert" : "status"}
      className={`pointer-events-auto flex items-start gap-2 rounded-md border bg-card px-3 py-2.5 text-sm shadow-lg animate-in slide-in-from-right ${tone}`}
    >
      <Icon className="h-4 w-4 mt-0.5 shrink-0" />
      <div className="flex-1 break-words leading-relaxed text-foreground">
        {item.message}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 rounded-sm opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Fechar notificação"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
