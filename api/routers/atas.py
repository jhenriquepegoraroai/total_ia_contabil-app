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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy import text

from api.atas import jobs_service, pipeline_geracao
from api.atas.schema import AtaCreate, AtaDetail, AtaInsumosUpdate, AtaSummary
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


@router.put(
    "/{ata_id}/insumos",
    response_model=AtaDetail,
    dependencies=[Depends(require_module("atas"))],
)
async def atualizar_insumos(
    ata_id: UUID,
    payload: AtaInsumosUpdate,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> AtaDetail:
    """
    Atualiza (merge) os insumos da geração: cabecalho, resumo, edital,
    complemento e dados adicionais (presidente/secretário/CNPJ). Aceita
    update parcial — só os campos não-nulos sobrescrevem.

    Pelo menos `cabecalho` e `resumo` precisam estar preenchidos antes do
    `/gerar`. Validação ocorre lá, não aqui (UX permite salvar rascunho
    incompleto).
    """
    if user.is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Superadmin não edita atas — use a conta do consultor.",
        )
    async with tenant_session(user.tenant_id) as session:
        try:
            await jobs_service.atualizar_insumos(
                session,
                tenant_id=user.tenant_id,
                ata_id=ata_id,
                patch=payload.model_dump(exclude_unset=True),
                ator_user_id=UUID(user.user_id),
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        ata = await jobs_service.buscar_ata(session, user.tenant_id, ata_id)
    assert ata is not None
    return _ata_detail(ata)


@router.post(
    "/{ata_id}/gerar",
    response_model=AtaDetail,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_module("atas"))],
)
async def gerar_ata(
    ata_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> AtaDetail:
    """
    Dispara a geração da ata via LLM (3 passos) em background.

    Pré-condições:
      - ata existe no tenant
      - insumos_json contém ao menos `cabecalho` e `resumo`
      - tenant tem TenantAtasConfig (modelo OpenAI configurado)
      - status atual é compatível com (re)geração (rascunho, gerada, falhou)

    Resposta 202 imediata; o background task atualiza `atas.status` para
    `aguardando_geracao` → `gerada` (sucesso) ou `falhou` (erro). UI faz
    polling em `GET /atas/{id}` pra ver a transição.
    """
    if user.is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Superadmin não dispara geração — use a conta do consultor.",
        )

    # 1. Busca ata e valida estado
    async with tenant_session(user.tenant_id) as session:
        ata = await jobs_service.buscar_ata(session, user.tenant_id, ata_id)
    if not ata:
        raise HTTPException(status_code=404, detail="Ata não encontrada.")

    insumos_json = ata.get("insumos_json") or {}
    if not insumos_json.get("cabecalho") or not insumos_json.get("resumo"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Insumos incompletos: `cabecalho` e `resumo` são obrigatórios. "
                "Use PUT /atas/{id}/insumos antes de disparar a geração."
            ),
        )

    estados_validos = {"rascunho", "gerada", "falhou", "revisao_consultor"}
    if ata["status"] not in estados_validos:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ata em status '{ata['status']}' não pode (re)gerar. "
                f"Estados válidos: {sorted(estados_validos)}."
            ),
        )

    # 2. Resolve tenant_config + valida que ele tem modulo atas com config
    registry = request.app.state.tenant_registry
    tenant_config = registry.get(user.tenant_id, only_enabled=True)
    if tenant_config.atas is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tenant sem TenantAtasConfig — super admin precisa cadastrar "
                "o modelo OpenAI do módulo atas."
            ),
        )

    # 3. Agenda background task
    background_tasks.add_task(
        pipeline_geracao.processar_em_background,
        tenant_config=tenant_config,
        ata_id=ata_id,
    )

    # 4. Atualiza status pra 'aguardando_geracao' antes de retornar (o
    #    background task vai assumir e mexer dali em diante).
    async with tenant_session(user.tenant_id) as session:
        await session.execute(
            text(
                "UPDATE atas SET status='aguardando_geracao', erro_detalhe=NULL, "
                "updated_at=NOW() WHERE id=:aid AND tenant_id=:tid"
            ),
            {"aid": str(ata_id), "tid": user.tenant_id},
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=user.tenant_id,
            ata_id=ata_id,
            ator_user_id=UUID(user.user_id),
            acao="geracao_iniciada",
            detalhe={"modelo": tenant_config.atas.openai_model},
        )
        ata = await jobs_service.buscar_ata(session, user.tenant_id, ata_id)
    assert ata is not None
    logger.info(f"[atas] geração agendada ata={ata_id} tenant={user.tenant_id}")
    return _ata_detail(ata)


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
