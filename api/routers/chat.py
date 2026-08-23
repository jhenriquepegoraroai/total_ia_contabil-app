"""
Endpoint principal — POST /chat.

Recebe (pergunta, referencia, session_id?). Roda o RAG completo, persiste
em chat_sessions/chat_messages (audit + futuro UX de histórico) e devolve
resposta com citações + categoria + trace_id.

REGRA CRÍTICA (RULES.md #4): tenant_id vem do JWT, NUNCA do body.

Gate de módulo: exige `chat` contratado pelo tenant (`require_module`), mesmo
padrão de `atas.py` e `cobrancas.py`. Sem ele, tenant que não contratou o
módulo conseguia chatar assim mesmo.

Persistência (RULES.md #28 — histórico por tenant):
  - Primeira request com `session_id=None` → cria chat_sessions
  - Cada request grava 2 chat_messages (user + assistant)
  - Citações vão em chat_citations
  Tudo no `tenant_session(tenant_id)` (RLS aplicada).
"""

import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import auth
from api.core.rag import RAGResposta, responder
from api.db import tenant_session
from api.llm import get_llm_client_for_tenant
from api.tenants.datasources.factory import criar_datasource
from api.tenants.deps import require_module


router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Schemas (request / response)
# =============================================================================
class ChatRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=2000)
    referencia: str = Field(..., min_length=1, max_length=64)
    session_id: str | None = None


class CitacaoOut(BaseModel):
    file_name: str
    record_id: str | None = None
    data_valida: str | None = None
    similarity: float | None = None


class ChatResponse(BaseModel):
    resposta: str
    categoria: int | None
    citacoes: list[CitacaoOut]
    via: str
    session_id: str
    trace_id: str
    duracao_ms: int


