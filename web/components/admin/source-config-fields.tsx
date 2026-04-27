"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { SourceConfigPayload, SourceType } from "@/lib/types";


export function SourceConfigFields({
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
        <Field
          label="Referência default (opcional)"
          hint="ID do condomínio ao qual os PDFs serão associados se o nome do arquivo não trouxer."
        >
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
            <Field label="Bucket">
              <Input value={(value as any).bucket ?? ""} onChange={(e) => set("bucket", e.target.value)} required />
            </Field>
            <Field label="Region">
              <Input value={(value as any).region ?? "sa-east-1"} onChange={(e) => set("region", e.target.value)} required />
            </Field>
          </div>
          <Field label="Prefix (opcional)">
            <Input value={(value as any).prefix ?? ""} onChange={(e) => set("prefix", e.target.value)} placeholder="documentos/condominios/" />
          </Field>
          <p className="text-xs text-muted-foreground">
            Em produção, credenciais via IAM role; em DEV, podem entrar nos campos abaixo.
          </p>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Access Key ID (DEV)">
              <Input value={(value as any).access_key_id ?? ""} onChange={(e) => set("access_key_id", e.target.value)} />
            </Field>
            <Field label="Secret Access Key (DEV)">
              <Input type="password" value={(value as any).secret_access_key ?? ""} onChange={(e) => set("secret_access_key", e.target.value)} />
            </Field>
          </div>
        </>
      );

    case "azure_blob":
      return (
        <>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Storage account">
              <Input value={(value as any).account ?? ""} onChange={(e) => set("account", e.target.value)} required />
            </Field>
            <Field label="Container">
              <Input value={(value as any).container ?? ""} onChange={(e) => set("container", e.target.value)} required />
            </Field>
          </div>
          <Field label="Prefix">
            <Input value={(value as any).prefix ?? ""} onChange={(e) => set("prefix", e.target.value)} />
          </Field>
          <Field label="SAS token (DEV)">
            <Input value={(value as any).sas_token ?? ""} onChange={(e) => set("sas_token", e.target.value)} />
          </Field>
        </>
      );

    case "postgres":
      return (
        <>
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Host">
              <Input value={(value as any).host ?? ""} onChange={(e) => set("host", e.target.value)} placeholder="db.cliente.com" required />
            </Field>
            <Field label="Porta">
              <Input type="number" value={(value as any).port ?? 5432} onChange={(e) => set("port", Number(e.target.value))} />
            </Field>
            <Field label="Database">
              <Input value={(value as any).database ?? ""} onChange={(e) => set("database", e.target.value)} required />
            </Field>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Usuário">
              <Input value={(value as any).user ?? ""} onChange={(e) => set("user", e.target.value)} required />
            </Field>
            <Field label="Senha (DEV)">
              <Input type="password" value={(value as any).password ?? ""} onChange={(e) => set("password", e.target.value)} />
            </Field>
          </div>
          <Field label="Tabela (opcional)">
            <Input value={(value as any).table ?? ""} onChange={(e) => set("table", e.target.value)} placeholder="condominio_documentos" />
          </Field>
          <Field label="SQL custom (opcional, ignora tabela)">
            <Textarea value={(value as any).custom_query ?? ""} onChange={(e) => set("custom_query", e.target.value)} placeholder="SELECT id, condominio_id, texto, data_doc FROM documentos" rows={3} />
          </Field>
        </>
      );

    case "sqlserver":
      return (
        <>
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="Host">
              <Input value={(value as any).host ?? ""} onChange={(e) => set("host", e.target.value)} required />
            </Field>
            <Field label="Porta">
              <Input type="number" value={(value as any).port ?? 1433} onChange={(e) => set("port", Number(e.target.value))} />
            </Field>
            <Field label="Database">
              <Input value={(value as any).database ?? ""} onChange={(e) => set("database", e.target.value)} required />
            </Field>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Usuário">
              <Input value={(value as any).user ?? ""} onChange={(e) => set("user", e.target.value)} required />
            </Field>
            <Field label="Senha (DEV)">
              <Input type="password" value={(value as any).password ?? ""} onChange={(e) => set("password", e.target.value)} />
            </Field>
          </div>
        </>
      );

    case "databricks":
      return (
        <>
          <Field label="Server hostname">
            <Input value={(value as any).server_hostname ?? ""} onChange={(e) => set("server_hostname", e.target.value)} required />
          </Field>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="HTTP path">
              <Input value={(value as any).http_path ?? ""} onChange={(e) => set("http_path", e.target.value)} required />
            </Field>
            <Field label="Cluster ID">
              <Input value={(value as any).cluster_id ?? ""} onChange={(e) => set("cluster_id", e.target.value)} required />
            </Field>
          </div>
          <Field label="Tabela de embeddings">
            <Input value={(value as any).table_embeddings ?? ""} onChange={(e) => set("table_embeddings", e.target.value)} required />
          </Field>
        </>
      );

    default:
      return null;
  }
}


export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
