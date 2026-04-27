"use client";

import { use, useEffect, useState, useRef } from "react";
import {
  CheckCircle2,
  Clock,
  History,
  Loader2,
  PlayCircle,
  XCircle,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, adminListarJobs } from "@/lib/api";
import type { IngestionJob } from "@/lib/types";


export default function JobsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function carregar() {
    try {
      const data = await adminListarJobs(tenantId, 50);
      setJobs(data);
      setErro(null);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [tenantId]);

  // Polling: se há job em queued/running, recarrega a cada 3s.
  useEffect(() => {
    const ativo = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (ativo) {
      intervalRef.current = setInterval(carregar, 3000);
      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }
  }, [jobs]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <History className="h-5 w-5 text-primary" /> Histórico de jobs
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Execuções do pipeline de ingestão. Atualiza automaticamente quando há job rodando.
        </p>
      </div>

      {erro && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <History className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Sem jobs ainda</p>
            <p className="text-sm mt-1">
              Vá em "Fontes de dados", suba PDFs e clique em "Executar ingestão".
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {jobs.map((j) => (
                <JobRow key={j.id} job={j} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}


function JobRow({ job }: { job: IngestionJob }) {
  return (
    <li className="px-4 py-3 flex items-start gap-3 text-sm">
      <StatusBadge status={job.status} />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <span className="font-medium">{job.source_name ?? "—"}</span>
          {job.referencia && (
            <span className="text-muted-foreground">
              ref <code className="text-xs">{job.referencia}</code>
            </span>
          )}
          {job.actor_email && (
            <span className="text-xs text-muted-foreground truncate">
              por {job.actor_email}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
          <span>{job.qtde_chunks_origem} chunks origem</span>
          <span>·</span>
          <span className="text-green-700">{job.qtde_processada} processados</span>
          <span>·</span>
          <span>{job.qtde_skipped} skipados</span>
          {job.qtde_erros > 0 && (
            <>
              <span>·</span>
              <span className="text-destructive">{job.qtde_erros} erros</span>
            </>
          )}
          {typeof job.duracao_segundos === "number" && (
            <>
              <span>·</span>
              <span>{job.duracao_segundos.toFixed(1)} s</span>
            </>
          )}
        </div>
        {job.erro_detalhe && (
          <div className="text-xs text-destructive mt-1 break-words">{job.erro_detalhe}</div>
        )}
      </div>
      <time className="text-xs text-muted-foreground tabular-nums shrink-0">
        {formatarData(job.created_at)}
      </time>
    </li>
  );
}


function StatusBadge({ status }: { status: IngestionJob["status"] }) {
  const map = {
    queued: { label: "agendado", icon: Clock, tone: "outline" as const },
    running: { label: "rodando", icon: Loader2, tone: "default" as const, spin: true },
    done: { label: "concluído", icon: CheckCircle2, tone: "default" as const },
    failed: { label: "falhou", icon: XCircle, tone: "destructive" as const },
    cancelled: { label: "cancelado", icon: XCircle, tone: "outline" as const },
  } as const;
  const m = map[status];
  const Icon = m.icon;
  return (
    <Badge variant={m.tone} className="gap-1 shrink-0 mt-0.5">
      <Icon className={`h-3 w-3 ${"spin" in m && m.spin ? "animate-spin" : ""}`} /> {m.label}
    </Badge>
  );
}


function formatarData(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
