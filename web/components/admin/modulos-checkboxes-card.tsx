"use client";

import { useEffect, useState } from "react";
import { Package, Loader2 } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, adminListarModulos } from "@/lib/api";
import type { ModuloInfo } from "@/lib/types";


/**
 * Card reutilizável para configurar quais módulos do SaaS o tenant contratou.
 *
 * O catálogo é carregado do backend (`GET /admin/modulos`) — nunca hardcoded
 * no frontend, pra evitar drift entre as duas listas.
 *
 * Uso:
 *   <ModulosContratadosCard value={modulos} onChange={setModulos} />
 *
 * - check  → `value[slug] = true`
 * - uncheck → remove `slug` do objeto (o backend trata ausente como não contratado)
 */
export function ModulosContratadosCard({
  value,
  onChange,
}: {
  value: Record<string, boolean>;
  onChange: (v: Record<string, boolean>) => void;
}) {
  const [catalogo, setCatalogo] = useState<ModuloInfo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    adminListarModulos()
      .then(setCatalogo)
      .catch((err) => setErro(err instanceof ApiError ? err.message : String(err)));
  }, []);

  function toggle(slug: string, ativo: boolean) {
    const next = { ...value };
    if (ativo) {
      next[slug] = true;
    } else {
      delete next[slug];
    }
    onChange(next);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Package className="h-4 w-4 text-primary" /> Módulos contratados
        </CardTitle>
        <CardDescription>
          Marque os módulos do SaaS Bella que este cliente contratou. O acesso
          às funcionalidades correspondentes é liberado conforme a marcação.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {erro && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {erro}
          </div>
        )}
        {!catalogo && !erro && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Carregando catálogo...
          </div>
        )}
        {catalogo && catalogo.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nenhum módulo no catálogo.
          </p>
        )}
        {catalogo &&
          catalogo.map((mod) => {
            const ativo = !!value[mod.slug];
            return (
              <label
                key={mod.slug}
                className={`flex items-start gap-3 rounded-md border p-3 cursor-pointer transition-colors ${
                  ativo ? "border-primary bg-primary/5" : "hover:bg-accent/30"
                }`}
              >
                <input
                  type="checkbox"
                  checked={ativo}
                  onChange={(e) => toggle(mod.slug, e.target.checked)}
                  className="h-4 w-4 mt-0.5 rounded"
                />
                <div className="min-w-0">
                  <div className="font-medium text-sm">
                    {mod.label}{" "}
                    <code className="text-xs text-muted-foreground font-mono">
                      ({mod.slug})
                    </code>
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {mod.descricao}
                  </div>
                </div>
              </label>
            );
          })}
      </CardContent>
    </Card>
  );
}
