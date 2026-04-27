"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  Loader2,
  Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Field, SourceConfigFields } from "@/components/admin/source-config-fields";
import {
  ApiError,
  adminAtualizarSource,
  adminBuscarSource,
  adminTestarConexao,
} from "@/lib/api";
import type { SourceConfigPayload, SourceDetail, SourceType } from "@/lib/types";


const TYPE_LABELS: Record<SourceType, string> = {
  pdf_upload: "Upload de PDFs",
  excel_upload: "Upload de Excel",
  csv_upload: "Upload de CSV",
  s3: "AWS S3",
  azure_blob: "Azure Blob Storage",
  postgres: "Postgres",
  sqlserver: "SQL Server",
  databricks: "Databricks",
};


export default function EditSourcePage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id: tenantId, sid: sourceId } = use(params);
  const router = useRouter();

  const [source, setSource] = useState<SourceDetail | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erroCarga, setErroCarga] = useState<string | null>(null);

  const [nome, setNome] = useState("");
  const [config, setConfig] = useState<Partial<SourceConfigPayload>>({});
  const [habilitada, setHabilitada] = useState(true);

  const [enviando, setEnviando] = useState(false);
  const [testando, setTestando] = useState(false);
  const [resultadoTest, setResultadoTest] = useState<{ ok: boolean; detail: string } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    adminBuscarSource(tenantId, sourceId)
      .then((s) => {
        setSource(s);
        setNome(s.name);
        setConfig({ ...(s.config as object), type: s.type } as Partial<SourceConfigPayload>);
        setHabilitada(s.enabled);
      })
      .catch((err) => setErroCarga(err instanceof ApiError ? err.message : String(err)))
      .finally(() => setCarregando(false));
  }, [tenantId, sourceId]);

  function buildConfig(): SourceConfigPayload {
    if (!source) throw new Error("source ainda não carregada");
    return { ...(config as object), type: source.type } as SourceConfigPayload;
  }

  async function testar() {
    setErro(null);
    setResultadoTest(null);
    setTestando(true);
    try {
      const r = await adminTestarConexao(buildConfig());
      setResultadoTest({ ok: r.ok, detail: r.detail });
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTestando(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await adminAtualizarSource(tenantId, sourceId, {
        name: nome.trim(),
        config: buildConfig(),
        enabled: habilitada,
      });
      router.replace(`/admin/tenants/${tenantId}/sources`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  if (carregando) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Carregando fonte…
      </div>
    );
  }

  if (erroCarga || !source) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {erroCarga ?? "Fonte não encontrada."}
      </div>
    );
  }

  const tipoExterno =
    source.type === "postgres" ||
    source.type === "s3" ||
    source.type === "sqlserver" ||
    source.type === "azure_blob";

  return (
    <>
      <Link
        href={`/admin/tenants/${tenantId}/sources`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ChevronLeft className="h-3 w-3" /> Voltar
      </Link>
      <h1 className="text-2xl font-bold flex items-center gap-2">
        Editar fonte
        <Badge variant="outline" className="text-xs font-normal">
          {TYPE_LABELS[source.type]}
        </Badge>
      </h1>
      <p className="text-sm text-muted-foreground mt-1 mb-6">
        Ajuste nome ou configuração. O tipo da fonte é imutável — para mudar
        o tipo, delete e recrie.
      </p>

      <form onSubmit={onSubmit} className="space-y-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configuração</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Nome da fonte">
              <Input
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
              />
            </Field>

            <SourceConfigFields
              tipo={source.type}
              value={config}
              onChange={setConfig}
            />

            <Field
              label="Status"
              hint="Fontes desabilitadas não aparecem para o RAG até serem reabilitadas."
            >
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={habilitada}
                  onChange={(e) => setHabilitada(e.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
                Fonte habilitada
              </label>
            </Field>
          </CardContent>
        </Card>

        {tipoExterno && (
          <div className="flex items-center gap-3">
            <Button type="button" variant="outline" onClick={testar} disabled={testando}>
              {testando ? <Loader2 className="animate-spin" /> : null}
              Testar conexão
            </Button>
            {resultadoTest && (
              <span
                className={`inline-flex items-center gap-1.5 text-sm ${
                  resultadoTest.ok ? "text-green-700" : "text-destructive"
                }`}
              >
                {resultadoTest.ok ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
                {resultadoTest.detail}
              </span>
            )}
          </div>
        )}

        {erro && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {erro}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="outline" asChild>
            <Link href={`/admin/tenants/${tenantId}/sources`}>Cancelar</Link>
          </Button>
          <Button type="submit" disabled={enviando}>
            {enviando ? <Loader2 className="animate-spin" /> : <Save />}
            Salvar alterações
          </Button>
        </div>
      </form>
    </>
  );
}
