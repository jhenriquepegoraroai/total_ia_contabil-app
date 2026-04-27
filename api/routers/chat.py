"""
Endpoint principal — POST /chat.

Recebe (pergunta, referencia, session_id?). Roda o RAG completo e devolve
resposta com citações + categoria + trace_id.

REGRA CRÍTICA (RULES.md #4): tenant_id vem do JWT, NUNCA do body.
"""

import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field

from api import auth
from api.core.rag import RAGResposta, responder
from api.db import tenant_session
from api.llm import get_llm_client_for_tenant
from api.tenants.datasources.factory import criar_datasource


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
@router.post("", response_model=ChatResponse)
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

    session_id = payload.session_id or str(uuid4())

    logger.info(
        f"chat ref={payload.referencia} session={session_id} "
        f"user={user.user_id} role={user.role}"
    )

    llm = get_llm_client_for_tenant(tenant_config)

    async with tenant_session(user.tenant_id) as session:
        datasource = criar_datasource(tenant_config, session)
        resposta_rag: RAGResposta = await responder(
            pergunta=payload.pergunta,
            referencia=payload.referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    duracao_ms = int((time.monotonic() - t0) * 1000)

    return ChatResponse(
        resposta=resposta_rag.resposta,
        categoria=resposta_rag.categoria,
        citacoes=[CitacaoOut(**c.__dict__) for c in resposta_rag.citacoes],
        via=resposta_rag.via,
        session_id=session_id,
        trace_id=trace_id,
        duracao_ms=duracao_ms,
    )
