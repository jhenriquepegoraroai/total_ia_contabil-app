"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { ChevronLeft, Save, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  ApiError,
  adminCriarSource,
  adminTestarConexao,
} from "@/lib/api";
import type { SourceConfigPayload, SourceType } from "@/lib/types";


const TYPE_OPTIONS: { type: SourceType; label: string; description: string }[] = [
  { type: "pdf_upload", label: "Upload de PDFs", description: "Suba PDFs (atas, regulamentos, editais) manualmente. Pronto para uso." },
  { type: "excel_upload", label: "Upload de Excel", description: "Planilhas .xlsx com FAQ ou regras. Mapeie a coluna de texto." },
  { type: "csv_upload", label: "Upload de CSV", description: "Idem Excel, em CSV. Delimitador configurável." },
  { type: "s3", label: "AWS S3", description: "Bucket do cliente. Pronto para uso (IAM role ou keys)." },
  { type: "azure_blob", label: "Azure Blob Storage", description: "Container Azure do cliente. Pronto para uso." },
  { type: "postgres", label: "Postgres do cliente", description: "Conexão direta a AWS RDS / Azure DB. Testável agora." },
  { type: "sqlserver", label: "SQL Server", description: "Para clientes com base on-prem ou Azure SQL. Em fase futura." },
  { type: "databricks", label: "Databricks", description: "Compatibilidade com a Bella original da Lello. Fase futura." },
];


