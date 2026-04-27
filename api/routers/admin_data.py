"""
Endpoints /admin/tenants/<id>/sources/* e /admin/tenants/<id>/ingestions/*
+ /admin/files (servir arquivos do storage local em DEV).

Restritos a superadmin. Operações cross-tenant via superadmin_session.
"""

import io
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.admin import (
    ingestion_service,
    sources_service,
    users_service,
)
from api.admin.sources_models import (
    CreateSourceRequest,
    SourceConfig,
    SourceDetail,
    SourceSummary,
)
from api.auth import CurrentUser, superadmin_required
from api.db import superadmin_session
from api.storage import get_storage, tenant_source_prefix


router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Sources — CRUD + test
# =============================================================================
@router.get("/tenants/{tenant_id}/sources", response_model=list[SourceSummary])
async def listar_sources(
    tenant_id: str,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[SourceSummary]:
    async with superadmin_session() as session:
        rows = await sources_service.listar_sources(session, tenant_id)
    return [SourceSummary(**r) for r in rows]


@router.get("/tenants/{tenant_id}/sources/{source_id}", response_model=SourceDetail)
async def buscar_source(
    tenant_id: str,
    source_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> SourceDetail:
    async with superadmin_session() as session:
        row = await sources_service.buscar_source(session, tenant_id, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    return SourceDetail(
        id=row["id"],
        tenant_id=row["tenant_id"],
        name=row["name"],
        type=row["type"],
        config=row["config_json"] or {},
        secret_name=row["secret_name"],
        enabled=row["enabled"],
        qtde_files=row["qtde_files"],
        last_run_at=row["last_run_at"],
        last_run_status=row["last_run_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post(
    "/tenants/{tenant_id}/sources",
    response_model=SourceDetail,
    status_code=status.HTTP_201_CREATED,
)
async def criar_source(
    tenant_id: str,
    payload: CreateSourceRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
    request: Request,
) -> SourceDetail:
    if tenant_id not in request.app.state.tenant_registry:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' não existe.")

    async with superadmin_session() as session:
        try:
            new_id = await sources_service.criar_source(
                session,
                tenant_id=tenant_id,
                name=payload.name,
                config=payload.config,
                secret_name=payload.secret_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        row = await sources_service.buscar_source(session, tenant_id, new_id)

    assert row is not None
    return SourceDetail(
        id=row["id"],
        tenant_id=row["tenant_id"],
        name=row["name"],
        type=row["type"],
        config=row["config_json"] or {},
        secret_name=row["secret_name"],
        enabled=row["enabled"],
        qtde_files=row["qtde_files"],
        last_run_at=row["last_run_at"],
        last_run_status=row["last_run_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/tenants/{tenant_id}/sources/{source_id}", status_code=204)
async def deletar_source(
    tenant_id: str,
    source_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> None:
    async with superadmin_session() as session:
        ok = await sources_service.deletar_source(session, tenant_id, source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")


class TestConnectionRequest(BaseModel):
    config: SourceConfig


class TestConnectionResponse(BaseModel):
    ok: bool
    detail: str
    metadata: dict[str, Any]


@router.post("/sources/test-connection", response_model=TestConnectionResponse)
async def testar_conexao(
    payload: TestConnectionRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> TestConnectionResponse:
    """Valida config sem persistir. Útil pro form da UI antes de salvar."""
    result = await sources_service.testar_conexao(payload.config)
    return TestConnectionResponse(**result)


# =============================================================================
# Upload de arquivos (multipart) para fontes do tipo *_upload
# =============================================================================
class UploadResultItem(BaseModel):
    filename: str
    key: str
    size_bytes: int
    ok: bool
    erro: str | None = None


class UploadResultResponse(BaseModel):
    uploaded: list[UploadResultItem]


@router.post(
    "/tenants/{tenant_id}/sources/{source_id}/files",
    response_model=UploadResultResponse,
)
async def upload_files(
    tenant_id: str,
    source_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
    files: list[UploadFile] = File(..., description="Multipart de arquivos."),
) -> UploadResultResponse:
    """
    Recebe arquivos via multipart e persiste no storage backend sob a key
    `<tenant>/sources/<source_id>/<filename>`. Idempotente por filename
    (substitui se já existe).
    """
    async with superadmin_session() as session:
        row = await sources_service.buscar_source(session, tenant_id, source_id)

    if not row:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    tipo = row["type"]
    if not tipo.endswith("_upload"):
        raise HTTPException(
            status_code=400,
            detail=f"Fonte do tipo '{tipo}' não aceita upload direto. "
                   "Use o pipeline correspondente para esse tipo.",
        )

    storage = get_storage()
    prefix = tenant_source_prefix(tenant_id, str(source_id))

    results: list[UploadResultItem] = []
    saved_count = 0
    for f in files:
        safe_name = _safe_filename(f.filename or "arquivo")
        key = f"{prefix}{safe_name}"
        try:
            content = await f.read()
            obj = await storage.save(key, io.BytesIO(content), content_type=f.content_type)
            results.append(
                UploadResultItem(
                    filename=safe_name,
                    key=obj.key,
                    size_bytes=obj.size_bytes,
                    ok=True,
                )
            )
            saved_count += 1
        except Exception as exc:
            logger.exception(f"Falha salvando {safe_name}")
            results.append(
                UploadResultItem(
                    filename=safe_name, key=key, size_bytes=0, ok=False, erro=str(exc)
                )
            )

    if saved_count > 0:
        from sqlalchemy import text
        async with superadmin_session() as session:
            await session.execute(
                text(
                    "UPDATE tenant_data_sources SET qtde_files = qtde_files + :n, "
                    "updated_at = NOW() WHERE id = :sid"
                ),
                {"n": saved_count, "sid": str(source_id)},
            )

    return UploadResultResponse(uploaded=results)


@router.get("/tenants/{tenant_id}/sources/{source_id}/files")
async def listar_files(
    tenant_id: str,
    source_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[dict[str, Any]]:
    """Lista arquivos do storage da fonte."""
    storage = get_storage()
    prefix = tenant_source_prefix(tenant_id, str(source_id))
    objects = await storage.list_prefix(prefix)
    return [
        {
            "key": o.key,
            "filename": o.key.split("/")[-1],
            "size_bytes": o.size_bytes,
            "last_modified": o.last_modified.isoformat() if o.last_modified else None,
        }
        for o in objects
    ]


# =============================================================================
# Ingestion jobs
# =============================================================================
class StartJobRequest(BaseModel):
    source_id: UUID
    referencia: str | None = None


class JobOut(BaseModel):
    id: UUID
    tenant_id: str
    source_id: UUID | None
    source_name: str | None = None
    source_type: str | None = None
    referencia: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    qtde_chunks_origem: int
    qtde_processada: int
    qtde_skipped: int
    qtde_erros: int
    duracao_segundos: float | None
    erro_detalhe: str | None
    actor_email: str | None
    created_at: datetime


@router.post(
    "/tenants/{tenant_id}/ingestions",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disparar_job(
    tenant_id: str,
    payload: StartJobRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
    request: Request,
) -> JobOut:
    if tenant_id not in request.app.state.tenant_registry:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' não existe.")

    registry = request.app.state.tenant_registry
    async with superadmin_session() as session:
        try:
            job_id = await ingestion_service.disparar_job(
                session,
                tenant_id=tenant_id,
                source_id=payload.source_id,
                referencia=payload.referencia,
                actor_user_id=user.user_id,
                actor_email=user.user_id,
                registry=registry,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Buscar para devolver o status inicial
        job = await ingestion_service.buscar_job(session, tenant_id, job_id)

    assert job is not None
    return JobOut(**_normalize_job(job))


@router.get("/tenants/{tenant_id}/ingestions", response_model=list[JobOut])
async def listar_jobs(
    tenant_id: str,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[JobOut]:
    async with superadmin_session() as session:
        rows = await ingestion_service.listar_jobs(session, tenant_id, limit=limit)
    return [JobOut(**_normalize_job(r)) for r in rows]


@router.get("/tenants/{tenant_id}/ingestions/{job_id}", response_model=JobOut)
async def buscar_job(
    tenant_id: str,
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> JobOut:
    async with superadmin_session() as session:
        row = await ingestion_service.buscar_job(session, tenant_id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return JobOut(**_normalize_job(row))


# =============================================================================
# Servir arquivos (DEV only — em prod, presigned URL do S3/Azure)
# =============================================================================
@router.get("/files")
async def servir_arquivo(
    key: str,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> StreamingResponse:
    """Servir arquivo do storage local. Em produção, usar signed URL nativo."""
    storage = get_storage()
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    stream = await storage.open(key)
    filename = key.split("/")[-1]
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# =============================================================================
# Helpers
# =============================================================================
def _safe_filename(name: str) -> str:
    """Sanitiza filename — remove path traversal e caracteres problemáticos."""
    bad = name.replace("\\", "/").rsplit("/", 1)[-1]
    out = "".join(c for c in bad if c.isalnum() or c in ".-_ ()[]áéíóúâêôãõçÁÉÍÓÚ")
    return out or "arquivo"


def _normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    """Garante que UUIDs e tipos numéricos cabem no schema."""
    out = dict(job)
    if out.get("duracao_segundos") is not None:
        out["duracao_segundos"] = float(out["duracao_segundos"])
    return out


# =============================================================================
# Users (gerenciar via UI superadmin)
# =============================================================================
class UserOut(BaseModel):
    id: UUID
    tenant_id: str
    email: str
    nome: str
    role: str
    enabled: bool
    is_superadmin: bool
    tem_senha: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    email: str
    nome: str
    role: str = "morador"
    password: str


class UpdateUserRequest(BaseModel):
    nome: str | None = None
    role: str | None = None
    enabled: bool | None = None


class ResetPasswordRequest(BaseModel):
    nova_senha: str


@router.get("/tenants/{tenant_id}/users", response_model=list[UserOut])
async def listar_usuarios(
    tenant_id: str,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> list[UserOut]:
    async with superadmin_session() as session:
        rows = await users_service.listar_users(session, tenant_id)
    return [UserOut(**r) for r in rows]


@router.post(
    "/tenants/{tenant_id}/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def criar_usuario(
    tenant_id: str,
    payload: CreateUserRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> UserOut:
    async with superadmin_session() as session:
        try:
            new_id = await users_service.criar_user(
                session,
                tenant_id=tenant_id,
                email=payload.email.strip().lower(),
                nome=payload.nome.strip(),
                role=payload.role,
                password=payload.password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        row = await users_service.buscar_user(session, tenant_id, new_id)
    assert row is not None
    return UserOut(**row)


@router.patch("/tenants/{tenant_id}/users/{user_id}", response_model=UserOut)
async def atualizar_usuario(
    tenant_id: str,
    user_id: UUID,
    payload: UpdateUserRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> UserOut:
    async with superadmin_session() as session:
        try:
            ok = await users_service.atualizar_user(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                nome=payload.nome,
                role=payload.role,
                enabled=payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        row = await users_service.buscar_user(session, tenant_id, user_id)
    assert row is not None
    return UserOut(**row)


@router.patch("/tenants/{tenant_id}/users/{user_id}/password", status_code=204)
async def resetar_senha(
    tenant_id: str,
    user_id: UUID,
    payload: ResetPasswordRequest,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> None:
    async with superadmin_session() as session:
        try:
            ok = await users_service.resetar_senha(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                nova_senha=payload.nova_senha,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")


@router.delete("/tenants/{tenant_id}/users/{user_id}", status_code=204)
async def deletar_usuario(
    tenant_id: str,
    user_id: UUID,
    user: Annotated[CurrentUser, Depends(superadmin_required)],
) -> None:
    async with superadmin_session() as session:
        try:
            ok = await users_service.deletar_user(
                session, tenant_id=tenant_id, user_id=user_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
