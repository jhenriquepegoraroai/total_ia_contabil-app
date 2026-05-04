"""
Service layer das atas (CRUD básico + queries).

Operações dos pipelines (gerar, comparar, corrigir, transcrever) ficam
nos respectivos `pipeline_*.py` e `stt_service.py`. Aqui só persistência.

Toda função recebe `tenant_id` explícito mesmo com RLS — defesa em
profundidade (RULES.md).
"""

from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Listagem / busca
# =============================================================================
async def listar_atas(
    session: AsyncSession,
    tenant_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Lista atas do tenant, ordenadas por última atualização (decrescente)."""
    sql = text(
        """
        SELECT id, tenant_id, titulo, referencia, status, versao_atual_id,
               consultor_user_id, sindico_user_id, presidente_user_id,
               erro_detalhe, created_at, updated_at
        FROM atas
        WHERE tenant_id = :tid
        ORDER BY updated_at DESC
        LIMIT :lim
        """
    )
    rows = (await session.execute(sql, {"tid": tenant_id, "lim": limit})).mappings().all()
    return [dict(r) for r in rows]


async def buscar_ata(
    session: AsyncSession, tenant_id: str, ata_id: UUID
) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT id, tenant_id, titulo, referencia, status, versao_atual_id,
               consultor_user_id, sindico_user_id, presidente_user_id,
               insumos_json, erro_detalhe, created_at, updated_at
        FROM atas
        WHERE tenant_id = :tid AND id = :aid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "aid": str(ata_id)})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# Criação
# =============================================================================
async def criar_ata(
    session: AsyncSession,
    *,
    tenant_id: str,
    titulo: str,
    referencia: str | None,
    consultor_user_id: UUID,
    sindico_user_id: UUID | None = None,
    presidente_user_id: UUID | None = None,
) -> UUID:
    """
    Cria uma ata em status='rascunho'. Síndico e presidente são opcionais
    aqui — podem ser definidos depois (ou na hora de enviar).

    Registra ação 'criada' em atas_acoes na mesma transação.
    """
    sql_insert = text(
        """
        INSERT INTO atas
            (tenant_id, titulo, referencia, status, consultor_user_id,
             sindico_user_id, presidente_user_id)
        VALUES (:tid, :t, :ref, 'rascunho', :cuid, :suid, :puid)
        RETURNING id
        """
    )
    row = (await session.execute(sql_insert, {
        "tid": tenant_id, "t": titulo, "ref": referencia,
        "cuid": str(consultor_user_id),
        "suid": str(sindico_user_id) if sindico_user_id else None,
        "puid": str(presidente_user_id) if presidente_user_id else None,
    })).first()
    assert row is not None
    ata_id: UUID = row.id

    await registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="criada",
        detalhe={"titulo": titulo, "referencia": referencia},
    )
    logger.info(f"[atas] criada ata={ata_id} tenant={tenant_id} consultor={consultor_user_id}")
    return ata_id


# =============================================================================
# Auditoria
# =============================================================================
async def registrar_acao(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    ator_user_id: UUID | None,
    acao: str,
    detalhe: dict[str, Any] | None = None,
) -> None:
    """Insere uma linha em atas_acoes. Não gera commit — caller decide."""
    import json
    await session.execute(
        text(
            """
            INSERT INTO atas_acoes (ata_id, tenant_id, ator_user_id, acao, detalhe_json)
            VALUES (:aid, :tid, :uid, :ac, CAST(:dj AS JSONB))
            """
        ),
        {
            "aid": str(ata_id),
            "tid": tenant_id,
            "uid": str(ator_user_id) if ator_user_id else None,
            "ac": acao,
            "dj": json.dumps(detalhe or {}),
        },
    )
