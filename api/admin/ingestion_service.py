"""
Ingestion service — disparar e monitorar jobs do pipeline a partir da UI.

Estratégia simples (Fase 6.1): asyncio.create_task no mesmo processo da API.
Cada job roda em uma task que chama o `ingestion.pipeline.executar`.

Para escala (vários workers / restart resiliente), migrar para Celery / RQ
em fase futura. Por ora, um único worker no mesmo processo serve para o
volume esperado (cada admin dispara N jobs por dia, não milhares).
"""

import asyncio
import json
import time
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import config
from api.db import superadmin_session, tenant_session
from api.storage import get_storage, tenant_source_prefix
from api.storage.local import LocalStorage
from api.tenants.registry import TenantRegistry
from ingestion.connectors.base import Connector
from ingestion.connectors.pdf_folder import PdfFolderConnector
from ingestion.connectors.storage_pdf import StoragePdfConnector
from ingestion.embeddings import cliente_padrao
from ingestion.pipeline import executar as pipeline_executar

from .sources_service import atualizar_estado_pos_job

# =============================================================================
# Resolução de referência
# =============================================================================
# Tipos cujo connector NUNCA preenche `referencia` no chunk — são todos os
# caminhos de PDF. Para eles, a referência tem que vir no disparo do job.
_TIPOS_SEM_REFERENCIA_PROPRIA: frozenset[str] = frozenset(
    {"pdf_upload", "s3", "azure_blob"}
)


def _exige_referencia_no_job(tipo: str, config_json: Any) -> bool:
    """
    True quando a fonte não consegue resolver a referência sozinha.

    Excel, CSV e Postgres resolvem por linha (`coluna_referencia`) ou por
    `referencia_default` da própria fonte. Os connectors de PDF não resolvem
    de jeito nenhum: o `PdfUploadConfig` documenta extração pelo nome do
    arquivo, mas nenhum connector implementa isso.
    """
    if tipo in _TIPOS_SEM_REFERENCIA_PROPRIA:
        return True

    config = config_json
    if isinstance(config, str):
        # Defesa contra driver que devolve JSONB como texto (mesmo cuidado
        # que o TenantRegistry já toma).
        try:
            config = json.loads(config)
        except json.JSONDecodeError:
            return True
    if not isinstance(config, dict):
        return True
    return not (config.get("coluna_referencia") or config.get("referencia_default"))


def _construir_connector(
    *,
    tipo: str,
    config_json: dict[str, Any],
    tenant_id: str,
    source_id: str,
) -> Connector:
    """Resolve o connector certo a partir do tipo da fonte + sua config."""
    if tipo == "pdf_upload":
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            prefix = tenant_source_prefix(tenant_id, source_id)
            return PdfFolderConnector(path=str(storage.root / prefix))
        return StoragePdfConnector(
            storage=storage, tenant_id=tenant_id, source_id=source_id
        )

    if tipo in ("excel_upload", "csv_upload"):
        # Arquivos foram subidos via UI para o storage local; resolvemos
        # o path absoluto e instanciamos o connector folder-based.
        storage = get_storage()
        if not isinstance(storage, LocalStorage):
            raise NotImplementedError(
                f"Tipo '{tipo}' com storage remoto ainda não suportado. "
                "Use STORAGE_PROVIDER=local em DEV."
            )
        prefix = tenant_source_prefix(tenant_id, source_id)
        local_path = storage.root / prefix
        if tipo == "excel_upload":
            from ingestion.connectors.excel import ExcelFolderConnector
            return ExcelFolderConnector(
                path=str(local_path),
                coluna_texto=config_json["coluna_texto"],
                coluna_referencia=config_json.get("coluna_referencia"),
                coluna_data=config_json.get("coluna_data"),
                referencia_default=config_json.get("referencia_default"),
            )
        from ingestion.connectors.csv_files import CsvFolderConnector
        return CsvFolderConnector(
            path=str(local_path),
            coluna_texto=config_json["coluna_texto"],
            coluna_referencia=config_json.get("coluna_referencia"),
            coluna_data=config_json.get("coluna_data"),
            referencia_default=config_json.get("referencia_default"),
            delimiter=config_json.get("delimiter", ","),
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

    if tipo == "azure_blob":
        from ingestion.connectors.azure_blob import AzureBlobPdfConnector
        return AzureBlobPdfConnector(
            account=config_json["account"],
            container=config_json["container"],
            prefix=config_json.get("prefix", ""),
            sas_token=config_json.get("sas_token"),
            account_key=config_json.get("account_key"),
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

    # Tipos suportados (Fase 6.2 completa):
    suportados = {
        "pdf_upload", "excel_upload", "csv_upload",
        "postgres", "s3", "azure_blob",
    }
    if row["type"] not in suportados:
        raise ValueError(
            f"Disparo via UI ainda não disponível para tipo '{row['type']}'. "
            f"Suportados: {sorted(suportados)}. "
            "Os demais tipos terão ativação em fase futura."
        )

    # 1.1 Referência é obrigatória quando a fonte não sabe resolvê-la sozinha.
    if not referencia and _exige_referencia_no_job(row["type"], row["config_json"]):
        raise ValueError(
            f"Fonte do tipo '{row['type']}' não fornece a referência do "
            "condomínio por documento — informe a referência no disparo do "
            "job. Sem isso, o acervo inteiro seria indexado sob um condomínio "
            "que não existe e ficaria invisível no chat."
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
            def __init__(self, items, desc):
                self._items = items
                self._desc = desc

            def read(self):
                return iter(self._items)

            def describe(self) -> str:
                return self._desc

        connector_pre = _PreLidoConnector(chunks_pre_lidos, connector.describe())

        # Resolve a chave OpenAI do tenant: se 'custom', usa a do cliente;
        # senão, cai na chave da Lello (OPEN_AI_KEY do env).
        tenant_openai = getattr(tenant_config, "openai", None)
        api_key_override = (
            tenant_openai.api_key
            if tenant_openai and tenant_openai.mode == "custom" and tenant_openai.api_key
            else None
        )
        if api_key_override:
            logger.info(f"[ingestion] usando chave OpenAI do tenant {tenant_id}")

        # Pipeline precisa de uma `tenant_session` (com RLS) para inserir
        # documents_embeddings/embeddings_audit corretamente.
        embedding_client = cliente_padrao(api_key=api_key_override)
        try:
            async with tenant_session(tenant_id) as session:
                audit = await pipeline_executar(
                    tenant_config=tenant_config,
                    # Sem fallback: `None` só chega aqui quando a fonte resolve
                    # a referência por linha. Se algum chunk ficar sem, o
                    # pipeline levanta em vez de inventar um condomínio.
                    referencia=referencia,
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
                # Não re-levanta: já estamos no caminho de falha do job e
                # perder o registro do estado não pode mascarar o erro
                # original. Mas engolir calado esconderia sessão caída —
                # loga com stack (RULES: `except: pass` é proibido).
                logger.exception(
                    f"Falha ao marcar source_id={source_id} como 'failed' "
                    f"apos erro no job {job_id}"
                )
