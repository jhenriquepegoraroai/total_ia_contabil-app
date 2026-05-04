"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { lerSessao } from "@/lib/auth";


/**
 * Bella Atas — placeholder da Fase 2 (bootstrap).
 *
 * Por ora, só lista atas (vem vazio na primeira execução). Fluxo completo
 * de gravação → geração → workflow multi-ator chega na Fase 8.
 *
 * Não usa a API ainda — só renderiza o frame e checa autenticação. A
 * primeira chamada real à `/api/atas` será adicionada quando o cliente
 * de API ganhar `cobrancasListarJobs`-equivalente para atas.
 */
export default function AtasPage() {
  const router = useRouter();
  const [carregando, setCarregando] = useState(true);

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
    setCarregando(false);
  }, [router]);

  if (carregando) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </main>
    );
  }

  return (
    <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <FileText className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Bella Atas</h1>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Geração e revisão de atas de assembleia condominial. Em
          construção — fases 3 a 9 do roadmap.
        </p>
      </header>

      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          <FileText className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium text-foreground">Nenhuma ata ainda</p>
          <p className="text-sm mt-1">
            O fluxo de gravação e geração será habilitado nas próximas fases.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
