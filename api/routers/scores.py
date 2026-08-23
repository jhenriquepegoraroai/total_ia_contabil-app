"""
Leitura dos scores das capacidades de ML.

A API **só lê**. Quem calcula é o worker de batch (`worker/scoring.py`), que
grava em `capability_scores`. Endpoint que pontuasse na hora faria a latência
do modelo virar latência de tela, e churn/fraude são recalculados por
competência sobre a carteira inteira — não por request.

Toda resposta carrega `ultima_execucao`. Lista vazia sem essa informação
deixaria o usuário sem saber se a carteira está saudável, se a carga não
chegou ou se o job falhou — três coisas muito diferentes.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import CurrentUser, usuario_atual
from api.db import tenant_session
from api.tenants.modulos import MODULO_SLUGS, tenant_tem_modulo

router = APIRouter(prefix="/scores", tags=["scores"])


# =============================================================================
# Schemas
# =============================================================================
class ScoreItem(BaseModel):
    referencia: str
    entidade_id: str
    score: float
    faixa: str | None
    modelo_versao: str
    calculado_em: datetime


class ExecucaoInfo(BaseModel):
    """Última execução do batch para esta capacidade."""

    status: str
    data_referencia: date | None
    linhas_lidas: int
    scores_gravados: int
    erro: str | None
    finished_at: datetime | None


class ScoresResponse(BaseModel):
    capability: str
    data_referencia: date | None
    total: int
    itens: list[ScoreItem]
    ultima_execucao: ExecucaoInfo | None


# =============================================================================
# Guard dinâmico por capacidade
# =============================================================================
async def capability_contratada(
    capability: str,
    request: Request,
    user: Annotated[CurrentUser, Depends(usuario_atual)],
) -> CurrentUser:
    """
    Variante de `require_module` para capacidade vinda do path.

    `require_module(slug)` fixa o slug na construção da rota; aqui a
    capacidade é parâmetro, então a checagem acontece em runtime — mesma
    regra, mesmo resultado.
    """
    if capability not in MODULO_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capacidade '{capability}' não existe no catálogo.",
        )

    if user.is_superadmin:
        return user

    registry = request.app.state.tenant_registry
    try:
        tenant_config = registry.get(user.tenant_id, only_enabled=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not tenant_tem_modulo(tenant_config, capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant '{user.tenant_id}' não contratou o módulo '{capability}'.",
        )
    return user


# =============================================================================
# Endpoint
# =============================================================================
@router.get("/{capability}", response_model=ScoresResponse)
async def listar_scores(
    capability: str,
    user: Annotated[CurrentUser, Depends(capability_contratada)],
    data_referencia: date | None = Query(
        None, description="Competência. Omitido, usa a mais recente disponível."
    ),
    referencia: str | None = Query(None, description="Filtra por condomínio."),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> ScoresResponse:
    async with tenant_session(user.tenant_id) as session:
        competencia = data_referencia
        if competencia is None:
            competencia = await _competencia_mais_recente(
                session, tenant_id=user.tenant_id, capability=capability
            )

        itens: list[ScoreItem] = []
        total = 0
        if competencia is not None:
            total = await _contar(
                session,
                tenant_id=user.tenant_id,
                capability=capability,
                competencia=competencia,
                referencia=referencia,
            )
            itens = await _listar(
                session,
                tenant_id=user.tenant_id,
                capability=capability,
                competencia=competencia,
                referencia=referencia,
                limit=limit,
                offset=offset,
            )

        execucao = await _ultima_execucao(
            session, tenant_id=user.tenant_id, capability=capability
        )

    return ScoresResponse(
        capability=capability,
        data_referencia=competencia,
        total=total,
        itens=itens,
        ultima_execucao=execucao,
    )


# =============================================================================
# Consultas — todas com tenant_id no WHERE, mesmo com RLS ativa (RULES.md)
# =============================================================================
async def _competencia_mais_recente(
    session, *, tenant_id: str, capability: str
) -> date | None:
    row = (
        await session.execute(
            text(
                "SELECT MAX(data_referencia) AS d FROM capability_scores "
                "WHERE tenant_id = :tid AND capability = :cap"
            ),
            {"tid": tenant_id, "cap": capability},
        )
    ).first()
    return row.d if row else None


async def _contar(
    session,
    *,
    tenant_id: str,
    capability: str,
    competencia: date,
    referencia: str | None,
) -> int:
    sql = (
        "SELECT COUNT(*) AS n FROM capability_scores "
        "WHERE tenant_id = :tid AND capability = :cap AND data_referencia = :data"
    )
    params: dict = {"tid": tenant_id, "cap": capability, "data": competencia}
    if referencia:
        sql += " AND referencia = :ref"
        params["ref"] = referencia
    row = (await session.execute(text(sql), params)).first()
    return int(row.n) if row else 0


async def _listar(
    session,
    *,
    tenant_id: str,
    capability: str,
    competencia: date,
    referencia: str | None,
    limit: int,
    offset: int,
) -> list[ScoreItem]:
    sql = (
        "SELECT referencia, entidade_id, score, faixa, modelo_versao, calculado_em "
        "FROM capability_scores "
        "WHERE tenant_id = :tid AND capability = :cap AND data_referencia = :data"
    )
    params: dict = {"tid": tenant_id, "cap": capability, "data": competencia}
    if referencia:
        sql += " AND referencia = :ref"
        params["ref"] = referencia
    sql += " ORDER BY score DESC, referencia, entidade_id LIMIT :lim OFFSET :off"
    params["lim"] = limit
    params["off"] = offset

    rows = (await session.execute(text(sql), params)).all()
    return [
        ScoreItem(
            referencia=r.referencia,
            entidade_id=r.entidade_id,
            score=float(r.score),
            faixa=r.faixa,
            modelo_versao=r.modelo_versao,
            calculado_em=r.calculado_em,
        )
        for r in rows
    ]


async def _ultima_execucao(
    session, *, tenant_id: str, capability: str
) -> ExecucaoInfo | None:
    row = (
        await session.execute(
            text(
                "SELECT status, data_referencia, linhas_lidas, scores_gravados, "
                "       erro, finished_at "
                "FROM scoring_runs "
                "WHERE tenant_id = :tid AND capability = :cap "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"tid": tenant_id, "cap": capability},
        )
    ).first()
    if row is None:
        return None
    return ExecucaoInfo(
        status=row.status,
        data_referencia=row.data_referencia,
        linhas_lidas=row.linhas_lidas,
        scores_gravados=row.scores_gravados,
        erro=row.erro,
        finished_at=row.finished_at,
    )
