"""
Persistência dos embeddings no Postgres.

Upsert por chave `(tenant_id, referencia, file_name, record_id)`. Conflito
significa REEMBED — atualiza o `embedding`, `paragraph`, `data_valida` e
`content_hash`.

A inserção é em batch (executemany) para reduzir round trips. Cada batch é
uma transação; se um chunk falhar, todo o batch dá rollback (atomicidade
prevista no RULES.md #20).
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EmbeddingRow:
    """Linha pronta para upsert em documents_embeddings."""

    tenant_id: str
    referencia: str
    file_name: str
    record_id: str
    paragraph: str
    embedding: list[float]
    data_valida: date | None
    content_hash: str
    embedding_model: str
    embedding_dim: int


async def upsert_batch(session: AsyncSession, rows: list[EmbeddingRow]) -> int:
    """
    Faz upsert de um batch de embeddings em transação única.

    Retorna o número de linhas afetadas (inseridas + atualizadas).
    """
    if not rows:
        return 0

    sql = text(
        """
        INSERT INTO documents_embeddings
            (tenant_id, referencia, file_name, record_id, paragraph,
             embedding, data_valida, content_hash, embedding_model, embedding_dim)
        VALUES
            (:tid, :ref, :fn, :rid, :par, CAST(:emb AS vector), :dv, :hash,
             :emb_model, :emb_dim)
        ON CONFLICT (tenant_id, referencia, file_name, record_id) DO UPDATE SET
            paragraph = EXCLUDED.paragraph,
            embedding = EXCLUDED.embedding,
            data_valida = EXCLUDED.data_valida,
            content_hash = EXCLUDED.content_hash,
            embedding_model = EXCLUDED.embedding_model,
            embedding_dim = EXCLUDED.embedding_dim
        """
    )

    params = [
        {
            "tid": r.tenant_id,
            "ref": r.referencia,
            "fn": r.file_name,
            "rid": r.record_id,
            "par": r.paragraph,
            "emb": _vector_literal(r.embedding),
            "dv": r.data_valida,
            "hash": r.content_hash,
            "emb_model": r.embedding_model,
            "emb_dim": r.embedding_dim,
        }
        for r in rows
    ]

    await session.execute(sql, params)
    return len(rows)


def _vector_literal(embedding: list[float]) -> str:
    """Mesmo formato consumido pelo cast `CAST(:emb AS vector)`."""
    return "[" + ",".join(f"{float(x):.7f}" for x in embedding) + "]"
