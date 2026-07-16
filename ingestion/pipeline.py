"""
Pipeline orquestrador.

Espelha o fluxo do script Spark da Lello:
    1. Connector lê origem → list[RawChunk]
    2. content_hash de cada chunk
    3. SELECT em documents_embeddings: quais hashes já existem
       (espelha o `leftanti` join do Spark)
    4. Truncate por tiktoken (MAX_TOKENS=8191)
    5. Split em batches de 100
    6. asyncio.gather com Semaphore(10) — espelha `max_workers=10` do Spark
       Cada task: chama OpenAI batch → upsert documents_embeddings
    7. Update audit final
"""

import asyncio
import time
from datetime import datetime
from itertools import islice
from typing import Iterable, TypeVar

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from api import config
from api.tenants.models import TenantConfig
from . import audit as audit_mod
from .chunking import truncar_para_limite_tokens
from .connectors.base import Connector, RawChunk
from .embeddings import EmbeddingClient
from .idempotency import content_hash
from .persistence import EmbeddingRow, upsert_batch


T = TypeVar("T")


def _batches(seq: list[T], size: int) -> Iterable[list[T]]:
    """Quebra `seq` em batches de até `size` itens."""
    it = iter(seq)
    while batch := list(islice(it, size)):
        yield batch


async def executar(
    *,
    tenant_config: TenantConfig,
    referencia: str,
    connector: Connector,
    session: AsyncSession,
    embedding_client: EmbeddingClient,
    batch_size: int = config.INGESTION_BATCH_SIZE,
    max_concurrent_batches: int = config.INGESTION_MAX_WORKERS,
) -> audit_mod.AuditRecord:
    """
    Executa o pipeline completo para `(tenant_id, referencia)`.

    A `session` deve estar em uma `tenant_session(tenant_id)` aberta — quem
    chama é responsável por isso (RULES.md #2).

    Retorna o `AuditRecord` final com contagens.
    """
    tenant_id = tenant_config.tenant_id
    started_at = datetime.now()
    t0 = time.monotonic()

    audit = audit_mod.AuditRecord(
        tenant_id=tenant_id,
        referencia=referencia,
        connector=connector.describe(),
        started_at=started_at,
    )
    await audit_mod.insert_audit_inicial(session, audit)
    logger.info(
        f"[start] tenant={tenant_id} ref={referencia} connector={connector.describe()}"
    )

    try:
        # 1. Leitura
        chunks_raw: list[RawChunk] = list(connector.read())
        audit.qtde_chunks_origem = len(chunks_raw)
        logger.info(f"[reading] {len(chunks_raw)} chunks lidos da origem")

        if not chunks_raw:
            logger.warning("Nenhum chunk para processar.")
            return await _finalizar(session, audit, t0)

        # 2. Resolver referência por chunk e content_hash.
        # Se o connector traz `referencia` no chunk, usamos ela; senão, a default.
        ref_por_chunk: dict[tuple[str, str], str] = {
            (c.file_name, c.record_id): (c.referencia or referencia)
            for c in chunks_raw
        }
        hashes_chunk = {
            (c.file_name, c.record_id): content_hash(
                tenant_id,
                ref_por_chunk[(c.file_name, c.record_id)],
                c.file_name,
                c.record_id,
                c.paragraph,
            )
            for c in chunks_raw
        }

        # 3. Idempotência — coleta de hashes existentes por referência.
        # Se há múltiplas referências entre os chunks, consulta cada uma.
        referencias_distintas = {
            ref_por_chunk[k] for k in ref_por_chunk
        }
        hashes_db: set[str] = set()
        for ref in referencias_distintas:
            hashes_db |= await audit_mod.hashes_ja_processados(session, tenant_id, ref)

        chunks_a_processar: list[RawChunk] = []
        for chunk in chunks_raw:
            h = hashes_chunk[(chunk.file_name, chunk.record_id)]
            if h in hashes_db:
                audit.qtde_skipped += 1
            else:
                chunks_a_processar.append(chunk)

        logger.info(
            f"[idempotency] {audit.qtde_skipped} já indexados (hash bate), "
            f"{len(chunks_a_processar)} a processar"
        )

        if not chunks_a_processar:
            return await _finalizar(session, audit, t0)

        # 4. Truncate (sync — tiktoken é CPU-bound mas rápido para nossos volumes)
        truncados = [
            (c, truncar_para_limite_tokens(c.paragraph, config.EMBEDDING_MAX_TOKENS))
            for c in chunks_a_processar
        ]

        # 5. Batches
        all_batches = list(_batches(truncados, batch_size))
        n_batches = len(all_batches)
        logger.info(
            f"[batches] {n_batches} batches de até {batch_size} chunks "
            f"com até {max_concurrent_batches} em paralelo"
        )

        # 6. Processamento paralelo
        sem = asyncio.Semaphore(max_concurrent_batches)

        async def _processar_batch(idx: int, batch: list[tuple[RawChunk, str]]) -> tuple[int, int]:
            """Retorna (qtde_processada, qtde_erros) deste batch."""
            async with sem:
                t_b = time.monotonic()
                paragraphs = [t for _, t in batch]
                logger.info(f"[batch {idx + 1}/{n_batches}] {len(batch)} chunks → OpenAI...")

                results = await embedding_client.embed_batch(paragraphs)

                rows: list[EmbeddingRow] = []
                erros = 0
                for r, (chunk, _truncado) in zip(results, batch):
                    if r.embedding is None:
                        erros += 1
                        logger.warning(
                            f"[batch {idx + 1}] chunk {chunk.file_name}/{chunk.record_id} "
                            f"FALHOU: {r.erro}"
                        )
                        continue
                    h = hashes_chunk[(chunk.file_name, chunk.record_id)]
                    rows.append(
                        EmbeddingRow(
                            tenant_id=tenant_id,
                            referencia=ref_por_chunk[(chunk.file_name, chunk.record_id)],
                            file_name=chunk.file_name,
                            record_id=chunk.record_id,
                            paragraph=chunk.paragraph,
                            embedding=r.embedding,
                            data_valida=chunk.data_valida,
                            content_hash=h,
                            embedding_model=embedding_client.model,
                            embedding_dim=len(r.embedding),
                        )
                    )

                if rows:
                    await upsert_batch(session, rows)

                logger.info(
                    f"[batch {idx + 1}/{n_batches}] OK em {time.monotonic() - t_b:.2f}s "
                    f"(processados={len(rows)}, erros={erros})"
                )
                return len(rows), erros

        tarefas = [_processar_batch(i, b) for i, b in enumerate(all_batches)]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        for r in resultados:
            if isinstance(r, BaseException):
                logger.exception(f"Batch levantou: {r}")
                # Se levantou, contabilizamos como falha de batch inteiro.
                # Defensivo: não temos como saber quantos chunks no batch sem trackear,
                # então registramos no erro_detalhe.
                audit.erro_detalhe = (audit.erro_detalhe or "") + f"\nBatch erro: {r}"
                continue
            qp, qe = r
            audit.qtde_processada += qp
            audit.qtde_erros += qe

        return await _finalizar(session, audit, t0)

    except Exception as exc:
        audit.erro_detalhe = f"Falha não tratada: {exc}"
        logger.exception("Pipeline falhou com exceção não tratada.")
        await _finalizar(session, audit, t0)
        raise


async def _finalizar(
    session: AsyncSession,
    audit: audit_mod.AuditRecord,
    t0: float,
) -> audit_mod.AuditRecord:
    audit.finished_at = datetime.now()
    audit.duracao_segundos = round(time.monotonic() - t0, 2)
    await audit_mod.update_audit_final(session, audit)

    logger.info(
        f"[finished] tenant={audit.tenant_id} ref={audit.referencia} "
        f"duracao={audit.duracao_segundos}s "
        f"processados={audit.qtde_processada} "
        f"skipped={audit.qtde_skipped} "
        f"erros={audit.qtde_erros}"
    )
    return audit
