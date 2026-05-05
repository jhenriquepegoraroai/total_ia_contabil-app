"""
Dependencies FastAPI ligadas ao tenant atual.

Mantemos isto separado de `api/tenants/modulos.py` (catálogo puro) para
que o `TenantConfig` possa importar o catálogo sem puxar FastAPI/JWT.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from api.auth import CurrentUser, usuario_atual
from api.tenants.modulos import MODULO_SLUGS, tenant_tem_modulo


def require_module(slug: str):
    """
    Factory de dependency FastAPI que exige que o tenant atual tenha o módulo `slug`.

    Uso:
        @router.get("/cobrancas/jobs", dependencies=[Depends(require_module("cobrancas"))])
        async def listar_jobs(...): ...

    Comportamento:
      - Superadmin (`is_superadmin=True`) passa sempre — opera fora dos módulos.
      - Tenant desabilitado → 404 (registry levanta).
      - Tenant sem o módulo contratado → 403 com mensagem clara.

    Levanta `ValueError` na construção se `slug` não está no catálogo —
    falha cedo no boot, não em runtime.
    """
    if slug not in MODULO_SLUGS:
        raise ValueError(
            f"Módulo '{slug}' não existe no catálogo. Disponíveis: {sorted(MODULO_SLUGS)}"
        )

    async def _dep(
        request: Request,
        user: Annotated[CurrentUser, Depends(usuario_atual)],
    ) -> CurrentUser:
        if user.is_superadmin:
            return user
        registry = request.app.state.tenant_registry
        try:
            tenant_config = registry.get(user.tenant_id, only_enabled=True)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not tenant_tem_modulo(tenant_config, slug):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant '{user.tenant_id}' não contratou o módulo '{slug}'.",
            )
        return user

    _dep.__name__ = f"require_module_{slug}"
    return _dep
