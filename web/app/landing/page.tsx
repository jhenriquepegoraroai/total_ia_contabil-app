/**
 * Landing institucional da Lello AI Platform.
 *
 * Página pública — sem autenticação.
 * Server Component: busca módulos do backend no render; fallback hardcoded
 * se a API estiver fora do ar (ex: demo offline).
 */

import Link from "next/link";

import { Calculadora } from "@/components/landing/Calculadora";
import { ModalidadePlanos } from "@/components/landing/ModalidadePlanos";
import { ModuloCard } from "@/components/landing/ModuloCard";

/* -------------------------------------------------------------------------- */
/* Tipos                                                                       */
/* -------------------------------------------------------------------------- */

interface ModuloInfo {
  slug: string;
  nome_produto: string;
  tagline: string;
  descricao: string;
  icone: string;
  status: "disponivel" | "preview";
  modalidades: string[];
}

/* -------------------------------------------------------------------------- */
/* Fallback hardcoded (espelha api/tenants/modulos.py)                         */
/* -------------------------------------------------------------------------- */

const MODULOS_FALLBACK: ModuloInfo[] = [
  {
    slug: "chat",
    nome_produto: "Agente Conversacional",
    tagline: "Responde perguntas sobre documentos do condomínio em segundos.",
    descricao: "Assistente virtual condominial (chatbot RAG sobre documentos).",
    icone: "message-circle",
    status: "disponivel",
    modalidades: ["A", "B"],
  },
  {
    slug: "atas",
    nome_produto: "Agente de Atas",
    tagline: "Transcreve, gera e aprova atas de assembleia com workflow digital.",
    descricao:
      "Geração, comparação e correção de atas de assembleia condominial a partir de gravação de áudio.",
    icone: "file-text",
    status: "disponivel",
    modalidades: ["A", "B"],
  },
  {
    slug: "cobrancas",
    nome_produto: "Agente Financeiro",
    tagline: "Extrai dados de boletos automaticamente e monitora inadimplência.",
    descricao:
      "Extração estruturada de PDFs de cobrança via Document AI e análise financeira condominial.",
    icone: "banknote",
    status: "disponivel",
    modalidades: ["A", "B"],
  },
  {
    slug: "churn",
    nome_produto: "Agente de Churn",
    tagline: "Identifica condôminos com risco de saída antes que isso aconteça.",
    descricao:
      "Previsão de risco de saída de condôminos inadimplentes com base em histórico de pagamentos.",
    icone: "trending-down",
    status: "preview",
    modalidades: ["A", "B", "C"],
  },
  {
    slug: "folha",
    nome_produto: "Agente Folha de Pagamento",
    tagline: "Processa a folha dos funcionários do condomínio sem planilha.",
    descricao:
      "Automação de folha de pagamento dos funcionários do condomínio com encargos e obrigações.",
    icone: "banknote",
    status: "preview",
    modalidades: ["A", "B"],
  },
  {
    slug: "sindico",
    nome_produto: "Agente do Síndico",
    tagline: "Copiloto do síndico para a gestão do condomínio.",
    descricao:
      "Assistente do síndico para prazos, obrigações legais e priorização de demandas.",
    icone: "bot",
    status: "preview",
    modalidades: ["A", "B"],
  },
  {
    slug: "chamado",
    nome_produto: "Agente Atendimento de Chamado",
    tagline: "Recebe, tria e encaminha chamados dos moradores automaticamente.",
    descricao:
      "Atendimento e triagem automática de chamados de moradores, roteando para o responsável certo.",
    icone: "message-circle",
    status: "preview",
    modalidades: ["A", "B"],
  },
];

/* -------------------------------------------------------------------------- */
/* Busca de módulos (server-side)                                               */
/* -------------------------------------------------------------------------- */

