"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  Cloud,
  CloudCog,
  Database,
  FileSpreadsheet,
  FileText,
  Loader2,
  Pencil,
  Play,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  adminDeletarSource,
  adminDispararJob,
  adminListarSources,
  adminUploadFiles,
} from "@/lib/api";
import type { SourceSummary, SourceType } from "@/lib/types";


const TYPE_META: Record<
  SourceType,
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  pdf_upload: { label: "PDFs (upload)", icon: FileText, tone: "bg-primary/10 text-primary" },
  excel_upload: { label: "Excel (upload)", icon: FileSpreadsheet, tone: "bg-green-500/10 text-green-700" },
  csv_upload: { label: "CSV (upload)", icon: FileSpreadsheet, tone: "bg-green-500/10 text-green-700" },
  s3: { label: "AWS S3", icon: Cloud, tone: "bg-amber-500/10 text-amber-700" },
  azure_blob: { label: "Azure Blob", icon: Cloud, tone: "bg-blue-500/10 text-blue-700" },
  postgres: { label: "Postgres", icon: Database, tone: "bg-sky-500/10 text-sky-700" },
  sqlserver: { label: "SQL Server", icon: Database, tone: "bg-red-500/10 text-red-700" },
  databricks: { label: "Databricks", icon: CloudCog, tone: "bg-orange-500/10 text-orange-700" },
};


export default function SourcesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  async function carregar() {
    try {
      const data = await adminListarSources(tenantId);
      setSources(data);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
  }, [tenantId]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">Fontes de dados</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Cadastre PDFs, planilhas, S3, Azure Blob, Postgres ou SQL Server.
            O conteúdo será chunked, embeddado e disponibilizado para o RAG.
          </p>
        </div>
        <Button asChild>
          <Link href={`/admin/tenants/${tenantId}/sources/new`}>
            <Plus className="h-4 w-4" /> Nova fonte
          </Link>
        </Button>
      </div>

      {erro && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <Database className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Nenhuma fonte cadastrada</p>
            <p className="text-sm mt-1">
              Comece criando uma nova fonte (upload de PDFs é o caminho mais rápido).
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <SourceRow
              key={s.id}
              tenantId={tenantId}
              source={s}
              onChanged={carregar}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function SourceRow({
  tenantId,
  source,
  onChanged,
}: {
  tenantId: string;
  source: SourceSummary;
  onChanged: () => void;
}) {
  const meta = TYPE_META[source.type];
  const Icon = meta.icon;
  const podeFazerUpload = source.type.endsWith("_upload");

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className={`h-10 w-10 rounded-md grid place-items-center shrink-0 ${meta.tone}`}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="font-medium flex items-center gap-2">
                {source.name}
                {!source.enabled && (
                  <Badge variant="outline" className="text-[10px]">desabilitada</Badge>
                )}
              </div>
              <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5">
                <span>{meta.label}</span>
                <span>·</span>
                <span>{source.qtde_files} arquivo{source.qtde_files === 1 ? "" : "s"}</span>
                {source.last_run_status && (
                  <>
                    <span>·</span>
                    <RunBadge status={source.last_run_status} />
                  </>
                )}
              </div>
            </div>
          </div>

          <SourceActions
            tenantId={tenantId}
            source={source}
            onChanged={onChanged}
          />
        </div>

        {podeFazerUpload && (
          <UploadArea
            tenantId={tenantId}
            sourceId={source.id}
            onUploaded={onChanged}
          />
        )}
      </CardContent>
    </Card>
  );
}


function RunBadge({ status }: { status: NonNullable<SourceSummary["last_run_status"]> }) {
  const map = {
    queued: { label: "agendado", cls: "text-muted-foreground" },
    running: { label: "executando…", cls: "text-amber-700" },
    done: { label: "última run OK", cls: "text-green-700" },
    failed: { label: "última run falhou", cls: "text-destructive" },
  } as const;
  const m = map[status];
  return <span className={m.cls}>{m.label}</span>;
}


function SourceActions({
  tenantId,
  source,
  onChanged,
}: {
  tenantId: string;
  source: SourceSummary;
  onChanged: () => void;
}) {
  const [executando, setExecutando] = useState(false);
  const [removendo, setRemovendo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function executar() {
    setErro(null);
    setExecutando(true);
    try {
      await adminDispararJob(tenantId, { source_id: source.id });
      // Pequeno delay para o backend gravar status running antes de recarregar.
      setTimeout(onChanged, 500);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setExecutando(false);
    }
  }

  async function remover() {
    if (!confirm(`Remover a fonte "${source.name}"? Os arquivos no storage permanecem.`)) return;
    setRemovendo(true);
    try {
      await adminDeletarSource(tenantId, source.id);
      onChanged();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
      setRemovendo(false);
    }
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      {source.qtde_files > 0 && source.type === "pdf_upload" && (
        <Button
          variant="outline"
          size="sm"
          onClick={executar}
          disabled={executando}
        >
          {executando ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Play />
          )}
          Executar ingestão
        </Button>
      )}
      <Button variant="ghost" size="icon" asChild title="Editar">
        <Link href={`/admin/tenants/${tenantId}/sources/${source.id}/edit`}>
          <Pencil className="h-4 w-4" />
        </Link>
      </Button>
      <Button variant="ghost" size="icon" onClick={remover} disabled={removendo} title="Remover">
        {removendo ? <Loader2 className="animate-spin h-4 w-4" /> : <Trash2 className="h-4 w-4" />}
      </Button>
      {erro && (
        <div className="absolute right-4 mt-1 text-xs text-destructive">{erro}</div>
      )}
    </div>
  );
}


function UploadArea({
  tenantId,
  sourceId,
  onUploaded,
}: {
  tenantId: string;
  sourceId: string;
  onUploaded: () => void;
}) {
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function handle(files: FileList | null) {
    if (!files || files.length === 0) return;
    setErro(null);
    setFeedback(null);
    setCarregando(true);
    try {
      const arr = Array.from(files);
      const resp = await adminUploadFiles(tenantId, sourceId, arr);
      const ok = resp.uploaded.filter((u) => u.ok).length;
      const fail = resp.uploaded.filter((u) => !u.ok).length;
      setFeedback(
        `${ok} arquivo${ok === 1 ? "" : "s"} salvo${ok === 1 ? "" : "s"}` +
        (fail ? `, ${fail} falhou` : "")
      );
      onUploaded();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="border border-dashed rounded-md p-3 bg-muted/30">
      <div className="flex items-center gap-3">
        <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
        <Input
          type="file"
          multiple
          accept=".pdf"
          onChange={(e) => handle(e.target.files)}
          disabled={carregando}
          className="border-0 bg-transparent shadow-none px-0 focus-visible:ring-0 file:text-primary file:font-medium"
        />
        {carregando && <Loader2 className="h-4 w-4 animate-spin shrink-0" />}
      </div>
      {feedback && <p className="text-xs text-green-700 mt-2">{feedback}</p>}
      {erro && <p className="text-xs text-destructive mt-2">{erro}</p>}
    </div>
  );
}
