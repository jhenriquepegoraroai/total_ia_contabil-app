"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  Download,
  FileJson,
  FileSpreadsheet,
  Loader2,
  Trash2,
  Upload,
  X,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  cobrancasBaixarExcel,
  cobrancasDeletarJob,
  cobrancasListarJobs,
  cobrancasResultado,
  cobrancasUploadPdf,
} from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type {
  CobrancaJob,
  CobrancaJobResult,
  CobrancaJobStatus,
} from "@/lib/types";


type Sessao = NonNullable<ReturnType<typeof lerSessao>>;

const POLL_INTERVAL_MS = 3000;
const STATUS_LABEL: Record<CobrancaJobStatus, string> = {
  queued: "Na fila",
  running: "Processando",
  done: "Concluído",
  failed: "Falhou",
};


export default function CobrancasPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [jobs, setJobs] = useState<CobrancaJob[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [resultModal, setResultModal] = useState<{
    job: CobrancaJob;
    result: CobrancaJobResult;
  } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<CobrancaJob | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auth + módulo
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
    if (!s.modulos_contratados.cobrancas) {
      router.replace("/");
      return;
    }
    setSessao(s);
  }, [router]);

  async function carregar() {
    try {
      const data = await cobrancasListarJobs();
      setJobs(data);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (!sessao) return;
    carregar();
  }, [sessao]);

  // Polling: se há jobs queued/running, refetch periodicamente.
  useEffect(() => {
    const ativos = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!ativos) return;
    const id = setInterval(carregar, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [jobs]);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setEnviando(true);
    try {
      await cobrancasUploadPdf(file);
      toast.success(`"${file.name}" enviado. Processamento iniciado.`);
      await carregar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function abrirResultado(job: CobrancaJob) {
    try {
      const res = await cobrancasResultado(job.id);
      setResultModal({ job, result: res });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function executarDelete(job: CobrancaJob) {
    setDeletingId(job.id);
    try {
      await cobrancasDeletarJob(job.id);
      setConfirmDelete(null);
      toast.success(`"${job.file_name}" removido do histórico.`);
      await carregar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  if (!sessao) return null;

  return (
    <AppShell
      tenantId={sessao.tenant_id}
      role={sessao.role}
      modulos={sessao.modulos_contratados}
    >
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
        <header className="mb-6">
          <div className="flex items-center gap-3">
            <FileJson className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Bella Cobranças</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Suba um PDF de relatório de cobrança e receba um JSON estruturado
            (até 15 páginas por arquivo nesta versão).
          </p>
        </header>

        {/* Upload zone --------------------------------------------------- */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={enviando}
              className="w-full rounded-md border-2 border-dashed border-muted-foreground/30 hover:border-primary hover:bg-primary/5 transition-colors p-8 text-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {enviando ? (
                <>
                  <Loader2 className="h-7 w-7 mx-auto mb-2 text-primary animate-spin" />
                  <div className="font-medium">Enviando...</div>
                </>
              ) : (
                <>
                  <Upload className="h-7 w-7 mx-auto mb-2 text-muted-foreground" />
                  <div className="font-medium">Subir PDF de cobrança</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Clique aqui pra selecionar (até 50 MB)
                  </div>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={onFile}
              className="hidden"
            />
          </CardContent>
        </Card>

        {/* Jobs list ----------------------------------------------------- */}
        {carregando ? (
          <div className="space-y-2">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        ) : jobs.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <FileJson className="h-10 w-10 mx-auto mb-3 opacity-40" />
              <p className="font-medium text-foreground">Nenhuma extração ainda</p>
              <p className="text-sm mt-1">
                Suba o primeiro PDF acima pra começar.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onVerResultado={() => abrirResultado(job)}
                onDeletar={() => setConfirmDelete(job)}
                deletando={deletingId === job.id}
              />
            ))}
          </div>
        )}

        {resultModal && (
          <ResultadoModal
            job={resultModal.job}
            result={resultModal.result}
            onClose={() => setResultModal(null)}
            onErro={(msg) => toast.error(msg)}
          />
        )}

        <ConfirmDialog
          open={confirmDelete !== null}
          title="Apagar do histórico"
          description={
            confirmDelete && (
              <>
                Vamos remover <strong>{confirmDelete.file_name}</strong> do histórico.
                <br />
                O PDF e o resultado também são apagados do servidor — esta ação não pode ser desfeita.
              </>
            )
          }
          confirmLabel="Apagar"
          destructive
          loading={deletingId !== null}
          onConfirm={() => confirmDelete && executarDelete(confirmDelete)}
          onCancel={() => deletingId === null && setConfirmDelete(null)}
        />
      </main>
    </AppShell>
  );
}


// =============================================================================
// Componentes
// =============================================================================
function JobCard({
  job,
  onVerResultado,
  onDeletar,
  deletando,
}: {
  job: CobrancaJob;
  onVerResultado: () => void;
  onDeletar: () => void;
  deletando: boolean;
}) {
  // Não permite apagar enquanto job está rodando — esperar finalizar.
  const podeApagar = job.status === "done" || job.status === "failed";
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-4">
        <StatusIcon status={job.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium truncate">{job.file_name}</span>
            <Badge variant={badgeVariant(job.status)} className="text-[10px]">
              {STATUS_LABEL[job.status]}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5 flex flex-wrap gap-x-3">
            <span>{formatBytes(job.file_size)}</span>
            {job.qtde_paginas != null && <span>· {job.qtde_paginas} págs</span>}
            {job.qtde_registros != null && (
              <span>· {job.qtde_registros} registros</span>
            )}
            {job.valor_total != null && (
              <span>· R$ {job.valor_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
            )}
            {job.duracao_segundos != null && (
              <span>· {job.duracao_segundos.toFixed(1)}s</span>
            )}
          </div>
          {job.status === "failed" && job.error_detail && (
            <div className="text-xs text-destructive mt-1 truncate" title={job.error_detail}>
              {job.error_detail}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {job.status === "done" && (
            <Button variant="outline" size="sm" onClick={onVerResultado}>
              Ver resultado
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={onDeletar}
            disabled={!podeApagar || deletando}
            title={podeApagar ? "Apagar do histórico" : "Aguarde concluir"}
            className="text-muted-foreground hover:text-destructive"
          >
            {deletando ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}


function StatusIcon({ status }: { status: CobrancaJobStatus }) {
  if (status === "done")
    return <CheckCircle2 className="h-5 w-5 text-green-700 shrink-0" />;
  if (status === "failed")
    return <XCircle className="h-5 w-5 text-destructive shrink-0" />;
  return <Loader2 className="h-5 w-5 text-primary animate-spin shrink-0" />;
}


function badgeVariant(s: CobrancaJobStatus): "default" | "secondary" | "outline" {
  if (s === "done") return "default";
  if (s === "failed") return "outline";
  return "secondary";
}


function ResultadoModal({
  job,
  result,
  onClose,
  onErro,
}: {
  job: CobrancaJob;
  result: CobrancaJobResult;
  onClose: () => void;
  onErro: (msg: string) => void;
}) {
  const [baixandoExcel, setBaixandoExcel] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function baixarJson() {
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${nomeBase(job.file_name)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function baixarExcel() {
    setBaixandoExcel(true);
    try {
      await cobrancasBaixarExcel(job.id, nomeBase(job.file_name));
    } catch (err) {
      onErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBaixandoExcel(false);
    }
  }

  const colunas: (keyof CobrancaJobResult["registros"][number])[] = [
    "CONDOMINIO",
    "UNIDADE",
    "PRIMEIRO_VENCTO",
    "NR_DO_RECIBO",
    "CONTA",
    "HISTORICO",
    "VALOR_ORIGINAL",
    "SITUACAO",
  ];

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-40 bg-black/50" aria-hidden />
      <div
        role="dialog"
        aria-modal
        className="fixed left-1/2 top-1/2 z-50 w-[95vw] max-w-5xl max-h-[85vh] -translate-x-1/2 -translate-y-1/2 flex flex-col rounded-lg bg-card border shadow-xl"
      >
        <header className="flex items-center justify-between p-4 border-b">
          <div>
            <h2 className="font-semibold">Resultado da extração</h2>
            <p className="text-xs text-muted-foreground">
              {result.metadata.total_registros ?? result.registros.length} registros
              {result.metadata.total_valor != null && (
                <> · total R$ {Number(result.metadata.total_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={baixarExcel}
              disabled={baixandoExcel}
            >
              {baixandoExcel ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FileSpreadsheet className="h-3.5 w-3.5" />
              )}
              Baixar Excel
            </Button>
            <Button variant="outline" size="sm" onClick={baixarJson}>
              <Download className="h-3.5 w-3.5" /> JSON
            </Button>
            <Button variant="ghost" size="icon" onClick={onClose} title="Fechar">
              <X />
            </Button>
          </div>
        </header>
        <div className="flex-1 overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur">
              <tr>
                {colunas.map((c) => (
                  <th key={c} className="text-left px-3 py-2 font-medium border-b">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.registros.map((r, i) => (
                <tr key={i} className="border-b hover:bg-accent/30">
                  {colunas.map((c) => (
                    <td key={c} className="px-3 py-1.5 align-top">
                      {formatCelula(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}


// =============================================================================
// Helpers
// =============================================================================
function nomeBase(fileName: string): string {
  return fileName.replace(/\.[^/.]+$/, "") || "cobrancas";
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function formatCelula(v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "number")
    return v.toLocaleString("pt-BR", { minimumFractionDigits: 2 });
  return String(v);
}