async function buscarModulos(): Promise<ModuloInfo[]> {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/modulos`, { cache: "no-store" });
    if (!res.ok) return MODULOS_FALLBACK;
    return (await res.json()) as ModuloInfo[];
  } catch {
    return MODULOS_FALLBACK;
  }
}

/* -------------------------------------------------------------------------- */
/* Dados estáticos das seções                                                   */
/* -------------------------------------------------------------------------- */

const MODALIDADES = [
  {
    letra: "A",
    emoji: "🏢",
    titulo: "Acoplada",
    ideal: "Administradoras que operam com white-label Lello.",
    descricao:
      "Integração nativa com os sistemas existentes. Implantação rápida sem precisar trocar infraestrutura.",
    destaque: "Menor fricção de implantação",
  },
  {
    letra: "B",
    emoji: "🚀",
    titulo: "Standalone",
    ideal: "Administradoras independentes que querem IA própria.",
    descricao:
      "Infraestrutura isolada, domínio e identidade da marca próprios. Controle total sobre os dados.",
    destaque: "Autonomia total",
  },
  {
    letra: "C",
    emoji: "📊",
    titulo: "Dados de Mercado",
    ideal: "Seguradoras, bancos e fintechs imobiliárias.",
    descricao:
      "Acesso a inteligência de mercado anonimizada em escala. Insights inéditos sobre o mercado condominial LATAM.",
    destaque: "Novo modelo de receita",
  },
];

const CAMADAS = [
  {
    numero: 1,
    nome: "Compreensão",
    horizonte: "Hoje",
    descricao: "Chat, Atas, Cobranças, Extração de dados",
    badge: "Em produção",
    badgeColor: "bg-green-100 text-green-800",
    check: true,
  },
  {
    numero: 2,
    nome: "Inteligência",
    horizonte: "9–12 meses",
    descricao: "ISC (Índice de Saúde do Condomínio), predição de inadimplência",
    badge: "Em desenvolvimento",
    badgeColor: "bg-blue-100 text-blue-800",
    check: false,
  },
  {
    numero: 3,
    nome: "Automação",
    horizonte: "12–18 meses",
    descricao:
      "Comunicados automáticos, convocações, assembleias digitais",
    badge: "Roadmap",
    badgeColor: "bg-purple-100 text-purple-800",
    check: false,
  },
  {
    numero: 4,
    nome: "Mercado",
    horizonte: "18–24 meses",
    descricao:
      "Dados anonimizados para seguradoras, bancos e imobiliárias",
    badge: "Visão",
    badgeColor: "bg-gray-100 text-gray-600",
    check: false,
  },
];

/* -------------------------------------------------------------------------- */
/* Componente da página                                                         */
/* -------------------------------------------------------------------------- */

export default async function LandingPage() {
  const modulos = await buscarModulos();

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ------------------------------------------------------------------ */}
      {/* NAV                                                                  */}
      {/* ------------------------------------------------------------------ */}
      <nav className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <span className="font-bold text-xl text-primary tracking-tight">
            Lello AI Platform
          </span>
          <div className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            <a href="#produtos" className="hover:text-foreground transition-colors">
              Produtos
            </a>
            <a href="#calculadora" className="hover:text-foreground transition-colors">
              ROI
            </a>
            <a href="#modalidades" className="hover:text-foreground transition-colors">
              Modalidades
            </a>
            <a href="#visao" className="hover:text-foreground transition-colors">
              Visão
            </a>
          </div>
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground text-sm font-medium h-9 px-4 hover:bg-primary/90 transition-colors"
          >
            Entrar
          </Link>
        </div>
      </nav>

      {/* ------------------------------------------------------------------ */}
      {/* HERO                                                                 */}
      {/* ------------------------------------------------------------------ */}
      <section className="bg-[hsl(var(--primary))] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-36">
          <p className="text-sm font-semibold tracking-widest uppercase opacity-75 mb-4">
            Lello AI Platform
          </p>
          <h1 className="text-4xl sm:text-5xl md:text-7xl font-extrabold leading-tight tracking-tight max-w-4xl">
            IA que transforma administração de condomínios em produto
          </h1>
          <p className="mt-6 text-lg sm:text-xl opacity-80 max-w-2xl leading-relaxed">
            O Brasil tem +500 mil condomínios e R$ 165 bi/ano em
            movimentação. A Lello tem agentes em produção. Agora qualquer
            administradora pode ter o mesmo.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <a
              href="#produtos"
              className="inline-flex items-center justify-center rounded-md border-2 border-white text-white font-semibold h-11 px-6 hover:bg-white hover:text-primary transition-colors"
            >
              Ver os produtos ↓
            </a>
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-md bg-white text-primary font-semibold h-11 px-6 hover:bg-white/90 transition-colors"
            >
              Entrar na plataforma →
            </Link>
          </div>

          {/* Stat strip */}
          <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-8 border-t border-white/20 pt-10">
            {[
              { valor: "+500 mil", label: "condomínios no Brasil" },
              { valor: "R$ 165 bi", label: "em movimentação anual" },
              { valor: "4 agentes", label: "em produção hoje" },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-3xl sm:text-4xl font-extrabold">{stat.valor}</p>
                <p className="mt-1 text-sm opacity-70">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* PORTFÓLIO                                                            */}
      {/* ------------------------------------------------------------------ */}
      <section id="produtos" className="bg-background py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-extrabold">Os Agentes</h2>
            <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
              De documentos a predição — cobrindo toda a operação condominial.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {modulos.map((m) => (
              <ModuloCard key={m.slug} {...m} />
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* CALCULADORA DE ROI                                                   */}
      {/* ------------------------------------------------------------------ */}
      <section id="calculadora" className="bg-muted py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-extrabold">
              Quanto vale para a sua operação?
            </h2>
            <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
              Ajuste os parâmetros da sua carteira e veja a projeção de retorno em tempo real.
            </p>
          </div>
          <Calculadora />
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* MODALIDADES                                                          */}
      {/* ------------------------------------------------------------------ */}
      <section id="modalidades" className="bg-muted py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-extrabold">
              3 formas de contratar
            </h2>
            <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
              Do modelo mais integrado ao mais autônomo — ou uma nova fonte de receita.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {MODALIDADES.map((mod) => (
              <div
                key={mod.letra}
                className="bg-background rounded-xl border border-border p-8 flex flex-col gap-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{mod.emoji}</span>
                  <div>
                    <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                      Modalidade {mod.letra}
                    </span>
                    <h3 className="text-xl font-bold">{mod.titulo}</h3>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed flex-1">
                  <span className="font-medium text-foreground">
                    Ideal para:
                  </span>{" "}
                  {mod.ideal}
                  <br />
                  <br />
                  {mod.descricao}
                </p>
                <div className="pt-2 border-t border-border">
                  <span className="text-xs font-semibold text-primary">
                    ✦ {mod.destaque}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* ESCOLHA SUA MODALIDADE (vitrine estática — sem preço/checkout)       */}
      {/* ------------------------------------------------------------------ */}
      <ModalidadePlanos />

      {/* ------------------------------------------------------------------ */}
      {/* VISÃO ESTRATÉGICA                                                    */}
      {/* ------------------------------------------------------------------ */}
      <section id="visao" className="bg-background py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-extrabold">
              Do atendimento ao mercado
            </h2>
            <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
              Uma plataforma construída em 4 camadas — da compreensão ao ecossistema.
            </p>
          </div>

          {/* Timeline vertical */}
          <div className="relative max-w-3xl mx-auto">
            {/* Linha vertical */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-border md:left-8" />

            <div className="flex flex-col gap-0">
              {CAMADAS.map((camada, idx) => (
                <div key={camada.numero} className="relative flex gap-6 md:gap-8 pb-12 last:pb-0">
                  {/* Círculo numerado */}
                  <div
                    className={`relative z-10 flex-shrink-0 w-12 h-12 md:w-16 md:h-16 rounded-full flex items-center justify-center font-extrabold text-lg border-4 ${
                      idx === 0
                        ? "bg-primary text-white border-primary"
                        : "bg-background text-muted-foreground border-border"
                    }`}
                  >
                    {camada.check ? "✅" : camada.numero}
                  </div>

                  {/* Conteúdo */}
                  <div className="pt-2 flex-1">
                    <div className="flex flex-wrap items-center gap-3 mb-1">
                      <h3 className="text-xl font-bold">{camada.nome}</h3>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full ${camada.badgeColor}`}
                      >
                        {camada.badge}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mb-1">
                      {camada.horizonte}
                    </p>
                    <p className="text-sm leading-relaxed">{camada.descricao}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* PERGUNTA-ÂNCORA                                                      */}
      {/* ------------------------------------------------------------------ */}
      <section className="bg-[hsl(var(--primary))] text-white py-20 sm:py-28">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-sm font-semibold tracking-widest uppercase opacity-70 mb-6">
            A pergunta que mudou tudo
          </p>
          <blockquote className="text-2xl sm:text-3xl md:text-4xl font-bold leading-snug">
            &ldquo;Quais condomínios da minha carteira tiveram aumento de
            inadimplência mencionado em ata nos últimos 6 meses?&rdquo;
          </blockquote>
          <p className="mt-8 text-lg opacity-80 max-w-2xl mx-auto">
            Esta pergunta hoje leva dias. Com a Lello AI Platform, leva
            segundos.
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* CTA FINAL                                                            */}
      {/* ------------------------------------------------------------------ */}
      <section className="bg-slate-900 text-white py-20 sm:py-28">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold">
            Pronto para estruturar IA como produto?
          </h2>
          <p className="mt-4 text-lg text-slate-300">
            Junte-se às administradoras que já transformam dados em vantagem
            competitiva.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <a
              href="#"
              className="inline-flex items-center justify-center rounded-md bg-primary text-white font-semibold h-12 px-8 text-base hover:bg-primary/90 transition-colors"
            >
              Agendar demonstração
            </a>
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-md border border-slate-500 text-slate-300 font-medium h-12 px-8 text-base hover:border-slate-300 hover:text-white transition-colors"
            >
              Entrar na plataforma →
            </Link>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* FOOTER                                                               */}
      {/* ------------------------------------------------------------------ */}
      <footer className="bg-slate-950 text-slate-500 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm">
          <span className="font-bold text-slate-300">Lello AI Platform</span>
          <span>© 2026 Lello AI Platform. Todos os direitos reservados.</span>
          <div className="flex gap-4">
            <Link href="/login" className="hover:text-slate-300 transition-colors">
              Entrar
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
