"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { ChevronLeft, Save, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, adminCriarTenant } from "@/lib/api";
import type {
  TenantCobrancasConfig,
  TenantConfig,
  TenantOpenAIConfig,
} from "@/lib/types";
import { OpenAIKeyCard } from "@/components/admin/openai-key-card";
import { ModulosContratadosCard } from "@/components/admin/modulos-checkboxes-card";
import { CobrancasCard } from "@/components/admin/cobrancas-card";

const PROMPT_PRINCIPAL_PADRAO =
  "Você é o assistente virtual desta administradora. Responda à pergunta do usuário com base EXCLUSIVAMENTE no contexto fornecido (parágrafos extraídos de documentos do condomínio). Tom: amigável, profissional, claro. Cite as fontes (nome do arquivo e data) ao final. Se a informação não estiver no contexto, responda exatamente: 'Não encontrei essa informação nos documentos do seu condomínio.'";
const PROMPT_FORMATACAO_PADRAO =
  "Reformule a pergunta do usuário para busca em base de documentos de condomínio. Preserve o significado e o sujeito (condomínio, morador, síndico, área comum, data). Não responda — apenas reformule.";
const PROMPT_ESCLARECIMENTO_PADRAO =
  "A pergunta do usuário está vaga ou ambígua. Peça gentilmente para o usuário esclarecer: qual condomínio, qual período, ou qual aspecto específico está perguntando.";
const CATEGORIAS_PROMPT_PADRAO =
  "Classifique a pergunta em uma destas categorias (retorne APENAS o número):\n  0 - Dados cadastrais do condomínio\n  42 - Áreas comuns\n  51 - Resumo de assembleia mais recente\n  65 - Conteúdo de edital\n  67 - Data do edital mais recente\n  68 - Comparação edital vs ata\n  -1 - Pergunta vaga\n  -2 - Outra (busca em documentos)";

