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


# =============================================================================
# Insumos (entrada do gerador)
# =============================================================================
async def atualizar_insumos(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    patch: dict[str, Any],
    ator_user_id: UUID | None,
) -> dict[str, Any]:
    """
    Faz merge dos campos não-nulos do `patch` no `atas.insumos_json`.

    Retorna o dict mesclado pós-update. Levanta ValueError se ata não
    existir no tenant. Não comita — caller decide.
    """
    import json

    ata = await buscar_ata(session, tenant_id, ata_id)
    if not ata:
        raise ValueError(f"Ata {ata_id} não encontrada no tenant {tenant_id}.")

    insumos_existentes = ata.get("insumos_json") or {}
    # Só sobrescreve campos que vieram com valor (None = não tocar).
    novos = {**insumos_existentes, **{k: v for k, v in patch.items() if v is not None}}

    await session.execute(
        text(
            "UPDATE atas SET insumos_json = CAST(:ij AS JSONB), updated_at = NOW() "
            "WHERE id = :aid AND tenant_id = :tid"
        ),
        {"ij": json.dumps(novos), "aid": str(ata_id), "tid": tenant_id},
    )

    await registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=ator_user_id,
        acao="editada_consultor",
        detalhe={"campos_atualizados": sorted(k for k, v in patch.items() if v is not None)},
    )
    return novos


# =============================================================================
# Versões — leitura, criação, atualização do ponteiro versao_atual_id
# =============================================================================
async def buscar_versao(
    session: AsyncSession, tenant_id: str, versao_id: UUID
) -> dict[str, Any] | None:
    """Carrega uma versão pelo id, com conteúdo HTML completo."""
    sql = text(
        """
        SELECT id, ata_id, tenant_id, tipo, conteudo_html, metadata_json,
               criada_por_user_id, criada_em
        FROM atas_versoes
        WHERE tenant_id = :tid AND id = :vid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "vid": str(versao_id)})).mappings().first()
    return dict(row) if row else None


async def listar_versoes(
    session: AsyncSession, tenant_id: str, ata_id: UUID
) -> list[dict[str, Any]]:
    """Lista versões de uma ata em ordem cronológica decrescente (mais nova primeiro)."""
    sql = text(
        """
        SELECT id, ata_id, tenant_id, tipo, metadata_json,
               criada_por_user_id, criada_em
        FROM atas_versoes
        WHERE tenant_id = :tid AND ata_id = :aid
        ORDER BY criada_em DESC
        """
    )
    rows = (await session.execute(sql, {"tid": tenant_id, "aid": str(ata_id)})).mappings().all()
    return [dict(r) for r in rows]


async def buscar_diff_mais_recente(
    session: AsyncSession, tenant_id: str, ata_id: UUID
) -> dict[str, Any] | None:
    """Versão mais recente do tipo='comparacao' da ata. None se nunca houve diff."""
    sql = text(
        """
        SELECT id, ata_id, tenant_id, tipo, conteudo_html, metadata_json,
               criada_em
        FROM atas_versoes
        WHERE tenant_id = :tid AND ata_id = :aid AND tipo = 'comparacao'
        ORDER BY criada_em DESC
        LIMIT 1
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "aid": str(ata_id)})).mappings().first()
    return dict(row) if row else None


async def criar_versao(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    tipo: str,
    conteudo_html: str,
    metadata: dict[str, Any] | None = None,
    criada_por_user_id: UUID | None = None,
) -> UUID:
    """
    Insere uma linha em atas_versoes (imutável). Caller decide se atualiza
    o `versao_atual_id` da ata mestre depois.
    """
    import json
    row = (await session.execute(
        text(
            """
            INSERT INTO atas_versoes
                (ata_id, tenant_id, tipo, conteudo_html, metadata_json, criada_por_user_id)
            VALUES (:aid, :tid, :tipo, :html, CAST(:meta AS JSONB), :uid)
            RETURNING id
            """
        ),
        {
            "aid": str(ata_id),
            "tid": tenant_id,
            "tipo": tipo,
            "html": conteudo_html,
            "meta": json.dumps(metadata or {}),
            "uid": str(criada_por_user_id) if criada_por_user_id else None,
        },
    )).first()
    assert row is not None
    return row.id


