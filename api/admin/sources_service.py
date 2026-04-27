"""
Service layer de fontes de dados — CRUD + teste de conexão.

Tudo via `superadmin_session` (sem RLS): superadmin vê fontes de qualquer
tenant. Em endpoints user-facing, sempre filtrar por tenant_id no SQL
mesmo assim (defesa em profundidade).
"""

import json
from typing import Any
from uuid import UUID

from loguru import logger
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .sources_models import (
    SourceConfig,
    PdfUploadConfig,
    PostgresSourceConfig,
    S3SourceConfig,
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
        # Stub funcional: valida só a estrutura. Fase 6.2 fará list_objects real.
        return {
            "ok": True,
            "detail": (
                "Configuração S3 aceita. NOTA: validação real (list_objects) "
                "vai ativar na Fase 6.2 quando aioboto3 for instalado."
            ),
            "metadata": {"bucket": config.bucket, "region": config.region},
        }

    if isinstance(config, PostgresSourceConfig):
        # Tenta conectar de fato — usa asyncpg que já está instalado.
        return await _testar_postgres(config)

    return {
        "ok": True,
        "detail": f"Tipo '{config.type}' aceito (validação completa na Fase 6.2).",
        "metadata": {},
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
