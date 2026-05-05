"use client";

import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileJson,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, adminTestarCobrancas } from "@/lib/api";
import type { TenantCobrancasConfig, TestConnectionResult } from "@/lib/types";


const CAMPOS_OBRIGATORIOS = ["type", "project_id", "client_email", "private_key"] as const;


/**
 * Card que configura as credenciais Google Document AI do tenant para
 * o módulo Bella Cobranças.
 *
 * Aparece somente quando `cobrancas` está nos módulos contratados — o
 * controle de visibilidade é responsabilidade do form pai.
 *
 * Estados do JSON:
 *   - Nenhum upload ainda → mostra zona de upload.
 *   - JSON carregado novo → mostra resumo + inputs + "Testar conexão".
 *   - JSON salvo (private_key mascarada vinda do GET) → idem, mas
 *     "Testar conexão" envia tenant_id pro backend completar a chave.
 */
export function CobrancasCard({
  value,
  onChange,
  tenantId,
}: {
  value: TenantCobrancasConfig | null;
  onChange: (v: TenantCobrancasConfig | null) => void;
  tenantId?: string;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [testando, setTestando] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);

  const v = value ?? makeEmpty();
  const creds = v.gcp_credentials_json;
  const credsConfigured = Boolean(creds && Object.keys(creds).length > 0);
  const credsMasked =
    credsConfigured &&
    typeof creds?.private_key === "string" &&
    creds.private_key.includes("***");

  function update(patch: Partial<TenantCobrancasConfig>) {
    onChange({ ...v, ...patch });
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    setParseError(null);
    setTestResult(null);
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const txt = await file.text();
      const parsed = JSON.parse(txt) as Record<string, unknown>;
      const faltando = CAMPOS_OBRIGATORIOS.filter((c) => !(c in parsed));
      if (faltando.length > 0) {
        throw new Error(
          `JSON faltando campos obrigatórios: ${faltando.join(", ")}`
        );
      }
      if (parsed.type !== "service_account") {
        throw new Error(
          `'type' deve ser 'service_account' (recebi: ${JSON.stringify(parsed.type)})`
        );
      }
      // Auto-preenche project_id se ainda vazio.
      const novoProjectId =
        v.gcp_project_id ?? (parsed.project_id as string | undefined) ?? null;
      onChange({
        ...v,
        gcp_credentials_json: parsed,
        gcp_project_id: novoProjectId,
      });
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
    } finally {
      // Permite re-selecionar o mesmo arquivo se quiser.
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function testarConexao() {
    if (!creds || !v.gcp_project_id || !v.processor_id) {
      setTestResult({
        ok: false,
        detail: "Preencha JSON, Project ID e Processor ID antes de testar.",
        metadata: {},
      });
      return;
    }
    setTestando(true);
    setTestResult(null);
    try {
      const res = await adminTestarCobrancas({
        gcp_credentials_json: creds as Record<string, unknown>,
        gcp_project_id: v.gcp_project_id,
        gcp_location: v.gcp_location,
        processor_id: v.processor_id,
        tenant_id: tenantId,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({
        ok: false,
        detail: err instanceof ApiError ? err.message : String(err),
        metadata: {},
      });
    } finally {
      setTestando(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <FileJson className="h-4 w-4 text-primary" /> Bella Cobranças — Google Document AI
        </CardTitle>
        <CardDescription>
          Suba o service account JSON do cliente. Cada parceiro usa o próprio
          projeto e processor — o consumo é cobrado na conta do cliente.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Bloco 1 — JSON de credenciais ------------------------------------ */}
        {!credsConfigured ? (
          <UploadZone
            onClick={() => fileInputRef.current?.click()}
            error={parseError}
          />
        ) : (
          <CredsSummary
            creds={creds as Record<string, unknown>}
            masked={credsMasked}
            onTrocar={() => fileInputRef.current?.click()}
            onRemover={() => {
              onChange(null);
              setTestResult(null);
            }}
            error={parseError}
          />
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/json,.json"
          onChange={onUpload}
          className="hidden"
        />

        {/* Bloco 2 — parâmetros do processor -------------------------------- */}
        <div className="grid sm:grid-cols-2 gap-3 pt-2 border-t">
          <Field label="GCP Project ID" hint="Auto-preenchido do JSON; pode editar">
            <Input
              value={v.gcp_project_id ?? ""}
              onChange={(e) => update({ gcp_project_id: e.target.value })}
              placeholder="meu-projeto-gcp"
            />
          </Field>
          <Field label="Location" hint='"us" ou "eu" (Document AI)'>
            <Input
              value={v.gcp_location}
              onChange={(e) => update({ gcp_location: e.target.value })}
              placeholder="us"
            />
          </Field>
          <Field label="Processor ID">
            <Input
              value={v.processor_id ?? ""}
              onChange={(e) => update({ processor_id: e.target.value })}
              placeholder="abc123def456"
            />
          </Field>
          <Field label="GCS Bucket" hint="Opcional — só pra PDFs grandes (>15 págs)">
            <Input
              value={v.gcs_bucket ?? ""}
              onChange={(e) => update({ gcs_bucket: e.target.value || null })}
              placeholder="meu-bucket-pdfs"
            />
          </Field>
        </div>

        {/* Bloco 3 — testar conexão ----------------------------------------- */}
        <div className="flex items-center gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={testarConexao}
            disabled={testando || !credsConfigured}
          >
            {testando ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Testando...
              </>
            ) : (
              "Testar conexão"
            )}
          </Button>
          <span className="text-xs text-muted-foreground">
            Faz um <code>get_processor</code> read-only na Google.
          </span>
        </div>
        {testResult && <TestResultBanner result={testResult} />}
      </CardContent>
    </Card>
  );
}


function makeEmpty(): TenantCobrancasConfig {
  return {
    gcp_credentials_json: null,
    gcp_project_id: null,
    gcp_location: "us",
    processor_id: null,
    gcs_bucket: null,
    secret_name: null,
  };
}


function UploadZone({
  onClick,
  error,
}: {
  onClick: () => void;
  error: string | null;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onClick}
        className="w-full rounded-md border-2 border-dashed border-muted-foreground/30 hover:border-primary hover:bg-primary/5 transition-colors p-6 text-center"
      >
        <Upload className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
        <div className="font-medium text-sm">Subir service account JSON</div>
        <div className="text-xs text-muted-foreground mt-1">
          Arquivo <code className="font-mono">.json</code> exportado do Google Cloud
        </div>
      </button>
      {error && (
        <div className="mt-2 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}


function CredsSummary({
  creds,
  masked,
  onTrocar,
  onRemover,
  error,
}: {
  creds: Record<string, unknown>;
  masked: boolean;
  onTrocar: () => void;
  onRemover: () => void;
  error: string | null;
}) {
  const clientEmail = String(creds.client_email ?? "—");
  const projectId = String(creds.project_id ?? "—");
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            Service account {masked ? "configurada (salva)" : "carregada"}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onTrocar}>
              Trocar JSON
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onRemover}>
              Remover
            </Button>
          </div>
        </div>
        <div className="text-xs text-muted-foreground space-y-0.5 pl-5">
          <div>
            <span className="font-medium">project_id:</span>{" "}
            <code className="font-mono">{projectId}</code>
          </div>
          <div>
            <span className="font-medium">client_email:</span>{" "}
            <code className="font-mono break-all">{clientEmail}</code>
          </div>
        </div>
      </div>
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}


function TestResultBanner({ result }: { result: TestConnectionResult }) {
  const Icon = result.ok ? CheckCircle2 : XCircle;
  const tone = result.ok
    ? "border-green-500/30 bg-green-500/10 text-green-700"
    : "border-destructive/30 bg-destructive/10 text-destructive";
  return (
    <div className={`rounded-md border px-3 py-2 text-sm ${tone}`}>
      <div className="flex items-start gap-2">
        <Icon className="h-4 w-4 mt-0.5 shrink-0" />
        <div className="space-y-1 min-w-0">
          <div className="font-medium">
            {result.ok ? "Conexão OK" : "Falha na conexão"}
          </div>
          <div className="text-xs leading-relaxed">{result.detail}</div>
          {result.ok && result.metadata?.processor_display_name ? (
            <div className="text-[11px] text-muted-foreground pt-1">
              <code className="font-mono">
                {String(result.metadata.processor_display_name)}
              </code>{" "}
              · {String(result.metadata.processor_type ?? "")}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}


function Field({
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
