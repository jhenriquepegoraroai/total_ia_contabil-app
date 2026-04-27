"""
Ingestion service — disparar e monitorar jobs do pipeline a partir da UI.

Estratégia simples (Fase 6.1): asyncio.create_task no mesmo processo da API.
Cada job roda em uma task que chama o `ingestion.pipeline.executar`.

Para escala (vários workers / restart resiliente), migrar para Celery / RQ
em fase futura. Por ora, um único worker no mesmo processo serve para o
volume esperado (cada admin dispara N jobs por dia, não milhares).
"""

import asyncio
import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import config
from api.db import superadmin_session, tenant_session
from api.tenants.registry import TenantRegistry
from api.storage import get_storage, tenant_source_prefix
from api.storage.local import LocalStorage
from ingestion.connectors.pdf_folder import PdfFolderConnector
from ingestion.connectors.storage_pdf import StoragePdfConnector
from ingestion.embeddings import cliente_padrao
from ingestion.pipeline import executar as pipeline_executar
from .sources_service import atualizar_estado_pos_job, parse_config


# =============================================================================
# Listagem
# =============================================================================
async def listar_jobs(
    session: AsyncSession,
    tenant_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT j.id, j.tenant_id, j.source_id, s.name AS source_name, s.type AS source_type,
               j.referencia, j.status, j.started_at, j.finished_at,
               j.qtde_chunks_origem, j.qtde_processada, j.qtde_skipped, j.qtde_erros,
               j.duracao_segundos, j.erro_detalhe, j.actor_email, j.created_at
        FROM ingestion_jobs j
        LEFT JOIN tenant_data_sources s ON s.id = j.source_id
        WHERE j.tenant_id = :tid
        ORDER BY j.created_at DESC
        LIMIT :lim
        """
    )
    rows = (await session.execute(sql, {"tid": tenant_id, "lim": limit})).mappings().all()
    return [dict(r) for r in rows]


async def buscar_job(
    session: AsyncSession, tenant_id: str, job_id: UUID
) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT j.id, j.tenant_id, j.source_id, s.name AS source_name, s.type AS source_type,
               j.referencia, j.status, j.started_at, j.finished_at,
               j.qtde_chunks_origem, j.qtde_processada, j.qtde_skipped, j.qtde_erros,
               j.duracao_segundos, j.erro_detalhe, j.actor_email, j.created_at
        FROM ingestion_jobs j
        LEFT JOIN tenant_data_sources s ON s.id = j.source_id
        WHERE j.tenant_id = :tid AND j.id = :jid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "jid": str(job_id)})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# Disparar job
# =============================================================================
async def disparar_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    source_id: UUID,
    referencia: str | None,
    actor_user_id: str,
    actor_email: str,
    registry: TenantRegistry,
) -> UUID:
    """
    Cria um job em status 'queued' e dispara a execução em background.
    Retorna o job_id imediatamente; UI consulta status via GET.
    """
    # 1. Validar source existe e é de tipo suportado nesta fase.
    src = await session.execute(
        text(
            "SELECT id, type, config_json, enabled FROM tenant_data_sources "
            "WHERE tenant_id = :tid AND id = :sid"
        ),
        {"tid": tenant_id, "sid": str(source_id)},
    )
    row = src.mappings().first()
    if not row:
        raise ValueError("Source não encontrada.")
    if not row["enabled"]:
        raise ValueError("Source desabilitada.")
    if row["type"] != "pdf_upload":
        raise ValueError(
            f"Disparo via UI só está habilitado para 'pdf_upload' nesta fase. "
            f"Source tipo '{row['type']}' será suportada em fase futura."
        )

    # 2. Cria job
    job_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO ingestion_jobs
                (id, tenant_id, source_id, referencia, status, actor_user_id, actor_email)
            VALUES (:id, :tid, :sid, :ref, 'queued', :uid, :em)
            """
        ),
        {
            "id": str(job_id),
            "tid": tenant_id,
            "sid": str(source_id),
            "ref": referencia,
            "uid": actor_user_id,
            "em": actor_email,
        },
    )

    logger.info(
        f"[ingestion] job {job_id} agendado tenant={tenant_id} source={source_id} ref={referencia}"
    )

    # 3. Dispara em background (fire-and-forget). A task tem sua própria sessão.
    asyncio.create_task(_executar_job(job_id, tenant_id, source_id, referencia, registry))

    return job_id


