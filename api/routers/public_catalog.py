"""
Endpoints públicos do catálogo de produtos Bella.

Sem autenticação — usados pela landing page e qualquer cliente externo
que queira exibir o portfólio de módulos disponíveis.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.tenants.modulos import MODULOS_DISPONIVEIS, ModuloInfo

router = APIRouter(prefix="/modulos", tags=["catalogo-publico"])


@router.get("", response_model=list[ModuloInfo])
async def listar_modulos() -> list[ModuloInfo]:
    """Retorna catálogo completo de módulos (disponíveis + preview)."""
    return list(MODULOS_DISPONIVEIS.values())
