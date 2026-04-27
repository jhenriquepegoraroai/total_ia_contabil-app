"""
Service layer de histórico de conversas — leitura para o painel do superadmin.

Tudo via `superadmin_session` (sem RLS): superadmin vê conversas de qualquer
tenant. Filtro por `tenant_id` em todas as queries (defesa em profundidade).

Funcionalidades:
  - listar_sessions(tenant_id)
  - buscar_session_com_mensagens(tenant_id, session_id)

Em prod, considerar paginação por cursor + retenção (LGPD: deletar conversas
mais antigas que X dias).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def listar_sessions(
    session: AsyncSession,
    tenant_id: str,
    *,
    limit: int = 100,
    referencia: str | None = None,
) -> list[dict[str, Any]]:
    """
    Lista sessões mais recentes com métricas: total de mensagens, primeira
    pergunta (resumo), e-mail do user (snapshot).
    """
    where = ["s.tenant_id = :tid"]
    params: dict[str, Any] = {"tid": tenant_id, "lim": limit}
    if referencia:
        where.append("s.referencia = :ref")
        params["ref"] = referencia
    where_clause = " AND ".join(where)

    sql = text(
        f"""
        SELECT
            s.id,
            s.tenant_id,
            s.user_id,
            u.email AS user_email,
            u.nome AS user_nome,
            s.referencia,
            s.started_at,
            s.ended_at,
            COALESCE(stats.qtde_mensagens, 0) AS qtde_mensagens,
            stats.primeira_pergunta,
            stats.ultima_at
        FROM chat_sessions s
        LEFT JOIN users u ON u.id = s.user_id
        LEFT JOIN (
            SELECT
                m.session_id,
                COUNT(*) AS qtde_mensagens,
                MAX(m.created_at) AS ultima_at,
                (
                    SELECT m2.content FROM chat_messages m2
                    WHERE m2.tenant_id = :tid
                      AND m2.session_id = m.session_id
                      AND m2.role = 'user'
                    ORDER BY m2.created_at
                    LIMIT 1
                ) AS primeira_pergunta
            FROM chat_messages m
            WHERE m.tenant_id = :tid
            GROUP BY m.session_id
        ) stats ON stats.session_id = s.id
        WHERE {where_clause}
        ORDER BY COALESCE(stats.ultima_at, s.started_at) DESC
        LIMIT :lim
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]


async def buscar_session_com_mensagens(
    session: AsyncSession,
    tenant_id: str,
    session_id: UUID,
) -> dict[str, Any] | None:
    """Retorna metadados + lista de mensagens com suas citações."""
    sess = (await session.execute(
        text(
            """
            SELECT s.id, s.tenant_id, s.user_id, u.email AS user_email,
                   u.nome AS user_nome, s.referencia, s.started_at, s.ended_at
            FROM chat_sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.tenant_id = :tid AND s.id = :sid
            """
        ),
        {"tid": tenant_id, "sid": str(session_id)},
    )).mappings().first()
    if not sess:
        return None

    msgs = (await session.execute(
        text(
            """
            SELECT id, role, content, categoria, trace_id, created_at
            FROM chat_messages
            WHERE tenant_id = :tid AND session_id = :sid
            ORDER BY created_at
            """
        ),
        {"tid": tenant_id, "sid": str(session_id)},
    )).mappings().all()

    # Carrega citações por message_id em uma query (evita N+1).
    msg_ids = [m["id"] for m in msgs]
    citations_by_msg: dict[str, list[dict[str, Any]]] = {}
    if msg_ids:
        cit_rows = (await session.execute(
            text(
                """
                SELECT c.message_id, e.file_name, e.record_id, e.data_valida,
                       c.similarity, c.rank_position
                FROM chat_citations c
                JOIN documents_embeddings e ON e.id = c.embedding_id
                WHERE c.tenant_id = :tid
                  AND c.message_id = ANY(CAST(:ids AS uuid[]))
                ORDER BY c.rank_position
                """
            ),
            {"tid": tenant_id, "ids": [str(i) for i in msg_ids]},
        )).mappings().all()
        for row in cit_rows:
            d = dict(row)
            mid = str(d.pop("message_id"))
            citations_by_msg.setdefault(mid, []).append(d)

    out = dict(sess)
    out["mensagens"] = [
        {**dict(m), "citacoes": citations_by_msg.get(str(m["id"]), [])}
        for m in msgs
    ]
    return out
