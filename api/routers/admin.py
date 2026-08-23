"""
Endpoints /admin/* — restritos a superadmin.

Todas as rotas usam `superadmin_session` (sem RLS) e registram audit log.
Fonte de verdade dos tenant configs é o DB; após cada mutação, o registry
em memória é recarregado para refletir a mudança nas próximas requests.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.admin import service as admin_service
from api.auth import CurrentUser, superadmin_required
from api.cobrancas import testar_conexao_documentai
from api.db import superadmin_session
from api.tenants.models import (
    TenantConfig,
    mascarar_gcp_credentials,
    mascarar_openai_key,
)
from api.tenants.modulos import MODULOS_DISPONIVEIS

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
    modulos_contratados: dict[str, bool] = Field(default_factory=dict)
    modalidade: str = "B"


class ModuloDisponivel(BaseModel):
    """Item do catálogo de módulos contratáveis (response do GET /admin/modulos)."""

    slug: str
    label: str
    descricao: str
    nome_produto: str = ""
    tagline: str = ""
    icone: str = "bot"
    status: str = "disponivel"
    modalidades: list[str] = []


class CobrancasTestConnectionRequest(BaseModel):
    """Payload do POST /admin/cobrancas/test-connection."""

    gcp_credentials_json: dict[str, Any]
    gcp_project_id: str
    gcp_location: str = "us"
    processor_id: str
    # Se vier preenchido com `tenant_id`, e a private_key estiver mascarada,
    # o endpoint busca a chave salva no DB (permite testar sem re-subir).
    tenant_id: str | None = None


class TestConnectionResponse(BaseModel):
    ok: bool
    detail: str
    metadata: dict[str, Any] = Field(default_factory=dict)


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


def _config_for_response(config_json: dict[str, Any]) -> TenantConfig:
    """
    Aceita o config_json bruto do DB e devolve um TenantConfig com:
      - chave OpenAI mascarada
      - private_key do service account Google mascarada
    O DB continua tendo os valores em texto.
    """
    cfg = TenantConfig(**config_json)
    if cfg.openai.api_key:
        cfg.openai.api_key = mascarar_openai_key(cfg.openai.api_key)
    if cfg.cobrancas and cfg.cobrancas.gcp_credentials_json:
        cfg.cobrancas.gcp_credentials_json = mascarar_gcp_credentials(
            cfg.cobrancas.gcp_credentials_json
        )
    return cfg


async def _merge_secrets_omissos(
    tenant_id: str,
    payload: TenantConfig,
) -> None:
    """
    Se o PUT vem com secrets vazios ou mascarados (frontend não tocou),
    preserva os valores salvos no DB. Vale para:
      - openai.api_key (modo 'custom')
      - cobrancas.gcp_credentials_json (private_key mascarada)

    Sem isso, o super admin teria que re-subir a chave OpenAI e o JSON
    Google a cada save de outro campo qualquer.
    """
    saved_cfg = await _carregar_config_atual(tenant_id)
    if saved_cfg is None:
        return

    # OpenAI ----------------------------------------------------------------
    if payload.openai.mode == "custom":
        incoming = payload.openai.api_key
        if (not incoming or _parece_mascarada(incoming)) and saved_cfg.openai.api_key:
            payload.openai.api_key = saved_cfg.openai.api_key

    # Cobranças -------------------------------------------------------------
    if payload.cobrancas and payload.cobrancas.gcp_credentials_json:
        creds = payload.cobrancas.gcp_credentials_json
        pk = creds.get("private_key", "")
        if isinstance(pk, str) and "***" in pk and saved_cfg.cobrancas:
            saved_creds = saved_cfg.cobrancas.gcp_credentials_json
            if saved_creds and saved_creds.get("private_key"):
                payload.cobrancas.gcp_credentials_json = saved_creds


async def _carregar_config_atual(tenant_id: str) -> TenantConfig | None:
    async with superadmin_session() as session:
        existing = await admin_service.buscar_tenant(session, tenant_id)
    if not existing or not existing.get("config_json"):
        return None
    return TenantConfig(**existing["config_json"])


def _parece_mascarada(key: str) -> bool:
    return "..." in key or "***" in key


# =============================================================================
# Endpoints
# =============================================================================
@router.get("/modulos", response_model=list[ModuloDisponivel])
async def listar_modulos(
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[ModuloDisponivel]:
    """Catálogo de módulos disponíveis para contratação por tenant."""
    return [
        ModuloDisponivel(
            slug=m.slug,
            label=m.label,
            descricao=m.descricao,
            nome_produto=m.nome_produto,
            tagline=m.tagline,
            icone=m.icone,
            status=m.status,
            modalidades=m.modalidades,
        )
        for m in MODULOS_DISPONIVEIS.values()
    ]


@router.post("/cobrancas/test-connection", response_model=TestConnectionResponse)
async def cobrancas_test_connection(
    payload: CobrancasTestConnectionRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TestConnectionResponse:
    """
    Testa as credenciais Google Document AI fornecidas chamando get_processor.
    Retorna status + metadata do processor (ou mensagem de erro amigável).

    Se `private_key` chega mascarada (admin testando sem re-upload), tenta
    completar com a chave salva no DB do tenant indicado.
    """
    creds = payload.gcp_credentials_json
    pk = creds.get("private_key", "") if isinstance(creds, dict) else ""
    if isinstance(pk, str) and "***" in pk and payload.tenant_id:
        saved = await _carregar_config_atual(payload.tenant_id)
        if saved and saved.cobrancas and saved.cobrancas.gcp_credentials_json:
            saved_creds = saved.cobrancas.gcp_credentials_json
            if saved_creds.get("private_key"):
                creds = {**creds, "private_key": saved_creds["private_key"]}

    result = testar_conexao_documentai(
        gcp_credentials_json=creds,
        gcp_project_id=payload.gcp_project_id,
        gcp_location=payload.gcp_location,
        processor_id=payload.processor_id,
    )
    return TestConnectionResponse(**result)


@router.get("/tenants", response_model=list[TenantSummary])
async def listar(
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[TenantSummary]:
    async with superadmin_session() as session:
        rows = await admin_service.listar_tenants(session)
    out: list[TenantSummary] = []
    for r in rows:
        cfg = r.get("config_json") or {}
        is_dict = isinstance(cfg, dict)
        ds_type = (cfg.get("datasource") or {}).get("type") if is_dict else None
        modulos = cfg.get("modulos_contratados") if is_dict else None
        modalidade = cfg.get("modalidade", "B") if is_dict else "B"
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
                modulos_contratados=modulos if isinstance(modulos, dict) else {},
                modalidade=modalidade,
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
        config=_config_for_response(r["config_json"]),
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
        config=_config_for_response(r["config_json"]),
    )


@router.put("/tenants/{tenant_id}", response_model=TenantDetail)
async def atualizar(
    tenant_id: str,
    payload: TenantConfig,
    request: Request,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TenantDetail:
    ip, ua = _client_meta(request)
    # Se o PUT vem sem secrets novos (frontend não tocou nos campos),
    # reaproveita os valores já salvos no DB pra não exigir re-input a cada save.
    await _merge_secrets_omissos(tenant_id, payload)

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
        config=_config_for_response(r["config_json"]),
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
