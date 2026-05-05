"""
Endpoints `/cobrancas/*` — extração de PDFs de cobrança via Bella Cobranças.

Todas as rotas exigem:
  - usuário autenticado do tenant (não superadmin)
  - tenant com módulo `cobrancas` contratado (require_module)
  - tenant com credenciais GCP cadastradas (validado no início do extract)

Uploads vão pro storage abstrato (api/storage), prefixados por tenant —
isolamento mantido mesmo com bucket compartilhado.
"""

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from loguru import logger
from pydantic import BaseModel

from api.auth import CurrentUser, usuario_atual
from api.cobrancas import jobs_service
from api.cobrancas.excel_export import gerar_xlsx
from api.cobrancas.pipeline import CobrancasPipeline, PipelineError
from api.cobrancas.schema import CobrancaResultado
from api.db import tenant_session
from api.storage.factory import get_storage
from api.tenants.deps import require_module


router = APIRouter(prefix="/cobrancas", tags=["cobrancas"])


# Tamanho máximo aceito (bytes). 50 MB cobre PDFs gigantes.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


# =============================================================================
# Schemas
# =============================================================================
class JobOut(BaseModel):
    id: str
    tenant_id: str
    status: str
    file_name: str
    file_size: int
    content_hash: str
    qtde_paginas: int | None = None
    qtde_registros: int | None = None
    valor_total: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duracao_segundos: float | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class JobResult(BaseModel):
    job_id: str
    status: str
    registros: list[dict[str, Any]]
    metadata: dict[str, Any]


# =============================================================================
# Dependency — usuário do tenant (não superadmin)
# =============================================================================
async def tenant_user_required(
    user: Annotated[CurrentUser, Depends(usuario_atual)],
) -> CurrentUser:
    if user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin não opera no módulo de cobranças — use a conta de admin do tenant.",
        )
    if user.tenant_id == "_system":
        raise HTTPException(status_code=403, detail="Tenant '_system' é reservado.")
    return user


# =============================================================================
# Endpoints
# =============================================================================
@router.post(
    "/extract",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module("cobrancas"))],
)
async def extract(
    request: Request,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
    file: UploadFile = File(..., description="PDF de cobrança condominial."),
) -> JobOut:
    """
    Recebe um PDF, valida, persiste no storage e enfileira a extração.
    Retorna o job em status='queued'. Cliente poll `GET /cobrancas/jobs/{id}`.

    Idempotência: se já existir job com o mesmo SHA256 do conteúdo (mesmo
    tenant) e status `done`, devolve esse — não reprocessa.
    """
    # 1. Validar config do tenant ------------------------------------------
    tenant_cfg = _tenant_config(request, user.tenant_id)
    cob = tenant_cfg.cobrancas
    if not cob or not cob.gcp_credentials_json:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tenant ainda não tem credenciais Google Document AI cadastradas. "
                "Peça ao super admin pra subir o service account JSON em /admin."
            ),
        )
    # Falha cedo se faltam project_id ou processor_id — sem isso o job só
    # ficaria failed depois de 1s, sujando o histórico.
    faltando: list[str] = []
    if not cob.gcp_project_id:
        faltando.append("gcp_project_id")
    if not cob.processor_id:
        faltando.append("processor_id")
    if faltando:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Configuração incompleta — falta: {', '.join(faltando)}. "
                f"Peça ao super admin pra completar em /admin."
            ),
        )

    # 2. Ler bytes ---------------------------------------------------------
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo grande demais ({len(pdf_bytes)} > {MAX_UPLOAD_BYTES} bytes).",
        )
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Arquivo não parece ser PDF.")

    # 3. Hash + contagem de páginas ----------------------------------------
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    qtde_paginas = _contar_paginas_pdf(pdf_bytes)

    # 4. Idempotência ------------------------------------------------------
    async with tenant_session(user.tenant_id) as session:
        existente = await jobs_service.buscar_por_hash(session, user.tenant_id, content_hash)
        if existente and existente["status"] == "done":
            logger.info(
                f"[cobrancas] dedup hash={content_hash[:8]} → job existente {existente['id']}"
            )
            job = await jobs_service.buscar_job(session, user.tenant_id, existente["id"])
            assert job is not None
            return _job_out(job)

    # 5. Salvar no storage -------------------------------------------------
    storage = get_storage()
    job_id = uuid4()
    storage_key = f"{user.tenant_id}/cobrancas/{job_id}/input.pdf"
    await storage.save(storage_key, io.BytesIO(pdf_bytes), content_type="application/pdf")

    # 6. Criar job em DB ---------------------------------------------------
    file_name = (file.filename or "upload.pdf")[:255]
    async with tenant_session(user.tenant_id) as session:
        # job_id explícito pra bater com o storage_key
        await session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO cobrancas_jobs "
                "(id, tenant_id, status, file_name, file_size, file_storage_key, "
                "content_hash, actor_user_id) "
                "VALUES (:jid, :tid, 'queued', :fn, :fs, :fk, :h, :uid)"
            ),
            {
                "jid": str(job_id), "tid": user.tenant_id, "fn": file_name,
                "fs": len(pdf_bytes), "fk": storage_key, "h": content_hash,
                "uid": user.user_id,
            },
        )
        job = await jobs_service.buscar_job(session, user.tenant_id, job_id)
    assert job is not None

    # 7. Agendar processamento em background -------------------------------
    background_tasks.add_task(
        _processar_em_background,
        request=request,
        tenant_id=user.tenant_id,
        job_id=job_id,
        pdf_bytes=pdf_bytes,
        qtde_paginas=qtde_paginas,
        storage_key_prefix=f"{user.tenant_id}/cobrancas/{job_id}",
    )

    return _job_out(job)