async def atualizar_versao_atual(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    versao_id: UUID,
) -> None:
    """Aponta `atas.versao_atual_id` pra uma versão. Caller decide o status."""
    await session.execute(
        text(
            "UPDATE atas SET versao_atual_id=:vid, updated_at=NOW() "
            "WHERE id=:aid AND tenant_id=:tid"
        ),
        {"vid": str(versao_id), "aid": str(ata_id), "tid": tenant_id},
    )


async def atualizar_status(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    status: str,
    erro_detalhe: str | None = None,
) -> None:
    """Atualiza atas.status (e limpa erro_detalhe quando o status muda pra um happy path)."""
    if erro_detalhe is None:
        await session.execute(
            text(
                "UPDATE atas SET status=:st, erro_detalhe=NULL, updated_at=NOW() "
                "WHERE id=:aid AND tenant_id=:tid"
            ),
            {"st": status, "aid": str(ata_id), "tid": tenant_id},
        )
    else:
        await session.execute(
            text(
                "UPDATE atas SET status=:st, erro_detalhe=:err, updated_at=NOW() "
                "WHERE id=:aid AND tenant_id=:tid"
            ),
            {"st": status, "err": erro_detalhe[:1000], "aid": str(ata_id), "tid": tenant_id},
        )


async def atualizar_versao_base(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    quem: str,                            # "sindico" ou "presidente"
    versao_id: UUID,
) -> None:
    """Snapshot da versão "antes" antes de enviar pro síndico ou presidente."""
    coluna = f"versao_base_{quem}_id"
    if quem not in ("sindico", "presidente"):
        raise ValueError(f"quem inválido: {quem!r}; aceitos: sindico|presidente")
    await session.execute(
        text(
            f"UPDATE atas SET {coluna}=:vid, updated_at=NOW() "
            f"WHERE id=:aid AND tenant_id=:tid"
        ),
        {"vid": str(versao_id), "aid": str(ata_id), "tid": tenant_id},
    )


# =============================================================================
# Usuários da ata (pra notificações)
# =============================================================================
async def usuarios_da_ata(
    session: AsyncSession, tenant_id: str, ata_id: UUID
) -> dict[str, dict[str, Any] | None]:
    """
    Resolve os 3 atores da ata (consultor, síndico opcional, presidente
    opcional) e devolve seus dados básicos pra notificação por e-mail.

    Formato:
        {
            "consultor":  {"id": ..., "email": ..., "nome": ...} | None,
            "sindico":    {...} | None,
            "presidente": {...} | None,
        }
    """
    sql = text(
        """
        SELECT a.consultor_user_id, a.sindico_user_id, a.presidente_user_id,
               c.id  AS c_id,  c.email  AS c_email,  c.nome  AS c_nome,
               s.id  AS s_id,  s.email  AS s_email,  s.nome  AS s_nome,
               p.id  AS p_id,  p.email  AS p_email,  p.nome  AS p_nome
        FROM atas a
        LEFT JOIN users c ON c.id = a.consultor_user_id
        LEFT JOIN users s ON s.id = a.sindico_user_id
        LEFT JOIN users p ON p.id = a.presidente_user_id
        WHERE a.tenant_id = :tid AND a.id = :aid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "aid": str(ata_id)})).mappings().first()
    if not row:
        return {"consultor": None, "sindico": None, "presidente": None}

    def _user_dict(prefix: str) -> dict[str, Any] | None:
        uid = row[f"{prefix}_id"]
        if uid is None:
            return None
        return {
            "id": str(uid),
            "email": row[f"{prefix}_email"],
            "nome": row[f"{prefix}_nome"],
        }

    return {
        "consultor": _user_dict("c"),
        "sindico": _user_dict("s"),
        "presidente": _user_dict("p"),
    }
