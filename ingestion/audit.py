"""
Auditoria do pipeline — equivalente da tabela
`controle_quantidade_tabelas_projeto_bella` do Spark da Lello.

Cada execução do pipeline gera uma linha em `embeddings_audit` com:
  - tenant_id, referencia, connector, started_at, finished_at
  - qtde_chunks_origem, qtde_processada, qtde_skipped, qtde_erros
  - duracao_segundos, erro_detalhe (se aplicável)

Função `hashes_ja_processados` consulta os content_hashes já registrados
para suportar idempotência (SKIP do que já foi feito).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AuditRecord:
    """Estado de uma execução do pipeline."""

    tenant_id: str
    referencia: Optional[str]
    connector: str
    started_at: datetime
    qtde_chunks_origem: int = 0
    qtde_processada: int = 0
    qtde_skipped: int = 0
    qtde_erros: int = 0
    finished_at: Optional[datetime] = None
    duracao_segundos: Optional[float] = None
    erro_detalhe: Optional[str] = None
    contador: Optional[int] = None  # preenchido após insert


async def hashes_ja_processados(
    session: AsyncSession,
    tenant_id: str,
    referencia: str,
) -> set[str]:
    """
    Retorna o set de content_hashes já existentes em documents_embeddings
    para `(tenant_id, referencia)`. Usado para SKIP de chunks idênticos.

    Importante: lê de `documents_embeddings` (não de `embeddings_audit`),
    porque é lá que ficam os hashes por chunk individual.
    """
    sql = """
        SELECT content_hash
        FROM documents_embeddings
        WHERE tenant_id = :tid AND referencia = :ref
    """
    result = await session.execute(text(sql), {"tid": tenant_id, "ref": referencia})
    return {row[0] for row in result.all()}


async def insert_audit_inicial(session: AsyncSession, audit: AuditRecord) -> int:
    """Cria a linha de auditoria com `started_at`. Retorna o `contador` gerado."""
    sql = """
        INSERT INTO embeddings_audit
            (tenant_id, referencia, connector, started_at,
             qtde_chunks_origem, qtde_processada, qtde_skipped, qtde_erros)
        VALUES (:tid, :ref, :conn, :sa, 0, 0, 0, 0)
        RETURNING contador
    """
    result = await session.execute(
        text(sql),
        {
            "tid": audit.tenant_id,
            "ref": audit.referencia,
            "conn": audit.connector,
            "sa": audit.started_at,
        },
    )
    contador = result.scalar_one()
    audit.contador = contador
    return contador


async def update_audit_final(session: AsyncSession, audit: AuditRecord) -> None:
    """Atualiza a linha com finished_at, contagens e duração."""
    if audit.contador is None:
        raise RuntimeError("AuditRecord sem contador — chame insert_audit_inicial antes.")

    sql = """
        UPDATE embeddings_audit
        SET finished_at = :fa,
            qtde_chunks_origem = :qo,
            qtde_processada = :qp,
            qtde_skipped = :qs,
            qtde_erros = :qe,
            duracao_segundos = :ds,
            erro_detalhe = :ed
        WHERE contador = :c
    """
    await session.execute(
        text(sql),
        {
            "fa": audit.finished_at,
            "qo": audit.qtde_chunks_origem,
            "qp": audit.qtde_processada,
            "qs": audit.qtde_skipped,
            "qe": audit.qtde_erros,
            "ds": audit.duracao_segundos,
            "ed": audit.erro_detalhe,
            "c": audit.contador,
        },
    )
