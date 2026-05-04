"""
Endpoints `/atas/*` — Bella Atas (geração, comparação, correção).

Todas as rotas exigem:
  - usuário autenticado do tenant (não superadmin, exceto pra suporte)
  - tenant com módulo `atas` contratado (require_module)

Bootstrap (Fase 2): só os endpoints CRUD básicos estão funcionais.
Os endpoints de pipeline (gerar, comparar, corrigir, transcrever) retornam
501 Not Implemented até as fases correspondentes.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from api.atas import jobs_service
from api.atas.schema import AtaCreate, AtaDetail, AtaSummary
from api.auth import CurrentUser, usuario_atual
from api.db import tenant_session
from api.tenants.deps import require_module


router = APIRouter(prefix="/atas", tags=["atas"])


# =============================================================================
# Dependency — usuário do tenant (não superadmin, não _system)
# =============================================================================
async def tenant_user_required(
    user: Annotated[CurrentUser, Depends(usuario_atual)],
) -> CurrentUser:
    """
    Aceita qualquer usuário do tenant (consultor/admin, síndico, presidente).
    Permissão por ata específica (sindico_user_id/presidente_user_id) é
    verificada nos handlers de cada operação na Fase 7.
    """
    if user.is_superadmin:
        # Superadmin pode ler para suporte; bloqueio fica nos endpoints de
        # ação (criar, gerar, aprovar). Aqui passa.
        return user
    if user.tenant_id == "_system":
        raise HTTPException(status_code=403, detail="Tenant '_system' é reservado.")
    return user


# =============================================================================
# CRUD básico — funcional na Fase 2
# =============================================================================
@router.get(
    "",
    response_model=list[AtaSummary],
    dependencies=[Depends(require_module("atas"))],
)
async def listar_atas(
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
    limit: int = 100,
) -> list[AtaSummary]:
    """Lista atas do tenant. Filtros mais finos (por status, ator) virão nas próximas fases."""
    async with tenant_session(user.tenant_id) as session:
        rows = await jobs_service.listar_atas(session, user.tenant_id, limit=limit)
    return [_ata_summary(r) for r in rows]


@router.post(
    "",
    response_model=AtaDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module("atas"))],
)
async def criar_ata(
    payload: AtaCreate,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> AtaDetail:
    """Cria uma ata em status='rascunho'. O consultor é o usuário autenticado."""
    if user.is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Superadmin não cria atas — use a conta do consultor do tenant.",
        )
    async with tenant_session(user.tenant_id) as session:
        ata_id = await jobs_service.criar_ata(
            session,
            tenant_id=user.tenant_id,
            titulo=payload.titulo,
            referencia=payload.referencia,
            consultor_user_id=UUID(user.user_id),
            sindico_user_id=payload.sindico_user_id,
            presidente_user_id=payload.presidente_user_id,
        )
        ata = await jobs_service.buscar_ata(session, user.tenant_id, ata_id)
    assert ata is not None
    logger.info(f"[atas] criada {ata_id} tenant={user.tenant_id}")
    return _ata_detail(ata)


@router.get(
    "/{ata_id}",
    response_model=AtaDetail,
    dependencies=[Depends(require_module("atas"))],
)
async def detalhe_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> AtaDetail:
    async with tenant_session(user.tenant_id) as session:
        ata = await jobs_service.buscar_ata(session, user.tenant_id, ata_id)
    if not ata:
        raise HTTPException(status_code=404, detail="Ata não encontrada.")
    return _ata_detail(ata)


# =============================================================================
# Stubs de pipeline — 501 até fase correspondente
# =============================================================================
@router.post(
    "/{ata_id}/audio",
    dependencies=[Depends(require_module("atas"))],
)
async def upload_audio(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 6 (STT).")


@router.post(
    "/{ata_id}/gerar",
    dependencies=[Depends(require_module("atas"))],
)
async def gerar_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 3 (gerador).")


@router.get(
    "/{ata_id}/diff",
    dependencies=[Depends(require_module("atas"))],
)
async def diff_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 4 (comparador).")


@router.post(
    "/{ata_id}/aprovar",
    dependencies=[Depends(require_module("atas"))],
)
async def aprovar_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 7 (workflow).")


@router.post(
    "/{ata_id}/corrigir",
    dependencies=[Depends(require_module("atas"))],
)
async def corrigir_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 5 (corretor).")


@router.get(
    "/{ata_id}/exportar",
    dependencies=[Depends(require_module("atas"))],
)
async def exportar_ata(
    ata_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    raise HTTPException(status_code=501, detail="Implementado na Fase 9 (exportação).")


# =============================================================================
# Helpers
# =============================================================================
def _ata_summary(row: dict[str, Any]) -> AtaSummary:
    return AtaSummary(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        titulo=row["titulo"],
        referencia=row.get("referencia"),
        status=row["status"],
        versao_atual_id=str(row["versao_atual_id"]) if row.get("versao_atual_id") else None,
        consultor_user_id=str(row["consultor_user_id"]),
        sindico_user_id=str(row["sindico_user_id"]) if row.get("sindico_user_id") else None,
        presidente_user_id=str(row["presidente_user_id"]) if row.get("presidente_user_id") else None,
        erro_detalhe=row.get("erro_detalhe"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ata_detail(row: dict[str, Any]) -> AtaDetail:
    return AtaDetail(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        titulo=row["titulo"],
        referencia=row.get("referencia"),
        status=row["status"],
        versao_atual_id=str(row["versao_atual_id"]) if row.get("versao_atual_id") else None,
        consultor_user_id=str(row["consultor_user_id"]),
        sindico_user_id=str(row["sindico_user_id"]) if row.get("sindico_user_id") else None,
        presidente_user_id=str(row["presidente_user_id"]) if row.get("presidente_user_id") else None,
        insumos_json=row.get("insumos_json") or {},
        erro_detalhe=row.get("erro_detalhe"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
