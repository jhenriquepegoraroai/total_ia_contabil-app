"""
Job de scoring — lê features, chama o modelo, grava score.

Desenho (decisão de arquitetura): **o batch escreve, a API só lê**. Inferência
sob demanda não é o caminho — churn e fraude são naturalmente recalculados por
competência, sobre a carteira inteira, e um endpoint que pontuasse na hora
faria a latência do modelo virar latência de tela.

Fluxo:
    1. abre `scoring_runs` (status='running')
    2. resolve o `feature_set` que o modelo declara esperar
    3. lê `feature_values` da competência
    4. valida cada linha contra o contrato (api.features)
    5. chama o scorer
    6. grava `capability_scores`
    7. fecha o run com contagem, ou com o erro

Tudo dentro de `tenant_session` — RLS aplicada, e todo SQL leva `tenant_id`
no WHERE mesmo assim (RULES.md, defesa em profundidade).
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from api.db import tenant_session
from api.features import validar_valores

from . import modelos


class ScoringError(RuntimeError):
    """Falha de execução do scoring já registrada em `scoring_runs`."""


async def executar_scoring(
    *,
    tenant_id: str,
    capability: str,
    data_referencia: date,
) -> UUID:
    """
    Executa o scoring de uma capacidade para uma competência.

    Retorna o id do `scoring_run`. Levanta `ScoringError` em falha — sempre
    depois de registrar o motivo no run, para que a falha seja consultável e
    não só um traceback no log do worker.
    """
    run_id = uuid4()

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text(
                "INSERT INTO scoring_runs "
                "(id, tenant_id, capability, status, data_referencia, started_at) "
                "VALUES (:id, :tid, :cap, 'running', :data, NOW())"
            ),
            {
                "id": str(run_id),
                "tid": tenant_id,
                "cap": capability,
                "data": data_referencia,
            },
        )

    try:
        scorer = modelos.obter(capability)

        async with tenant_session(tenant_id) as session:
            feature_set = await _resolver_feature_set(
                session, tenant_id=tenant_id, nome=scorer.feature_set_nome
            )
            linhas = await _ler_linhas(
                session,
                tenant_id=tenant_id,
                feature_set_id=feature_set["id"],
                data_referencia=data_referencia,
            )

        if not linhas:
            raise ScoringError(
                f"Nenhuma linha em feature_values para feature_set="
                f"'{scorer.feature_set_nome}' na competência {data_referencia}. "
                "Carga de dados do tenant não chegou."
            )

        _validar_lote(linhas, schema_json=feature_set["schema_json"])

        pontuacoes = scorer.pontuar(linhas)
        logger.info(
            f"[scoring] tenant={tenant_id} cap={capability} "
            f"linhas={len(linhas)} pontuacoes={len(pontuacoes)}"
        )

        async with tenant_session(tenant_id) as session:
            gravados = await _gravar_scores(
                session,
                tenant_id=tenant_id,
                capability=capability,
                data_referencia=data_referencia,
                modelo_versao=scorer.versao,
                run_id=run_id,
                pontuacoes=pontuacoes,
            )
            await _fechar_run(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
                status="done",
                linhas_lidas=len(linhas),
                scores_gravados=gravados,
                modelo_versao=scorer.versao,
            )

        return run_id

    except Exception as exc:
        # O run precisa registrar a falha mesmo quando a causa é externa
        # (modelo ausente, carga não chegou). Sem isso, o operador só vê um
        # run eternamente 'running'.
        logger.exception(
            f"[scoring] falhou tenant={tenant_id} cap={capability} run={run_id}"
        )
        async with tenant_session(tenant_id) as session:
            await _fechar_run(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
                status="failed",
                erro=str(exc)[:2000],
            )
        raise


# =============================================================================
# Leitura
# =============================================================================
async def _resolver_feature_set(
    session, *, tenant_id: str, nome: str
) -> dict[str, Any]:
    """Busca o contrato ativo de maior versão para o nome pedido."""
    row = (
        await session.execute(
            text(
                "SELECT id, schema_json, versao FROM feature_sets "
                "WHERE tenant_id = :tid AND nome = :nome AND enabled = TRUE "
                "ORDER BY versao DESC LIMIT 1"
            ),
            {"tid": tenant_id, "nome": nome},
        )
    ).first()

    if row is None:
        raise ScoringError(
            f"Tenant '{tenant_id}' não tem feature_set '{nome}' habilitado. "
            "O contrato de features precisa ser declarado antes do primeiro "
            "scoring (ver instrucao/contrato_features.md)."
        )
    return {"id": row.id, "schema_json": row.schema_json, "versao": row.versao}


async def _ler_linhas(
    session, *, tenant_id: str, feature_set_id: Any, data_referencia: date
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT referencia, entidade_id, valores FROM feature_values "
                "WHERE tenant_id = :tid AND feature_set_id = :fsid "
                "AND data_referencia = :data "
                "ORDER BY referencia, entidade_id"
            ),
            {"tid": tenant_id, "fsid": feature_set_id, "data": data_referencia},
        )
    ).all()

    return [
        {
            "referencia": r.referencia,
            "entidade_id": r.entidade_id,
            "valores": r.valores,
        }
        for r in rows
    ]


def _validar_lote(linhas: list[dict[str, Any]], *, schema_json: dict) -> None:
    """
    Valida todas as linhas contra o contrato antes de qualquer scoring.

    Falha o lote inteiro, não linha a linha: score parcial de uma carteira é
    pior que score nenhum — quem lê a tela não tem como saber que faltou
    metade.
    """
    problemas: list[str] = []
    for linha in linhas:
        erros = validar_valores(schema_json, linha["valores"])
        if erros:
            detalhe = "; ".join(str(e) for e in erros)
            problemas.append(f"{linha['referencia']}/{linha['entidade_id']}: {detalhe}")

    if problemas:
        amostra = problemas[:5]
        raise ScoringError(
            f"{len(problemas)} de {len(linhas)} linhas violam o contrato de "
            f"features. Primeiras: {' | '.join(amostra)}"
        )


# =============================================================================
# Escrita
# =============================================================================
async def _gravar_scores(
    session,
    *,
    tenant_id: str,
    capability: str,
    data_referencia: date,
    modelo_versao: str,
    run_id: UUID,
    pontuacoes: list[modelos.Pontuacao],
) -> int:
    """Grava as pontuações. Reexecução da mesma competência substitui."""
    import json

    gravados = 0
    for p in pontuacoes:
        await session.execute(
            text(
                "INSERT INTO capability_scores "
                "(tenant_id, capability, referencia, entidade_id, data_referencia, "
                " score, faixa, modelo_versao, explicacao, scoring_run_id) "
                "VALUES (:tid, :cap, :ref, :ent, :data, :score, :faixa, :ver, "
                "        CAST(:expl AS JSONB), :run) "
                "ON CONFLICT (tenant_id, capability, referencia, entidade_id, "
                "             data_referencia, modelo_versao) "
                "DO UPDATE SET score = EXCLUDED.score, "
                "              faixa = EXCLUDED.faixa, "
                "              explicacao = EXCLUDED.explicacao, "
                "              scoring_run_id = EXCLUDED.scoring_run_id, "
                "              calculado_em = NOW()"
            ),
            {
                "tid": tenant_id,
                "cap": capability,
                "ref": p.referencia,
                "ent": p.entidade_id,
                "data": data_referencia,
                "score": p.score,
                "faixa": p.faixa,
                "ver": modelo_versao,
                "expl": json.dumps(p.explicacao) if p.explicacao else None,
                "run": str(run_id),
            },
        )
        gravados += 1
    return gravados


async def _fechar_run(
    session,
    *,
    tenant_id: str,
    run_id: UUID,
    status: str,
    linhas_lidas: int = 0,
    scores_gravados: int = 0,
    modelo_versao: str | None = None,
    erro: str | None = None,
) -> None:
    await session.execute(
        text(
            "UPDATE scoring_runs SET status = :st, linhas_lidas = :lidas, "
            "scores_gravados = :grav, modelo_versao = :ver, erro = :erro, "
            "finished_at = NOW() "
            "WHERE tenant_id = :tid AND id = :id"
        ),
        {
            "st": status,
            "lidas": linhas_lidas,
            "grav": scores_gravados,
            "ver": modelo_versao,
            "erro": erro,
            "tid": tenant_id,
            "id": str(run_id),
        },
    )


# =============================================================================
# Entrada do RQ (síncrona — o worker não é async)
# =============================================================================
def job_scoring(tenant_id: str, capability: str, data_referencia_iso: str) -> str:
    """
    Função enfileirada no Redis. RQ executa funções síncronas, então a ponte
    para o mundo async acontece aqui.
    """
    data_referencia = date.fromisoformat(data_referencia_iso)
    run_id = asyncio.run(
        executar_scoring(
            tenant_id=tenant_id,
            capability=capability,
            data_referencia=data_referencia,
        )
    )
    return str(run_id)