@router.get(
    "/jobs",
    response_model=list[JobOut],
    dependencies=[Depends(require_module("cobrancas"))],
)
async def listar_jobs(
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
    limit: int = 50,
) -> list[JobOut]:
    async with tenant_session(user.tenant_id) as session:
        rows = await jobs_service.listar_jobs(session, user.tenant_id, limit=limit)
    return [_job_out(r) for r in rows]


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
    dependencies=[Depends(require_module("cobrancas"))],
)
async def detalhe_job(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> JobOut:
    async with tenant_session(user.tenant_id) as session:
        job = await jobs_service.buscar_job(session, user.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return _job_out(job)


@router.get(
    "/jobs/{job_id}/result",
    response_model=JobResult,
    dependencies=[Depends(require_module("cobrancas"))],
)
async def resultado_job(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> JobResult:
    job, data = await _carregar_resultado(user.tenant_id, job_id)
    return JobResult(
        job_id=str(job["id"]),
        status=job["status"],
        registros=data.get("registros", []),
        metadata=data.get("metadata", {}),
    )


@router.get(
    "/jobs/{job_id}/excel",
    dependencies=[Depends(require_module("cobrancas"))],
)
async def resultado_excel(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> Response:
    """Devolve o resultado do job como `.xlsx`. Stream único, não toca disco."""
    job, data = await _carregar_resultado(user.tenant_id, job_id)
    resultado = CobrancaResultado(**data)
    xlsx_bytes = gerar_xlsx(resultado, file_name=job.get("file_name"))
    base = (job.get("file_name") or "cobrancas").rsplit(".", 1)[0]
    download_name = f"{base}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.delete(
    "/jobs/{job_id}",
    status_code=204,
    dependencies=[Depends(require_module("cobrancas"))],
)
async def deletar_job(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(tenant_user_required)],
) -> None:
    """Remove o job do histórico + apaga input.pdf e result.json do storage."""
    async with tenant_session(user.tenant_id) as session:
        removido = await jobs_service.deletar_job(
            session, tenant_id=user.tenant_id, job_id=job_id
        )
    if removido is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    storage = get_storage()
    for chave in (removido.get("file_storage_key"), removido.get("result_storage_key")):
        if chave:
            try:
                await storage.delete(chave)
            except Exception as exc:
                # Não falha o request — DB já está limpo, log o storage órfão.
                logger.warning(
                    f"[cobrancas] delete storage falhou key={chave} err={exc}"
                )


async def _carregar_resultado(
    tenant_id: str, job_id: UUID
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Helper: valida job done + carrega JSON do storage. Levanta HTTPException."""
    async with tenant_session(tenant_id) as session:
        job = await jobs_service.buscar_job(session, tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409, detail=f"Job ainda não concluído (status={job['status']})."
        )
    if not job.get("result_storage_key"):
        raise HTTPException(status_code=500, detail="Job done sem result_storage_key.")
    storage = get_storage()
    stream = await storage.open(job["result_storage_key"])
    try:
        data = json.loads(stream.read())
    finally:
        stream.close()
    return job, data


# =============================================================================
# Background processing
# =============================================================================
async def _processar_em_background(
    *,
    request: Request,
    tenant_id: str,
    job_id: UUID,
    pdf_bytes: bytes,
    qtde_paginas: int,
    storage_key_prefix: str,
) -> None:
    """
    Roda o pipeline e atualiza o job. Engole exceções (já registradas em
    error_detail no DB) — BackgroundTasks não tem onde reportar.
    """
    started_at = datetime.now(timezone.utc)
    try:
        async with tenant_session(tenant_id) as session:
            await jobs_service.marcar_running(session, tenant_id=tenant_id, job_id=job_id)

        tenant_cfg = _tenant_config(request, tenant_id)
        if not tenant_cfg.cobrancas:
            raise PipelineError("Tenant perdeu credenciais GCP entre o enqueue e o processamento.")

        pipeline = CobrancasPipeline(tenant_cfg.cobrancas)
        # Pipeline é síncrono (Document AI client é sync) — roda no event loop
        # mesmo assim. Pra PDFs ≤15 págs, ~5-15s. Aceitável aqui; se virar
        # gargalo, mover pra `asyncio.to_thread`.
        resultado = pipeline.processar_pdf(pdf_bytes, qtde_paginas)

        # Salvar JSON resultado
        storage = get_storage()
        result_key = f"{storage_key_prefix}/result.json"
        result_bytes = resultado.model_dump_json(indent=2).encode("utf-8")
        await storage.save(result_key, io.BytesIO(result_bytes), content_type="application/json")

        async with tenant_session(tenant_id) as session:
            await jobs_service.marcar_done(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                result_storage_key=result_key,
                qtde_paginas=qtde_paginas,
                qtde_registros=resultado.metadata.total_registros,
                valor_total=resultado.metadata.total_valor,
                started_at=started_at,
            )
    except Exception as exc:
        logger.exception(f"[cobrancas] erro no job {job_id}: {exc}")
        try:
            async with tenant_session(tenant_id) as session:
                await jobs_service.marcar_failed(
                    session,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    error_detail=str(exc),
                    started_at=started_at,
                )
        except Exception as inner:
            logger.exception(f"[cobrancas] falha ao marcar job {job_id} como failed: {inner}")


# =============================================================================
# Helpers
# =============================================================================
def _contar_paginas_pdf(pdf_bytes: bytes) -> int:
    """Conta páginas via PyMuPDF. Levanta HTTPException 400 se PDF inválido."""
    try:
        import fitz
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PyMuPDF não instalado no servidor.") from exc
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return len(doc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF ilegível: {exc}") from exc


def _tenant_config(request: Request, tenant_id: str):
    registry = request.app.state.tenant_registry
    return registry.get(tenant_id, only_enabled=True)


def _job_out(row: dict[str, Any]) -> JobOut:
    return JobOut(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        status=row["status"],
        file_name=row["file_name"],
        file_size=row["file_size"],
        content_hash=row["content_hash"],
        qtde_paginas=row.get("qtde_paginas"),
        qtde_registros=row.get("qtde_registros"),
        valor_total=float(row["valor_total"]) if row.get("valor_total") is not None else None,
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        duracao_segundos=(
            float(row["duracao_segundos"]) if row.get("duracao_segundos") is not None else None
        ),
        error_detail=row.get("error_detail"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
