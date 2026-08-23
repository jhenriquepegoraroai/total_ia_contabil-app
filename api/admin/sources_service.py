"""
Service layer de fontes de dados — CRUD + teste de conexão.

Tudo via `superadmin_session` (sem RLS): superadmin vê fontes de qualquer
tenant. Em endpoints user-facing, sempre filtrar por tenant_id no SQL
mesmo assim (defesa em profundidade).
"""

from typing import Any
from uuid import UUID

from loguru import logger
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .sources_models import (
    AzureBlobSourceConfig,
    PdfUploadConfig,
    PostgresSourceConfig,
    S3SourceConfig,
    SourceConfig,
)

_SourceConfigAdapter = TypeAdapter(SourceConfig)


# =============================================================================
# CRUD
# =============================================================================
async def listar_sources(
    session: AsyncSession, tenant_id: str
) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT id, tenant_id, name, type, enabled, qtde_files,
               last_run_at, last_run_status, created_at, updated_at
        FROM tenant_data_sources
        WHERE tenant_id = :tid
        ORDER BY created_at DESC
        """
    )
    rows = (await session.execute(sql, {"tid": tenant_id})).mappings().all()
    return [dict(r) for r in rows]


async def buscar_source(
    session: AsyncSession, tenant_id: str, source_id: UUID
) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT id, tenant_id, name, type, config_json, secret_name,
               enabled, qtde_files, last_run_at, last_run_status,
               created_at, updated_at
        FROM tenant_data_sources
        WHERE tenant_id = :tid AND id = :sid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "sid": str(source_id)})).mappings().first()
    return dict(row) if row else None


async def criar_source(
    session: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    config: SourceConfig,
    secret_name: str | None,
) -> UUID:
    """Cria uma fonte. Retorna o id gerado."""
    try:
        sql = text(
            """
            INSERT INTO tenant_data_sources
                (tenant_id, name, type, config_json, secret_name)
            VALUES (:tid, :nm, :tp, CAST(:cj AS jsonb), :sn)
            RETURNING id
            """
        )
        result = await session.execute(
            sql,
            {
                "tid": tenant_id,
                "nm": name,
                "tp": config.type,
                "cj": config.model_dump_json(),
                "sn": secret_name,
            },
        )
        new_id = result.scalar_one()
        logger.info(f"[sources] criada {new_id} ({config.type}) para tenant {tenant_id}")
        return new_id
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError(
                f"Já existe fonte com nome '{name}' para o tenant '{tenant_id}'."
            ) from exc
        raise


async def atualizar_source(
    session: AsyncSession,
    *,
    tenant_id: str,
    source_id: UUID,
    name: str,
    config: SourceConfig,
    secret_name: str | None,
    enabled: bool | None = None,
) -> bool:
    """
    Atualiza uma fonte existente. O `type` da fonte é imutável — se a config
    enviada for de outro tipo, levanta ValueError.
    Retorna True se a row foi atualizada, False se a fonte não existe.
    """
    existing = await buscar_source(session, tenant_id, source_id)
    if not existing:
        return False
    if existing["type"] != config.type:
        raise ValueError(
            f"Tipo da fonte é imutável: '{existing['type']}' != '{config.type}'. "
            "Para mudar o tipo, delete e recrie a fonte."
        )

    try:
        sql = text(
            """
            UPDATE tenant_data_sources SET
                name = :nm,
                config_json = CAST(:cj AS jsonb),
                secret_name = :sn,
                enabled = COALESCE(:en, enabled),
                updated_at = NOW()
            WHERE tenant_id = :tid AND id = :sid
            """
        )
        result = await session.execute(
            sql,
            {
                "tid": tenant_id,
                "sid": str(source_id),
                "nm": name,
                "cj": config.model_dump_json(),
                "sn": secret_name,
                "en": enabled,
            },
        )
        logger.info(
            f"[sources] atualizada {source_id} ({config.type}) para tenant {tenant_id}"
        )
        return result.rowcount > 0
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError(
                f"Já existe outra fonte com nome '{name}' para o tenant '{tenant_id}'."
            ) from exc
        raise


async def deletar_source(
    session: AsyncSession, tenant_id: str, source_id: UUID
) -> bool:
    sql = text(
        "DELETE FROM tenant_data_sources WHERE tenant_id = :tid AND id = :sid"
    )
    result = await session.execute(sql, {"tid": tenant_id, "sid": str(source_id)})
    return result.rowcount > 0


# =============================================================================
# Teste de conexão (validação leve, não roda pipeline)
# =============================================================================
async def testar_conexao(config: SourceConfig) -> dict[str, Any]:
    """
    Valida a config de uma fonte. Para tipos `*_upload`, checa apenas
    estrutura (sempre OK). Para fontes externas, tenta conectar de fato.

    Retorna `{"ok": bool, "detail": str, "metadata": {...}}`.
    """
    if isinstance(config, PdfUploadConfig):
        return {"ok": True, "detail": "PDF upload — pronto para receber arquivos.", "metadata": {}}

    if isinstance(config, S3SourceConfig):
        return await _testar_s3(config)

    if isinstance(config, AzureBlobSourceConfig):
        return await _testar_azure_blob(config)

    if isinstance(config, PostgresSourceConfig):
        return await _testar_postgres(config)

    return {
        "ok": True,
        "detail": f"Tipo '{config.type}' aceito (validação completa na Fase 6.2).",
        "metadata": {},
    }


async def _testar_s3(config: S3SourceConfig) -> dict[str, Any]:
    """List_objects_v2 limitado a 1 chave para validar conexão."""
    try:
        import aioboto3  # noqa: F401
    except ImportError:
        return {
            "ok": False,
            "detail": "aioboto3 não instalado nesta API.",
            "metadata": {},
        }

    import aioboto3
    session_kwargs: dict = {}
    if config.access_key_id and config.secret_access_key:
        session_kwargs["aws_access_key_id"] = config.access_key_id
        session_kwargs["aws_secret_access_key"] = config.secret_access_key

    try:
        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", region_name=config.region) as s3:
            resp = await s3.list_objects_v2(
                Bucket=config.bucket,
                Prefix=config.prefix or "",
                MaxKeys=1,
            )
        keycount = resp.get("KeyCount", 0)
        return {
            "ok": True,
            "detail": (
                f"Bucket acessível. Encontradas {keycount} chave(s) com "
                f"prefix={config.prefix!r} (limit=1)."
            ),
            "metadata": {"bucket": config.bucket, "region": config.region, "key_count_amostra": keycount},
        }
    except Exception as exc:
        logger.warning(f"Falha testando S3: {exc}")
        return {
            "ok": False,
            "detail": f"Falha de conexão S3: {exc}",
            "metadata": {"bucket": config.bucket},
        }


async def _testar_azure_blob(config: AzureBlobSourceConfig) -> dict[str, Any]:
    """List blobs com max=1 para validar conexão."""
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient
    except ImportError:
        return {
            "ok": False,
            "detail": "azure-storage-blob não instalado nesta API.",
            "metadata": {},
        }

    url = f"https://{config.account}.blob.core.windows.net"
    try:
        if config.sas_token:
            client = BlobServiceClient(account_url=f"{url}?{config.sas_token}")
        elif config.account_key:
            client = BlobServiceClient(account_url=url, credential=config.account_key)
        else:
            client = BlobServiceClient(account_url=url, credential=DefaultAzureCredential())

        async with client:
            container = client.get_container_client(config.container)
            count = 0
            async for _ in container.list_blobs(name_starts_with=config.prefix or "", results_per_page=1):
                count += 1
                break

        return {
            "ok": True,
            "detail": (
                f"Container acessível. {'Pelo menos 1 blob encontrado' if count else 'Container vazio ou sem prefix correspondente'}."
            ),
            "metadata": {"account": config.account, "container": config.container},
        }
    except Exception as exc:
        logger.warning(f"Falha testando Azure Blob: {exc}")
        return {
            "ok": False,
            "detail": f"Falha de conexão Azure Blob: {exc}",
            "metadata": {"account": config.account, "container": config.container},
        }


async def _testar_postgres(config: PostgresSourceConfig) -> dict[str, Any]:
    """Tenta conectar no Postgres do cliente. Retorna sucesso ou erro detalhado."""
    import asyncpg

    if not config.password:
        return {
            "ok": False,
            "detail": "Senha do Postgres não fornecida (em produção, usar secret_name).",
            "metadata": {},
        }

    dsn = (
        f"postgres://{config.user}:{config.password}@{config.host}:{config.port}"
        f"/{config.database}"
    )
    try:
        conn = await asyncpg.connect(dsn, ssl=config.ssl_mode != "disable", timeout=10)
        try:
            ver = await conn.fetchval("SELECT version()")
        finally:
            await conn.close()
        return {
            "ok": True,
            "detail": "Conexão estabelecida com sucesso.",
            "metadata": {"version": str(ver)[:80]},
        }
    except Exception as exc:
        logger.warning(f"Falha testando Postgres do cliente: {exc}")
        return {"ok": False, "detail": f"Falha de conexão: {exc}", "metadata": {}}


# =============================================================================
# Atualizações de estado pós-job
# =============================================================================
async def atualizar_estado_pos_job(
    session: AsyncSession,
    *,
    source_id: UUID,
    status: str,
    qtde_files_delta: int = 0,
) -> None:
    """Chamado pelo ingestion_service após a execução."""
    sql = text(
        """
        UPDATE tenant_data_sources SET
            last_run_at = NOW(),
            last_run_status = :st,
            qtde_files = qtde_files + :delta,
            updated_at = NOW()
        WHERE id = :sid
        """
    )
    await session.execute(sql, {"st": status, "delta": qtde_files_delta, "sid": str(source_id)})


def parse_config(type_: str, config_dict: dict[str, Any]) -> SourceConfig:
    """Re-hidrata um SourceConfig a partir do JSON salvo no DB."""
    payload = dict(config_dict)
    payload["type"] = type_  # garante o discriminator
    return _SourceConfigAdapter.validate_python(payload)
