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

REGRA: este catálogo lista **somente o que a API serve**. Ele é a fonte de
verdade do `require_module()`, que gateia rota — um slug aqui sem backend
correspondente permite que um tenant "contrate" algo que não existe.
Produto que a Lello opera internamente mas a plataforma ainda não expõe
pertence ao catálogo comercial da landing, não a este.

Portfólio servido pela API:
  chat      → Agente Conversacional — RAG sobre documentos do condomínio
  atas      → Agente de Atas        — geração e workflow de ata de assembleia
  cobrancas → Agente Financeiro     — extração de PDFs via Document AI
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
    # `churn` entra aqui junto com o endpoint dele (trilho de ML: zona de
    # features + worker de scoring). Enquanto a API não servir, ele vive só
    # no catálogo comercial da landing, como "em operação na Lello".
}

# Conjunto de slugs válidos — usado pelo validator do `TenantConfig`.
MODULO_SLUGS: frozenset[str] = frozenset(MODULOS_DISPONIVEIS.keys())


def tenant_tem_modulo(tenant_config: "TenantConfig", slug: str) -> bool:
    """Retorna True se o tenant contratou o módulo `slug` (e está marcado como ativo)."""
    return bool(tenant_config.modulos_contratados.get(slug, False))
