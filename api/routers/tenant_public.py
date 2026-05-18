"""
Endpoints públicos de tenant — sem autenticação.

Expõe apenas metadados não-sensíveis usados pelo frontend para aplicar
theming, logo e favicon antes do login. Não expõe prompts, configurações
internas, credenciais ou dados de usuários.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/tenants", tags=["tenant-public"])


class TemaPublico(BaseModel):
    """Dados de aparência do tenant — seguros para expor sem autenticação."""

    tenant_id: str
    nome_empresa: str
    nome_assistente: str
    modalidade: str
    primary: str
    secondary: str
    accent: str
    ink: str
    muted: str
    background: str
    logo_url: str
    favicon_url: str
    font_family: str


@router.get("/{tenant_id}/tema", response_model=TemaPublico)
async def tema_publico(tenant_id: str, request: Request) -> TemaPublico:
    """
    Retorna os dados visuais de um tenant (cores, logo, favicon).
    Não requer autenticação — usado pelo frontend para aplicar CSS variables
    antes e durante o login.
    """
    registry = request.app.state.tenant_registry
    try:
        cfg = registry.get(tenant_id, only_enabled=True)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' não encontrado.")

    t = cfg.theme
    return TemaPublico(
        tenant_id=cfg.tenant_id,
        nome_empresa=cfg.nome_empresa,
        nome_assistente=cfg.nome_assistente,
        modalidade=cfg.modalidade,
        primary=t.primary,
        secondary=t.secondary,
        accent=t.accent,
        ink=t.ink,
        muted=t.muted,
        background=t.background,
        logo_url=t.logo_url,
        favicon_url=t.favicon_url,
        font_family=t.font_family,
    )
