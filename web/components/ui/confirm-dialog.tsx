"use client";

import { useEffect } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";


/**
 * Modal de confirmação consistente com o tema do app.
 * Substitui `window.confirm()` em fluxos destrutivos.
 *
 * Uso:
 *   const [open, setOpen] = useState(false);
 *   ...
 *   <ConfirmDialog
 *     open={open}
 *     title="Apagar arquivo"
 *     description="Esta ação não pode ser desfeita."
 *     confirmLabel="Apagar"
 *     destructive
 *     onConfirm={async () => { await deletar(); setOpen(false); }}
 *     onCancel={() => setOpen(false)}
 *   />
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  destructive = false,
  loading = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string | React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  // ESC fecha (só se não está em loading — evita cancelar ação em curso).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, loading, onCancel]);

  if (!open) return null;

  return (
    <>
      <div
        onClick={loading ? undefined : onCancel}
        className="fixed inset-0 z-50 bg-black/50 animate-in fade-in"
        aria-hidden
      />
      <div
        role="alertdialog"
        aria-modal
        aria-labelledby="confirm-title"
        aria-describedby="confirm-desc"
        className="fixed left-1/2 top-1/2 z-50 w-[95vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-card border shadow-xl"
      >
        <header className="flex items-start justify-between gap-3 p-4 border-b">
          <div className="flex items-start gap-3">
            <div
              className={`shrink-0 rounded-full p-1.5 ${
                destructive
                  ? "bg-destructive/10 text-destructive"
                  : "bg-primary/10 text-primary"
              }`}
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <h2 id="confirm-title" className="font-semibold text-base mt-0.5">
              {title}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onCancel}
            disabled={loading}
            title="Fechar"
            className="-mt-1 -mr-1 h-7 w-7"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div id="confirm-desc" className="px-4 py-4 text-sm text-muted-foreground">
          {description}
        </div>

        <footer className="flex justify-end gap-2 p-4 border-t bg-muted/20 rounded-b-lg">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </Button>
        </footer>
      </div>
    </>
  );
}
