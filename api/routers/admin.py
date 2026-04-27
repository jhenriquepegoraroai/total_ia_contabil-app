"""
Endpoints /admin/* — restritos a superadmin.

Todas as rotas usam `superadmin_session` (sem RLS) e registram audit log.
Fonte de verdade dos tenant configs é o DB; após cada mutação, o registry
em memória é recarregado para refletir a mudança nas próximas requests.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.admin import service as admin_service
from api.auth import CurrentUser, superadmin_required
from api.db import superadmin_session
from api.tenants.models import TenantConfig


router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Schemas
# =============================================================================
class TenantSummary(BaseModel):
    id: str
    nome_empresa: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    qtde_documents: int
    qtde_embeddings: int
    qtde_users: int
    datasource_type: str | None = None


class TenantDetail(BaseModel):
    id: str
    nome_empresa: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    config: TenantConfig


class EnabledPatch(BaseModel):
    enabled: bool


class AuditEntry(BaseModel):
    id: int
    actor_user_id: str
    actor_email: str
    action: str
    target_tenant_id: str | None
    payload: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


# =============================================================================
# Helpers
# =============================================================================
def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.client.host if request.client else None, request.headers.get("user-agent")


# =============================================================================
# Endpoints
# =============================================================================
@router.get("/tenants", response_model=list[TenantSummary])
async def listar(
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[TenantSummary]:
    async with superadmin_session() as session:
        rows = await admin_service.listar_tenants(session)
    out: list[TenantSummary] = []
    for r in rows:
        cfg = r.get("config_json") or {}
        ds_type = (cfg.get("datasource") or {}).get("type") if isinstance(cfg, dict) else None
        out.append(
            TenantSummary(
                id=r["id"],
                nome_empresa=r["nome_empresa"],
                enabled=r["enabled"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                qtde_documents=r["qtde_documents"],
                qtde_embeddings=r["qtde_embeddings"],
                qtde_users=r["qtde_users"],
                datasource_type=ds_type,
            )
        )
    return out


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
async def detalhe(
    tenant_id: str,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TenantDetail:
    async with superadmin_session() as session:
        r = await admin_service.buscar_tenant(session, tenant_id)
    if not r or not r.get("config_json"):
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' não encontrado.")
    return TenantDetail(
        id=r["id"],
        nome_empresa=r["nome_empresa"],
        enabled=r["enabled"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        config=TenantConfig(**r["config_json"]),
    )


@router.post("/tenants", response_model=TenantDetail, status_code=status.HTTP_201_CREATED)
async def criar(
    payload: TenantConfig,
    request: Request,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TenantDetail:
    ip, ua = _client_meta(request)
    async with superadmin_session() as session:
        try:
            await admin_service.criar_tenant(
                session,
                payload,
                actor_user_id=user.user_id,
                actor_email=user.user_id,  # email é guardado no claim sub do superadmin
                ip=ip,
                user_agent=ua,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        r = await admin_service.buscar_tenant(session, payload.tenant_id)

    # Recarrega registry em memória para refletir o novo tenant
    registry = request.app.state.tenant_registry
    async with superadmin_session() as session:
        await registry.recarregar(session)

    assert r is not None
    return TenantDetail(
        id=r["id"],
        nome_empresa=r["nome_empresa"],
        enabled=r["enabled"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        config=TenantConfig(**r["config_json"]),
    )


@router.put("/tenants/{tenant_id}", response_model=TenantDetail)
async def atualizar(
    tenant_id: str,
    payload: TenantConfig,
    request: Request,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TenantDetail:
    ip, ua = _client_meta(request)
    async with superadmin_session() as session:
        try:
            await admin_service.atualizar_tenant(
                session,
                tenant_id,
                payload,
                actor_user_id=user.user_id,
                actor_email=user.user_id,
                ip=ip,
                user_agent=ua,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        r = await admin_service.buscar_tenant(session, tenant_id)

    registry = request.app.state.tenant_registry
    async with superadmin_session() as session:
        await registry.recarregar(session)

    assert r is not None
    return TenantDetail(
        id=r["id"],
        nome_empresa=r["nome_empresa"],
        enabled=r["enabled"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        config=TenantConfig(**r["config_json"]),
    )


@router.patch("/tenants/{tenant_id}/enabled", response_model=TenantSummary)
async def toggle_enabled(
    tenant_id: str,
    payload: EnabledPatch,
    request: Request,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TenantSummary:
    ip, ua = _client_meta(request)
    async with superadmin_session() as session:
        try:
            await admin_service.setar_enabled(
                session,
                tenant_id,
                payload.enabled,
                actor_user_id=user.user_id,
                actor_email=user.user_id,
                ip=ip,
                user_agent=ua,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    registry = request.app.state.tenant_registry
    async with superadmin_session() as session:
        await registry.recarregar(session)
        rows = await admin_service.listar_tenants(session)

    target = next((r for r in rows if r["id"] == tenant_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado após update.")
    cfg = target.get("config_json") or {}
    ds_type = (cfg.get("datasource") or {}).get("type") if isinstance(cfg, dict) else None
    return TenantSummary(
        id=target["id"],
        nome_empresa=target["nome_empresa"],
        enabled=target["enabled"],
        created_at=target["created_at"],
        updated_at=target["updated_at"],
        qtde_documents=target["qtde_documents"],
        qtde_embeddings=target["qtde_embeddings"],
        qtde_users=target["qtde_users"],
        datasource_type=ds_type,
    )


@router.get("/audit", response_model=list[AuditEntry])
async def audit(
    user: Annotated[CurrentUser, Depends(superadmin_required)],
    limit: int = 100,
    target_tenant_id: str | None = None,
) -> list[AuditEntry]:
    async with superadmin_session() as session:
        rows = await admin_service.listar_audit(
            session, limit=limit, target_tenant_id=target_tenant_id
        )
    return [
        AuditEntry(
            id=r["id"],
            actor_user_id=str(r["actor_user_id"]),
            actor_email=r["actor_email"],
            action=r["action"],
            target_tenant_id=r["target_tenant_id"],
            payload=r["payload"],
            ip_address=r["ip_address"],
            user_agent=r["user_agent"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
