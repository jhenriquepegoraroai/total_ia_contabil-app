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
from ingestion.connectors.base import Connector
from ingestion.connectors.pdf_folder import PdfFolderConnector
from ingestion.connectors.storage_pdf import StoragePdfConnector
from ingestion.embeddings import cliente_padrao
from ingestion.pipeline import executar as pipeline_executar
from .sources_service import atualizar_estado_pos_job, parse_config


# =============================================================================
# Listagem
# =============================================================================
def _construir_connector(
    *,
    tipo: str,
    config_json: dict[str, Any],
    tenant_id: str,
    source_id: str,
) -> Connector:
    """Resolve o connector certo a partir do tipo da fonte + sua config."""
    if tipo == "pdf_upload":
        # Lê do storage local — atalho síncrono, sem asyncio.run.
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            prefix = tenant_source_prefix(tenant_id, source_id)
            return PdfFolderConnector(path=str(storage.root / prefix))
        # Storage não-local: connector que usa asyncio.run internamente.
        return StoragePdfConnector(
            storage=storage, tenant_id=tenant_id, source_id=source_id
        )

    if tipo == "postgres":
        from ingestion.connectors.postgres import PostgresConnector
        return PostgresConnector(
            host=config_json["host"],
            port=int(config_json.get("port", 5432)),
            database=config_json["database"],
            user=config_json["user"],
            password=config_json.get("password", ""),
            ssl_mode=config_json.get("ssl_mode", "require"),
            table=config_json.get("table"),
            schema_name=config_json.get("schema_name", "public"),
            coluna_referencia=config_json.get("coluna_referencia"),
            coluna_texto=config_json.get("coluna_texto"),
            coluna_data=config_json.get("coluna_data"),
            custom_query=config_json.get("custom_query"),
        )

    if tipo == "s3":
        from ingestion.connectors.s3 import S3PdfConnector
        return S3PdfConnector(
            bucket=config_json["bucket"],
            region=config_json.get("region", "sa-east-1"),
            prefix=config_json.get("prefix", ""),
            access_key_id=config_json.get("access_key_id"),
            secret_access_key=config_json.get("secret_access_key"),
        )

    raise ValueError(f"Tipo de connector desconhecido para ingestão: {tipo}")


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
    # 1. Validar source existe e é de tipo suportado.
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

    # Tipos suportados na Fase 6.2:
    #   pdf_upload, postgres, s3 — rodam pipeline real.
    #   demais — ainda em stub, recusar disparo.
    suportados = {"pdf_upload", "postgres", "s3"}
    if row["type"] not in suportados:
        raise ValueError(
            f"Disparo via UI ainda não disponível para tipo '{row['type']}'. "
            f"Suportados: {sorted(suportados)}. "
            "Os demais tipos terão ativação em fase futura."
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

        # Resolve o tipo + config a partir do DB.
        async with superadmin_session() as session:
            row = (await session.execute(
                text(
                    "SELECT type, config_json FROM tenant_data_sources "
                    "WHERE id = :sid"
                ),
                {"sid": str(source_id)},
            )).mappings().first()
        if not row:
            raise RuntimeError("Source removida durante a execução.")

        connector = _construir_connector(
            tipo=row["type"],
            config_json=row["config_json"] or {},
            tenant_id=tenant_id,
            source_id=str(source_id),
        )

        # Conectores que usam `asyncio.run` internamente (postgres, s3) não
        # podem rodar dentro do event loop atual. Solução: ler todos os chunks
        # em thread separada e passar para o pipeline já materializados.
        chunks_pre_lidos = await asyncio.to_thread(lambda: list(connector.read()))
        logger.info(f"[ingestion] {len(chunks_pre_lidos)} chunks pre-lidos do connector")

        # Wrapper trivial que devolve os chunks pre-lidos.
        class _PreLidoConnector(Connector):
            def __init__(self, items, desc): self._items = items; self._desc = desc
            def read(self): return iter(self._items)
            def describe(self) -> str: return self._desc

        connector_pre = _PreLidoConnector(chunks_pre_lidos, connector.describe())

        # Pipeline precisa de uma `tenant_session` (com RLS) para inserir
        # documents_embeddings/embeddings_audit corretamente.
        embedding_client = cliente_padrao()
        try:
            async with tenant_session(tenant_id) as session:
                audit = await pipeline_executar(
                    tenant_config=tenant_config,
                    referencia=referencia or "0",
                    connector=connector_pre,
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

    except Exception as exc:  # noqa: BLE001
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