export default function NewTenantPage() {
  const router = useRouter();
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Campos do form
  const [tenantId, setTenantId] = useState("");
  const [nomeEmpresa, setNomeEmpresa] = useState("");
  const [nomeAssistente, setNomeAssistente] = useState("Assistente Virtual");
  const [telefone, setTelefone] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [whatsappLink, setWhatsappLink] = useState("");
  const [email, setEmail] = useState("");
  const [appMoradores, setAppMoradores] = useState("");
  const [portalResolva, setPortalResolva] = useState("");
  const [primary, setPrimary] = useState("#CB1D40");
  const [secondary, setSecondary] = useState("#5D0E1F");
  const [accent, setAccent] = useState("#F5B79E");
  const [modalidade, setModalidade] = useState<"A" | "B" | "C">("B");
  const [openai, setOpenai] = useState<TenantOpenAIConfig>({
    mode: "lello",
    api_key: null,
    secret_name: null,
  });
  // Default razoável: novo tenant entra com Bella Chat marcado.
  // O super admin desmarca se não foi contratado.
  const [modulosContratados, setModulosContratados] = useState<Record<string, boolean>>({
    chat: true,
  });
  const [cobrancas, setCobrancas] = useState<TenantCobrancasConfig | null>(null);

  // ---- Preenchimento rápido para demonstração --------------------------
  // Administradora fictícia, usada para mostrar multi-tenancy ao vivo.
  function preencherDemo() {
    setTenantId("demo");
    setNomeEmpresa("Administradora Demonstração");
    setNomeAssistente("Bella");
    setTelefone("(11) 91234-5678");
    setWhatsapp("5511912345678");
    setWhatsappLink("https://wa.me/5511912345678");
    setEmail("contato@exemplo.com.br");
    setAppMoradores("http://localhost:3001");
    setPortalResolva("http://localhost:3001");
    setPrimary("#1E40AF");
    setSecondary("#1E3A8A");
    setAccent("#93C5FD");
    setModalidade("B");
    setModulosContratados({ chat: true });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);

    const config: TenantConfig = {
      schema_version: "2.0",
      tenant_id: tenantId.trim().toLowerCase(),
      nome_empresa: nomeEmpresa.trim(),
      nome_assistente: nomeAssistente.trim() || "Assistente Virtual",
      modalidade,
      enabled: false,
      contatos: {
        telefone: telefone.trim(),
        whatsapp: whatsapp.trim(),
        whatsapp_link: whatsappLink.trim(),
        email: email.trim(),
      },
      urls: {
        app_moradores: appMoradores.trim(),
        portal_resolva_facil: portalResolva.trim(),
      },
      datasource: { type: "postgres_pgvector" },
      theme: {
        primary: primary.toUpperCase(),
        primary_foreground: "#FFFFFF",
        secondary: secondary.toUpperCase(),
        secondary_foreground: "#FFFFFF",
        accent: accent.toUpperCase(),
        accent_foreground: "#0E0E0E",
        ink: "#0E0E0E",
        muted: "#EDEDED",
        background: "#FFFFFF",
        logo_url: "/themes/lello/logo.svg",
        favicon_url: "/themes/lello/favicon.ico",
        font_family: "Inter, sans-serif",
      },
      rag: { top_k: 8, similarity_threshold: 0.3, completion_temperature: 0.2 },
      openai: {
        mode: openai.mode,
        api_key: openai.mode === "custom" ? (openai.api_key || null) : null,
        secret_name: openai.secret_name,
      },
      schemas_estruturados: { condominios: "condominios", areas: "condominio_areas" },
      prompt_principal: PROMPT_PRINCIPAL_PADRAO,
      prompt_formatacao: PROMPT_FORMATACAO_PADRAO,
      prompt_esclarecimento: PROMPT_ESCLARECIMENTO_PADRAO,
      categorias_prompt: CATEGORIAS_PROMPT_PADRAO,
      prompts_por_categoria: {},
      respostas_padrao: {},
      resposta_sem_documento:
        "Não encontramos documentos cadastrados para esse condomínio. Entre em contato com a administradora.",
      mensagem_nao_encontrada:
        "Não encontrei essa informação nos documentos do seu condomínio.",
      modulos_contratados: modulosContratados,
      cobrancas: modulosContratados.cobrancas ? cobrancas : null,
    };

    try {
      await adminCriarTenant(config);
      router.replace("/admin");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  const idValido = /^[a-z][a-z0-9_]{1,31}$/.test(tenantId.trim().toLowerCase());

  return (
    <>
      <header className="mb-6">
        <Link
          href="/admin"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3 w-3" /> Voltar
        </Link>
        <div className="flex items-start justify-between gap-4 mt-2">
          <div>
            <h1 className="text-2xl font-bold">Nova administradora</h1>
            <p className="text-sm text-muted-foreground mt-1">
              O tenant é criado desabilitado. Configure as fontes de dados e habilite depois.
            </p>
          </div>
          <button
            type="button"
            onClick={preencherDemo}
            className="shrink-0 inline-flex items-center gap-2 rounded-lg border-2 border-dashed border-amber-400 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-100 transition-colors"
            title="Pré-preenche os campos com uma administradora fictícia, para demonstração ao vivo"
          >
            ⚡ Demo — Pré-preencher
          </button>
        </div>
      </header>

      <form onSubmit={onSubmit} className="space-y-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identificação</CardTitle>
            <CardDescription>Dados básicos da administradora.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="ID do tenant" hint="snake-lower, único (ex: apsa, graiche)">
              <Input
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="apsa"
                required
                pattern="[a-z][a-z0-9_]{1,31}"
                autoFocus
              />
              {tenantId && !idValido && (
                <p className="text-xs text-destructive mt-1">
                  Use apenas letras minúsculas, números e underscore. 2 a 32 caracteres.
                </p>
              )}
            </Field>
            <Field label="Nome da empresa">
              <Input
                value={nomeEmpresa}
                onChange={(e) => setNomeEmpresa(e.target.value)}
                placeholder="APSA Administradora"
                required
              />
            </Field>
            <Field label="Nome do assistente" hint="Como o bot se apresenta ao usuário">
              <Input
                value={nomeAssistente}
                onChange={(e) => setNomeAssistente(e.target.value)}
                placeholder="Assistente Virtual"
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contatos</CardTitle>
            <CardDescription>Aparece nas respostas do assistente quando aplicável.</CardDescription>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 gap-4">
            <Field label="Telefone">
              <Input
                value={telefone}
                onChange={(e) => setTelefone(e.target.value)}
                placeholder="11 1234-5678"
                required
              />
            </Field>
            <Field label="E-mail">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="atendimento@empresa.com.br"
                required
              />
            </Field>
            <Field label="WhatsApp">
              <Input
                value={whatsapp}
                onChange={(e) => setWhatsapp(e.target.value)}
                placeholder="11 91234-5678"
                required
              />
            </Field>
            <Field label="Link WhatsApp" hint="https://wa.me/55XXXXXXXXXXX">
              <Input
                value={whatsappLink}
                onChange={(e) => setWhatsappLink(e.target.value)}
                placeholder="https://wa.me/5511912345678"
                required
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
                value={appMoradores}
                onChange={(e) => setAppMoradores(e.target.value)}
                placeholder="https://app.empresa.com.br"
                required
              />
            </Field>
            <Field label="Portal Resolva Fácil">
              <Input
                value={portalResolva}
                onChange={(e) => setPortalResolva(e.target.value)}
                placeholder="https://portal.empresa.com.br"
                required
              />
            </Field>
          </CardContent>
        </Card>

        {/* ---- Modalidade ---- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Modalidade de contratação</CardTitle>
            <CardDescription>
              Define como este tenant se integra à plataforma.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-3 gap-3">
              {(
                [
                  { value: "A", emoji: "🏢", titulo: "Acoplada", desc: "White-label Lello — integração nativa" },
                  { value: "B", emoji: "🚀", titulo: "Standalone", desc: "Administradora independente — infra isolada" },
                  { value: "C", emoji: "📊", titulo: "Dados de Mercado", desc: "Acesso à inteligência anonimizada" },
                ] as const
              ).map((op) => (
                <button
                  key={op.value}
                  type="button"
                  onClick={() => setModalidade(op.value)}
                  className={`flex flex-col gap-1 rounded-lg border-2 p-4 text-left transition-colors ${
                    modalidade === op.value
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/40"
                  }`}
                >
                  <span className="text-xl">{op.emoji}</span>
                  <span className="font-semibold text-sm">
                    {op.value} — {op.titulo}
                  </span>
                  <span className="text-xs text-muted-foreground">{op.desc}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ---- Identidade visual ---- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identidade visual</CardTitle>
            <CardDescription>
              Cores aplicadas no chat dos usuários do tenant. Substituir os defaults da Lello.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid sm:grid-cols-3 gap-4">
              <ColorField label="Primária" value={primary} onChange={setPrimary} />
              <ColorField label="Secundária" value={secondary} onChange={setSecondary} />
              <ColorField label="Accent" value={accent} onChange={setAccent} />
            </div>
            {/* Preview em tempo real */}
            <div className="rounded-lg border border-border overflow-hidden">
              <div
                className="h-10 flex items-center px-4 gap-3"
                style={{ backgroundColor: primary }}
              >
                <span className="text-white text-sm font-bold">{nomeEmpresa || "Nome da empresa"}</span>
              </div>
              <div className="flex gap-2 p-3 bg-white">
                <span
                  className="rounded px-3 py-1 text-xs font-semibold text-white"
                  style={{ backgroundColor: primary }}
                >
                  Botão primário
                </span>
                <span
                  className="rounded px-3 py-1 text-xs font-semibold text-white"
                  style={{ backgroundColor: secondary }}
                >
                  Secundário
                </span>
                <span
                  className="rounded px-3 py-1 text-xs font-semibold"
                  style={{ backgroundColor: accent, color: "#0E0E0E" }}
                >
                  Accent
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <ModulosContratadosCard
          value={modulosContratados}
          onChange={setModulosContratados}
        />

        {modulosContratados.cobrancas && (
          <CobrancasCard value={cobrancas} onChange={setCobrancas} />
        )}

        <OpenAIKeyCard value={openai} onChange={setOpenai} />

        {erro && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {erro}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="outline" asChild>
            <Link href="/admin">Cancelar</Link>
          </Button>
          <Button type="submit" disabled={enviando || !idValido}>
            {enviando ? (
              <>
                <Loader2 className="animate-spin" /> Criando...
              </>
            ) : (
              <>
                <Save /> Criar administradora
              </>
            )}
          </Button>
        </div>
      </form>
    </>
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
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-14 rounded-md border cursor-pointer"
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          pattern="^#[A-Fa-f0-9]{6}$"
          required
        />
      </div>
    </div>
  );
}
