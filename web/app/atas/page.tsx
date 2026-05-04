"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FileText, Loader2, Plus, RefreshCw } from "lucide-react";

import { AtaStatusBadge } from "@/components/atas/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, atasListar } from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type { AtaSummary } from "@/lib/types";


/**
 * Lista de atas do tenant.
 *
 * Polling automático a cada 5s se alguma ata está em estado "vivo"
 * (transcrevendo, gerando, comparando, corrigindo).
 */
const STATUS_POLLING = new Set([
  "aguardando_transcricao",
  "aguardando_geracao",
  "comparando",
  "corrigindo",
]);


export default function AtasListPage() {
  const router = useRouter();
  const [atas, setAtas] = useState<AtaSummary[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [moduloOk, setModuloOk] = useState<boolean | null>(null);

  // Auth + gate de módulo
  useEffect(() => {
    const s = lerSessao();
    if (!s) {
      router.replace("/login");
      return;
    }
    if (s.is_superadmin || s.tenant_id === "_system") {
      router.replace("/admin");
      return;
    }
    if (!s.modulos_contratados.atas) {
      setModuloOk(false);
      return;
    }
    setModuloOk(true);
  }, [router]);

  async function carregar() {
    try {
      setErro(null);
      const data = await atasListar();
      setAtas(data);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    }
  }

  useEffect(() => {
    if (moduloOk === true) {
      carregar();
    }
  }, [moduloOk]);

  // Polling se há atas em estado "vivo".
  useEffect(() => {
    if (!atas) return;
    const ativas = atas.some((a) => STATUS_POLLING.has(a.status));
    if (!ativas) return;
    const id = setInterval(carregar, 5000);
    return () => clearInterval(id);
  }, [atas]);

  if (moduloOk === null) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </main>
    );
  }

  if (moduloOk === false) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center">
            <FileText className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
            <p className="font-semibold">Bella Atas não está habilitado</p>
            <p className="text-sm text-muted-foreground mt-2">
              Seu plano atual não inclui o módulo Bella Atas. Entre em contato
              com sua administradora pra contratar.
            </p>
            <Button asChild variant="outline" className="mt-4">
              <Link href="/">Voltar pro início</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <FileText className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Bella Atas</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Geração e revisão de atas de assembleia condominial.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={carregar}>
            <RefreshCw className="h-4 w-4" /> Atualizar
          </Button>
          <Button asChild>
            <Link href="/atas/nova">
              <Plus className="h-4 w-4" /> Nova ata
            </Link>
          </Button>
        </div>
      </header>

      {erro && (
        <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {atas === null ? (
        <div className="space-y-2">
          <Card><CardContent className="h-20" /></Card>
          <Card><CardContent className="h-20" /></Card>
        </div>
      ) : atas.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            <FileText className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Nenhuma ata ainda</p>
            <p className="text-sm mt-1">
              Clique em "Nova ata" pra começar a primeira.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {atas.map((ata) => (
            <Link
              key={ata.id}
              href={`/atas/${ata.id}`}
              className="block focus:outline-none focus:ring-2 focus:ring-ring rounded-md"
            >
              <Card className="hover:bg-accent/30 transition-colors">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium truncate">{ata.titulo}</span>
                      <AtaStatusBadge status={ata.status} />
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5 flex flex-wrap gap-x-3">
                      {ata.referencia && <span>condomínio {ata.referencia}</span>}
                      <span>· atualizada {new Date(ata.updated_at).toLocaleString("pt-BR")}</span>
                    </div>
                    {ata.erro_detalhe && (
                      <div className="text-xs text-destructive mt-1 truncate" title={ata.erro_detalhe}>
                        {ata.erro_detalhe}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