export default function NewSourcePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const router = useRouter();

  const [tipo, setTipo] = useState<SourceType>("pdf_upload");
  const [nome, setNome] = useState("");
  const [config, setConfig] = useState<Partial<SourceConfigPayload>>({});
  const [enviando, setEnviando] = useState(false);
  const [testando, setTestando] = useState(false);
  const [resultadoTest, setResultadoTest] = useState<{ ok: boolean; detail: string } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  function buildConfig(): SourceConfigPayload {
    return { ...(config as object), type: tipo } as SourceConfigPayload;
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
      await adminCriarSource(tenantId, {
        name: nome.trim(),
        config: buildConfig(),
      });
      router.replace(`/admin/tenants/${tenantId}/sources`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  const opcaoSelecionada = TYPE_OPTIONS.find((o) => o.type === tipo)!;

  return (
    <>
      <Link
        href={`/admin/tenants/${tenantId}/sources`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ChevronLeft className="h-3 w-3" /> Voltar
      </Link>
      <h1 className="text-2xl font-bold">Nova fonte de dados</h1>
      <p className="text-sm text-muted-foreground mt-1 mb-6">
        Cadastre uma origem de documentos. Você poderá testar a conexão e
        depois disparar a ingestão para popular os embeddings.
      </p>

      <form onSubmit={onSubmit} className="space-y-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tipo da fonte</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.type}
                  type="button"
                  onClick={() => {
                    setTipo(opt.type);
                    setConfig({});
                    setResultadoTest(null);
                  }}
                  className={`text-left rounded-md border p-3 transition-colors ${
                    tipo === opt.type
                      ? "border-primary bg-primary/5"
                      : "hover:bg-accent/30"
                  }`}
                >
                  <div className="font-medium text-sm flex items-center gap-2">
                    {opt.label}
                    {tipo === opt.type && (
                      <Badge variant="default" className="text-[9px] py-0">selecionado</Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {opt.description}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configuração</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Nome da fonte" hint="Identificação interna. Ex: 'Atas 2024' ou 'RDS produção'.">
              <Input
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Ex: PDFs internos"
                required
              />
            </Field>

            <DynamicConfigFields tipo={tipo} value={config} onChange={setConfig} />
          </CardContent>
        </Card>

        {(tipo === "postgres" || tipo === "s3" || tipo === "sqlserver" || tipo === "azure_blob") && (
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
            Criar fonte
          </Button>
        </div>
      </form>
    </>
  );
}


// =============================================================================
// Campos por tipo
// =============================================================================
function DynamicConfigFields({
  tipo,
  value,
  onChange,
}: {
  tipo: SourceType;
  value: Partial<SourceConfigPayload>;
  onChange: (v: Partial<SourceConfigPayload>) => void;
}) {
  function set<K extends string>(key: K, v: unknown) {
    onChange({ ...(value as object), [key]: v } as Partial<SourceConfigPayload>);
  }

  switch (tipo) {
    case "pdf_upload":
      return (
        <Field label="Referência default (opcional)" hint="ID do condomínio ao qual os PDFs serão associados se o nome do arquivo não trouxer.">
          <Input
            value={(value as Record<string, unknown>).referencia_default as string ?? ""}
            onChange={(e) => set("referencia_default", e.target.value || null)}
            placeholder="Ex: 12345"
          />
        </Field>
      );

    case "excel_upload":
    case "csv_upload":
      return (
        <>
          <Field
            label="Coluna de texto (obrigatório)"
            hint="Nome da coluna que será indexada como conteúdo."
          >
            <Input
              value={(value as Record<string, unknown>).coluna_texto as string ?? ""}
              onChange={(e) => set("coluna_texto", e.target.value)}
              placeholder="resposta"
              required
            />
          </Field>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field
              label="Coluna de referência (opcional)"
              hint="Coluna que tem o ID do condomínio."
            >
              <Input
                value={(value as Record<string, unknown>).coluna_referencia as string ?? ""}
                onChange={(e) => set("coluna_referencia", e.target.value)}
                placeholder="condominio_id"
              />
            </Field>
            <Field
              label="Coluna de data (opcional)"
              hint="Coluna que tem a data do registro."
            >
              <Input
                value={(value as Record<string, unknown>).coluna_data as string ?? ""}
                onChange={(e) => set("coluna_data", e.target.value)}
                placeholder="data"
              />
            </Field>
          </div>
          <Field
            label="Referência default (opcional)"
            hint="Usada quando a linha não traz o id do condomínio."
          >
            <Input
              value={(value as Record<string, unknown>).referencia_default as string ?? ""}
              onChange={(e) => set("referencia_default", e.target.value || null)}
              placeholder="Ex: 12345"
            />
          </Field>
          {tipo === "csv_upload" && (
            <Field label="Delimitador" hint="Default: vírgula. Use ; para CSV brasileiro.">
              <Input
                value={(value as Record<string, unknown>).delimiter as string ?? ","}
                onChange={(e) => set("delimiter", e.target.value)}
                placeholder=","
                maxLength={1}
                className="max-w-[80px]"
              />
            </Field>
          )}
        </>
      );

    case "s3":
      return (
        <>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Bucket"><Input value={(value as any).bucket ?? ""} onChange={(e) => set("bucket", e.target.value)} required /></Field>
            <Field label="Region"><Input value={(value as any).region ?? "sa-east-1"} onChange={(e) => set("region", e.target.value)} required /></Field>
          </div>
          <Field label="Prefix (opcional)"><Input value={(value as any).prefix ?? ""} onChange={(e) => set("prefix", e.target.value)} placeholder="documentos/condominios/" /></Field>
          <p className="text-xs text-muted-foreground">
            Em produção, credenciais via IAM role; em DEV, podem entrar nos campos abaixo.
          </p>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Access Key ID (DEV)"><Input value={(value as any).access_key_id ?? ""} onChange={(e) => set("access_key_id", e.target.value)} /></Field>
            <Field label="Secret Access Key (DEV)"><Input type="password" value={(value as any).secret_access_key ?? ""} onChange={(e) => set("secret_access_key", e.target.value)} /></Field>
          </div>
        </>
      );

    case "azure_blob":
      return (
        <>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Storage account"><Input value={(value as any).account ?? ""} onChange={(e) => set("account", e.target.value)} required /></Field>
            <Field label="Container"><Input value={(value as any).container ?? ""} onChange={(e) => set("container", e.target.value)} required /></Field>
          </div>
          <Field label="Prefix"><Input value={(value as any).prefix ?? ""} onChange={(e) => set("prefix", e.target.value)} /></Field>
          <Field label="SAS token (DEV)"><Input value={(value as any).sas_token ?? ""} onChange={(e) => set("sas_token", e.target.value)} /></Field>
        </>
      );

    case "postgres":
      return (
        <>
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Host"><Input value={(value as any).host ?? ""} onChange={(e) => set("host", e.target.value)} placeholder="db.cliente.com" required /></Field>
            <Field label="Porta"><Input type="number" value={(value as any).port ?? 5432} onChange={(e) => set("port", Number(e.target.value))} /></Field>
            <Field label="Database"><Input value={(value as any).database ?? ""} onChange={(e) => set("database", e.target.value)} required /></Field>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Usuário"><Input value={(value as any).user ?? ""} onChange={(e) => set("user", e.target.value)} required /></Field>
            <Field label="Senha (DEV)"><Input type="password" value={(value as any).password ?? ""} onChange={(e) => set("password", e.target.value)} /></Field>
          </div>
          <Field label="Tabela (opcional)"><Input value={(value as any).table ?? ""} onChange={(e) => set("table", e.target.value)} placeholder="condominio_documentos" /></Field>
          <Field label="SQL custom (opcional, ignora tabela)"><Textarea value={(value as any).custom_query ?? ""} onChange={(e) => set("custom_query", e.target.value)} placeholder="SELECT id, condominio_id, texto, data_doc FROM documentos" rows={3} /></Field>
        </>
      );

    case "sqlserver":
      return (
        <>
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Host"><Input value={(value as any).host ?? ""} onChange={(e) => set("host", e.target.value)} required /></Field>
            <Field label="Porta"><Input type="number" value={(value as any).port ?? 1433} onChange={(e) => set("port", Number(e.target.value))} /></Field>
            <Field label="Database"><Input value={(value as any).database ?? ""} onChange={(e) => set("database", e.target.value)} required /></Field>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Usuário"><Input value={(value as any).user ?? ""} onChange={(e) => set("user", e.target.value)} required /></Field>
            <Field label="Senha (DEV)"><Input type="password" value={(value as any).password ?? ""} onChange={(e) => set("password", e.target.value)} /></Field>
          </div>
        </>
      );

    case "databricks":
      return (
        <>
          <Field label="Server hostname"><Input value={(value as any).server_hostname ?? ""} onChange={(e) => set("server_hostname", e.target.value)} required /></Field>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="HTTP path"><Input value={(value as any).http_path ?? ""} onChange={(e) => set("http_path", e.target.value)} required /></Field>
            <Field label="Cluster ID"><Input value={(value as any).cluster_id ?? ""} onChange={(e) => set("cluster_id", e.target.value)} required /></Field>
          </div>
          <Field label="Tabela de embeddings"><Input value={(value as any).table_embeddings ?? ""} onChange={(e) => set("table_embeddings", e.target.value)} required /></Field>
        </>
      );

    default:
      return null;
  }
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
