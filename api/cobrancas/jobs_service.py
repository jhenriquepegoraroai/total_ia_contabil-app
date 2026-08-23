"""
Service layer pros jobs do Bella Cobranças.

Persistência em `cobrancas_jobs` (PG, com RLS por tenant_id). Toda função
recebe `tenant_id` explícito mesmo quando RLS está ativo (defesa em
profundidade exigida pelo RULES.md).

Operações:
  - listar_jobs(tenant_id)
  - buscar_job(tenant_id, job_id)
  - buscar_por_hash(tenant_id, content_hash)  → idempotência
  - criar_job(...)                            → cria em status='queued'
  - marcar_running(...)
  - marcar_done(...)
  - marcar_failed(...)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Listagem / busca
# =============================================================================
async def listar_jobs(
    session: AsyncSession, tenant_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT id, tenant_id, status, file_name, file_size, content_hash,
               qtde_paginas, qtde_registros, valor_total,
               started_at, finished_at, duracao_segundos, error_detail,
               created_at, updated_at
        FROM cobrancas_jobs
        WHERE tenant_id = :tid
        ORDER BY created_at DESC
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
        SELECT id, tenant_id, status, file_name, file_size, file_storage_key,
               content_hash, result_storage_key, qtde_paginas, qtde_registros,
               valor_total, started_at, finished_at, duracao_segundos,
               error_detail, created_at, updated_at
        FROM cobrancas_jobs
        WHERE tenant_id = :tid AND id = :jid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "jid": str(job_id)})).mappings().first()
    return dict(row) if row else None


async def buscar_por_hash(
    session: AsyncSession, tenant_id: str, content_hash: str
) -> dict[str, Any] | None:
    """Devolve o job mais recente do tenant com este hash (idempotência)."""
    sql = text(
        """
        SELECT id, status, file_name, qtde_registros, created_at
        FROM cobrancas_jobs
        WHERE tenant_id = :tid AND content_hash = :h
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "h": content_hash})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# Criação / transições
# =============================================================================
async def criar_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    file_name: str,
    file_size: int,
    file_storage_key: str,
    content_hash: str,
    actor_user_id: UUID | None = None,
) -> UUID:
    sql = text(
        """
        INSERT INTO cobrancas_jobs
            (tenant_id, status, file_name, file_size, file_storage_key,
             content_hash, actor_user_id)
        VALUES
            (:tid, 'queued', :fn, :fs, :fk, :h, :uid)
        RETURNING id
        """
    )
    row = (await session.execute(sql, {
        "tid": tenant_id, "fn": file_name, "fs": file_size, "fk": file_storage_key,
        "h": content_hash, "uid": str(actor_user_id) if actor_user_id else None,
    })).first()
    assert row is not None
    logger.info(f"[cobrancas/jobs] criado job {row.id} tenant={tenant_id} file={file_name}")
    return row.id


async def marcar_running(
    session: AsyncSession, *, tenant_id: str, job_id: UUID
) -> None:
    await session.execute(
        text(
            "UPDATE cobrancas_jobs SET status='running', started_at=NOW(), "
            "updated_at=NOW() WHERE tenant_id=:tid AND id=:jid"
        ),
        {"tid": tenant_id, "jid": str(job_id)},
    )


async def marcar_done(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: UUID,
    result_storage_key: str,
    qtde_paginas: int,
    qtde_registros: int,
    valor_total: float,
    started_at: datetime,
) -> None:
    duracao = (datetime.now(UTC) - started_at).total_seconds()
    await session.execute(
        text(
            """
            UPDATE cobrancas_jobs
               SET status='done',
                   result_storage_key=:rk,
                   qtde_paginas=:qp,
                   qtde_registros=:qr,
                   valor_total=:vt,
                   finished_at=NOW(),
                   duracao_segundos=:du,
                   error_detail=NULL,
                   updated_at=NOW()
             WHERE tenant_id=:tid AND id=:jid
            """
        ),
        {
            "tid": tenant_id, "jid": str(job_id), "rk": result_storage_key,
            "qp": qtde_paginas, "qr": qtde_registros, "vt": valor_total, "du": duracao,
        },
    )
    logger.info(
        f"[cobrancas/jobs] done job={job_id} tenant={tenant_id} "
        f"paginas={qtde_paginas} registros={qtde_registros} "
        f"valor={valor_total:.2f} duracao={duracao:.1f}s"
    )


async def deletar_job(
    session: AsyncSession, *, tenant_id: str, job_id: UUID
) -> dict[str, Any] | None:
    """
    Apaga o job do DB. Devolve o registro removido (com storage_keys) pro
    chamador limpar os arquivos do storage. Retorna None se não existia.
    """
    job = await buscar_job(session, tenant_id, job_id)
    if not job:
        return None
    await session.execute(
        text("DELETE FROM cobrancas_jobs WHERE tenant_id=:tid AND id=:jid"),
        {"tid": tenant_id, "jid": str(job_id)},
    )
    logger.info(f"[cobrancas/jobs] deletado job={job_id} tenant={tenant_id}")
    return job


async def marcar_failed(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: UUID,
    error_detail: str,
    started_at: datetime | None = None,
) -> None:
    duracao = (
        (datetime.now(UTC) - started_at).total_seconds() if started_at else None
    )
    await session.execute(
        text(
            """
            UPDATE cobrancas_jobs
               SET status='failed',
                   finished_at=NOW(),
                   duracao_segundos=:du,
                   error_detail=:ed,
                   updated_at=NOW()
             WHERE tenant_id=:tid AND id=:jid
            """
        ),
        {"tid": tenant_id, "jid": str(job_id), "ed": error_detail[:2000], "du": duracao},
    )
    logger.warning(f"[cobrancas/jobs] failed job={job_id} tenant={tenant_id} err={error_detail[:200]}")
