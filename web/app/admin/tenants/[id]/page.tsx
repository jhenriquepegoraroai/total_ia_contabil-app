"use client";

import { use, useEffect, useState } from "react";
import { CheckCircle2, CircleSlash, Database, FileText, Users } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  adminBuscarTenant,
  adminListarTenants,
} from "@/lib/api";
import type { TenantConfig, TenantSummary } from "@/lib/types";

export default function TenantOverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [summary, setSummary] = useState<TenantSummary | null>(null);
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([adminListarTenants(), adminBuscarTenant(id)])
      .then(([tenants, detail]) => {
        const found = tenants.find((t) => t.id === id);
        setSummary(found ?? null);
        setConfig(detail.config);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : String(err)));
  }, [id]);

  if (erro) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {erro}
      </div>
    );
  }

  if (!summary || !config) {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-32" /> <Skeleton className="h-32" /> <Skeleton className="h-32" />
      </div>
    );
  }

  const theme = config.theme || {};

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            {summary.nome_empresa}
            {summary.enabled ? (
              <Badge variant="default" className="gap-1">
                <CheckCircle2 className="h-3 w-3" /> Ativo
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1">
                <CircleSlash className="h-3 w-3" /> Inativo
              </Badge>
            )}
          </h1>
          <code className="text-sm text-muted-foreground">{summary.id}</code>
        </div>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat icon={FileText} label="Documentos indexados" value={summary.qtde_documents} />
        <Stat icon={Database} label="Chunks vetoriais" value={summary.qtde_embeddings} />
        <Stat icon={Users} label="Usuários" value={summary.qtde_users} />
      </div>

      {/* Identidade */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <h2 className="font-semibold">Identidade</h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <Field label="Nome do assistente" value={config.nome_assistente} />
            <Field
              label="Datasource"
              value={
                <code className="text-xs">{config.datasource.type}</code>
              }
            />
            <Field label="E-mail" value={config.contatos.email} />
            <Field label="Telefone" value={config.contatos.telefone} />
            <Field label="WhatsApp" value={config.contatos.whatsapp} />
            <Field
              label="Horário"
              value={config.contatos.horario_atendimento || "—"}
            />
          </dl>

          {/* Paleta */}
          <div className="pt-3 border-t">
            <div className="text-sm font-medium mb-2">Paleta de cores</div>
            <div className="flex flex-wrap gap-2">
              <ColorChip label="primary" hex={theme.primary} />
              <ColorChip label="secondary" hex={theme.secondary} />
              <ColorChip label="accent" hex={theme.accent} />
              <ColorChip label="ink" hex={theme.ink} />
              <ColorChip label="muted" hex={theme.muted} />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-md bg-primary/10 text-primary grid place-items-center">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-2xl font-bold">{value.toLocaleString("pt-BR")}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs mb-0.5">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function ColorChip({ label, hex }: { label: string; hex: string | undefined }) {
  if (!hex) return null;
  return (
    <div className="inline-flex items-center gap-2 rounded-md border bg-card px-2 py-1.5">
      <span
        className="h-5 w-5 rounded border"
        style={{ backgroundColor: hex }}
      />
      <div className="text-xs">
        <div className="font-medium leading-none">{label}</div>
        <code className="text-[10px] text-muted-foreground">{hex}</code>
      </div>
    </div>
  );
}