# =============================================================================
# Endpoint
# =============================================================================
@router.post(
    "",
    response_model=ChatResponse,
    dependencies=[Depends(require_module("chat"))],
)
async def chat(
    payload: ChatRequest,
    request: Request,
    user: Annotated[auth.CurrentUser, Depends(auth.usuario_atual)],
) -> ChatResponse:
    t0 = time.monotonic()
    trace_id: str = request.state.trace_id
    registry = request.app.state.tenant_registry

    try:
        tenant_config = registry.get(user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # Sanitiza session_id vindo do client (deve ser UUID válido).
    session_uuid = _safe_uuid(payload.session_id)

    logger.info(
        f"chat ref={payload.referencia} session={session_uuid} "
        f"user={user.user_id} role={user.role}"
    )

    llm = get_llm_client_for_tenant(tenant_config)

    async with tenant_session(user.tenant_id) as session:
        datasource = criar_datasource(tenant_config, session)

        # 1. Garante session no DB (cria se primeiro contato).
        session_uuid = await _garantir_session(
            session=session,
            tenant_id=user.tenant_id,
            session_uuid=session_uuid,
            user_id=user.user_id,
            referencia=payload.referencia,
        )

        # 2. Roda RAG.
        resposta_rag: RAGResposta = await responder(
            pergunta=payload.pergunta,
            referencia=payload.referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

        # 3. Persiste pergunta + resposta + citações.
        await _persistir_mensagem(
            session=session,
            tenant_id=user.tenant_id,
            session_id=session_uuid,
            role="user",
            content=payload.pergunta,
            categoria=None,
            trace_id=trace_id,
        )
        message_assistant_id = await _persistir_mensagem(
            session=session,
            tenant_id=user.tenant_id,
            session_id=session_uuid,
            role="assistant",
            content=resposta_rag.resposta,
            categoria=resposta_rag.categoria,
            trace_id=trace_id,
        )
        await _persistir_citacoes(
            session=session,
            tenant_id=user.tenant_id,
            message_id=message_assistant_id,
            citacoes=resposta_rag.citacoes,
        )

    duracao_ms = int((time.monotonic() - t0) * 1000)

    return ChatResponse(
        resposta=resposta_rag.resposta,
        categoria=resposta_rag.categoria,
        citacoes=[CitacaoOut(**c.__dict__) for c in resposta_rag.citacoes],
        via=resposta_rag.via,
        session_id=str(session_uuid),
        trace_id=trace_id,
        duracao_ms=duracao_ms,
    )


# =============================================================================
# Persistência interna
# =============================================================================
def _safe_uuid(s: str | None) -> UUID | None:
    """Aceita UUID válido; descarta string lixo (cliente pode mandar qualquer coisa)."""
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        return None


async def _garantir_session(
    *,
    session: AsyncSession,
    tenant_id: str,
    session_uuid: UUID | None,
    user_id: str,
    referencia: str,
) -> UUID:
    """Retorna o UUID da session — cria no DB se não existe."""
    if session_uuid:
        # Tenta reaproveitar (filtro por tenant + RLS — defesa em profundidade)
        existing = (await session.execute(
            text(
                "SELECT id FROM chat_sessions WHERE tenant_id = :tid AND id = :sid"
            ),
            {"tid": tenant_id, "sid": str(session_uuid)},
        )).first()
        if existing:
            return session_uuid

    new_uuid = uuid4()
    user_uuid = _safe_uuid(user_id)  # dev-token usa "joao" ou similar — UUID None
    await session.execute(
        text(
            "INSERT INTO chat_sessions (id, tenant_id, user_id, referencia) "
            "VALUES (:id, :tid, :uid, :ref)"
        ),
        {
            "id": str(new_uuid),
            "tid": tenant_id,
            "uid": str(user_uuid) if user_uuid else None,
            "ref": referencia,
        },
    )
    return new_uuid


async def _persistir_mensagem(
    *,
    session: AsyncSession,
    tenant_id: str,
    session_id: UUID,
    role: str,
    content: str,
    categoria: int | None,
    trace_id: str | None,
) -> UUID:
    """Insere uma mensagem e retorna o id gerado."""
    msg_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO chat_messages "
            "(id, tenant_id, session_id, role, content, categoria, trace_id) "
            "VALUES (:id, :tid, :sid, :rl, :ct, :cat, :tr)"
        ),
        {
            "id": str(msg_id),
            "tid": tenant_id,
            "sid": str(session_id),
            "rl": role,
            "ct": content,
            "cat": categoria,
            "tr": trace_id,
        },
    )
    return msg_id


async def _persistir_citacoes(
    *,
    session: AsyncSession,
    tenant_id: str,
    message_id: UUID,
    citacoes,
) -> None:
    """Persiste as citações ligadas à mensagem do assistant."""
    if not citacoes:
        return

    # Para cada citação, tenta resolver o documents_embeddings.id pelo
    # (file_name, record_id). Se não encontrar (categorias estruturado/pattern
    # com "Registro N" como file_name), descarta a citação — não há link real.
    rank = 0
    for c in citacoes:
        record_id = getattr(c, "record_id", None)
        file_name = getattr(c, "file_name", None)
        similarity = getattr(c, "similarity", None)

        if not (record_id and file_name):
            continue

        emb = (await session.execute(
            text(
                "SELECT id FROM documents_embeddings "
                "WHERE tenant_id = :tid AND file_name = :fn AND record_id = :rid "
                "LIMIT 1"
            ),
            {"tid": tenant_id, "fn": file_name, "rid": record_id},
        )).first()
        if not emb:
            continue

        rank += 1
        await session.execute(
            text(
                "INSERT INTO chat_citations "
                "(tenant_id, message_id, embedding_id, similarity, rank_position) "
                "VALUES (:tid, :mid, :eid, :sim, :rk)"
            ),
            {
                "tid": tenant_id,
                "mid": str(message_id),
                "eid": emb[0],
                "sim": float(similarity) if similarity is not None else None,
                "rk": rank,
            },
        )