# =============================================================================
# Worker — roda dentro do processo da API
# =============================================================================
async def _executar_job(
    job_id: UUID,
    tenant_id: str,
    source_id: UUID,
    referencia: str | None,
    registry: TenantRegistry,
) -> None:
    """Background task. Não levanta — todos os erros viram status='failed'."""
    t0 = time.monotonic()

    # Marcar como running.
    async with superadmin_session() as session:
        await session.execute(
            text(
                "UPDATE ingestion_jobs SET status='running', started_at=NOW() WHERE id=:id"
            ),
            {"id": str(job_id)},
        )

    try:
        tenant_config = registry.get(tenant_id, only_enabled=False)
        storage = get_storage()
        # Atalho para LocalStorage: usa o PdfFolderConnector apontando para a
        # pasta no filesystem (evita `asyncio.run` dentro do event loop).
        # Para S3/Azure (Fase 6.2), substituir por StoragePdfConnector com
        # download para tempdir, ou implementar variante async.
        if isinstance(storage, LocalStorage):
            prefix = tenant_source_prefix(tenant_id, str(source_id))
            local_path = storage.root / prefix
            connector = PdfFolderConnector(path=str(local_path))
        else:
            connector = StoragePdfConnector(
                storage=storage,
                tenant_id=tenant_id,
                source_id=str(source_id),
            )

        # Pipeline precisa de uma `tenant_session` (com RLS) para inserir
        # documents_embeddings/embeddings_audit corretamente.
        embedding_client = cliente_padrao()
        try:
            async with tenant_session(tenant_id) as session:
                audit = await pipeline_executar(
                    tenant_config=tenant_config,
                    referencia=referencia or "0",
                    connector=connector,
                    session=session,
                    embedding_client=embedding_client,
                    batch_size=config.INGESTION_BATCH_SIZE,
                    max_concurrent_batches=config.INGESTION_MAX_WORKERS,
                )
        finally:
            await embedding_client.aclose()

        # Marcar como done + propagar contagens.
        async with superadmin_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE ingestion_jobs SET
                        status='done',
                        finished_at=NOW(),
                        qtde_chunks_origem=:qo,
                        qtde_processada=:qp,
                        qtde_skipped=:qs,
                        qtde_erros=:qe,
                        duracao_segundos=:ds
                    WHERE id=:id
                    """
                ),
                {
                    "id": str(job_id),
                    "qo": audit.qtde_chunks_origem,
                    "qp": audit.qtde_processada,
                    "qs": audit.qtde_skipped,
                    "qe": audit.qtde_erros,
                    "ds": round(time.monotonic() - t0, 2),
                },
            )
            await atualizar_estado_pos_job(
                session, source_id=source_id, status="done"
            )
        logger.info(f"[ingestion] job {job_id} concluído ({audit.qtde_processada} processados)")

    except Exception as exc:
        logger.exception(f"[ingestion] job {job_id} falhou: {exc}")
        async with superadmin_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE ingestion_jobs SET
                        status='failed', finished_at=NOW(),
                        erro_detalhe=:err,
                        duracao_segundos=:ds
                    WHERE id=:id
                    """
                ),
                {
                    "id": str(job_id),
                    "err": str(exc)[:1000],
                    "ds": round(time.monotonic() - t0, 2),
                },
            )
            try:
                await atualizar_estado_pos_job(
                    session, source_id=source_id, status="failed"
                )
            except Exception:
                pass
