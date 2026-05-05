"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { ChevronLeft, Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  adminAtualizarTenant,
  adminBuscarTenant,
} from "@/lib/api";
import type {
  TenantCobrancasConfig,
  TenantConfig,
  TenantOpenAIConfig,
} from "@/lib/types";
import { OpenAIKeyCard } from "@/components/admin/openai-key-card";
import { ModulosContratadosCard } from "@/components/admin/modulos-checkboxes-card";
import { CobrancasCard } from "@/components/admin/cobrancas-card";


export default function EditTenantPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const router = useRouter();
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    adminBuscarTenant(tenantId)
      .then((d) => setConfig(d.config))
      .catch((err) => setErro(err instanceof ApiError ? err.message : String(err)));
  }, [tenantId]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setErro(null);
    setEnviando(true);
    try {
      await adminAtualizarTenant(tenantId, config);
      router.replace(`/admin/tenants/${tenantId}`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  if (erro && !config) {
    return (
      <>
        <BackLink tenantId={tenantId} />
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      </>
    );
  }

  if (!config) {
    return (
      <>
        <BackLink tenantId={tenantId} />
        <div className="space-y-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-48" />
          <Skeleton className="h-32" />
        </div>
      </>
    );
  }

  function update<K extends keyof TenantConfig>(key: K, value: TenantConfig[K]) {
    setConfig((c) => (c ? { ...c, [key]: value } : c));
  }
  function updateContatos(patch: Partial<TenantConfig["contatos"]>) {
    setConfig((c) => (c ? { ...c, contatos: { ...c.contatos, ...patch } } : c));
  }
  function updateUrls(patch: Partial<TenantConfig["urls"]>) {
    setConfig((c) => (c ? { ...c, urls: { ...c.urls, ...patch } } : c));
  }
  function updateTheme(patch: Record<string, string>) {
    setConfig((c) =>
      c ? { ...c, theme: { ...(c.theme || {}), ...patch } } : c
    );
  }
  function updateOpenAI(novo: TenantOpenAIConfig) {
    setConfig((c) => (c ? { ...c, openai: novo } : c));
  }
  function updateModulos(novo: Record<string, boolean>) {
    setConfig((c) => (c ? { ...c, modulos_contratados: novo } : c));
  }
  function updateCobrancas(novo: TenantCobrancasConfig | null) {
    setConfig((c) => (c ? { ...c, cobrancas: novo } : c));
  }

  const openaiValue: TenantOpenAIConfig = config.openai ?? {
    mode: "lello",
    api_key: null,
    secret_name: null,
  };

  const theme = config.theme ?? {};

  return (
    <>
      <BackLink tenantId={tenantId} />
      <h1 className="text-2xl font-bold">Editar tenant</h1>
      <p className="text-sm text-muted-foreground mt-1 mb-6">
        ID <code className="font-mono text-xs">{tenantId}</code> — campos
        sensíveis (datasource, prompts) podem ser editados aqui.
      </p>

      <form onSubmit={onSubmit} className="space-y-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identificação</CardTitle>
            <CardDescription>Dados básicos da administradora.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Nome da empresa">
              <Input
                value={config.nome_empresa}
                onChange={(e) => update("nome_empresa", e.target.value)}
                required
              />
            </Field>
            <Field label="Nome do assistente">
              <Input
                value={config.nome_assistente}
                onChange={(e) => update("nome_assistente", e.target.value)}
                required
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => update("enabled", e.target.checked)}
                className="h-4 w-4 rounded"
              />
              <span>Ativo</span>
              <span className="text-muted-foreground text-xs ml-1">
                (pode ser alternado também na lista de tenants)
              </span>
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contatos</CardTitle>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 gap-4">
            <Field label="Telefone">
              <Input
                value={config.contatos.telefone}
                onChange={(e) => updateContatos({ telefone: e.target.value })}
                required
              />
            </Field>
            <Field label="E-mail">
              <Input
                type="email"
                value={config.contatos.email}
                onChange={(e) => updateContatos({ email: e.target.value })}
                required
              />
            </Field>
            <Field label="WhatsApp">
              <Input
                value={config.contatos.whatsapp}
                onChange={(e) => updateContatos({ whatsapp: e.target.value })}
                required
              />
            </Field>
            <Field label="Link WhatsApp">
              <Input
                value={config.contatos.whatsapp_link}
                onChange={(e) => updateContatos({ whatsapp_link: e.target.value })}
                required
              />
            </Field>
            <Field label="Horário de atendimento" className="sm:col-span-2">
              <Input
                value={config.contatos.horario_atendimento ?? ""}
                onChange={(e) => updateContatos({ horario_atendimento: e.target.value })}
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">URLs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="App de moradores">
              <Input
                value={config.urls.app_moradores}
                onChange={(e) => updateUrls({ app_moradores: e.target.value })}
                required
              />
            </Field>
            <Field label="Portal Resolva Fácil">
              <Input
                value={config.urls.portal_resolva_facil}
                onChange={(e) => updateUrls({ portal_resolva_facil: e.target.value })}
                required
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identidade visual</CardTitle>
            <CardDescription>
              Cores aplicadas na UI dos usuários do tenant. Hex em formato #RRGGBB.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-3 gap-4">
            <ColorField label="Primária" value={theme.primary ?? ""} onChange={(v) => updateTheme({ primary: v })} />
            <ColorField label="Secundária" value={theme.secondary ?? ""} onChange={(v) => updateTheme({ secondary: v })} />
            <ColorField label="Accent" value={theme.accent ?? ""} onChange={(v) => updateTheme({ accent: v })} />
          </CardContent>
        </Card>

        <ModulosContratadosCard
          value={config.modulos_contratados ?? {}}
          onChange={updateModulos}
        />

        {config.modulos_contratados?.cobrancas && (
          <CobrancasCard
            value={config.cobrancas ?? null}
            onChange={updateCobrancas}
            tenantId={tenantId}
          />
        )}

        <OpenAIKeyCard value={openaiValue} onChange={updateOpenAI} />

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Prompts</CardTitle>
            <CardDescription>Mude com cuidado — afeta o tom e a qualidade das respostas.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Prompt principal" hint="System prompt usado na geração de resposta">
              <Textarea
                value={config.prompt_principal}
                onChange={(e) => update("prompt_principal", e.target.value)}
                rows={5}
                required
              />
            </Field>
            <Field label="Prompt de reformulação" hint="Refraseia a pergunta antes de buscar embeddings">
              <Textarea
                value={config.prompt_formatacao}
                onChange={(e) => update("prompt_formatacao", e.target.value)}
                rows={3}
                required
              />
            </Field>
            <Field label="Prompt de esclarecimento" hint="Resposta para perguntas vagas (categoria -1)">
              <Textarea
                value={config.prompt_esclarecimento}
                onChange={(e) => update("prompt_esclarecimento", e.target.value)}
                rows={3}
                required
              />
            </Field>
            <Field label="Prompt de classificação" hint="Define as categorias possíveis e como classificar">
              <Textarea
                value={config.categorias_prompt}
                onChange={(e) => update("categorias_prompt", e.target.value)}
                rows={6}
                required
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Mensagens de fallback</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Resposta sem documento">
              <Textarea
                value={config.resposta_sem_documento}
                onChange={(e) => update("resposta_sem_documento", e.target.value)}
                rows={2}
                required
              />
            </Field>
            <Field label="Mensagem 'não encontrado'">
              <Textarea
                value={config.mensagem_nao_encontrada}
                onChange={(e) => update("mensagem_nao_encontrada", e.target.value)}
                rows={2}
                required
              />
            </Field>
          </CardContent>
        </Card>

        {erro && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {erro}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="outline" asChild>
            <Link href={`/admin/tenants/${tenantId}`}>Cancelar</Link>
          </Button>
          <Button type="submit" disabled={enviando}>
            {enviando ? <Loader2 className="animate-spin" /> : <Save />}
            Salvar
          </Button>
        </div>
      </form>
    </>
  );
}


function BackLink({ tenantId }: { tenantId: string }) {
  return (
    <Link
      href={`/admin/tenants/${tenantId}`}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
    >
      <ChevronLeft className="h-3 w-3" /> Voltar
    </Link>
  );
}

function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1 ${className ?? ""}`}>
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      <div className="flex gap-2">
        <input
          type="color"
          value={value || "#CB1D40"}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-14 rounded-md border cursor-pointer"
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          pattern="^#[A-Fa-f0-9]{6}$"
          placeholder="#CB1D40"
        />
      </div>
    </div>
  );
}
