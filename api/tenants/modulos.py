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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from api.tenants.models import TenantConfig


class ModuloInfo(BaseModel):
    """Metadados de um módulo do catálogo."""

    slug: str
    label: str
    descricao: str


# Catálogo único e centralizado. Slugs aqui são a fonte da verdade —
# o validator de `TenantConfig.modulos_contratados` rejeita chaves fora desta lista.
MODULOS_DISPONIVEIS: dict[str, ModuloInfo] = {
    "chat": ModuloInfo(
        slug="chat",
        label="Bella Chat",
        descricao="Assistente virtual condominial (chatbot RAG sobre documentos).",
    ),
    "cobrancas": ModuloInfo(
        slug="cobrancas",
        label="Bella Cobranças",
        descricao=(
            "Extração inteligente de PDFs de cobrança condominial em JSON "
            "estruturado (módulo implementado em branch paralelo)."
        ),
    ),
    "atas": ModuloInfo(
        slug="atas",
        label="Bella Atas",
        descricao=(
            "Geração, comparação e correção de atas de assembleia condominial "
            "a partir de gravação de áudio."
        ),
    ),
}

# Conjunto de slugs válidos — usado pelo validator do `TenantConfig`.
MODULO_SLUGS: frozenset[str] = frozenset(MODULOS_DISPONIVEIS.keys())


def tenant_tem_modulo(tenant_config: "TenantConfig", slug: str) -> bool:
    """Retorna True se o tenant contratou o módulo `slug` (e está marcado como ativo)."""
    return bool(tenant_config.modulos_contratados.get(slug, False))
