"""
Endpoints `/tenant-users/*` — gerenciados pelo admin do PRÓPRIO tenant.

Diferente de `/admin/tenants/{id}/users/*` (super admin), aqui o `tenant_id`
SEMPRE vem do JWT — admin de tenant A não consegue tocar tenant B nem
escolhendo via path. Defesa em profundidade exigida pelo RULES.md.

Operações suportadas:
  - GET    /tenant-users          → lista usuários do meu tenant
  - POST   /tenant-users          → cria usuário comum (sindico/morador/atendente)
  - PATCH  /tenant-users/{id}     → edita nome/role/enabled/referencia
  - PATCH  /tenant-users/{id}/password → reseta senha do user

Não permite:
  - Criar/promover a `admin` (só superadmin promove)
  - Criar/editar superadmin (só CLI)
  - Deletar (Fase 3.x — desativar via enabled basta por enquanto)
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from api.admin import users_service
from api.auth import CurrentUser, tenant_admin_required
from api.db import superadmin_session


router = APIRouter(prefix="/tenant-users", tags=["tenant-users"])


# Roles que o admin do tenant PODE criar/atribuir.
# `admin` é deliberadamente excluído — só superadmin promove.
RoleAtribuivel = Literal["sindico", "morador", "atendente"]


# =============================================================================
# Schemas
# =============================================================================
class TenantUserOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    nome: str
    role: str
    referencia: str | None
    enabled: bool
    is_superadmin: bool
    tem_senha: bool
    created_at: datetime


class CreateTenantUser(BaseModel):
    email: EmailStr
    nome: str = Field(..., min_length=2, max_length=120)
    role: RoleAtribuivel = "morador"
    password: str = Field(..., min_length=8, max_length=128)
    referencia: str | None = None


class UpdateTenantUser(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    role: RoleAtribuivel | None = None
    enabled: bool | None = None
    referencia: str | None = None
    referencia_set: bool = False


class ResetPasswordPayload(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


# =============================================================================
# Endpoints
# =============================================================================
@router.get("", response_model=list[TenantUserOut])
async def listar(
    user: Annotated[CurrentUser, Depends(tenant_admin_required)],
) -> list[TenantUserOut]:
    """Lista todos os usuários do meu tenant (do JWT)."""
    async with superadmin_session() as session:
        rows = await users_service.listar_users(session, user.tenant_id)
    return [TenantUserOut(**_serializar(r)) for r in rows]


@router.post("", response_model=TenantUserOut, status_code=status.HTTP_201_CREATED)
async def criar(
    payload: CreateTenantUser,
    user: Annotated[CurrentUser, Depends(tenant_admin_required)],
) -> TenantUserOut:
    """Cria sindico/morador/atendente no meu tenant."""
    if user.is_superadmin and user.tenant_id == "_system":
        raise HTTPException(
            status_code=400,
            detail="Superadmin precisa usar /admin/tenants/{id}/users (não opera no _system).",
        )
    async with superadmin_session() as session:
        try:
            new_id = await users_service.criar_user(
                session,
                tenant_id=user.tenant_id,
                email=payload.email,
                nome=payload.nome.strip(),
                role=payload.role,
                password=payload.password,
                referencia=payload.referencia,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        novo = await users_service.buscar_user(session, user.tenant_id, new_id)
    assert novo is not None
    return TenantUserOut(**_serializar(novo))


@router.patch("/{user_id}", response_model=TenantUserOut)
async def atualizar(
    user_id: UUID,
    payload: UpdateTenantUser,
    user: Annotated[CurrentUser, Depends(tenant_admin_required)],
) -> TenantUserOut:
    """Edita nome/role/enabled/referencia de um usuário do meu tenant."""
    async with superadmin_session() as session:
        try:
            ok = await users_service.atualizar_user(
                session,
                tenant_id=user.tenant_id,
                user_id=user_id,
                nome=payload.nome.strip() if payload.nome else None,
                role=payload.role,
                enabled=payload.enabled,
                referencia=payload.referencia,
                referencia_set=payload.referencia_set,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        atualizado = await users_service.buscar_user(session, user.tenant_id, user_id)
    assert atualizado is not None
    return TenantUserOut(**_serializar(atualizado))


@router.patch("/{user_id}/password", status_code=204)
async def resetar_senha(
    user_id: UUID,
    payload: ResetPasswordPayload,
    user: Annotated[CurrentUser, Depends(tenant_admin_required)],
) -> None:
    """Reseta a senha de um usuário do meu tenant."""
    async with superadmin_session() as session:
        try:
            ok = await users_service.resetar_senha(
                session,
                tenant_id=user.tenant_id,
                user_id=user_id,
                nova_senha=payload.new_password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")


# =============================================================================
# Helpers
# =============================================================================
def _serializar(r: dict) -> dict:
    """Converte dict do service em payload pro response_model (UUID → str)."""
    return {**r, "id": str(r["id"])}
