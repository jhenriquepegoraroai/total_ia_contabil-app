"""
Catálogo de módulos contratáveis do SaaS Bella.

Cada tenant contrata um ou mais módulos. O super admin marca quais via UI;
a configuração persiste em `TenantConfig.modulos_contratados` (slug → bool).

Para adicionar um novo módulo ao catálogo:
  1. Acrescente uma entrada em `MODULOS_DISPONIVEIS`.
  2. Use `require_module("<slug>")` (em `api/tenants/deps.py`) como dependency
     nas rotas exclusivas dele.
  3. Atualize a UI de cadastro de tenant para incluir o checkbox.

Convenções de slug: snake-lower, ASCII puro (sem cedilha/til), curto.
Slugs são gravados em JSONB no DB — renomear depois exige migration de dados.

Este módulo é deliberadamente "puro" (sem FastAPI/auth) para poder ser
importado pelo `TenantConfig` sem ciclo. A dependency FastAPI vive em
`api/tenants/deps.py`.

Portfólio do demo (maio 2026):
  chat      → Agente Conversacional     — disponível
  atas      → Agente de Atas            — disponível
  cobrancas → Agente Financeiro         — disponível (inclui extração DocumentAI)
  churn     → Agente de Churn           — preview (stub sem backend real)
  folha     → Agente Folha de Pagamento — preview (roadmap)
  sindico   → Agente do Síndico         — preview (roadmap)
  chamado   → Agente de Chamado         — preview (roadmap)
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from api.tenants.models import TenantConfig

# Modalidades de venda: A=acoplado Lello, B=standalone, C=dados de mercado.
Modalidade = Literal["A", "B", "C"]
StatusModulo = Literal["disponivel", "preview"]


class ModuloInfo(BaseModel):
    """Metadados de um módulo do catálogo."""

    slug: str
    label: str
    descricao: str

    # Campos comerciais — usados no demo, landing e calculadora de ROI.
    nome_produto: str = ""
    tagline: str = ""
    icone: str = "bot"
    status: StatusModulo = "disponivel"
    modalidades: list[Modalidade] = ["A", "B"]


# Catálogo único e centralizado. Slugs aqui são a fonte da verdade —
# o validator de `TenantConfig.modulos_contratados` rejeita chaves fora desta lista.
MODULOS_DISPONIVEIS: dict[str, ModuloInfo] = {
    "chat": ModuloInfo(
        slug="chat",
        label="Bella Chat",
        descricao="Assistente virtual condominial (chatbot RAG sobre documentos).",
        nome_produto="Agente Conversacional",
        tagline="Responde perguntas sobre documentos do condomínio em segundos.",
        icone="message-circle",
        status="disponivel",
        modalidades=["A", "B"],
    ),
    "atas": ModuloInfo(
        slug="atas",
        label="Bella Atas",
        descricao=(
            "Geração, comparação e correção de atas de assembleia condominial "
            "a partir de gravação de áudio."
        ),
        nome_produto="Agente de Atas",
        tagline="Transcreve, gera e aprova atas de assembleia com workflow digital.",
        icone="file-text",
        status="disponivel",
        modalidades=["A", "B"],
    ),
    "cobrancas": ModuloInfo(
        slug="cobrancas",
        label="Bella Cobranças",
        descricao=(
            "Extração estruturada de PDFs de cobrança (boletos, demonstrativos) "
            "via Document AI e análise financeira condominial."
        ),
        nome_produto="Agente Financeiro",
        tagline="Extrai dados de boletos automaticamente e monitora inadimplência.",
        icone="banknote",
        status="disponivel",
        modalidades=["A", "B"],
    ),
    "churn": ModuloInfo(
        slug="churn",
        label="Bella Churn",
        descricao=(
            "Previsão de risco de saída de condôminos inadimplentes com base "
            "em histórico de pagamentos e padrão de engajamento. (Em desenvolvimento)"
        ),
        nome_produto="Agente de Churn",
        tagline="Identifica condôminos com risco de saída antes que isso aconteça.",
        icone="trending-down",
        status="preview",
        modalidades=["A", "B", "C"],
    ),
    "folha": ModuloInfo(
        slug="folha",
        label="Bella Folha",
        descricao=(
            "Automação de folha de pagamento dos funcionários do condomínio "
            "(zelador, porteiros, limpeza) com encargos e obrigações. (Roadmap)"
        ),
        nome_produto="Agente Folha de Pagamento",
        tagline="Processa a folha dos funcionários do condomínio sem planilha.",
        icone="banknote",
        status="preview",
        modalidades=["A", "B"],
    ),
    "sindico": ModuloInfo(
        slug="sindico",
        label="Bella Síndico",
        descricao=(
            "Assistente do síndico para decisões do dia a dia: prazos, "
            "obrigações legais, priorização de demandas e comunicação. (Roadmap)"
        ),
        nome_produto="Agente do Síndico",
        tagline="Copiloto do síndico para a gestão do condomínio.",
        icone="bot",
        status="preview",
        modalidades=["A", "B"],
    ),
    "chamado": ModuloInfo(
        slug="chamado",
        label="Bella Chamado",
        descricao=(
            "Atendimento e triagem automática de chamados de moradores, "
            "roteando para o responsável certo. (Roadmap)"
        ),
        nome_produto="Agente Atendimento de Chamado",
        tagline="Recebe, tria e encaminha chamados dos moradores automaticamente.",
        icone="message-circle",
        status="preview",
        modalidades=["A", "B"],
    ),
}

# Conjunto de slugs válidos — usado pelo validator do `TenantConfig`.
MODULO_SLUGS: frozenset[str] = frozenset(MODULOS_DISPONIVEIS.keys())


def tenant_tem_modulo(tenant_config: "TenantConfig", slug: str) -> bool:
    """Retorna True se o tenant contratou o módulo `slug` (e está marcado como ativo)."""
    return bool(tenant_config.modulos_contratados.get(slug, False))
